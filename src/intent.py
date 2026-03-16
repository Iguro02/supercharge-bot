"""
intent.py
Keyword + heuristic intent classifier.
Returns one of: faq | price | lead | escalation | fault | greeting | unknown
"""
from __future__ import annotations
import re

# ── keyword maps ─────────────────────────────────────────────────────────────
_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("greeting", [
        r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bgood (morning|afternoon|evening)\b",
        r"\bstart\b", r"^/start$",
    ]),
    ("escalation", [
        r"\bspeak to (a |an |)(human|person|agent|staff|team|someone)\b",
        r"\btalk to (a |an |)(human|person|agent|staff|team|someone)\b",
        r"\bneed help from\b",
        r"\bcontact (your |the |)(team|staff|agent)\b",
        r"\bescalate\b",
        r"\breal person\b",
        r"\bhuman (support|agent|help)\b",
    ]),
    ("fault", [
        r"\bfault\b", r"\bbroken\b", r"\bnot working\b", r"\berror\b",
        r"\bcharger (is |)(down|offline|stuck|fail)\b",
        r"\breport (a |)(issue|problem|fault|error)\b",
        r"\bmaintenance\b",
    ]),
    ("lead", [
        r"\binterested in\b", r"\bwant to (buy|install|get|enquire|know more)\b",
        r"\bquote\b", r"\bsite assessment\b", r"\bbook (a |an |)(appointment|visit|call)\b",
        r"\bsign up\b", r"\bget in touch\b", r"\bcontact (me|us)\b",
        r"\binstall (solar|charger|ev)\b",
        r"\bbuy (solar|charger|ev)\b",
    ]),
    ("price", [
        r"\bhow much\b", r"\bpric(e|ing|es)\b", r"\bcost\b", r"\brate\b",
        r"\bsgd\b", r"\baffordable\b", r"\bcheap\b", r"\bexpensive\b",
        r"\bsubsid(y|ies|ised)\b", r"\bgrant\b",
    ]),
    ("faq", [
        r"\bwhat is\b", r"\bwhat are\b", r"\bhow (do|does|can|long|much)\b",
        r"\bwhy\b", r"\bwhen\b", r"\bwhere\b", r"\bcan i\b", r"\bdo you\b",
        r"\btr25\b", r"\bocpp\b", r"\becis\b", r"\bocpi\b",
        r"\bsolar\b", r"\bev\b", r"\bcharger\b", r"\binstall\b",
        r"\bhdb\b", r"\bcondo\b", r"\blanded\b",
        r"\bwarrant(y|ies)\b", r"\bapproval\b", r"\blicen(ce|se)\b",
    ]),
]

def detect_intent(text: str) -> str:
    """Return the most likely intent for a given user message."""
    t = text.lower().strip()
    for intent, patterns in _INTENT_PATTERNS:
        for p in patterns:
            if re.search(p, t):
                return intent
    return "unknown"
