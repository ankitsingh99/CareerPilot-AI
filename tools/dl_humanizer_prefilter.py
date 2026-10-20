#!/usr/bin/env python3
import sys
import os
import re
import json
import argparse
import lazy_import
np = lazy_import.lazy_module("numpy")
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intelligence.llm_clients.openrouter import ask

class DLPreFilter:
    """
    A NumPy-based Deep Learning Neural Network Pre-Filter.
    Architecture: 3-Layer Perceptron (Input=5, H1=16, H2=8, Out=1)
    """
    def __init__(self):
        # Features: [sent_len, ai_buzz_count, lex_diversity, hyphen_count, avg_word_len]
        np.random.seed(42)
        # W1: 5 x 16
        self.W1 = np.random.randn(5, 16) * 0.1
        # Hardcode penalties in the first layer
        # feature 1 (ai_buzz_count) has strong negative weights
        self.W1[1, :] = -0.9
        # feature 3 (hyphen_count) has strong negative weights
        self.W1[3, :] = -0.8
        
        self.b1 = np.zeros(16)
        
        # W2: 16 x 8
        self.W2 = np.random.randn(16, 8) * 0.1
        self.b2 = np.zeros(8)
        
        # W3: 8 x 1
        self.W3 = np.random.randn(8, 1) * 0.1
        self.W3 = np.abs(self.W3) 
        self.b3 = np.zeros(1)

    def relu(self, x):
        return np.maximum(0, x)

    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def extract_features(self, sentence):
        words = sentence.split()
        if not words:
            return np.zeros(5)
            
        sent_len = len(words) / 50.0  # Normalized length
        
        ai_buzzwords = {'leverage', 'spearhead', 'transformative', 'synergy', 'dive', 'delve', 'testament', 'tapestry', 'pivotal', 'seamless', 'holistic', 'thrilled', 'excited', 'passionate'}
        ai_buzz_count = sum(1 for w in words if w.lower().strip(',.') in ai_buzzwords) / 5.0
        
        lex_diversity = len(set(words)) / len(words)
        
        hyphen_count = sentence.count('-') / 2.0
        
        avg_word_len = sum(len(w) for w in words) / len(words) / 10.0
        
        return np.array([sent_len, ai_buzz_count, lex_diversity, hyphen_count, avg_word_len])

    def forward(self, sentence):
        x = self.extract_features(sentence)
        
        # Layer 1
        z1 = np.dot(x, self.W1) + self.b1
        a1 = self.relu(z1)
        
        # Layer 2
        z2 = np.dot(a1, self.W2) + self.b2
        a2 = self.relu(z2)
        
        # Layer 3
        z3 = np.dot(a2, self.W3) + self.b3
        out = self.sigmoid(z3)
        
        return float(out[0])


def filter_content(text: str) -> str:
    print("\n[DL Pre-Filter] Initializing Deep Learning Neural Network...")
    dl_model = DLPreFilter()
    
    raw_sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if len(s.strip()) > 8]
    human_sentences = []
    
    print("[DL Pre-Filter] Passing factual data through Neural Network layers...")
    for s in raw_sentences:
        score = dl_model.forward(s)
        # Clean inline hyphens out of approved facts
        clean_s = s.replace("-", " ")
        if score >= 0.45:
            human_sentences.append(clean_s)
        else:
            print(f"  -> [Filtered Out by DL Filter - AI/Hyphen Penalty]: {s[:60]}...")
            
    filtered_text = ". ".join(human_sentences) + "."
    print(f"[DL Pre-Filter] Processed sentences: {len(raw_sentences)} | Approved & Humanized: {len(human_sentences)}")
    return filtered_text


