import os
import json
from datetime import datetime, timezone
from google.cloud import bigquery
from openai import OpenAI
 
BQ_PROJECT = "focus-on-energy"
BQ_DATASET = "job_radar"
BQ_TABLE = "jobs"
 
RESUME = """
ADIR RAPHAEL
Madison, WI | (608) 417-0502 | adirraph@gmail.com
 
PROFESSIONAL SUMMARY
Business Analyst with experience spanning analytics engineering, business intelligence, and data infrastructure. I build automated end-to-end data pipelines that turn messy datasets into clean, reliable reporting that support strategic goals. Strong expertise in the modern data stack, SQL, Python, BI tooling, and AI-assisted development tools, with a proven ability to bridge the gap between raw data and business insights.
 
EDUCATION
University of Wisconsin - Madison
Bachelor of Science in Information Science | Certificate in Data Science, Class of 2025
Relevant Coursework: Data Programming, Data Science Modeling, Statistical Data Visualization, Database Design, Calculus, Microeconomics
 
WORK EXPERIENCE
APTIM Government Solutions, LLC — Business Analyst (Full-Time) — July 2025 – Present
- Own end-to-end data pipelines, from ingestion and data modeling to transformation, testing and production deployment, including scheduled automated workflows.
- Leverage Claude Code daily to accelerate data engineering tasks across dbt modeling, Python scripting and pipeline debugging.
- Build and maintain Looker Studio and Power BI dashboards used by marketing team to monitor website traffic and user behavior.
- Surfaced behavioral patterns from ActiveCampaign API data that informed campaign optimizations, contributing to a 15% increase in user conversion rates.
- Manage GA4 configurations and implement custom solutions across GTM containers to enhance data accuracy and delivery.
 
APTIM Government Solutions, LLC — Business Analyst (Internship & Part-Time) — May 2024 – June 2025
- Transformed 1M+ rows of residential home assessment data into clean, interactive Power BI dashboards using power query and DAX measures.
- Analyzed energy program data across 5+ utility programs by combining disparate data sources in SQL.
- Built and deployed web applications using Python and Streamlit, including a GA4 analytics dashboard connected to live API data.
 
Israel Defense Force — Supply Chain Manager — August 2018 – April 2021
- Optimized $150K monthly food procurement through tracking systems and supplier data, reducing costs by 20%.
 
PROJECTS
Thinkific Data Pipeline Automation | Airbyte, GCP, Docker, BigQuery, dbt, Looker Studio
Website AI Agent Analytics | Zendesk API, Python, Pandas, BigQuery, GCP, Power BI
E-Commerce Analytics | Python, Snowflake, dbt, SQL, GitHub Actions, Tableau
 
TECHNICAL SKILLS
Technologies & Skills: Python, SQL, HTML/CSS, dbt Core, GitHub Actions, Docker, REST APIs, BigQuery, Snowflake, MySQL, Git, Claude Code, GCP, AWS, Looker Studio, Power BI, Tableau, Streamlit, GA4, Excel.
"""
 
SCORING_PROMPT = """You are an expert job matcher. Given a candidate's resume and a job description, score how well the candidate matches the job.
 
RESUME:
{resume}
 
JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION:
{job_description}
 
Respond ONLY with a valid JSON object in exactly this format, no other text:
{{
  "match_score": <integer 0-100>,
  "recommendation": "<Apply|Maybe|Skip>",
  "matched_skills": "<comma-separated list of skills from resume that match the job>",
  "missing_skills": "<comma-separated list of key skills the job requires that are missing from resume>",
  "score_reasoning": "<2-3 sentence explanation of the score>"
}}
 
Scoring guidelines:
- Apply (75-100): Strong match, candidate has most required skills and relevant experience
- Maybe (50-74): Partial match, candidate has some relevant skills but missing key requirements  
- Skip (0-49): Poor match, candidate lacks most required skills or experience level
"""
 
 
def get_unscored_jobs(client: bigquery.Client) -> list[dict]:
    query = f"""
        SELECT unique_key, job_title, employer_name, job_description
        FROM `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE match_score IS NULL
        AND job_description IS NOT NULL
        AND job_description != ''
    """
    result = client.query(query).result()
    return [dict(row) for row in result]
 
 
def score_job(openai_client: OpenAI, job: dict) -> dict | None:
    prompt = SCORING_PROMPT.format(
        resume=RESUME,
        job_title=job.get("job_title", ""),
        company=job.get("employer_name", ""),
        job_description=(job.get("job_description") or "")[:4000],
    )
 
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        # strip markdown fences if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  Error scoring job {job['unique_key']}: {e}")
        return None
 
 
def update_job_score(client: bigquery.Client, unique_key: str, score: dict):
    matched = score['matched_skills'].replace("'", "\\'")
    missing = score['missing_skills'].replace("'", "\\'")
    reasoning = score['score_reasoning'].replace("'", "\\'")
    scored_at = datetime.now(timezone.utc).isoformat()
    query = f"""
        UPDATE `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
        SET
            match_score = {score['match_score']},
            recommendation = '{score['recommendation']}',
            matched_skills = '{matched}',
            missing_skills = '{missing}',
            score_reasoning = '{reasoning}',
            scored_at = '{scored_at}'
        WHERE unique_key = '{unique_key}'
    """
    client.query(query).result()
 
 
def main():
    bq_client = bigquery.Client(project=BQ_PROJECT)
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
 
    unscored = get_unscored_jobs(bq_client)
    print(f"Unscored jobs: {len(unscored)}")
 
    if not unscored:
        print("All jobs already scored.")
        return
 
    scored = 0
    failed = 0
 
    for i, job in enumerate(unscored):
        print(f"Scoring {i+1}/{len(unscored)}: {job['job_title']} at {job['employer_name']}")
        score = score_job(openai_client, job)
 
        if score:
            update_job_score(bq_client, job["unique_key"], score)
            print(f"  → {score['recommendation']} | {score['match_score']}% match")
            scored += 1
        else:
            failed += 1
 
    print(f"\nDone! Scored: {scored} | Failed: {failed}")
 
 
if __name__ == "__main__":
    main()
 