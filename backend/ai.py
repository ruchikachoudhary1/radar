"""
AI bullet-point rewriting.

When a Google Gemini API key is configured the rewriter uses Gemini with a
carefully engineered prompt. With no key the module degrades gracefully to a
deterministic rule-based rewriter, so the app is fully functional offline —
the AI layer is an enhancement, never a hard dependency.
"""
from __future__ import annotations

import os
import re

REWRITE_PROMPT = """You are a resume coach. Rewrite the résumé bullet below into \
{n} stronger variants. Rules:
- Start each with a strong past-tense action verb (Built, Led, Optimized, Shipped...).
- Add a plausible quantified impact (%, time, scale, users) ONLY if the original implies one; \
never fabricate specific numbers, use a [metric] placeholder instead.
- One line each, under 24 words, no first person, no fluff.
Return only the variants as a plain numbered list.

Original bullet: "{bullet}"
"""

# Weak openers to strip. The remainder is capitalised so the bullet leads with
# its real action word instead of an awkward "Built migrating..." substitution.
WEAK_OPENERS = [
    "was responsible for", "responsible for", "were responsible for",
    "worked on", "was tasked with", "tasked with", "assisted with", "assisted in",
    "involved in", "participated in", "in charge of", "helped to", "helped",
    "handled", "dealt with", "duties included",
]


def gemini_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def rewrite_bullet(bullet: str, n: int = 3) -> dict:
    bullet = bullet.strip()
    if not bullet:
        return {"engine": "none", "variants": []}
    if gemini_available():
        variants = _gemini_rewrite(bullet, n)
        if variants:
            return {"engine": "gemini", "variants": variants}
    return {"engine": "rule-based", "variants": _rule_rewrite(bullet, n)}


def _gemini_rewrite(bullet: str, n: int) -> list[str]:
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        resp = model.generate_content(REWRITE_PROMPT.format(bullet=bullet, n=n))
        lines = [
            re.sub(r"^\s*\d+[.)]\s*", "", ln).strip(" -*\t")
            for ln in resp.text.splitlines()
            if ln.strip()
        ]
        return [ln for ln in lines if ln][:n]
    except Exception:
        return []


def _rule_rewrite(bullet: str, n: int) -> list[str]:
    """Deterministic improvement so the feature always returns something useful."""
    base = bullet.strip().lstrip("•-–—* ").rstrip(".")
    low = base.lower()

    # Strip a weak opener and lead with the real action word.
    core = base
    for opener in WEAK_OPENERS:
        if low.startswith(opener):
            core = base[len(opener):].strip()
            break
    core = (core[0].upper() + core[1:]) if core else core

    has_metric = bool(re.search(r"\d", base))
    variants = [core]
    if not has_metric:
        variants.append(f"{core}, cutting [metric] by [X]%")
        variants.append(f"{core}, impacting [N] users")
    else:
        variants.append(f"{core} (lead with the strongest number)")
        variants.append(f"{core} — name the tools you used")

    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out[:n]
