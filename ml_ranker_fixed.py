from typing import List, Tuple

import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from storage.postgres import get_connection


def load_offers(limit: int = 1000) -> List[Tuple[int, str]]:
    """
    Récupère des offres depuis Postgres : (job_id, texte_concatené).
    """
    print("DEBUG entering load_offers")

    sql = """
        SELECT job_id, title, description
        FROM app.job_offer
        WHERE description IS NOT NULL
        ORDER BY job_id
        LIMIT %s;
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
            print("DEBUG raw row from DB =", rows[0])
            print("DEBUG type rows[0] =", type(rows[0]))
    finally:
        conn.close()

    offers: List[Tuple[int, str]] = []

    # rows est une liste de RealDictRow (dict), on accède par clés
    for idx, row in enumerate(rows):
        print(f"DEBUG row[{idx}] =", row)

        job_id = row["job_id"]
        title = row["title"]
        description = row["description"]

        text_parts: List[str] = []
        if title:
            text_parts.append(title)
        if description:
            text_parts.append(description)

        full_text = "\n".join(text_parts)
        offers.append((job_id, full_text))

        if idx == 0:
            print("DEBUG offers[0] inside loop =", offers[0])

    print("DEBUG offers[0] after loop =", offers[0])
    print("DEBUG leaving load_offers")

    return offers


class TfidfJobRanker:
    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(
            max_features=20000,
            ngram_range=(1, 2),
        )
        self.offer_ids: List[int] = []
        self.offer_matrix = None  # matrice TF-IDF des offres

    def fit(self, offers: List[Tuple[int, str]]) -> None:
        """
        Entraîne le vectorizer sur les textes d'offres.
        """
        print("DEBUG entering TfidfJobRanker.fit")

        self.offer_ids = [job_id for job_id, _ in offers]
        texts = [text for _, text in offers]
        print("DEBUG first offer id + text =", self.offer_ids[0], texts[0])

        self.offer_matrix = self.vectorizer.fit_transform(texts)

        print("DEBUG leaving TfidfJobRanker.fit")

    def rank(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Calcule la similarité cosinus de la requête avec chaque offre
        et renvoie les top_k (job_id, score).
        """
        print("DEBUG entering TfidfJobRanker.rank")

        if self.offer_matrix is None:
            raise ValueError("Le ranker n'a pas encore été entraîné (fit).")

        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.offer_matrix)[0]  # array 1D

        # indices des scores triés décroissants
        top_idx = np.argsort(sims)[::-1][:top_k]

        results: List[Tuple[int, float]] = []
        for idx in top_idx:
            job_id = self.offer_ids[idx]
            score = float(sims[idx])
            results.append((job_id, score))

        print("DEBUG leaving TfidfJobRanker.rank")

        return results


def main() -> None:
    print("DEBUG __file__ =", __file__)
    print("DEBUG cwd =", os.getcwd())
    print("DEBUG load_offers function object =", load_offers)

    # 1. Charger des offres depuis la base
    offers = load_offers(limit=1000)
    print("DEBUG type first offer =", type(offers[0]), offers[0])
    print("DEBUG repr first offer =", repr(offers[0]))
    print(f"{len(offers)} offres chargées depuis la base.")

    # 2. Entraîner le TF-IDF
    ranker = TfidfJobRanker()
    ranker.fit(offers)
    print("Vectorisation TF-IDF terminée.")

    # 3. Saisir une requête utilisateur
    query = input("Tape ta requête (ex: 'technicien réseau IDF'): ")

    # 4. Calculer les top résultats
    results = ranker.rank(query, top_k=10)

    print("DEBUG results[:3] =", results[:3])

    print("\nTop 10 offres pour ta requête :")
    for job_id, score in results:
        print(f"- job_id={job_id}, score={score:.8f}")


if __name__ == "__main__":
    main()
