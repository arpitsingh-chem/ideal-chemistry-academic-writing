"""Optional LLM adapter.

Design rule: the model is a *writer*, never a source of facts.  It receives a
grounded outline (numbers, citation keys, compound records) and must return
prose that uses only those.  Output is validated by the same checks as the
deterministic path.  Works with any OpenAI-compatible endpoint, Ollama,
Gemini or Groq; nothing is sent anywhere unless the user runs this command.
"""
from __future__ import annotations

import json
import os
import urllib.request

from .project import Project

SYSTEM = """You are a scientific writer for chemistry journals.
Rules:
1. Use ONLY the numbers, compounds, citation keys and claims in the provided evidence pack.
2. Never invent a citation key, DOI, yield, or measurement.
3. Write precise, compact academic English (mean sentence length 18-26 words).
4. No hype words: novel, first, unprecedented, excellent, remarkable, groundbreaking.
5. Every quantitative sentence must be traceable to the evidence pack.
Return only the requested text."""


def evidence_pack(project: Project) -> dict:
    """Everything a writer (human or model) may use as fact, and nothing else."""
    from .draft import compose
    from .checks import evidence_number_set

    doc = compose(project)
    pack = {
        "title": doc.title,
        "journal": doc.profile.journal,
        "article_type": doc.profile.article_type,
        "abstract": doc.abstract,
        "sections": [{"heading": s.heading,
                      "paragraphs": [p["text"] for p in s.paragraphs if not p["text"].startswith("__SUB__")]}
                     for s in doc.sections],
        "compounds": [
            {"id": c.id, "formula": c.formula, "yield": c.yield_percent,
             "hrms_calcd": c.hrms_calcd, "hrms_found": c.hrms_found,
             "nmr_1h": c.nmr_1h, "nmr_13c": c.nmr_13c}
            for c in project.compounds
        ],
        "citation_keys": [r.key for r in project.references],
        "numbers_present_in_data": sorted(evidence_number_set(project), key=float),
        "journal_limits": {
            "abstract_max_words": doc.profile.limits.abstract_max,
            "body_max_words": doc.profile.limits.body_max_words,
            "title_max_words": doc.profile.title_max_words,
        },
    }
    return pack


def build_prompt(project: Project) -> str:
    pack = evidence_pack(project)
    return (
        "Rewrite the manuscript sections for clarity without changing any fact. "
        "Use the evidence pack exactly.\n\nEVIDENCE PACK:\n"
        + json.dumps(pack, indent=1, ensure_ascii=False)
        + "\n\nReturn Markdown with the same section headings."
    )


def _post(url: str, payload: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def draft_with_llm(project: Project, provider: str = "ollama", model: str = "") -> str:  # pragma: no cover
    prompt = build_prompt(project)
    if provider == "ollama":
        model = model or "llama3.1:8b"
        data = _post("http://localhost:11434/api/generate",
                     {"model": model, "prompt": SYSTEM + "\n\n" + prompt, "stream": False},
                     {"Content-Type": "application/json"})
        return data.get("response", "")
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        data = _post(os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions",
                     {"model": model or "gpt-4o-mini",
                      "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]},
                     {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        return data["choices"][0]["message"]["content"]
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        model = model or "gemini-2.0-flash"
        data = _post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            {"contents": [{"parts": [{"text": SYSTEM + "\n\n" + prompt}]}]},
            {"Content-Type": "application/json"})
        return data["candidates"][0]["content"]["parts"][0]["text"]
    if provider == "groq":
        key = os.environ.get("GROQ_API_KEY", "")
        data = _post("https://api.groq.com/openai/v1/chat/completions",
                     {"model": model or "llama-3.3-70b-versatile",
                      "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]},
                     {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        return data["choices"][0]["message"]["content"]
    raise ValueError(f"unknown provider {provider!r} (use ollama/openai/gemini/groq)")


def validate_llm_output(text: str, project: Project) -> list[str]:
    """Return grounding violations in LLM output (unknown keys / untraceable numbers)."""
    from .checks import evidence_number_set, find_numbers
    from .util import sentences

    issues = []
    keys = {r.key for r in project.references}
    for token in set(__import__("re").findall(r"\[([A-Za-z0-9_,;\s-]+)\]", text)):
        for k in __import__("re").split(r"[,;]", token):
            k = k.strip()
            if k and k not in keys and not k.isdigit():
                issues.append(f"unknown citation key: {k}")
    evidence = evidence_number_set(project)
    for n in find_numbers(text):
        if n not in evidence:
            issues.append(f"number not in evidence: {n}")
    return issues
