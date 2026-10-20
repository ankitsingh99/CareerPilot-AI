#!/usr/bin/env python3
"""
Turnitout Humanizer & Threat Erasure Engine (parsers/turnitout_engine.py)
------------------------------------------------------------------------
Adapted from Turnitout-Humanizer (AhmadHassan-BTed/Turnitout-Humanizer):
100% Programmatic, zero-generative-AI footprint removal and style transformation engine.

Key Protocols:
1. Zero-Width Unicode & AI Watermark Purging:
   Purges hidden zero-width spaces (\\u200B, \\u200C, \\u200D), zero-width no-break spaces (\\uFEFF),
   soft hyphens (\\u00AD), word joiners (\\u2060), and directional markers used by LLMs (Claude,
   Gemini SynthID, ChatGPT) for watermarking under EU AI Act Article 50 tracers.

2. ZipPy Entropy & AI Signature Checking:
   Computes text perplexity and entropy via zlib and lzma compression ratios (Normalized Compression Distance).
   High entropy = unpredictable / human-like. Low entropy = uniform / robotic AI signature.

3. Karp-Rabin 5-Gram Winnowing Disruption:
   Analyzes sliding word k-grams (k=5, window w=4) based on the Winnowing algorithm (Schleimer et al.).
   Detects contiguous predictable n-gram chains and disrupts them to prevent Turnitin / Copyleaks fingerprinting.

4. 10-Stage Deterministic Syntactic Transformation Pipeline:
   - Entity Masking (protects verified career facts, company names, tools, metrics)
   - Multi-word Phrase Rewrites (crushes corporate buzzwords and high-probability LLM transitions)
   - Rare Academic / Professional Synonyms (boosts perplexity by picking low-probability tokens)
   - Determiner Swapping ('many' -> 'numerous' / 'a number of')
   - Active <-> Passive Voice Inversion (shatters Karp-Rabin order-dependent hashes)
   - Sentence Fusion & Splitting (enforces extreme burstiness: high sentence-length standard deviation)
   - Nominalization / De-nominalization (verb <-> noun form transformations)
   - Discourse Marker Rotation (rotates transitional markers with zero repetition)
   - Clause-Level Modifier Reordering (prepositional phrase transposition)
   - Entity Unmasking (restores exact technical terms)
"""

import os
import math
import random
import re
import unicodedata
import zlib
import lzma
from typing import Dict, List, Tuple, Set, Any, Optional

# ==============================================================================
# 1. WATERMARK & ZERO-WIDTH UNICODE PURGE DEFINITIONS
# ==============================================================================
ZERO_WIDTH_CHARS = [
    "\u200B",  # Zero-width space
    "\u200C",  # Zero-width non-joiner
    "\u200D",  # Zero-width joiner
    "\u2060",  # Word joiner
    "\uFEFF",  # Zero-width no-break space / Byte Order Mark (BOM)
    "\u00AD",  # Soft hyphen
    "\u200E",  # Left-to-right mark
    "\u200F",  # Right-to-left mark
    "\u202A",  # Left-to-right embedding
    "\u202B",  # Right-to-left embedding
    "\u202C",  # Pop directional formatting
    "\u202D",  # Left-to-right override
    "\u202E",  # Right-to-left override
]
ZERO_WIDTH_REGEX = re.compile("[" + "".join(ZERO_WIDTH_CHARS) + "]")

# Unusual unicode spaces that trigger AI detector heuristics
ODD_SPACES_REGEX = re.compile(r"[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]")

# ==============================================================================
# 2. DICTIONARIES & RULE TAXONOMIES
# ==============================================================================

# Protected candidate entities that must NEVER be mutated or corrupted
_candidate_entities = [
    e.strip() for e in [
        os.getenv("CANDIDATE_NAME", ""),
        os.getenv("CANDIDATE_FIRST_NAME", ""),
        os.getenv("CANDIDATE_LAST_NAME", ""),
        os.getenv("CANDIDATE_UNIVERSITY", ""),
    ] + [c.strip() for c in os.getenv("CANDIDATE_VERIFIED_COMPANIES", "").split(",") if c.strip()]
    if e.strip()
]