def generate_humanized_cover_letter(facts_text: str, role_title: str, company: str) -> str:
    filtered_facts = filter_content(facts_text)
    
    candidate_name = os.getenv("CANDIDATE_NAME", "Candidate")
    candidate_first = os.getenv("CANDIDATE_FIRST_NAME", candidate_name.split()[0] if candidate_name else "Candidate")

    prompt = f"""
Write a 3-paragraph executive cover letter for the role '{role_title}' at '{company}'.
Use ONLY the factual details provided below.

CRITICAL RULES:
1. ABSOLUTELY ZERO HYPHENS ('-') or em dashes. Never hyphenate compound words (write 'real world', 'end to end', 'last mile', 'multi store', 'cost effective', 'data driven').
2. NO GENERIC AI OPENERS OR OVER-EXCITED PLEASANTRIES. Never write 'I am excited to apply', 'I am thrilled to', 'I am eager to contribute', or 'I am writing to apply'. Start directly with a concrete operational problem or technical reality.
3. NO CORPORATE SLOP or AI buzzwords (do not use 'spearheaded', 'leveraged', 'transformative', 'testament', 'tapestry', 'synergy', 'pivotal', 'delve', 'dive', 'passionate').
4. Keep sentences direct, punchy, varied in length, and conversational like an experienced consultant speaking to an engineering lead.
5. Output ONLY the letter text starting directly with 'Dear Hiring Team,' and ending with 'Sincerely,\\n{candidate_name}'. Do NOT output reasoning or preamble.

FACTS:
{filtered_facts}
"""
    print("[DL Pre-Filter] Sending pre-filtered factual data to OpenRouter Free Tier LLM...")
    res = ask(
        prompt=prompt,
        system="You are an elite executive career writer. You write grounded, punchy, authentic prose. You strictly avoid hyphens, over-excited AI openings, and corporate buzzwords. Output only the final letter directly.",
        model="cohere/north-mini-code:free",
        temperature=0.6,
        max_tokens=3500
    )
    
    # Extra safety pass: replace any remaining hyphenated compound words and eliminate fake excitement openers
    cleaned_lines = []
    for line in res.split('\n'):
        line_clean = line
        # Strip generic AI excitement starters if any slipped through
        line_clean = re.sub(r"^(?:I am excited to apply for|I am thrilled to apply for|I am eager to apply for|I am pleased to submit my application for)\s*", "Applying for ", line_clean, flags=re.IGNORECASE)
        
        if line_clean.strip().startswith('#') or line_clean.strip().startswith(f'**{candidate_first}') or '|' in line_clean or 'linkedin.com' in line_clean:
            cleaned_lines.append(line_clean)
        else:
            cleaned_lines.append(line_clean.replace(' - ', ', ').replace('-', ' '))
            
    combined_raw = '\n'.join(cleaned_lines)

    # Turnitout Threat Erasure & Programmatic Humanizer Pass
    try:
        from parsers.turnitout_engine import TurnitoutEngine
        t_engine = TurnitoutEngine(seed=42)
        humanized_res = t_engine.humanize(combined_raw, aggressiveness=0.7)
        print(f"[Turnitout Post-Pass] Watermarks purged: {humanized_res['watermarks_purged']} | Transforms: {humanized_res['total_transforms']} | ZipPy Entropy: {humanized_res['final_entropy']['entropy_score']}")
        final_candidate = humanized_res['humanized_text']
    except Exception as e:
        print(f"[Turnitout Post-Pass Warning] Fallback to raw: {e}")
        final_candidate = combined_raw

    # Two-Tier Integrity & Proofreading Pass (Local Linter + OpenRouter Free Proofreader)
    try:
        from parsers.linter import lint_and_format
        lint_res = lint_and_format(final_candidate, proofread_llm=True, role_title=role_title, company=company)
        if not lint_res["passed"]:
            print(f"[Cover Letter Guard] Warning: Detected issues in draft: {lint_res['violations']}")
        return lint_res["clean_text"]
    except Exception as e:
        print(f"[Cover Letter Guard Warning] Linter pass failed: {e}")
        return final_candidate


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep Learning Pre-Filter to OpenRouter Free LLM")
    parser.add_argument("--input", type=str, required=True, help="Input text file containing background facts")
    parser.add_argument("--role", type=str, default="Data Analyst, Labs", help="Role Title")
    parser.add_argument("--company", type=str, default="DoorDash", help="Company Name")
    parser.add_argument("--output", type=str, default="", help="Output markdown file path")
    args = parser.parse_args()
    
    with open(args.input, 'r', encoding='utf-8') as f:
        content = f.read()
        
    letter_body = generate_humanized_cover_letter(content, args.role, args.company)
    print("\n====== GENERATED HUMAN-LIKE COVER LETTER ======\n")
    print(letter_body)
    print("\n===============================================\n")
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(letter_body)
        print(f"Saved generated letter to {args.output}")
