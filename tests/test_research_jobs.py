import csv
import os
from pathlib import Path

def test_extract_keywords(tmp_path: Path):
    # create a fake tracker CSV
    csv_path = tmp_path / "job_search_tracker.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["role", "company"])
        writer.writeheader()
        writer.writerow({"role": "Data Engineer", "company": "ABC Corp"})
        writer.writerow({"role": "Senior Data Analyst", "company": "XYZ Ltd"})
    # import the function from the script
    from tools.research_jobs import extract_keywords_from_history
    keywords = extract_keywords_from_history(csv_path)
    assert "data" in keywords
    assert "engineer" in keywords
    assert "senior" not in keywords  # stop word
    assert len(keywords) >= 2