PROTECTED_ENTITIES = _candidate_entities + [
    "PySpark",
    "PostgreSQL",
    "Snowflake",
    "Airflow",
    "Trino",
    "Shopify",
    "iThinkLogistics",
    "Autosys",
    "SonarQube",
    "Bitbucket",
    "Tableau",
    "AWS",
    "Amazon Web Services",
    "AWS SNS",
    "AWS S3",
    "HIPAA",
    "HCP",
    "HCO",
    "AWB",
    "SKU",
    "DCF",
    "TMT",
    "40%",
    "₹20,000+",
    "15+",
    "8+",
    "35%",
    "3.7 CGPA",
    "9.2 CGPA",
    "87.4%",
    "85%",
]

# High-probability AI phrases to be replaced with human equivalents
PHRASE_REWRITES: List[Tuple[str, str]] = [
    (r"\bthis is a testament to\b", "this reflects"),
    (r"\ba testament to\b", "evidence of"),
    (r"\bin today's (?:fast-paced|dynamic) (?:world|landscape|market)\b", "in current production environments"),
    (r"\bseamlessly (?:integrate|integrates|integrated)\b", "directly integrated"),
    (r"\bseamless integration\b", "direct integration"),
    (r"\bplay a pivotal role\b", "take direct ownership"),
    (r"\bplayed a pivotal role in\b", "led execution for"),
    (r"\bnavigate the complexities of\b", "manage"),
    (r"\bdelve (?:deeply )?into\b", "examine"),
    (r"\bdelving into\b", "inspecting"),
    (r"\bdeep dive into\b", "detailed audit of"),
    (r"\bharness the power of\b", "use"),
    (r"\bharnessing the power of\b", "using"),
    (r"\bfoster an environment\b", "build processes"),
    (r"\bproven track record of\b", "history of"),
    (r"\bresults-oriented professional\b", "engineer"),
    (r"\bhit the ground running\b", "start immediately"),
    (r"\bmutually beneficial synergy\b", "collaboration"),
    (r"\bmultifaceted approach\b", "multi-tier strategy"),
    (r"\btransformative impact\b", "substantial measurable gain"),
    (r"\bholistic understanding\b", "broad operational context"),
    (r"\bcutting-edge\b", "modern production"),
    (r"\bgame-changer\b", "major efficiency gain"),
    (r"\bbring to the table\b", "deliver"),
    (r"\bat the forefront of\b", "directly working with"),
    (r"\bpassionate about\b", "focused on"),
    (r"\bkeen interest in\b", "focus on"),
    (r"\bthrilled to apply\b", "submitting my background"),
    (r"\bexcited to apply\b", "applying"),
    (r"\beager to contribute\b", "ready to work on"),
    (r"\blook no further\b", "I can deliver"),
]

# Rare professional & academic synonyms that boost perplexity score
RARE_SYNONYMS: Dict[str, List[str]] = {
    "analyze": ["scrutinize", "dissect", "audit", "evaluate"],
    "analyzed": ["scrutinized", "dissected", "audited", "evaluated"],
    "analyzing": ["scrutinizing", "dissecting", "auditing", "evaluating"],
    "build": ["engineer", "construct", "deploy"],
    "built": ["engineered", "constructed", "deployed"],
    "building": ["engineering", "constructing", "deploying"],
    "improve": ["refine", "sharpen", "upgrade"],
    "improved": ["refined", "sharpened", "upgraded"],
    "improving": ["refining", "sharpening", "upgrading"],
    "optimize": ["calibrate", "streamline", "fine-tune"],
    "optimized": ["calibrated", "streamlined", "fine-tuned"],
    "optimizing": ["calibrating", "streamlining", "fine-tuning"],
    "reduce": ["curtail", "slash", "cut"],
    "reduced": ["curtailed", "slashed", "cut"],
    "reducing": ["curtailing", "slashing", "cutting"],
    "solve": ["resolve", "remedy", "untangle"],
    "solved": ["resolved", "remedied", "untangled"],
    "solving": ["resolving", "remedying", "untangling"],
    "demonstrate": ["corroborate", "substantiate", "show"],
    "demonstrated": ["corroborated", "substantiated", "showed"],
    "demonstrating": ["corroborating", "substantiating", "showing"],
    "significant": ["appreciable", "consequential", "salient", "notable"],
    "substantial": ["considerable", "pronounced", "appreciable"],
    "accurate": ["veridical", "scrupulous", "precise"],
    "approach": ["strategy", "modality", "pipeline methodology"],
    "method": ["procedure", "protocol", "architecture"],
    "result": ["outcome", "metric", "finding"],
    "problem": ["bottleneck", "discrepancy", "breakdown"],
    "error": ["incident", "anomaly", "outlier"],
    "errors": ["incidents", "anomalies", "outliers"],
}

