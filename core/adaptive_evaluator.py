#!/usr/bin/env python3
"""
CareerPilot AI - Self-Learning & Adaptive Evaluator Engine.

Synthesizes negative constraints from candidate feedback, user corrections,
and ATS validation errors. Enforces zero-regression execution across all job
applications via deterministic pre-submission invariant checks.

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted. Zero financial cost. Zero hardcoded PII.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple


class AdaptiveEvaluator:
    """
    Deterministic rule evaluator and self-learning engine.
    Validates form data against permanent candidate preferences and negative constraints.
    """

    # Core learned invariants
    INVARIANTS = {
        "ZERO_REFERENCE_FABRICATION": "Reference person details must be empty unless candidate explicitly provides references.",
        "COLLEGE_ONLY_EDUCATION": "Education must default strictly to College/University (no Class 10th or 12th unless mandatory).",
        "OMIT_OPTIONAL_SCORES": "Academic scores/CGPA must be omitted unless explicitly marked mandatory by the portal.",
        "MANDATORY_DATES": "All education and work experience records must include valid start and end dates.",
        "RUSH_BY_KIRA_RETAIL": "Rush by Kira must be categorized as Retail (D2C Retail & E-Commerce Operations).",
    }

    @classmethod
    def audit_form_state(cls, form_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Audits a structured form state dictionary against all learned invariants.

        Args:
            form_state: Dictionary containing sections:
                - 'references': list of dicts or dict of fields
                - 'education': list of dicts
                - 'work_experience': list of dicts

        Returns:
            Dict containing 'passed': bool, 'violations': List[str], and 'remediations': List[str].
        """
        violations: List[str] = []
        remediations: List[str] = []

        # ── 1. Check References Invariant ────────────────────────────────────────
        refs = form_state.get("references", [])
        if isinstance(refs, list):
            for idx, ref in enumerate(refs):
                name = str(ref.get("name", "")).strip()
                phone = str(ref.get("phone", "")).strip()
                email = str(ref.get("email", "")).strip()
                if name or phone or email:
                    violations.append(
                        f"ZERO_REFERENCE_FABRICATION: Reference row {idx+1} contains fabricated data "
                        f"(name='{name}', email='{email}', phone='{phone}')."
                    )
                    remediations.append(f"Clear reference row {idx+1} fields to empty strings.")
        elif isinstance(refs, dict):
            for k in ["name", "custname", "phone", "custphone", "email", "custemail", "company", "custcompany"]:
                val = str(refs.get(k, "")).strip()
                if val:
                    violations.append(
                        f"ZERO_REFERENCE_FABRICATION: Reference field '{k}' has fabricated value '{val}'."
                    )
                    remediations.append(f"Clear reference field '{k}' to empty string.")

        # ── 2. Check Education Invariant (College Only) ──────────────────────────
        edus = form_state.get("education", [])
        allow_secondary = form_state.get("allow_secondary_education", False)
        if isinstance(edus, list) and not allow_secondary:
            if len(edus) > 1:
                violations.append(
                    f"COLLEGE_ONLY_EDUCATION: Found {len(edus)} education entries. Only 1 college degree allowed."
                )
                remediations.append("Prune education rows to keep only the University/College entry.")

            for idx, edu in enumerate(edus):
                inst = str(edu.get("institution", "")).lower()
                deg = str(edu.get("degree", "")).lower()
                if any(k in inst or k in deg for k in ["school", "sainik", "air force", "secondary", "10th", "12th", "cbse", "icse"]):
                    violations.append(
                        f"COLLEGE_ONLY_EDUCATION: Entry {idx+1} represents non-college school education ('{inst}')."
                    )
                    remediations.append(f"Remove non-college education entry {idx+1}.")

                # ── 3. Check Score / CGPA Omission Invariant ─────────────────────
                is_mandatory_grade = edu.get("is_grade_mandatory", False)
                grade = str(edu.get("grade", "") or edu.get("final_grade", "") or edu.get("cgpa", "")).strip()
                if grade and not is_mandatory_grade:
                    violations.append(
                        f"OMIT_OPTIONAL_SCORES: Entry {idx+1} contains grade '{grade}' but score is not mandatory."
                    )
                    remediations.append(f"Clear grade field in education entry {idx+1}.")

                # ── 4. Check Education Dates ─────────────────────────────────────
                start_date = str(edu.get("start_date", "")).strip()
                end_date = str(edu.get("end_date", "")).strip()
                if not start_date or not end_date:
                    violations.append(
                        f"MANDATORY_DATES: Education entry {idx+1} is missing dates (start='{start_date}', end='{end_date}')."
                    )
                    remediations.append(f"Populate start and end dates for education entry {idx+1}.")

        # ── 5. Check Work Experience Dates & Rush by Kira Classification ─────────
        exps = form_state.get("work_experience", [])
        if isinstance(exps, list):
            for idx, exp in enumerate(exps):
                company = str(exp.get("company", ""))
                is_current = exp.get("is_current", False)
                start_date = str(exp.get("start_date", "")).strip()
                end_date = str(exp.get("end_date", "")).strip()

                if not start_date:
                    violations.append(f"MANDATORY_DATES: Work experience entry {idx+1} ({company}) is missing start_date.")
                    remediations.append(f"Populate start_date for work experience entry {idx+1}.")

                if not is_current and not end_date:
                    violations.append(f"MANDATORY_DATES: Past work experience {idx+1} ({company}) is missing end_date.")
                    remediations.append(f"Populate end_date for work experience entry {idx+1}.")

                if "rush by kira" in company.lower() or "kira" in company.lower():
                    b_type = str(exp.get("business_type", "")).strip()
                    org = str(exp.get("organization", "")).strip()
                    if b_type.lower() != "retail":
                        violations.append(
                            f"RUSH_BY_KIRA_RETAIL: Rush by Kira business type is '{b_type}', must be 'Retail'."
                        )
                        remediations.append("Update business type for Rush by Kira to 'Retail'.")
                    if "d2c" not in org.lower() and "retail" not in org.lower():
                        violations.append(
                            f"RUSH_BY_KIRA_RETAIL: Rush by Kira organization is '{org}', must specify D2C Retail."
                        )
                        remediations.append("Update organization for Rush by Kira to 'D2C Retail & E-Commerce Operations'.")

        return {
            "passed": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
            "remediations": remediations,
        }

    @classmethod
    def sanitize_form_state(cls, form_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies automatic remediations to enforce all learned invariants.

        Returns:
            Sanitized deep copy of form_state complying with all rules.
        """
        import copy
        state = copy.deepcopy(form_state)

        # 1. Sanitize references
        if "references" in state:
            if isinstance(state["references"], list):
                for ref in state["references"]:
                    for k in ["name", "custname", "phone", "custphone", "email", "custemail", "company", "custcompany", "title", "occupation"]:
                        if k in ref:
                            ref[k] = ""
            elif isinstance(state["references"], dict):
                for k in ["name", "custname", "phone", "custphone", "email", "custemail", "company", "custcompany", "title", "occupation"]:
                    if k in state["references"]:
                        state["references"][k] = ""

        # 2. Sanitize education (college only)
        if "education" in state and isinstance(state["education"], list) and not state.get("allow_secondary_education", False):
            college_entries = [
                e for e in state["education"]
                if not any(k in str(e.get("institution", "")).lower() or k in str(e.get("degree", "")).lower()
                           for k in ["school", "sainik", "air force", "secondary", "10th", "12th"])
            ]
            if not college_entries and state["education"]:
                college_entries = [state["education"][0]]
            state["education"] = college_entries[:1]

            # Clear optional scores
            for edu in state["education"]:
                if not edu.get("is_grade_mandatory", False):
                    for gk in ["grade", "final_grade", "cgpa", "score", "percentage"]:
                        if gk in edu:
                            edu[gk] = ""

        # 3. Sanitize Rush by Kira classification
        if "work_experience" in state and isinstance(state["work_experience"], list):
            for exp in state["work_experience"]:
                comp = str(exp.get("company", "")).lower()
                if "rush by kira" in comp or "kira" in comp:
                    exp["business_type"] = "Retail"
                    exp["organization"] = "D2C Retail & E-Commerce Operations"

        return state

    @classmethod
    def parse_user_correction(cls, text: str) -> Dict[str, Any]:
        """
        Extracts semantic corrections from natural language user feedback.
        """
        text_lower = text.lower()
        detections = []

        if "reference" in text_lower and any(k in text_lower for k in ["never", "did i ever", "thin air", "don't pull", "dont pull", "fabricat", "no reference"]):
            detections.append({
                "invariant": "ZERO_REFERENCE_FABRICATION",
                "directive": "Never pull references out of thin air. Leave reference person fields blank."
            })

        if "education" in text_lower and any(k in text_lower for k in ["college only", "other than college", "dont add education", "don't add education"]):
            detections.append({
                "invariant": "COLLEGE_ONLY_EDUCATION",
                "directive": "Do not add education other than college/university unless specifically mandated."
            })

        if any(k in text_lower for k in ["cgpa", "score", "grade", "percentage"]) and any(k in text_lower for k in ["dont write", "don't write", "unless necessary", "unless asked"]):
            detections.append({
                "invariant": "OMIT_OPTIONAL_SCORES",
                "directive": "Do not enter CGPA or scores unless explicitly mandatory on the form."
            })

        if "date" in text_lower and any(k in text_lower for k in ["missing", "populate dates", "dates are missing", "start date", "end date"]):
            detections.append({
                "invariant": "MANDATORY_DATES",
                "directive": "Ensure start and end dates are always populated for all roles and degrees."
            })

        if "rush by kira" in text_lower and any(k in text_lower for k in ["d2c", "retail", "business"]):
            detections.append({
                "invariant": "RUSH_BY_KIRA_RETAIL",
                "directive": "Rush by Kira is strictly a D2C retail e-commerce business."
            })

        return {
            "matched_corrections": detections,
            "total_matches": len(detections),
            "status": "LEARNED" if detections else "NO_MATCH"
        }


def audit_form_state(form_state: Dict[str, Any]) -> Dict[str, Any]:
    """Helper shortcut for AdaptiveEvaluator.audit_form_state."""
    return AdaptiveEvaluator.audit_form_state(form_state)
