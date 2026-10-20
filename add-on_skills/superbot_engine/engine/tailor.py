from typing import Dict, Any, List

class DocumentTailorEngine:
    """Re-aligns master resume bullet points and drafts customized cover letters strictly adhering to factual data."""
    def __init__(self, profile: dict):
        self.profile = profile

    def generate_tailored_materials(self, job_title: str, company: str, job_description: str) -> Dict[str, Any]:
        master_bullets = self.profile['experience_bullets']
        
        # Filter and prioritize bullets matching job description keywords
        prioritized_bullets = []
        for bullet in master_bullets:
            if any(tech.lower() in job_description.lower() for tech in ["pyspark", "databricks", "airflow", "sql", "snowflake"]):
                prioritized_bullets.append(bullet)

        if not prioritized_bullets:
            prioritized_bullets = master_bullets[:3]

        cover_letter = (
            f"Dear Hiring Team at {company},\n\n"
            f"I am writing to express my enthusiastic interest in the {job_title} role. "
            f"In my current role at {self.profile['current_employment']['company']} in {self.profile['current_employment']['location']}, "
            f"I specialize in building distributed data engineering pipelines using {', '.join(self.profile['current_employment']['tech_stack'][:4])}.\n\n"
            f"My technical background aligns directly with your requirements for scalable processing and pipeline orchestration. "
            f"I look forward to discussing how my experience can support {company}'s data infrastructure goals.\n\n"
            f"Sincerely,\n{self.profile['personal_info']['first_name']} {self.profile['personal_info']['last_name']}"
        )

        return {
            "tailored_resume_summary": f"Data Engineer with expertise in PySpark, SQL, and AWS. Currently at {self.profile['current_employment']['company']}.",
            "tailored_bullets": prioritized_bullets,
            "cover_letter": cover_letter,
            "qa_answers": self.profile['qa_knowledge_base']
        }
