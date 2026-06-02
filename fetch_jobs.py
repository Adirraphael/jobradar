import os
import requests
import hashlib
from datetime import datetime, timezone
from google.cloud import bigquery

RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
BQ_PROJECT = "focus-on-energy"
BQ_DATASET = "job_radar"
BQ_TABLE = "jobs"

JOB_TITLES = [
    "Data Analyst",
    "Business Analyst",
    "Analytics Engineer",
    "BI Developer",
    "Data Engineer",
]

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}


def fetch_jobs_for_title(title: str, num_pages: int = 3) -> list[dict]:
    jobs = []
    for page in range(1, num_pages + 1):
        params = {
            "query": title,
            "page": str(page),
            "num_pages": "1",
            "date_posted": "week",
        }
        response = requests.get(JSEARCH_URL, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        jobs.extend(data.get("data", []))
        print(f"  Fetched page {page} for '{title}' — {len(data.get('data', []))} jobs")
    return jobs


def parse_job(job: dict, search_title: str) -> dict:
    job_id = job.get("job_id", "")
    # stable unique key: hash of job_id
    unique_key = hashlib.md5(job_id.encode()).hexdigest()

    return {
        "unique_key": unique_key,
        "job_id": job_id,
        "search_title": search_title,
        "job_title": job.get("job_title", ""),
        "employer_name": job.get("employer_name", ""),
        "employer_logo": job.get("employer_logo", ""),
        "job_publisher": job.get("job_publisher", ""),
        "job_employment_type": job.get("job_employment_type", ""),
        "job_apply_link": job.get("job_apply_link", ""),
        "job_description": (job.get("job_description") or "")[:5000],
        "job_is_remote": job.get("job_is_remote", False),
        "job_city": job.get("job_city", ""),
        "job_state": job.get("job_state", ""),
        "job_country": job.get("job_country", ""),
        "job_posted_at": job.get("job_posted_at_datetime_utc", None),
        "date_fetched": datetime.now(timezone.utc).isoformat(),
        # scoring fields — filled later by score_jobs.py
        "match_score": None,
        "recommendation": None,
        "matched_skills": None,
        "missing_skills": None,
        "score_reasoning": None,
        "scored_at": None,
    }


def get_existing_keys(client: bigquery.Client) -> set:
    query = f"SELECT unique_key FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`"
    try:
        result = client.query(query).result()
        return {row.unique_key for row in result}
    except Exception:
        # table doesn't exist yet
        return set()


def create_table_if_not_exists(client: bigquery.Client):
    schema = [
        bigquery.SchemaField("unique_key", "STRING"),
        bigquery.SchemaField("job_id", "STRING"),
        bigquery.SchemaField("search_title", "STRING"),
        bigquery.SchemaField("job_title", "STRING"),
        bigquery.SchemaField("employer_name", "STRING"),
        bigquery.SchemaField("employer_logo", "STRING"),
        bigquery.SchemaField("job_publisher", "STRING"),
        bigquery.SchemaField("job_employment_type", "STRING"),
        bigquery.SchemaField("job_apply_link", "STRING"),
        bigquery.SchemaField("job_description", "STRING"),
        bigquery.SchemaField("job_is_remote", "BOOLEAN"),
        bigquery.SchemaField("job_city", "STRING"),
        bigquery.SchemaField("job_state", "STRING"),
        bigquery.SchemaField("job_country", "STRING"),
        bigquery.SchemaField("job_posted_at", "TIMESTAMP"),
        bigquery.SchemaField("date_fetched", "TIMESTAMP"),
        bigquery.SchemaField("match_score", "FLOAT"),
        bigquery.SchemaField("recommendation", "STRING"),
        bigquery.SchemaField("matched_skills", "STRING"),
        bigquery.SchemaField("missing_skills", "STRING"),
        bigquery.SchemaField("score_reasoning", "STRING"),
        bigquery.SchemaField("scored_at", "TIMESTAMP"),
    ]
    table_ref = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table, exists_ok=True)
    print(f"Table {table_ref} ready.")


def main():
    client = bigquery.Client(project=BQ_PROJECT)
    create_table_if_not_exists(client)
    existing_keys = get_existing_keys(client)
    print(f"Existing jobs in BigQuery: {len(existing_keys)}")

    all_new_jobs = []
    seen_keys = set()

    for title in JOB_TITLES:
        print(f"\nFetching: {title}")
        raw_jobs = fetch_jobs_for_title(title)
        for raw in raw_jobs:
            parsed = parse_job(raw, title)
            key = parsed["unique_key"]
            # skip duplicates (same job across multiple title searches)
            if key not in existing_keys and key not in seen_keys:
                all_new_jobs.append(parsed)
                seen_keys.add(key)

    print(f"\nNew jobs to insert: {len(all_new_jobs)}")

    if all_new_jobs:
        table_ref = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"
        errors = client.insert_rows_json(table_ref, all_new_jobs)
        if errors:
            print(f"BigQuery insert errors: {errors}")
        else:
            print(f"Successfully inserted {len(all_new_jobs)} jobs into BigQuery.")
    else:
        print("No new jobs to insert.")


if __name__ == "__main__":
    main()
