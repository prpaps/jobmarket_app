import os
import time
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
BASE_URL = "https://api.francetravail.io"
SEARCH_URL = f"{BASE_URL}/partenaire/offresdemploi/v2/offres/search"

CLIENT_ID = os.getenv("FRANCE_TRAVAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET")
SCOPE = os.getenv("FRANCE_TRAVAIL_SCOPE", "api_offresdemploiv2 o2dsoffre")

DEFAULT_DEPARTMENTS = [d.strip() for d in os.getenv("DEFAULT_DEPARTMENTS", "75,92,93,94").split(",") if d.strip()]
DEFAULT_DAYS = int(os.getenv("DEFAULT_DAYS", "1"))
DEFAULT_MAX_PAGES = int(os.getenv("DEFAULT_MAX_PAGES", "20"))
DEFAULT_PER_PAGE = int(os.getenv("DEFAULT_PER_PAGE", "150"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
REQUEST_SLEEP = float(os.getenv("REQUEST_SLEEP", "0.25"))

def get_access_token():
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    data = {
        "grant_type": "client_credentials",
        "scope": SCOPE,
    }

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        data=data,
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=REQUEST_TIMEOUT,
    )

    print("Token status:", response.status_code)
    print("Token response:", response.text)

    response.raise_for_status()
    return response.json()["access_token"]

def _date_min():
    return (datetime.utcnow() - timedelta(days=DEFAULT_DAYS)).strftime("%Y-%m-%dT00:00:00Z")

def search_offers(token, departement, page=1, per_page=DEFAULT_PER_PAGE):
    start = (page - 1) * per_page
    end = start + per_page - 1

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    params = {
        "departement": departement,
        "range": f"{start}-{end}",
    }

    response = requests.get(
        SEARCH_URL,
        headers=headers,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    if not response.ok:
        print("Search status:", response.status_code)
        print("Search URL:", response.url)
        print("Search response:", response.text)

    response.raise_for_status()
    return response.json()

def iter_offers_by_department(token, departement):
    for page in range(1, DEFAULT_MAX_PAGES + 1):
        data = search_offers(token, departement, page=page)
        offers = data.get("resultats", [])

        if not offers:
            break

        for offer in offers:
            yield offer

        if len(offers) < DEFAULT_PER_PAGE:
            break

        time.sleep(REQUEST_SLEEP)
