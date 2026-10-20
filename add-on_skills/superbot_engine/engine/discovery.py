import re
from typing import List, Dict, Any

class DiscoveryEngine:
    """Scrapes multi-board listings and filters via deterministic Python rules."""
    def __init__(self, config: dict):
        self.target_roles = config['candidate_filters']['target_roles']
        self.excluded_regex = config['candidate_filters']['excluded_titles_regex']
        self.allowed_locations = config['candidate_filters']['allowed_locations']

    def is_rule_compliant(self, title: str, location: str) -> bool:
        # Title exclusions check
        if re.search(self.excluded_regex, title):
            return False
        
        # Target role relevance check
        role_match = any(role.lower() in title.lower() for role in ["data engineer", "pyspark", "analytics", "governance"])
        if not role_match:
            return False

        # Location check
        loc_match = any(allowed.lower() in location.lower() for allowed in self.allowed_locations)
        return loc_match

    async def fetch_mock_jobs(self) -> List[Dict[str, Any]]:
        """Simulates structured incoming postings from scrapers (JobSpy / APIs)."""
        return [
            {
                "job_id": "LINKEDIN_882910",
                "source": "LinkedIn",
                "title": "Data Engineer - PySpark/Databricks",
                "company": "TechCorp India",
                "location": "Noida, Uttar Pradesh",
                "apply_url": "https://example.com/apply/882910",
                "description": "Looking for a Data Engineer with strong PySpark, SQL, Databricks, and AWS experience to build analytics pipelines."
            },
            {
                "job_id": "WORKDAY_99211",
                "source": "Workday",
                "title": "Engineering Manager - Data",
                "company": "Global Analytics Ltd",
                "location": "Remote",
                "apply_url": "https://example.com/apply/99211",
                "description": "Seeking an Engineering Manager to lead a team of 15 data engineers."
            }
        ]