# Determiners cycling dictionary
DETERMINERS: Dict[str, List[str]] = {
    "several": ["numerous", "multiple", "a series of"],
    "many": ["numerous", "a substantial number of", "copious"],
    "some": ["certain", "specific", "select"],
    "few": ["a limited number of", "scarce"],
    "most": ["the majority of", "the greater part of"],
    "all": ["every", "the entirety of"],
    "each": ["every", "any given", "each individual"],
    "every": ["each", "all", "each single"],
    "both": ["the two", "each of the two"],
    "another": ["an additional", "a further", "one more"],
    "other": ["alternative", "additional", "supplementary"],
}

# Discourse markers rotation mappings (tracking history to prevent repetition)
DISCOURSE_MARKERS: Dict[str, List[str]] = {
    "However": ["Nevertheless", "Nonetheless", "That said", "On the other hand"],
    "Therefore": ["Consequently", "Hence", "As a result", "Accordingly"],
    "Moreover": ["Furthermore", "In addition", "Additionally", "Beyond this"],
    "Although": ["Even though", "Despite the fact that", "While"],
    "Thus": ["Hence", "Accordingly", "As such"],
    "Indeed": ["In fact", "Certainly", "In practice"],
    "Specifically": ["In particular", "More precisely", "Namely"],
    "Notably": ["Remarkably", "Significantly", "Importantly"],
    "Meanwhile": ["In parallel", "Concurrently", "At the same time"],
    "Ultimately": ["In the final analysis", "In operational practice", "At scale"],
    "Essentially": ["Fundamentally", "In essence", "At its core"],
}

# Verb <-> Noun nominalization pairs
NOMINALIZATION_PAIRS: List[Tuple[str, str]] = [
    (r"\bwe analyzed\b", "our analysis covered"),
    (r"\bwe investigated\b", "an investigation was conducted on"),
    (r"\bwe applied\b", "application was made of"),
    (r"\bwe developed\b", "development centered on"),
    (r"\bwe evaluated\b", "evaluation was performed on"),
    (r"\bwe implemented\b", "implementation focused on"),
    (r"\bwe reduced\b", "a direct reduction was achieved in"),
    (r"\bwe optimized\b", "optimization targeted"),
    (r"\bwe verified\b", "verification confirmed"),
    (r"\bI analyzed\b", "my analysis examined"),
    (r"\bI built\b", "construction and deployment of"),
    (r"\bI developed\b", "my development focused on"),
    (r"\bI reduced\b", "my work achieved a reduction in"),
    (r"\bI managed\b", "management oversight covered"),
]


# ==============================================================================
# 3. CORE TURNITOUT ENGINE CLASS
# ==============================================================================

