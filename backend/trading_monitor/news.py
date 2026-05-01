from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .models import NewsContext


@dataclass(frozen=True)
class Headline:
    title: str
    source: str = "unknown"


NEGATIVE_TERMS = {
    "crash",
    "selloff",
    "recession",
    "default",
    "war",
    "geopolitical",
    "inflation shock",
    "rate hike",
    "hawkish",
}
POSITIVE_TERMS = {"soft landing", "rate cut", "dovish", "disinflation", "cooling inflation"}
HIGH_RISK_TERMS = {"market halt", "bank failure", "flash crash", "invasion", "terror attack"}
GOLD_TERMS = {"gold", "treasury yield", "real yield", "dollar", "geopolitical"}
FED_TERMS = {"federal reserve", "fed", "interest rate", "powell"}


def analyze_headlines(headlines: Iterable[Headline], symbol: str = "") -> NewsContext:
    seen = set()
    categories: List[str] = []
    score_modifier = 0
    risk_override = False

    for headline in headlines:
        title = headline.title.strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        if any(term in key for term in HIGH_RISK_TERMS):
            risk_override = True
            categories.append("high_risk")
        if any(term in key for term in NEGATIVE_TERMS):
            score_modifier -= 4
            categories.append("negative_macro")
        if any(term in key for term in POSITIVE_TERMS):
            score_modifier += 3
            categories.append("positive_macro")
        if any(term in key for term in FED_TERMS):
            categories.append("fed_rates")
        if symbol.upper() in {"IAU", "GLD"} and any(term in key for term in GOLD_TERMS):
            categories.append("gold_macro")

    unique_categories = sorted(set(categories))
    if not seen:
        return NewsContext(summary="News context unavailable or neutral.", score_modifier=0)
    if risk_override:
        return NewsContext(
            summary="Major risk headline detected; confidence reduced.",
            score_modifier=-15,
            risk_override=True,
            categories=unique_categories,
        )

    bounded_modifier = max(-15, min(15, score_modifier))
    if bounded_modifier > 0:
        summary = "News context is modestly supportive."
    elif bounded_modifier < 0:
        summary = "News context is negative and reduces confidence."
    else:
        summary = "News context is neutral."
    return NewsContext(summary=summary, score_modifier=bounded_modifier, categories=unique_categories)

