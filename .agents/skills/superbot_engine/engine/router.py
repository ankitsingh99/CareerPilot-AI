import os
from typing import Literal

class DynamicModelRouter:
    """Selects the lowest-cost LLM tier capable of handling a specific task."""
    def __init__(self, config: dict):
        self.tier_1 = config['llm_tier_assignments']['tier_1']
        self.tier_2 = config['llm_tier_assignments']['tier_2']
        self.tier_3 = config['llm_tier_assignments']['tier_3']

    def route_task(self, task_type: Literal["extract", "score", "tailor", "qa_match"], token_estimate: int = 1000) -> str:
        if task_type == "extract":
            return self.tier_1
        elif task_type == "score":
            return self.tier_1 if token_estimate < 1200 else self.tier_2
        elif task_type == "qa_match":
            return self.tier_2
        elif task_type == "tailor":
            return self.tier_3
        return self.tier_2
