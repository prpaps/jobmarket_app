from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from storage.postgres import get_connection


def load_offers(limit: int = 1000) -> List[Tuple[int, str]]:
    """
    Récupère des offres depuis Postgres : (job_id, texte_concatené).
    """
    sql = """
        SELECT job_id, title, description
        FROM app.job_offer
        WHERE description IS NOT NULL
        LIMIT %s;
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()

    offers: List[Tuple[int, str]] = []
    for job_id, title, description in rows:
        text_parts: List[str] = []
        if title:
            text_parts.append(title)
        if description:
            text_parts.append(description)
        full_text = "\n".join(text_parts)
        offers.append((job_id, full_text))

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
        self.offer_ids = [job_id for job_id, _ in offers]
        texts = [text for _, text in offers]
        self.offer_matrix = self.vectorizer.fit_transform(texts)

    def rank(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """
        Calcule la similarité cosinus de la requête avec chaque offre
        et renvoie les top_k (job_id, score).
        """
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

        return results


def main() -> None:
    # 1. Charger des offres depuis la base
    offers = load_offers(limit=1000)
    print(f"DEBUG first offer = {offers[0]}")
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
        print(f"- job_id={job_id}, score={score:.4f}")


if __name__ == "__main__":
    main()
