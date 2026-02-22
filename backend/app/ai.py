"""
AI utilities — resume text extraction and embedding-based candidate analysis.

Scoring uses sentence-transformers (all-MiniLM-L6-v2) to embed the resume
and job text independently, then computes cosine similarity for three
dimensions: overall fit, skills alignment, and experience alignment.

The model (~90 MB) is downloaded from HuggingFace on first use and cached
locally by the sentence-transformers library.
"""
from __future__ import annotations

import io
import json
import re

_model = None


def _get_model():
    """Lazy-load the embedding model — downloaded once, cached on disk."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Return plain text from a PDF, concatenating all pages."""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Return plain text from a Word (.docx) document."""
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text).strip()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity between two texts, scaled to 0–100."""
    from sklearn.metrics.pairwise import cosine_similarity
    model = _get_model()
    emb = model.encode([text_a, text_b])
    raw = float(cosine_similarity([emb[0]], [emb[1]])[0][0])
    return round(max(0.0, min(1.0, raw)) * 100, 1)


def _extract_experience_years(text: str) -> float | None:
    """Heuristic: find the largest 'N years' mention in the resume text."""
    matches = re.findall(r"(\d+)\+?\s*years?\b", text, re.IGNORECASE)
    if not matches:
        return None
    return float(max(int(m) for m in matches))


def _parse_skills_list(raw: str) -> list[str]:
    """Parse skills_required — handles JSON arrays and comma-separated strings."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(s) for s in parsed]
    except (json.JSONDecodeError, ValueError):
        pass
    return [s.strip() for s in raw.split(",") if s.strip()]


def _matched_skills(resume_text: str, skills_required: str) -> list[str]:
    """Return which required skills are mentioned verbatim in the resume."""
    skills = _parse_skills_list(skills_required)
    lower = resume_text.lower()
    return [s for s in skills if s.lower() in lower]


# ── Main entry point ──────────────────────────────────────────────────────────

def analyze_resume(resume_text: str, job) -> dict:
    """
    Compute embedding-based match scores between a resume and a job.

    Returns a dict with the same keys expected by the application router:
        match_score, skills_match, experience_match,
        skills, experience_years, education, summary,
        ai_summary, recommendation
    """
    # Build context strings for each scoring dimension
    job_overview = "\n".join(filter(None, [
        job.title,
        job.description,
        job.requirements,
        job.responsibilities,
    ]))
    job_skills_text = "\n".join(filter(None, [
        job.skills_required,
        job.title,
    ]))
    job_experience_text = "\n".join(filter(None, [
        job.experience_level,
        job.requirements,
        job.title,
    ]))

    match_score      = _similarity(job_overview, resume_text)
    skills_match     = _similarity(job_skills_text, resume_text)
    experience_match = _similarity(job_experience_text, resume_text)

    matched_skills   = _matched_skills(resume_text, job.skills_required or "")
    experience_years = _extract_experience_years(resume_text)

    if match_score >= 75:
        recommendation = "strong_yes"
    elif match_score >= 60:
        recommendation = "yes"
    elif match_score >= 45:
        recommendation = "maybe"
    else:
        recommendation = "no"

    ai_summary = (
        f"Resume shows {match_score:.0f}% semantic alignment with the role. "
        f"Skills coverage: {skills_match:.0f}%. "
        f"Experience alignment: {experience_match:.0f}%."
    )

    return {
        "match_score":      int(match_score),
        "skills_match":     int(skills_match),
        "experience_match": int(experience_match),
        "skills":           matched_skills,
        "experience_years": experience_years,
        "education":        None,
        "summary":          None,
        "ai_summary":       ai_summary,
        "recommendation":   recommendation,
    }
