# backend/main.py

from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os
import math
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


# Charger le .env
load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "jobmarket")
PGUSER = os.getenv("PGUSER", "jobmarket_app")
PGPASSWORD = os.getenv("PGPASSWORD", "change_me_app")

app = FastAPI()

# CORS pour le front
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Modèles ---------

class SearchRequest(BaseModel):
    query: str
    city: Optional[str] = None
    period: Optional[str] = None
    limit: int = 10


class Offer(BaseModel):
    job_id: int
    title: str
    description: str
    score: float


class SearchResponse(BaseModel):
    total: int
    results: List[Offer]


class ClickEvent(BaseModel):
    query: str
    city: Optional[str] = None
    job_id: int


# --------- Connexion Postgres ---------

def get_connection():
    return psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
    )


def log_search(query: str, city: Optional[str], result_count: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO app.search_log (query, city, result_count)
                VALUES (%s, %s, %s)
            """
            cur.execute(sql, (query, city, result_count))
        conn.commit()
    finally:
        conn.close()


def log_click(query: str, city: Optional[str], job_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO app.search_click (query, city, job_id)
                VALUES (%s, %s, %s)
            """
            cur.execute(sql, (query, city, job_id))
        conn.commit()
    finally:
        conn.close()


def load_click_boosts_for_query(query: str) -> dict[int, float]:
    """
    Charge tous les multiplicateurs de score pour une requête donnée
    sous la forme {job_id: boost}.
    Une seule requête SQL par recherche.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT job_id, click_count
                FROM app.search_click_stats
                WHERE query = %s
            """
            cur.execute(sql, (query,))
            rows = cur.fetchall()
    finally:
        conn.close()

    alpha = 0.2  # poids de l'effet des clics
    boosts: dict[int, float] = {}
    for row in rows:
        click_count = row["click_count"]
        job_id = row["job_id"]
        boost = 1.0 + alpha * math.log(1 + click_count)
        boosts[job_id] = boost

    return boosts


# --------- TF-IDF global ---------

tfidf_vectorizer: TfidfVectorizer | None = None
tfidf_matrix = None
offers_index: List[dict] = []


def load_offers_for_tfidf(limit: int = 5000):
    global tfidf_vectorizer, tfidf_matrix, offers_index

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT
                    job_id,
                    title,
                    description,
                    contract_type,
                    sector,
                    remote_type
                FROM app.job_offer
                WHERE title IS NOT NULL
                LIMIT %s
            """
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()

    documents: List[str] = []
    offers_index = []

    for row in rows:
        title = (row["title"] or "").strip()
        description = (row["description"] or "").strip()
        contract_type = (row.get("contract_type") or "").strip()
        sector = (row.get("sector") or "").strip()
        remote_type = (row.get("remote_type") or "").strip()

        parts = [
            title,
            title,  # titre répété pour plus de poids
            description,
            f"Contrat: {contract_type}",
            f"Secteur: {sector}",
            f"Télétravail: {remote_type}",
        ]
        text = "\n".join(p for p in parts if p)

        documents.append(text)
        offers_index.append(
            {
                "job_id": row["job_id"],
                "title": title,
                "description": description,
            }
        )

    tfidf_vectorizer = TfidfVectorizer(
        stop_words=None,
        max_features=5000,
    )
    tfidf_matrix = tfidf_vectorizer.fit_transform(documents)
    print(f"TF-IDF entraîné sur {len(offers_index)} offres.")


@app.on_event("startup")
def startup_event():
    load_offers_for_tfidf()


# --------- Endpoints ---------

@app.post("/search", response_model=SearchResponse)
async def search_offers(payload: SearchRequest):
    global tfidf_vectorizer, tfidf_matrix, offers_index

    print(
        f"Recherche reçue: query='{payload.query}', city='{payload.city}', "
        f"period='{payload.period}', limit={payload.limit}"
    )

    if tfidf_vectorizer is None or tfidf_matrix is None:
        raise HTTPException(status_code=500, detail="Indice TF-IDF non initialisé.")

    # 1. Vectoriser la requête
    query_vec = tfidf_vectorizer.transform([payload.query])

    # 2. Similarité cosinus
    cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

    # 2bis. Charger tous les boosts de clics pour cette requête
    click_boosts = load_click_boosts_for_query(payload.query)

    # 3. Associer score + filtre ville + boost clics
    scored_offers: List[Offer] = []
    for idx, score in enumerate(cosine_similarities):
        offer = offers_index[idx]

        if payload.city:
            city_lower = payload.city.lower()
            if city_lower not in offer["title"].lower() and city_lower not in offer[
                "description"
            ].lower():
                continue

        base_score = float(score)
        boost = click_boosts.get(offer["job_id"], 1.0)
        final_score = base_score * boost

        scored_offers.append(
            Offer(
                job_id=offer["job_id"],
                title=offer["title"],
                description=offer["description"],
                score=final_score,
            )
        )

    # 4. Tri + limite
    scored_offers.sort(key=lambda o: o.score, reverse=True)
    limited = scored_offers[: payload.limit]

    # 5. Log de la recherche
    log_search(payload.query, payload.city, len(limited))

    return SearchResponse(total=len(limited), results=limited)


@app.post("/track-click")
async def track_click(event: ClickEvent):
    print(f"Click reçu: query='{event.query}', city='{event.city}', job_id={event.job_id}")
    log_click(event.query, event.city, event.job_id)
    return {"status": "ok"}


@app.get("/offers/{job_id}", response_model=Offer)
async def get_offer(job_id: int):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT job_id, title, description
                FROM app.job_offer
                WHERE job_id = %s
            """
            cur.execute(sql, (job_id,))
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    title = row["title"] or ""
    description = row["description"] or ""

    return Offer(
        job_id=row["job_id"],
        title=title,
        description=description,
        score=1.0,
    )