import streamlit as st
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import json
import os

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="JobRadar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Hide default streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Main background */
.stApp {
    background-color: #0f1117;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #161b27;
    border-right: 1px solid #1e2535;
}

/* Metric cards */
[data-testid="stMetric"] {
    background-color: #161b27;
    border: 1px solid #1e2535;
    border-radius: 12px;
    padding: 16px;
}

[data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace;
    font-size: 28px !important;
    color: #e2e8f0 !important;
}

[data-testid="stMetricLabel"] {
    color: #64748b !important;
    font-size: 12px !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Job cards */
.job-card {
    background: #161b27;
    border: 1px solid #1e2535;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.job-card:hover {
    border-color: #334155;
}
.job-card.apply {
    border-left: 3px solid #10b981;
}
.job-card.maybe {
    border-left: 3px solid #f59e0b;
}
.job-card.skip {
    border-left: 3px solid #475569;
}

.job-title {
    font-size: 16px;
    font-weight: 600;
    color: #e2e8f0;
    margin: 0 0 4px 0;
}
.job-company {
    font-size: 13px;
    color: #64748b;
    margin: 0 0 12px 0;
}
.job-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}
.badge {
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 100px;
    font-weight: 500;
}
.badge-remote { background: #064e3b; color: #6ee7b7; }
.badge-hybrid { background: #1e1b4b; color: #a5b4fc; }
.badge-onsite { background: #1e293b; color: #94a3b8; }
.badge-apply { background: #064e3b; color: #6ee7b7; }
.badge-maybe { background: #451a03; color: #fcd34d; }
.badge-skip { background: #1e293b; color: #94a3b8; }

.score-pct {
    font-family: 'DM Mono', monospace;
    font-size: 24px;
    font-weight: 500;
    color: #e2e8f0;
}

.skills-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.skill-match {
    font-size: 11px; padding: 2px 8px;
    border-radius: 6px;
    background: #052e16; color: #86efac;
}
.skill-missing {
    font-size: 11px; padding: 2px 8px;
    border-radius: 6px;
    background: #2d0a0a; color: #fca5a5;
}

.reasoning {
    font-size: 12px;
    color: #64748b;
    margin-top: 10px;
    line-height: 1.6;
    border-top: 1px solid #1e2535;
    padding-top: 10px;
}

.header-title {
    font-size: 28px;
    font-weight: 600;
    color: #e2e8f0;
    letter-spacing: -0.5px;
}
.header-sub {
    font-size: 13px;
    color: #475569;
    margin-top: 2px;
}
.radar-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    margin-right: 8px;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* Inputs */
.stTextInput input, .stSelectbox select {
    background: #161b27 !important;
    border-color: #1e2535 !important;
    color: #e2e8f0 !important;
}

/* Section label */
.section-label {
    font-size: 11px;
    font-weight: 600;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}

.apply-link {
    font-size: 12px;
    color: #3b82f6;
    text-decoration: none;
}
</style>
""", unsafe_allow_html=True)


# ── BigQuery connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_bq_client():
    if "gcp_service_account" in st.secrets:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        return bigquery.Client(credentials=credentials, project="focus-on-energy")
    else:
        return bigquery.Client(project="focus-on-energy")


@st.cache_data(ttl=300)
def load_jobs():
    client = get_bq_client()
    query = """
        SELECT
            job_title, employer_name, job_city, job_state, job_country,
            job_is_remote, job_employment_type, job_apply_link,
            job_posted_at, match_score, recommendation,
            matched_skills, missing_skills, score_reasoning,
            search_title, job_publisher, date_fetched
        FROM `focus-on-energy.job_radar.jobs`
        WHERE match_score IS NOT NULL
        ORDER BY match_score DESC
    """
    df = client.query(query).to_dataframe()
    return df


# ── Load data ─────────────────────────────────────────────────────────────────
try:
    df = load_jobs()
    data_loaded = True
except Exception as e:
    st.error(f"Could not connect to BigQuery: {e}")
    data_loaded = False
    df = pd.DataFrame()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="header-title">📡 JobRadar</div>', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown('<div class="section-label">Search</div>', unsafe_allow_html=True)
    search_query = st.text_input("", placeholder="Search job title or company...", label_visibility="collapsed")

    st.markdown('<div class="section-label" style="margin-top:16px">Work type</div>', unsafe_allow_html=True)
    work_type = st.selectbox("", ["All", "Remote", "Hybrid", "On-site"], label_visibility="collapsed")

    st.markdown('<div class="section-label" style="margin-top:16px">Recommendation</div>', unsafe_allow_html=True)
    rec_filter = st.selectbox("", ["All", "Apply", "Maybe", "Skip"], label_visibility="collapsed", key="rec")

    st.markdown('<div class="section-label" style="margin-top:16px">Min match %</div>', unsafe_allow_html=True)
    min_match = st.slider("", 0, 100, 0, label_visibility="collapsed")

    st.markdown('<div class="section-label" style="margin-top:16px">Job category</div>', unsafe_allow_html=True)
    categories = ["All"] + sorted(df["search_title"].unique().tolist()) if data_loaded and not df.empty else ["All"]
    category = st.selectbox("", categories, label_visibility="collapsed", key="cat")

    st.markdown('<div class="section-label" style="margin-top:16px">Posted within</div>', unsafe_allow_html=True)
    days_filter = st.selectbox("", ["Any time", "Last 7 days", "Last 14 days", "Last 30 days"], label_visibility="collapsed", key="days")

    st.markdown("---")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── Filter data ───────────────────────────────────────────────────────────────
if data_loaded and not df.empty:
    filtered = df.copy()

    if search_query:
        mask = (
            filtered["job_title"].str.contains(search_query, case=False, na=False) |
            filtered["employer_name"].str.contains(search_query, case=False, na=False)
        )
        filtered = filtered[mask]

    if work_type != "All":
        if work_type == "Remote":
            filtered = filtered[filtered["job_is_remote"] == True]
        elif work_type == "On-site":
            filtered = filtered[filtered["job_is_remote"] == False]

    if rec_filter != "All":
        filtered = filtered[filtered["recommendation"] == rec_filter]

    if min_match > 0:
        filtered = filtered[filtered["match_score"] >= min_match]

    if category != "All":
        filtered = filtered[filtered["search_title"] == category]

    if days_filter != "Any time":
        days_map = {"Last 7 days": 7, "Last 14 days": 14, "Last 30 days": 30}
        days = days_map[days_filter]
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)
        filtered = filtered[filtered["job_posted_at"] >= cutoff]

# ── Main content ──────────────────────────────────────────────────────────────
col_title, col_refresh = st.columns([4, 1])
with col_title:
    last_updated = df["date_fetched"].max().strftime("%b %d, %Y at %I:%M %p") if data_loaded and not df.empty else "N/A"
    st.markdown(f"""
        <div style="padding: 8px 0 20px 0">
            <span class="radar-dot"></span>
            <span class="header-title">Job matches</span>
            <div class="header-sub">Last updated {last_updated}</div>
        </div>
    """, unsafe_allow_html=True)

# ── Stats row ─────────────────────────────────────────────────────────────────
if data_loaded and not df.empty:
    total = len(filtered)
    apply_count = len(filtered[filtered["recommendation"] == "Apply"])
    maybe_count = len(filtered[filtered["recommendation"] == "Maybe"])
    avg_match = filtered["match_score"].mean()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total jobs", total)
    with c2:
        st.metric("Apply", apply_count)
    with c3:
        st.metric("Maybe", maybe_count)
    with c4:
        st.metric("Avg match", f"{avg_match:.0f}%" if not pd.isna(avg_match) else "—")

    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)

    # ── Job cards ─────────────────────────────────────────────────────────────
    if filtered.empty:
        st.markdown("<div style='color: #475569; padding: 40px 0; text-align: center'>No jobs match your filters.</div>", unsafe_allow_html=True)
    else:
        for _, job in filtered.iterrows():
            rec = (job["recommendation"] or "").lower()
            is_remote = job["job_is_remote"]
            location = " · ".join(filter(None, [str(job["job_city"]) if pd.notna(job["job_city"]) else "", str(job["job_state"]) if pd.notna(job["job_state"]) else "", str(job["job_country"]) if pd.notna(job["job_country"]) else ""]))

            work_badge = '<span class="badge badge-remote">Remote</span>' if is_remote else '<span class="badge badge-onsite">On-site</span>'

            rec_badge = ""
            if rec == "apply":
                rec_badge = '<span class="badge badge-apply">Apply</span>'
            elif rec == "maybe":
                rec_badge = '<span class="badge badge-maybe">Maybe</span>'
            else:
                rec_badge = '<span class="badge badge-skip">Skip</span>'

            matched = [s.strip() for s in (job["matched_skills"] or "").split(",") if s.strip()]
            missing = [s.strip() for s in (job["missing_skills"] or "").split(",") if s.strip()]

            matched_html = "".join([f'<span class="skill-match">{s}</span>' for s in matched[:6]])
            missing_html = "".join([f'<span class="skill-missing">{s}</span>' for s in missing[:4]])

            score = int(job["match_score"]) if not pd.isna(job["match_score"]) else 0
            reasoning = str(job["score_reasoning"]) if pd.notna(job["score_reasoning"]) else "" or ""
            apply_link = str(job["job_apply_link"]) if pd.notna(job["job_apply_link"]) else "" or ""
            apply_html = f'<a href="{apply_link}" target="_blank" class="apply-link">Apply →</a>' if apply_link else ""

            posted = ""
            if pd.notna(job["job_posted_at"]):
                posted = job["job_posted_at"].strftime("%b %d")

            logo_url = str(job["employer_logo"]) if pd.notna(job["employer_logo"]) else ""
            no_logo = '<div style="width:36px;height:36px;border-radius:8px;background:#1e2535;margin-right:14px;flex-shrink:0"></div>'
            if logo_url:
                onerror = "this.style.display='none'"
                logo_html = f'<img src="{logo_url}" style="width:36px;height:36px;border-radius:8px;object-fit:contain;background:#1e2535;padding:4px;margin-right:14px;flex-shrink:0" onerror="{onerror}">'
            else:
                logo_html = no_logo

            card_html = f"""
            <div class="job-card {rec}">
                <div style="display:flex; justify-content:space-between; align-items:flex-start">
                    <div style="display:flex; align-items:flex-start; flex:1">
                        {logo_html}
                        <div style="flex:1">
                        <div class="job-title">{job['job_title']}</div>
                        <div class="job-company">{job['employer_name']} {f'· {location}' if location else ''} {f'· {posted}' if posted else ''}</div>
                        <div class="job-meta">{work_badge} {rec_badge} {apply_html}</div>
                        <div class="skills-row">{matched_html}{missing_html}</div>
                        {f'<div class="reasoning">{reasoning}</div>' if reasoning else ''}
                        </div>
                    </div>
                    <div style="text-align:right; padding-left:20px; min-width:70px">
                        <div class="score-pct">{score}%</div>
                        <div style="font-size:11px; color:#475569">match</div>
                    </div>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
else:
    st.markdown("<div style='color: #475569; padding: 60px 0; text-align: center'>No data loaded.</div>", unsafe_allow_html=True)