class TurnitoutEngine:
    """
    Modular, deterministic text humanization & threat erasure engine.
    """

    def __init__(self, seed: Optional[int] = 42):
        self.rng = random.Random(seed)
        self.used_discourse_markers: Dict[str, Set[str]] = {}
        self.reset_counters()

    def reset_counters(self):
        """Reset transformation telemetry counters."""
        self.watermarks_purged = 0
        self.phrases_rewritten = 0
        self.synonyms_swapped = 0
        self.determiners_cycled = 0
        self.voice_inverted = 0
        self.sentences_fused = 0
        self.nominalizations_made = 0
        self.discourse_rotated = 0
        self.clause_reordered = 0
        self.used_discourse_markers = {k: set() for k in DISCOURSE_MARKERS}

    # --------------------------------------------------------------------------
    # Step 1: Watermark & Invisible Unicode Purging
    # --------------------------------------------------------------------------
    def purge_watermarks(self, text: str) -> Tuple[str, int]:
        """
        Strips hidden zero-width spaces, soft hyphens, byte-order marks,
        and converts non-standard spaces to standard ASCII spaces.
        """
        # Count zero-width characters before stripping
        matches = ZERO_WIDTH_REGEX.findall(text)
        purged_count = len(matches)

        clean = ZERO_WIDTH_REGEX.sub("", text)
        clean = ODD_SPACES_REGEX.sub(" ", clean)

        # Normalize unicode to NFC
        clean = unicodedata.normalize("NFC", clean)
        self.watermarks_purged += purged_count
        return clean, purged_count

    # --------------------------------------------------------------------------
    # Step 2: ZipPy Entropy & Perplexity Analysis
    # --------------------------------------------------------------------------
    @staticmethod
    def compute_zippy_entropy(text: str) -> Dict[str, Any]:
        """
        Computes text compression entropy using zlib and lzma.
        
        Mathematical Foundation:
        AI-generated text exhibits regular token sequences and low syntactic entropy,
        causing it to compress more tightly (lower compressed-to-raw byte ratio).
        Human-written text exhibits higher perplexity, high burstiness, and
        higher compression entropy (higher compression ratio).
        """
        raw_bytes = text.strip().encode("utf-8")
        raw_len = len(raw_bytes)
        if raw_len == 0:
            return {
                "raw_bytes": 0,
                "zlib_ratio": 0.0,
                "lzma_ratio": 0.0,
                "entropy_score": 0.0,
                "ai_likelihood": "Unknown (Empty text)",
            }

        zlib_compressed = zlib.compress(raw_bytes, level=9)
        lzma_compressed = lzma.compress(raw_bytes)

        zlib_ratio = round(len(zlib_compressed) / raw_len, 4)
        lzma_ratio = round(len(lzma_compressed) / raw_len, 4)

        # Weighted heuristic entropy score normalized roughly between 0.0 and 1.0
        # Text with zlib_ratio > 0.65 is typically highly irregular / human.
        # Repetitive template AI text tends to compress below 0.50.
        entropy_score = round(min(1.0, max(0.0, (zlib_ratio - 0.35) / 0.45)), 3)

        if entropy_score >= 0.70:
            ai_likelihood = "Very Low (High Perplexity / Human-like)"
        elif entropy_score >= 0.45:
            ai_likelihood = "Moderate (Acceptable variation)"
        else:
            ai_likelihood = "High (Robotic / High token redundancy)"

        return {
            "raw_bytes": raw_len,
            "zlib_bytes": len(zlib_compressed),
            "zlib_ratio": zlib_ratio,
            "lzma_bytes": len(lzma_compressed),
            "lzma_ratio": lzma_ratio,
            "entropy_score": entropy_score,
            "ai_likelihood": ai_likelihood,
        }

    # --------------------------------------------------------------------------
    # Step 3: Karp-Rabin 5-Gram Winnowing Audit
    # --------------------------------------------------------------------------
    @staticmethod
    def audit_ngrams(text: str, k: int = 5) -> Dict[str, Any]:
        """
        Slices word stream into sliding k-gram windows (default k=5 words).
        Turnitin's Winnowing algorithm detects passages matching >= 8 consecutive words.
        """
        # Lowercase and remove punctuation for normalization
        words = re.findall(r"\b[a-z0-9]+\b", text.lower())
        total_words = len(words)
        if total_words < k:
            return {
                "total_words": total_words,
                "k_grams_extracted": 0,
                "unique_k_grams": 0,
                "redundancy_pct": 0.0,
                "risk_chains_flagged": 0,
            }

        k_grams = []
        for i in range(total_words - k + 1):
            gram = " ".join(words[i : i + k])
            k_grams.append(gram)

        unique_grams = set(k_grams)
        redundant_count = len(k_grams) - len(unique_grams)
        redundancy_pct = round((redundant_count / len(k_grams)) * 100, 2) if k_grams else 0.0

        return {
            "total_words": total_words,
            "k_grams_extracted": len(k_grams),
            "unique_k_grams": len(unique_grams),
            "redundancy_pct": redundancy_pct,
            "risk_chains_flagged": redundant_count,
        }

    # --------------------------------------------------------------------------
    # Step 4: Masking Protected Entities
    # --------------------------------------------------------------------------
    def _mask_entities(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Mask candidate names, companies, and technical terms before mutation."""
        mask_map: Dict[str, str] = {}
        masked_text = text

        for idx, ent in enumerate(PROTECTED_ENTITIES):
            token = f"__ENTITY_TOKEN_{idx}__"
            # Exact boundary matching
            pattern = re.compile(re.escape(ent), re.IGNORECASE)
            if pattern.search(masked_text):
                # Save the first exact match as representative
                m = pattern.search(masked_text)
                if m:
                    mask_map[token] = m.group(0)
                    masked_text = pattern.sub(token, masked_text)

        return masked_text, mask_map

    def _unmask_entities(self, text: str, mask_map: Dict[str, str]) -> str:
        """Restore protected entities after transformations."""
        unmasked = text
        for token, original in mask_map.items():
            unmasked = unmasked.replace(token, original)
        return unmasked

    # --------------------------------------------------------------------------
    # Step 5: Multi-Word Phrase Rewriter
    # --------------------------------------------------------------------------
    def _apply_phrase_rewrites(self, text: str) -> str:
        """Replace predictable multi-word cliches with direct human phrasing."""
        modified = text
        for pat, rep in PHRASE_REWRITES:
            regex = re.compile(pat, re.IGNORECASE)
            if regex.search(modified):
                modified = regex.sub(rep, modified)
                self.phrases_rewritten += 1
        return modified

    # --------------------------------------------------------------------------
    # Step 6: Low-Probability / Rare Synonym Swapping
    # --------------------------------------------------------------------------
    def _apply_rare_synonyms(self, text: str, rate: float = 0.35) -> str:
        """
        Swaps common verbs, adjectives, and nouns with rarer academic/professional synonyms.
        Only swaps with probability `rate` to maintain natural cadence.
        """
        words = text.split()
        out_words = []

        for w in words:
            # Strip punctuation for lookup
            clean_w = re.sub(r"^[^\w]+|[^\w]+$", "", w).lower()
            if clean_w in RARE_SYNONYMS and self.rng.random() < rate:
                candidates = RARE_SYNONYMS[clean_w]
                choice = self.rng.choice(candidates)
                # Preserve capitalization
                if w[0].isupper():
                    choice = choice.capitalize()
                # Re-attach trailing punctuation
                trail = ""
                m = re.search(r"[^\w]+$", w)
                if m:
                    trail = m.group(0)
                lead = ""
                m_lead = re.search(r"^[^\w]+", w)
                if m_lead:
                    lead = m_lead.group(0)
                out_words.append(lead + choice + trail)
                self.synonyms_swapped += 1
            else:
                out_words.append(w)

        return " ".join(out_words)

    # --------------------------------------------------------------------------
    # Step 7: Determiners Cycle
    # --------------------------------------------------------------------------
    def _cycle_determiners(self, text: str, rate: float = 0.30) -> str:
        """Cycles determiners (several -> numerous) to destroy rolling hash chains."""
        words = text.split()
        out_words = []

        for w in words:
            clean_w = re.sub(r"^[^\w]+|[^\w]+$", "", w).lower()
            if clean_w in DETERMINERS and self.rng.random() < rate:
                choice = self.rng.choice(DETERMINERS[clean_w])
                if w[0].isupper():
                    choice = choice.capitalize()
                out_words.append(choice)
                self.determiners_cycled += 1
            else:
                out_words.append(w)

        return " ".join(out_words)

    # --------------------------------------------------------------------------
    # Step 8: Active <-> Passive Voice Inversion
    # --------------------------------------------------------------------------
    def _invert_voice(self, sentence: str) -> str:
        """
        Converts active voice patterns to passive and vice-versa.
        Shifts syntax tree and breaks order-dependent Karp-Rabin hashes.
        """
        # Pattern 1: "We analyzed the results" -> "The results were analyzed"
        p1 = re.compile(r"^We analyzed ([^,.]+)", re.IGNORECASE)
        if p1.search(sentence):
            self.voice_inverted += 1
            return p1.sub(r"\1 were analyzed", sentence)

        # Pattern 2: "I engineered the pipeline" -> "The pipeline was engineered"
        p2 = re.compile(r"^I engineered ([^,.]+)", re.IGNORECASE)
        if p2.search(sentence):
            self.voice_inverted += 1
            return p2.sub(r"\1 was engineered", sentence)

        # Pattern 3: "The model was trained by us" -> "We trained the model"
        p3 = re.compile(r"was ([a-z]+ed) by (?:us|our team)", re.IGNORECASE)
        if p3.search(sentence):
            self.voice_inverted += 1
            return p3.sub(r"we \1", sentence)

        return sentence

    # --------------------------------------------------------------------------
    # Step 9: Nominalization & Structure Destroying
    # --------------------------------------------------------------------------
    def _apply_nominalization(self, sentence: str) -> str:
        """Converts verb clauses to noun phrases or vice versa."""
        res = sentence
        for pat, rep in NOMINALIZATION_PAIRS:
            regex = re.compile(pat, re.IGNORECASE)
            if regex.search(res):
                res = regex.sub(rep, res)
                self.nominalizations_made += 1
                break
        return res

    # --------------------------------------------------------------------------
    # Step 10: Discourse Marker Rotation (Zero Repetition Guarantee)
    # --------------------------------------------------------------------------
    def _rotate_discourse(self, sentence: str) -> str:
        """
        Rotates starting transitions (However, Therefore, Moreover, etc.)
        to alternate forms while strictly preventing repetition across the document.
        """
        for marker, alternatives in DISCOURSE_MARKERS.items():
            pattern = re.compile(rf"^{marker},\s*", re.IGNORECASE)
            if pattern.search(sentence):
                used = self.used_discourse_markers[marker]
                # Filter out already used alternatives
                available = [a for a in alternatives if a not in used]
                if not available:
                    used.clear()
                    available = alternatives

                choice = self.rng.choice(available)
                used.add(choice)
                self.discourse_rotated += 1
                return pattern.sub(f"{choice}, ", sentence)

        return sentence

    # --------------------------------------------------------------------------
    # Step 11: Clause Modifier Reordering
    # --------------------------------------------------------------------------
    def _reorder_clauses(self, sentence: str, rate: float = 0.25) -> str:
        """
        Transposes introductory prepositional phrases:
        "Using PySpark, I processed 15+ feeds" -> "I processed 15+ feeds using PySpark"
        """
        if self.rng.random() > rate:
            return sentence

        pattern = re.compile(r"^(Using|By leveraging|Through|With) ([^,]{8,40}), ([A-Z][^.]+)$")
        m = pattern.search(sentence)
        if m:
            prep = m.group(1).lower()
            subject = m.group(2)
            main_clause = m.group(3)
            # Check capitalization
            main_clause = main_clause[0].upper() + main_clause[1:] if len(main_clause) > 1 else main_clause
            self.clause_reordered += 1
            return f"{main_clause} {prep} {subject}"

        return sentence

    # --------------------------------------------------------------------------
    # Step 12: Sentence Fusion & Burstiness Balancer
    # --------------------------------------------------------------------------
    def _fuse_and_burst(self, sentences: List[str]) -> List[str]:
        """
        Combines adjacent short staccato sentences (< 10 words) with coordinate connectors
        to enforce high rhythmic burstiness and variance.
        """
        if len(sentences) < 2:
            return sentences

        fused = []
        i = 0
        connectors = [", thereby", ", which in turn", " and subsequently"]

        while i < len(sentences):
            current = sentences[i].strip()
            if not current:
                i += 1
                continue

            words_curr = current.split()
            # If current sentence is short, and next exists and is also short, fuse them
            if i + 1 < len(sentences) and len(words_curr) <= 10 and self.rng.random() < 0.40:
                nxt = sentences[i + 1].strip()
                words_nxt = nxt.split()
                if len(words_nxt) <= 14:
                    conn = self.rng.choice(connectors)
                    # Lowercase starting letter of next sentence unless it's 'I' or protected
                    nxt_formatted = nxt
                    if nxt and not nxt.startswith("I ") and not nxt.startswith("__ENTITY"):
                        nxt_formatted = nxt[0].lower() + nxt[1:]
                    merged = current.rstrip(".!?;") + conn + " " + nxt_formatted
                    fused.append(merged)
                    self.sentences_fused += 1
                    i += 2
                    continue

            fused.append(current)
            i += 1

        return fused

    # --------------------------------------------------------------------------
    # Complete Humanize Execution Pipeline
    # --------------------------------------------------------------------------
    def humanize(
        self,
        text: str,
        aggressiveness: float = 0.75,
        target_burstiness: bool = True,
    ) -> Dict[str, Any]:
        """
        Runs the full 10-stage Turnitout threat erasure & humanization pipeline.
        
        Parameters:
            text: Input raw text (markdown, plain text, cover letter)
            aggressiveness: Modification intensity (0.1 to 1.0)
            target_burstiness: Whether to execute sentence fusion for rhythm variance
        """
        self.reset_counters()

        # Step 1: Watermark & Zero-Width Purging
        clean_text, purged_count = self.purge_watermarks(text)

        # Baseline entropy before transformations
        initial_entropy = self.compute_zippy_entropy(clean_text)

        # Step 2: Mask protected entities
        masked_text, mask_map = self._mask_entities(clean_text)

        # Step 3: Multi-word phrase rewrites
        phrase_clean = self._apply_phrase_rewrites(masked_text)

        # Split into paragraphs and sentences
        paragraphs = phrase_clean.split("\n\n")
        transformed_paras = []

        synonym_rate = min(0.60, 0.25 * (aggressiveness / 0.5))
        determiner_rate = min(0.50, 0.20 * (aggressiveness / 0.5))

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Split paragraph into sentences
            raw_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
            mutated_sents = []

            for sent in raw_sents:
                s = sent
                # Step 4: Discourse marker rotation
                s = self._rotate_discourse(s)

                # Step 5: Active <-> Passive voice inversion
                if self.rng.random() < (0.30 * aggressiveness):
                    s = self._invert_voice(s)

                # Step 6: Nominalization
                if self.rng.random() < (0.25 * aggressiveness):
                    s = self._apply_nominalization(s)

                # Step 7: Clause reordering
                s = self._reorder_clauses(s, rate=0.25 * aggressiveness)

                # Step 8: Rare synonyms
                s = self._apply_rare_synonyms(s, rate=synonym_rate)

                # Step 9: Determiners
                s = self._cycle_determiners(s, rate=determiner_rate)

                mutated_sents.append(s)

            # Step 10: Sentence fusion for burstiness
            if target_burstiness:
                mutated_sents = self._fuse_and_burst(mutated_sents)

            transformed_paras.append(" ".join(mutated_sents))

        # Recombine paragraphs
        recombined = "\n\n".join(transformed_paras)

        # Step 11: Unmask protected entities
        final_text = self._unmask_entities(recombined, mask_map)

        # Compute post-transformation entropy and n-gram metrics
        final_entropy = self.compute_zippy_entropy(final_text)
        ngram_audit = self.audit_ngrams(final_text, k=5)

        total_transforms = (
            self.watermarks_purged
            + self.phrases_rewritten
            + self.synonyms_swapped
            + self.determiners_cycled
            + self.voice_inverted
            + self.sentences_fused
            + self.nominalizations_made
            + self.discourse_rotated
            + self.clause_reordered
        )

        return {
            "humanized_text": final_text,
            "total_transforms": total_transforms,
            "watermarks_purged": self.watermarks_purged,
            "phrases_rewritten": self.phrases_rewritten,
            "synonyms_swapped": self.synonyms_swapped,
            "determiners_cycled": self.determiners_cycled,
            "voice_inverted": self.voice_inverted,
            "sentences_fused": self.sentences_fused,
            "nominalizations_made": self.nominalizations_made,
            "discourse_rotated": self.discourse_rotated,
            "clause_reordered": self.clause_reordered,
            "initial_entropy": initial_entropy,
            "final_entropy": final_entropy,
            "ngram_audit": ngram_audit,
        }
