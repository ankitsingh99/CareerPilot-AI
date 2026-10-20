import subprocess
import json
import csv
import os
import re

BUN_PATH = "/Users/ashish/.bun/bin/bun"
CLI_PATH = ".agents/skills/linkedin-search/cli/src/cli.ts"

# Top Target GCCs from GCC master db.csv + Roblox
targets = [
    # Pharma & Healthcare GCCs
    {"company": "Novartis", "category": "Pharma & Healthcare", "queries": ["Novartis Data Engineer", "Novartis Analytics", "Novartis AI", "Novartis Data Scientist"]},
    {"company": "AstraZeneca", "category": "Pharma & Healthcare", "queries": ["AstraZeneca Data Engineer", "AstraZeneca Data Analyst", "AstraZeneca Clinical Data"]},
    {"company": "Bristol Myers Squibb", "category": "Pharma & Healthcare", "queries": ["Bristol Myers Squibb Data", "BMS Analytics", "Bristol Myers Squibb Engineer"]},
    {"company": "Sanofi", "category": "Pharma & Healthcare", "queries": ["Sanofi Data", "Sanofi Analytics", "Sanofi AI"]},
    {"company": "GSK", "category": "Pharma & Healthcare", "queries": ["GSK Data", "GSK Analytics", "GSK Engineer"]},
    {"company": "Eli Lilly", "category": "Pharma & Healthcare", "queries": ["Eli Lilly Data", "Eli Lilly Analytics", "Eli Lilly Engineer"]},
    {"company": "Novo Nordisk", "category": "Pharma & Healthcare", "queries": ["Novo Nordisk Data", "Novo Nordisk Analytics"]},
    {"company": "Bayer", "category": "Pharma & Healthcare", "queries": ["Bayer Data", "Bayer Analytics", "Bayer Engineer"]},
    {"company": "Siemens Healthineers", "category": "MedTech & Diagnostics", "queries": ["Siemens Healthineers Data", "Siemens Healthineers AI", "Siemens Healthineers Software"]},
    {"company": "Medtronic", "category": "MedTech & Diagnostics", "queries": ["Medtronic Data", "Medtronic Analytics", "Medtronic Software"]},
    {"company": "Philips", "category": "MedTech & Diagnostics", "queries": ["Philips Data", "Philips Analytics", "Philips AI"]},
    {"company": "GE HealthCare", "category": "MedTech & Diagnostics", "queries": ["GE HealthCare Data", "GE HealthCare Analytics", "GE HealthCare Engineer"]},
    {"company": "Baxter", "category": "MedTech & Diagnostics", "queries": ["Baxter Data", "Baxter Analytics"]},
    {"company": "Boston Scientific", "category": "MedTech & Diagnostics", "queries": ["Boston Scientific Data", "Boston Scientific Analytics"]},
    {"company": "BD", "category": "MedTech & Diagnostics", "queries": ["BD Data", "Becton Dickinson Analytics"]},
    {"company": "Optum", "category": "Healthcare Services", "queries": ["Optum Data Engineer", "Optum Analytics", "Optum Data Analyst"]},
    {"company": "Providence India", "category": "Healthcare Services", "queries": ["Providence India Data", "Providence Healthcare Analytics"]},
    {"company": "Johnson & Johnson", "category": "Healthcare Services", "queries": ["Johnson & Johnson Data", "Johnson & Johnson Analytics"]},
    {"company": "Abbott", "category": "Healthcare Services", "queries": ["Abbott Data", "Abbott Analytics"]},
    {"company": "Roche", "category": "Healthcare Services", "queries": ["Roche Data", "Roche Analytics"]},
    {"company": "IQVIA", "category": "Life Sciences Data & Clinical Tech", "queries": ["IQVIA Data Engineer", "IQVIA Analytics", "IQVIA Data Analyst"]},
    {"company": "ZS Associates", "category": "Life Sciences Consulting & Analytics", "queries": ["ZS Associates Data", "ZS Associates Consultant", "ZS Associates Analytics"]},
    {"company": "Trinity Life Sciences", "category": "Life Sciences Consulting & Analytics", "queries": ["Trinity Life Sciences Analytics", "Trinity Life Sciences Consultant"]},
    {"company": "Clarivate", "category": "Scientific & Pharma Intelligence", "queries": ["Clarivate Data", "Clarivate Analytics"]},
    {"company": "CitiusTech", "category": "Healthcare Technology & Analytics", "queries": ["CitiusTech Data Engineer", "CitiusTech Analytics"]},
    {"company": "Eversana", "category": "Commercialization Services for Pharma", "queries": ["Eversana Data", "Eversana Analytics"]},
    {"company": "Evalueserve", "category": "Data Analytics & Market Research", "queries": ["Evalueserve Analytics", "Evalueserve Data"]},
    {"company": "Roblox", "category": "Gaming & Platform Tech", "queries": ["Roblox Support Specialist Gurugram", "Roblox Operations", "Roblox Data"]}
]

