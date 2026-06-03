# pipelines/ingest_francetravail.py

import hashlib
from decimal import Decimal, InvalidOperation

from storage.postgres import get_connection
from services.francetravail_client import (
    get_access_token,
    iter_offers_by_department,
    DEFAULT_DEPARTMENTS,
)

# Id of France Travail source in app.source
# Adjust this value if needed (for example by checking SELECT * FROM app.source;)
SOURCE_ID = 1


def make_fingerprint(external_id: str) -> str:
    """
    Build a SHA256 fingerprint from the external id.
    The fingerprint column is character(64) NOT NULL.
    """
    if not external_id:
        return None
    return hashlib.sha256(external_id.encode("utf-8")).hexdigest()


def make_name_fingerprint(name: str) -> str:
    """
    Fingerprint for company names (normalized to lowercase, trimmed).
    Intended for a UNIQUE constraint on app.company.name_fingerprint.
    """
    if not name:
        return None
    return hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()


def parse_decimal(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def get_or_create_company(cur, entreprise: dict):
    """
    Insert or fetch a company id from app.company based on the name.
    Requires:
      - app.company.company_id (PK)
      - app.company.name (text)
      - app.company.name_fingerprint char(64) UNIQUE
    """
    if not entreprise:
        return None

    name = entreprise.get("nom")
    if not name:
        return None

    fp = make_name_fingerprint(name)
    if not fp:
        return None

    cur.execute(
        """
        INSERT INTO app.company (name, name_fingerprint)
        VALUES (%s, %s)
        ON CONFLICT (name_fingerprint) DO UPDATE
        SET name = EXCLUDED.name
        RETURNING company_id;
        """,
        (name, fp),
    )
    row = cur.fetchone()
    return row["company_id"] if row else None


def get_or_create_location(cur, lieu_travail: dict):
    """
    Insert or fetch a location_id from app.location based on:
      - postal_code
      - insee_code (when commune looks numeric)
      - city_label (display label)
    Requires:
      - app.location.location_id (PK)
      - app.location.postal_code text
      - app.location.city text (legacy raw field)
      - app.location.insee_code text
      - app.location.city_label text
      - app.location.location_fingerprint char(64) UNIQUE
    """
    if not lieu_travail:
        return None

    postal_code = lieu_travail.get("codePostal")

    raw_commune = lieu_travail.get("commune")
    raw_label = lieu_travail.get("libelle") or raw_commune

    insee_code = None
    city_label = None

    if raw_commune and str(raw_commune).isdigit():
        # Example: 93066, 92050... treat as INSEE
        insee_code = str(raw_commune)
        city_label = raw_label
    else:
        city_label = raw_label

    if not postal_code and not city_label and not insee_code:
        return None

    key = f"{(postal_code or '').strip()}|{(insee_code or '').strip()}|{(city_label or '').strip().lower()}"
    fp = hashlib.sha256(key.encode("utf-8")).hexdigest()

    cur.execute(
        """
        INSERT INTO app.location (
            postal_code,
            city,
            insee_code,
            city_label,
            location_fingerprint
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (location_fingerprint) DO UPDATE
        SET postal_code = EXCLUDED.postal_code,
            city = EXCLUDED.city,
            insee_code = EXCLUDED.insee_code,
            city_label = EXCLUDED.city_label
        RETURNING location_id;
        """,
        (
            postal_code,
            raw_commune,  # legacy raw field
            insee_code,
            city_label,
            fp,
        ),
    )
    row = cur.fetchone()
    return row["location_id"] if row else None


def save_offer(cur, offer, departement: str) -> None:
    """
    Map one France Travail offer to app.job_offer with enriched fields
    and normalized company and location.
    """

    external_id = offer.get("id")
    title = offer.get("intitule")
    description = offer.get("description")
    contract_type = offer.get("typeContrat")
    contract_nature = offer.get("natureContrat")

    salaire = offer.get("salaire") or {}
    salary_min = parse_decimal(salaire.get("minimum"))
    salary_max = parse_decimal(salaire.get("maximum"))
    salary_currency = (salaire.get("devise") or "EUR")[:3]
    salary_text = salaire.get("libelle")

    experience_required = offer.get("experience") or None

    raw_sector = offer.get("secteurActivite")
    if isinstance(raw_sector, dict):
        sector = raw_sector.get("libelle")
    else:
        sector = raw_sector

    raw_remote = offer.get("teletravail")
    if isinstance(raw_remote, dict):
        remote_type = raw_remote.get("libelle")
    else:
        remote_type = raw_remote

    entreprise = offer.get("entreprise") or {}
    lieu_travail = offer.get("lieuTravail") or {}

    company_id = get_or_create_company(cur, entreprise)
    location_id = get_or_create_location(cur, lieu_travail)

    if not external_id or not title:
        return

    fingerprint = make_fingerprint(external_id)
    if not fingerprint:
        return

    cur.execute(
        """
        INSERT INTO app.job_offer (
            source_id,
            run_id,
            company_id,
            location_id,
            external_id,
            fingerprint,
            title,
            description,
            contract_type,
            contract_nature,
            salary_min,
            salary_max,
            salary_currency,
            salary_text,
            experience_required,
            sector,
            remote_type
        )
        VALUES (
            %s,       -- source_id
            NULL,     -- run_id
            %s,       -- company_id
            %s,       -- location_id
            %s,       -- external_id
            %s,       -- fingerprint
            %s,       -- title
            %s,       -- description
            %s,       -- contract_type
            %s,       -- contract_nature
            %s,       -- salary_min
            %s,       -- salary_max
            %s,       -- salary_currency
            %s,       -- salary_text
            %s,       -- experience_required
            %s,       -- sector
            %s        -- remote_type
        )
        ON CONFLICT (fingerprint) DO UPDATE
        SET title = EXCLUDED.title,
            description = EXCLUDED.description,
            contract_type = EXCLUDED.contract_type,
            contract_nature = EXCLUDED.contract_nature,
            salary_min = EXCLUDED.salary_min,
            salary_max = EXCLUDED.salary_max,
            salary_currency = EXCLUDED.salary_currency,
            salary_text = EXCLUDED.salary_text,
            experience_required = EXCLUDED.experience_required,
            sector = EXCLUDED.sector,
            remote_type = EXCLUDED.remote_type,
            company_id = EXCLUDED.company_id,
            location_id = EXCLUDED.location_id;
        """,
        (
            SOURCE_ID,
            company_id,
            location_id,
            external_id,
            fingerprint,
            title,
            description,
            contract_type,
            contract_nature,
            salary_min,
            salary_max,
            salary_currency,
            salary_text,
            experience_required,
            sector,
            remote_type,
        ),
    )


def main() -> None:
    token = get_access_token()
    conn = get_connection()
    cur = conn.cursor()

    total = 0

    try:
        for departement in DEFAULT_DEPARTMENTS:
            print(f"Ingestion departement {departement}")
            for offer in iter_offers_by_department(token, departement):
                save_offer(cur, offer, departement)
                total += 1

        conn.commit()
        print(f"Total offers processed: {total}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()