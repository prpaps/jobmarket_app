from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from storage.postgres import get_connection

app = FastAPI(title="Job Market API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # pour dev uniquement
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobOffer(BaseModel):
    job_id: int
    title: str
    description: Optional[str]
    contract_type: Optional[str]
    contract_nature: Optional[str]
    salary_min: Optional[float]
    salary_max: Optional[float]
    salary_currency: Optional[str]
    salary_text: Optional[str]
    experience_required: Optional[str]
    sector: Optional[str]
    remote_type: Optional[str]
    company_name: Optional[str]
    postal_code: Optional[str]
    city_label: Optional[str]
    insee_code: Optional[str]


def fetch_offers(
    page: int = 1,
    page_size: int = 50,
    department: Optional[str] = None,
    postal_code: Optional[str] = None,
    contract_type: Optional[str] = None,
    remote: Optional[str] = None,
) -> List[JobOffer]:
    offset = (page - 1) * page_size

    where_clauses = []
    params = []

    if department:
        # Filter by department using the postal code prefix, e.g. '75', '92'
        where_clauses.append("l.postal_code LIKE %s")
        params.append(department + "%")

    if postal_code:
        where_clauses.append("l.postal_code = %s")
        params.append(postal_code)

    if contract_type:
        where_clauses.append("j.contract_type = %s")
        params.append(contract_type)

    if remote:
        where_clauses.append("j.remote_type ILIKE %s")
        params.append(f"%{remote}%")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
        SELECT
            j.job_id,
            j.title,
            j.description,
            j.contract_type,
            j.contract_nature,
            j.salary_min,
            j.salary_max,
            j.salary_currency,
            j.salary_text,
            j.experience_required,
            j.sector,
            j.remote_type,
            c.name AS company_name,
            l.postal_code,
            l.city_label,
            l.insee_code
        FROM app.job_offer j
        LEFT JOIN app.company c ON j.company_id = c.company_id
        LEFT JOIN app.location l ON j.location_id = l.location_id
        {where_sql}
        ORDER BY j.job_id DESC
        LIMIT %s OFFSET %s;
    """

    params.extend([page_size, offset])

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    return [JobOffer(**row) for row in rows]

def fetch_offer_by_id(job_id: int) -> JobOffer:
    sql = """
        SELECT
            j.job_id,
            j.title,
            j.description,
            j.contract_type,
            j.contract_nature,
            j.salary_min,
            j.salary_max,
            j.salary_currency,
            j.salary_text,
            j.experience_required,
            j.sector,
            j.remote_type,
            c.name AS company_name,
            l.postal_code,
            l.city_label,
            l.insee_code
        FROM app.job_offer j
        LEFT JOIN app.company c ON j.company_id = c.company_id
        LEFT JOIN app.location l ON j.location_id = l.location_id
        WHERE j.job_id = %s;
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (job_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Job offer not found")

    return JobOffer(**row)


@app.get("/offers", response_model=List[JobOffer])
def list_offers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    department: Optional[str] = Query(None, description="Department code, e.g. '75'"),
    postal_code: Optional[str] = Query(None),
    contract_type: Optional[str] = Query(None),
    remote: Optional[str] = Query(None),
):
    """
    List job offers with basic filters.
    """
    return fetch_offers(
        page=page,
        page_size=page_size,
        department=department,
        postal_code=postal_code,
        contract_type=contract_type,
        remote=remote,
    )

@app.get("/offers/{job_id}", response_model=JobOffer)
def get_offer(job_id: int):
    """
    Get detailed information for a single job offer.
    """
    return fetch_offer_by_id(job_id)