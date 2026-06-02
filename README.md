JobRadar:
A personal job tracker that runs on autopilot. Every morning it pulls fresh job listings, scores them against my resume using GPT-4o, and surfaces the ones worth applying to — all in a clean dashboard.
What it does
Searches for Data Analyst, Business Analyst, Analytics Engineer, BI Developer, and Data Engineer roles daily. For each job it figures out how well my skills match, what I'm missing, and whether it's worth applying to. Everything gets stored in BigQuery and displayed in the app.
How it works
JSearch API pulls job listings every morning via GitHub Actions. Each job gets sent to GPT-4o along with my resume — it comes back with a match percentage, a recommendation (Apply / Maybe / Skip), and a breakdown of matched vs missing skills. Results live in BigQuery and the Streamlit app reads from there.
Stack

JSearch API — job listings from LinkedIn, Indeed, Glassdoor
GPT-4o — resume matching and scoring
BigQuery — stores all jobs and scores
GitHub Actions — runs the pipeline every morning at 7AM UTC
Streamlit — the dashboard

Live app
https://adirraphael-jobradar.streamlit.app
