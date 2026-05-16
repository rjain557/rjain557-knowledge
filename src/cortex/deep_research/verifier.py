"""
Verifier — runs after Deep Research synthesis and flags claims in the
article that are either (a) unsupported by their inline citation or
(b) commonly known to be false.

Uses Claude Haiku 4.5 — cheap enough to run on every article (~$0.01/run).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import structlog

from cortex.llm import complete

log = structlog.get_logger(__name__)

_SYSTEM = """You are a fact-checker for a knowledge brain.

You receive a markdown research article with inline footnote citations like [^1] [^2],
plus a list of the source URLs each footnote points to.

Your job is to flag any claim that meets EITHER condition:
 (a) UNSUPPORTED — a non-trivial factual claim that lacks an inline citation,
     OR cites a footnote whose source URL is clearly unrelated.
 (b) LIKELY_FALSE — a claim that contradicts widely-accepted facts (dates,
     model versions, who-built-what, license types, etc.) based on your
     training. Be conservative: only flag if you are fairly confident the
     claim is wrong.

Return STRICT JSON of this exact shape — NO prose, NO markdown fencing:

{
  "verdict": "passed" | "flagged" | "failed",
  "flagged_claims": [
    {
      "claim":    "short quote of the claim, max 200 chars",
      "type":     "unsupported" | "likely_false",
      "reason":   "one-sentence reason",
      "citation": "the [^N] footnote referenced, or null"
    }
  ]
}

verdict rules:
  - "passed"  if flagged_claims is empty
  - "flagged" if 1-2 unsupported OR up to 1 likely_false
  - "failed"  if 3+ unsupported OR 2+ likely_false (article is suspect)

If the article body is empty or trivial, return verdict=failed with one
flagged_claim explaining why.
"""


@dataclass
class VerificationResult:
    verdict: str                            # passed | flagged | failed
    flagged_claims: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def is_clean(self) -> bool:
        return self.verdict == "passed"


def verify_article(article_markdown: str, citations: list[dict]) -> VerificationResult:
    """Return a VerificationResult; never raises."""
    if not article_markdown or len(article_markdown.strip()) < 200:
        return VerificationResult(verdict="failed",
                                  flagged_claims=[{"claim": "(article body too short)",
                                                   "type": "unsupported",
                                                   "reason": "Verifier received <200 chars of article body",
                                                   "citation": None}])

    # Trim citations payload to keep token cost low — we only need URL + title
    cite_lines = []
    for i, c in enumerate(citations[:50], start=1):
        url = (c.get("url") or "").strip()
        title = (c.get("title") or "").strip()[:120]
        cite_lines.append(f"[^{i}]: {title} — {url}")
    citations_block = "\n".join(cite_lines) or "(no citations attached)"

    prompt = (
        f"Article markdown:\n---\n{article_markdown[:30000]}\n---\n\n"
        f"Citation index (footnote -> URL):\n{citations_block}\n\n"
        f"Return the verification JSON now."
    )

    try:
        raw = complete(
            system=_SYSTEM,
            prompt=prompt,
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            temperature=0.0,
        )
        data = _parse_json(raw)
        verdict = data.get("verdict", "failed")
        flagged = data.get("flagged_claims", []) or []
        log.info("verifier.done", verdict=verdict, flagged=len(flagged))
        return VerificationResult(verdict=verdict, flagged_claims=flagged)
    except Exception as exc:
        log.warning("verifier.error", error=str(exc))
        # Fail safe — don't block the article, but flag that we couldn't check
        return VerificationResult(
            verdict="flagged",
            flagged_claims=[{"claim": "(verifier could not run)",
                             "type": "unsupported",
                             "reason": f"verifier exception: {str(exc)[:200]}",
                             "citation": None}],
            error=str(exc),
        )


def render_verification_section(result: VerificationResult) -> str:
    """Markdown to append to the article body."""
    if result.is_clean:
        return ""

    icon = "⚠️" if result.verdict == "flagged" else "🛑"
    title_word = "Flagged claims" if result.verdict == "flagged" else "FAILED — likely false content"

    lines = ["", "---", "", f"## {icon} Verification Notes ({result.verdict})", "",
             f"_Automated check by `cortex.deep_research.verifier` (Haiku 4.5). The article above contains the following questionable claims._",
             ""]
    for fc in result.flagged_claims:
        kind = fc.get("type", "?").upper()
        cite = f" {fc.get('citation')}" if fc.get("citation") else ""
        lines.append(f"- **{kind}**{cite}: {fc.get('reason', '?')}")
        claim = (fc.get("claim") or "").strip()
        if claim:
            lines.append(f"  > {claim[:300]}")
    lines.append("")
    return "\n".join(lines)


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)
