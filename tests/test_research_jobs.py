import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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


class TestResearchJobsLocalFilter(unittest.TestCase):
    def test_discover_jobs_filters_excluded_and_scores_locally(self):
        from tools import research_jobs

        sample_jobs = [
            {
                "company": "Acme",
                "title": "Data Engineer (Python, SQL, Snowflake)",
                "location": "Bengaluru, India",
                "description": "Build ETL pipelines with Python, SQL, Snowflake, Apache Airflow, AWS.",
                "apply_url": "https://boards.greenhouse.io/acme/jobs/1",
            },
            {
                "company": "Acme",
                "title": "Java Spring Boot Engineer",
                "location": "Bengaluru, India",
                "description": "Java, Spring Boot microservices.",
                "apply_url": "https://boards.greenhouse.io/acme/jobs/2",
            },
        ]

        with tempfile.TemporaryDirectory() as td:
            tmp_root = Path(td)
            (tmp_root / "user_inputs").mkdir()
            (tmp_root / "user_inputs" / "job_search_tracker.csv").write_text(
                "company,role\nAcme,Data Engineer\n", encoding="utf-8"
            )
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmp_root)
                with patch.object(
                    research_jobs,
                    "_lazy_import_pollers",
                    return_value={"greenhouse": lambda slug: sample_jobs if slug == "acme" else []},
                ):
                    matches = research_jobs.discover_jobs({"data", "engineer"})
            finally:
                os.chdir(orig_cwd)

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["job_title"], "Data Engineer (Python, SQL, Snowflake)")
            self.assertGreaterEqual(float(matches[0]["local_fit_score"]), 80.0)


if __name__ == "__main__":
    unittest.main()