def clean_no_em_dash(text):
    if not text:
        return ""
    return text.replace("—", "-").replace("–", "-").strip()

def get_location_tier(loc_str):
    loc_lower = loc_str.lower()
    if "remote" in loc_lower:
        return (1, "100% Remote")
    elif any(d in loc_lower for d in ["delhi", "noida", "gurgaon", "gurugram", "ncr", "haryana"]):
        return (2, "Delhi NCR")
    elif any(b in loc_lower for b in ["bangalore", "bengaluru", "karnataka"]):
        return (3, "Bangalore")
    elif any(h in loc_lower for h in ["hyderabad", "telangana"]):
        return (4, "Hyderabad")
    else:
        return (5, "Rest of India")

results = []
seen_urls = set()

print("Starting GCC and Target Opportunities Search...")

for t in targets:
    company = t["company"]
    category = t["category"]
    print(f"\nSearching for {company} ({category})...")
    
    for q in t["queries"]:
        cmd = [BUN_PATH, "run", CLI_PATH, "search", "-q", q, "-l", "India", "--limit", "4", "--format", "json"]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if p.returncode == 0 and p.stdout:
                data = json.loads(p.stdout)
                for item in data.get("results", []):
                    url = item.get("url")
                    title = clean_no_em_dash(item.get("title", ""))
                    loc = clean_no_em_dash(item.get("location", "India"))
                    job_id = item.get("id", "")
                    
                    if not url or url in seen_urls:
                        continue
                    
                    # Filter out non-relevant positions (HR, Sales Executive, Intern, Nursing, Lab Technician, Doctor, Medical Officer)
                    lower_title = title.lower()
                    if any(bad in lower_title for bad in ["intern", "technician", "nursing", "nurse", "operator", "executive assistant", "receptionist", "sales representative", "medical sales"]):
                        continue
                        
                    # Calculate fit rating based on domain and role
                    fit = 85
                    reasons = []
                    if any(k in lower_title for k in ["data engineer", "data engineering", "big data"]):
                        fit += 10
                        reasons.append("Core Data Engineering (PySpark, SQL, Airflow, Snowflake, ETL)")
                    if any(k in lower_title for k in ["analytics", "data analyst", "bi engineer", "business intelligence"]):
                        fit += 9
                        reasons.append("Advanced Analytics & BI suites (Tableau, SQL, Python, Cohort Analytics)")
                    if any(k in lower_title for k in ["data scientist", "machine learning", "ml", "ai"]):
                        fit += 9
                        reasons.append("Machine Learning & AI Modeling (Scikit-learn, Feature Eng, Anomaly Models)")
                    if any(k in lower_title for k in ["consultant", "associate", "specialist", "operations", "strategy"]):
                        fit += 7
                        reasons.append("Consulting, Strategy & Cross-Functional Delivery (Ex-ZS Associates, Rush by Kira)")
                    if any(p_kw in category.lower() for p_kw in ["pharma", "healthcare", "life sciences", "medtech"]):
                        fit += 4
                        reasons.append("Pharma / Life Sciences / HealthTech domain expertise (HIPAA, Commercial Analytics, ZS)")
                        
                    fit = min(fit, 98)
                    
                    tier_order, tier_name = get_location_tier(loc)
                    
                    seen_urls.add(url)
                    results.append({
                        "company": company,
                        "category": category,
                        "title": title,
                        "job_id": job_id,
                        "location": loc,
                        "tier_order": tier_order,
                        "tier_name": tier_name,
                        "fit_rating": f"{fit}%",
                        "match_reasons": "; ".join(reasons) if reasons else "Strong quantitative and analytical problem-solving match",
                        "url": url
                    })
        except Exception as e:
            print(f"Error querying {q}: {e}")

