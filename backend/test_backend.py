from backend.main import fetch_offers_by_ids

if __name__ == '__main__':
    sample = fetch_offers_by_ids([1])
    print(sample)
