"""Typo-canonicalization for free-text tags manually entered by CS agents.

Standalone on purpose, not wired into pipeline.pipeline's steps -- mirrors the real
system, where this kind of cleanup ran as its own separate pass rather than as part
of the main daily pipeline. See docs/adr/003.
"""

TYPO_MAP = {
    "intersted": "interested",
    "interrested": "interested",
    "folowup": "follow_up",
    "follow up": "follow_up",
    "follow-up": "follow_up",
    "komplain": "complaint",
    "complain": "complaint",
    "gajadi": "not_interested",
    "ga jadi": "not_interested",
    "batal": "not_interested",
    "cancel": "not_interested",
}


def canonicalize_tag(raw: str) -> str:
    if not raw or not str(raw).strip():
        return "unknown"
    key = str(raw).strip().lower()
    return TYPO_MAP.get(key, key.replace(" ", "_").replace("-", "_"))


def canonicalize_series(series):
    return series.fillna("").map(canonicalize_tag)