# Include Roblox Gurugram roles explicitly
roblox_roles = [
    {
        "company": "Roblox",
        "category": "Gaming & Platform Tech",
        "title": "Product Support Specialist",
        "job_id": "8070027",
        "location": "Gurugram, Haryana, India",
        "tier_order": 2,
        "tier_name": "Delhi NCR",
        "fit_rating": "94%",
        "match_reasons": "Product reliability, incident response, SQL/Python analytics, cross-functional operations and root-cause analysis",
        "url": "https://careers.roblox.com/jobs/8070027?gh_jid=8070027&gh_src=da92d0c91"
    },
    {
        "company": "Roblox",
        "category": "Gaming & Platform Tech",
        "title": "Senior Product Support Specialist",
        "job_id": "8111889",
        "location": "Gurugram, Haryana, India",
        "tier_order": 2,
        "tier_name": "Delhi NCR",
        "fit_rating": "95%",
        "match_reasons": "Senior incident response, escalations, process automation, metric tracking, and engineering collaboration",
        "url": "https://careers.roblox.com/jobs/8111889"
    },
    {
        "company": "Roblox",
        "category": "Gaming & Platform Tech",
        "title": "Lead, Support Operations Excellence",
        "job_id": "8070037",
        "location": "Gurugram, Haryana, India",
        "tier_order": 2,
        "tier_name": "Delhi NCR",
        "fit_rating": "96%",
        "match_reasons": "Support operations scaling, process optimization, workflow automation, and metrics governance",
        "url": "https://careers.roblox.com/jobs/8070037"
    }
]

for rb in roblox_roles:
    if rb["url"] not in seen_urls:
        results.append(rb)

# Sort results by Location Tier (Remote > Delhi NCR > Bangalore > Hyderabad > Rest of India), then by Fit Rating descending
def sort_key(item):
    tier = item["tier_order"]
    fit_val = int(item["fit_rating"].replace("%", ""))
    return (tier, -fit_val)

results.sort(key=sort_key)

print(f"\nTotal validated opportunities found: {len(results)}")

# Write to CSV
csv_file = "researched_opportunities.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "priority_rank",
        "company",
        "industry_category",
        "role_title",
        "job_id",
        "location",
        "location_tier",
        "fit_rating",
        "match_reasons",
        "job_url"
    ])
    for idx, r in enumerate(results, 1):
        writer.writerow([
            idx,
            r["company"],
            r["category"],
            r["title"],
            r["job_id"],
            r["location"],
            r["tier_name"],
            r["fit_rating"],
            r["match_reasons"],
            r["url"]
        ])

print(f"Saved {csv_file}")

# Write to Markdown Report
md_file = "researched_opportunities.md"
with open(md_file, "w", encoding="utf-8") as f:
    candidate_name = os.getenv("CANDIDATE_NAME", "Candidate")
    f.write(f"**Candidate:** {candidate_name}\n")
    f.write("**Location Ranking:** 1. 100% Remote | 2. Delhi NCR | 3. Bangalore | 4. Hyderabad | 5. Rest of India\n")
    f.write(f"**Total Opportunities Identified:** {len(results)}\n\n")
    f.write("---\n\n")
    
    current_tier = None
    for idx, r in enumerate(results, 1):
        if r["tier_name"] != current_tier:
            current_tier = r["tier_name"]
            f.write(f"\n## Tier: {current_tier}\n\n")
            f.write("| Rank | Company | Role Title | Location | Fit | Key Match Highlights | Link |\n")
            f.write("|---|---|---|---|---|---|---|\n")
        f.write(f"| {idx} | **{r['company']}** | {r['title']} | {r['location']} | `{r['fit_rating']}` | {r['match_reasons']} | [View Job]({r['url']}) |\n")

print(f"Saved {md_file}")
