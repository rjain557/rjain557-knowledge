"""
Build the Technijian-branded "My Cortex — System Specification" PDF.

Reads brand assets from the tech-branding repo, composes a multi-page HTML
document with inline SVG diagrams (no external deps), and renders to PDF via
Playwright (Python 3.11). Brand values follow tech-branding/assets/brand-tokens.json.

    py -3.11 scripts/build_cortex_spec.py
"""

from __future__ import annotations

import base64
import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BRAND = Path(r"D:/VSCode/tech-branding/tech-branding")
LOGOS = BRAND / "assets" / "logos" / "png"
OUT = Path(r"D:/VSCode/rjain557-knowledge/rjain557-knowledge/docs/My Cortex - System Specification.pdf")

# ── Brand tokens (from brand-tokens.json) ───────────────────────────────────
BLUE = "#006DB6"
ORANGE = "#F67D4B"
TEAL = "#1EAAC8"
CHARTREUSE = "#CBDB2D"
GREY = "#59595B"
DARK = "#1A1A2E"
NEAR_BLACK = "#2D2D2D"
OFF_WHITE = "#F8F9FA"
LIGHT = "#E9ECEF"
WHITE = "#FFFFFF"
GREEN = "#28A745"

TODAY = datetime.date(2026, 5, 24).strftime("%B %d, %Y")


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


LOGO_COLOR = f"data:image/png;base64,{b64(LOGOS / 'technijian-logo-full-color-600x125.png')}"
LOGO_DARK = f"data:image/png;base64,{b64(LOGOS / 'technijian-logo-dark-bg-transparent.png')}"
ICON = f"data:image/png;base64,{b64(LOGOS / 'technijian-icon-full-color-256x256.png')}"


# ── SVG diagrams (4px grid, one orange highlight each, ≥12px text) ──────────

def diagram_architecture() -> str:
    return f"""
<figure class="diagram" role="img" aria-labelledby="d1">
  <figcaption id="d1">Figure 1 — Knowledge flow, source to consumer</figcaption>
  <svg viewBox="0 0 960 360" preserveAspectRatio="xMidYMid meet">
    <defs>
      <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
        <path d="M0,0 L10,5 L0,10 Z" fill="{BLUE}"/>
      </marker>
    </defs>
    <!-- Sources -->
    <rect x="16" y="120" width="160" height="120" rx="8" fill="{OFF_WHITE}" stroke="{BLUE}" stroke-width="2"/>
    <text x="96" y="152" text-anchor="middle" font-size="15" font-weight="700" fill="{DARK}">Sources</text>
    <text x="96" y="178" text-anchor="middle" font-size="12" fill="{GREY}">M365 mail</text>
    <text x="96" y="196" text-anchor="middle" font-size="12" fill="{GREY}">RSS · arXiv</text>
    <text x="96" y="214" text-anchor="middle" font-size="12" fill="{GREY}">GitHub · HN</text>
    <line x1="176" y1="180" x2="216" y2="180" stroke="{BLUE}" stroke-width="2" marker-end="url(#ar)"/>
    <!-- Extractors -->
    <rect x="216" y="120" width="168" height="120" rx="8" fill="{OFF_WHITE}" stroke="{BLUE}" stroke-width="2"/>
    <text x="300" y="152" text-anchor="middle" font-size="15" font-weight="700" fill="{DARK}">Extractors</text>
    <text x="300" y="178" text-anchor="middle" font-size="12" fill="{GREY}">article · pdf · video</text>
    <text x="300" y="196" text-anchor="middle" font-size="12" fill="{GREY}">transcription</text>
    <text x="300" y="214" text-anchor="middle" font-size="12" fill="{GREY}">(faster-whisper)</text>
    <line x1="384" y1="180" x2="424" y2="180" stroke="{BLUE}" stroke-width="2" marker-end="url(#ar)"/>
    <!-- Scorer (highlight) -->
    <rect x="424" y="120" width="160" height="120" rx="8" fill="{ORANGE}" stroke="{ORANGE}" stroke-width="2"/>
    <text x="504" y="158" text-anchor="middle" font-size="15" font-weight="700" fill="{DARK}">Relevance</text>
    <text x="504" y="178" text-anchor="middle" font-size="15" font-weight="700" fill="{DARK}">scoring</text>
    <text x="504" y="206" text-anchor="middle" font-size="12" fill="{DARK}">3 AI domains</text>
    <line x1="584" y1="180" x2="624" y2="180" stroke="{BLUE}" stroke-width="2" marker-end="url(#ar)"/>
    <!-- Writer -->
    <rect x="624" y="120" width="160" height="120" rx="8" fill="{OFF_WHITE}" stroke="{BLUE}" stroke-width="2"/>
    <text x="704" y="158" text-anchor="middle" font-size="15" font-weight="700" fill="{DARK}">Vault writer</text>
    <text x="704" y="184" text-anchor="middle" font-size="12" fill="{GREY}">note + DB row</text>
    <text x="704" y="202" text-anchor="middle" font-size="12" fill="{GREY}">one transaction</text>
    <line x1="784" y1="180" x2="824" y2="180" stroke="{BLUE}" stroke-width="2" marker-end="url(#ar)"/>
    <!-- Stores -->
    <rect x="824" y="60" width="120" height="110" rx="8" fill="{OFF_WHITE}" stroke="{TEAL}" stroke-width="2"/>
    <text x="884" y="100" text-anchor="middle" font-size="13" font-weight="700" fill="{DARK}">SQL 2025</text>
    <text x="884" y="122" text-anchor="middle" font-size="12" fill="{GREY}">vectors</text>
    <text x="884" y="140" text-anchor="middle" font-size="12" fill="{GREY}">+ JSON</text>
    <rect x="824" y="190" width="120" height="110" rx="8" fill="{OFF_WHITE}" stroke="{TEAL}" stroke-width="2"/>
    <text x="884" y="230" text-anchor="middle" font-size="13" font-weight="700" fill="{DARK}">Obsidian</text>
    <text x="884" y="252" text-anchor="middle" font-size="12" fill="{GREY}">vault</text>
    <text x="884" y="270" text-anchor="middle" font-size="12" fill="{GREY}">(OneDrive)</text>
    <!-- enrichment row -->
    <rect x="216" y="280" width="368" height="56" rx="8" fill="{WHITE}" stroke="{LIGHT}" stroke-width="2"/>
    <text x="400" y="304" text-anchor="middle" font-size="13" font-weight="700" fill="{BLUE}">Deep research · cross-page synthesis · lint</text>
    <text x="400" y="324" text-anchor="middle" font-size="12" fill="{GREY}">Claude + web search, run after ingestion</text>
    <line x1="504" y1="280" x2="504" y2="240" stroke="{BLUE}" stroke-width="2" marker-end="url(#ar)"/>
  </svg>
</figure>"""


def diagram_model_routing() -> str:
    return f"""
<figure class="diagram" role="img" aria-labelledby="d2">
  <figcaption id="d2">Figure 2 — LLM task routing through complete_task()</figcaption>
  <svg viewBox="0 0 960 380" preserveAspectRatio="xMidYMid meet">
    <defs>
      <marker id="ar2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
        <path d="M0,0 L10,5 L0,10 Z" fill="{BLUE}"/>
      </marker>
    </defs>
    <!-- tasks -->
    <text x="120" y="36" text-anchor="middle" font-size="13" font-weight="700" fill="{GREY}">TASKS</text>
    <g font-size="12" fill="{DARK}">
      <rect x="24" y="56" width="192" height="40" rx="6" fill="{OFF_WHITE}" stroke="{LIGHT}" stroke-width="2"/>
      <text x="120" y="81" text-anchor="middle">relevance scoring</text>
      <rect x="24" y="108" width="192" height="40" rx="6" fill="{OFF_WHITE}" stroke="{LIGHT}" stroke-width="2"/>
      <text x="120" y="133" text-anchor="middle">verifier · contradiction</text>
      <rect x="24" y="160" width="192" height="40" rx="6" fill="{OFF_WHITE}" stroke="{LIGHT}" stroke-width="2"/>
      <text x="120" y="185" text-anchor="middle">cross-page synthesis</text>
      <rect x="24" y="212" width="192" height="40" rx="6" fill="{OFF_WHITE}" stroke="{LIGHT}" stroke-width="2"/>
      <text x="120" y="237" text-anchor="middle">repo review · refresh</text>
      <rect x="24" y="264" width="192" height="40" rx="6" fill="{OFF_WHITE}" stroke="{LIGHT}" stroke-width="2"/>
      <text x="120" y="289" text-anchor="middle">deep research</text>
    </g>
    <!-- router (highlight) -->
    <rect x="372" y="120" width="180" height="120" rx="10" fill="{ORANGE}" stroke="{ORANGE}"/>
    <text x="462" y="166" text-anchor="middle" font-size="16" font-weight="700" fill="{DARK}">complete_task()</text>
    <text x="462" y="190" text-anchor="middle" font-size="12" fill="{DARK}">config/models.yaml</text>
    <text x="462" y="210" text-anchor="middle" font-size="12" fill="{DARK}">route + fallback</text>
    <g stroke="{BLUE}" stroke-width="2">
      <line x1="216" y1="76"  x2="368" y2="150" marker-end="url(#ar2)"/>
      <line x1="216" y1="128" x2="368" y2="165" marker-end="url(#ar2)"/>
      <line x1="216" y1="180" x2="368" y2="180" marker-end="url(#ar2)"/>
      <line x1="216" y1="232" x2="368" y2="200" marker-end="url(#ar2)"/>
      <line x1="216" y1="284" x2="368" y2="216" marker-end="url(#ar2)"/>
    </g>
    <!-- providers -->
    <text x="780" y="36" text-anchor="middle" font-size="13" font-weight="700" fill="{GREY}">PROVIDERS</text>
    <rect x="624" y="56" width="312" height="56" rx="8" fill="{OFF_WHITE}" stroke="{TEAL}" stroke-width="2"/>
    <text x="640" y="80" font-size="13" font-weight="700" fill="{DARK}">Gemini 2.5 Flash-Lite</text>
    <text x="640" y="100" font-size="12" fill="{GREY}">cheap classification · verification</text>
    <rect x="624" y="124" width="312" height="56" rx="8" fill="{OFF_WHITE}" stroke="{BLUE}" stroke-width="2"/>
    <text x="640" y="148" font-size="13" font-weight="700" fill="{DARK}">Claude Sonnet 4.6 / Opus 4.7</text>
    <text x="640" y="168" font-size="12" fill="{GREY}">synthesis · code · web search</text>
    <rect x="624" y="192" width="312" height="56" rx="8" fill="{WHITE}" stroke="{LIGHT}" stroke-width="2" stroke-dasharray="5 4"/>
    <text x="640" y="216" font-size="13" font-weight="700" fill="{DARK}">Claude Haiku 4.5</text>
    <text x="640" y="236" font-size="12" fill="{GREY}">automatic fallback on provider error</text>
    <g stroke="{BLUE}" stroke-width="2">
      <line x1="552" y1="160" x2="620" y2="84"  marker-end="url(#ar2)"/>
      <line x1="552" y1="180" x2="620" y2="152" marker-end="url(#ar2)"/>
      <line x1="552" y1="200" x2="620" y2="220" marker-end="url(#ar2)" stroke-dasharray="5 4"/>
    </g>
    <text x="480" y="300" text-anchor="middle" font-size="12" fill="{GREY}">Keys loaded at runtime from the OneDrive key vault — never stored in the repo.</text>
  </svg>
</figure>"""


def diagram_workflows() -> str:
    rows = [
        ("Mail poll", "every hour", BLUE, 0.10),
        ("GitHub scan", "every hour", BLUE, 0.10),
        ("Wiki lint", "daily 02:00 PT", TEAL, 0.46),
        ("Repo review", "daily 03:00 PT", TEAL, 0.55),
        ("Topic refresh", "weekly Mon 04:00 PT", ORANGE, 0.78),
        ("Model refresh", "weekly Mon 05:00 PT", ORANGE, 0.88),
    ]
    bars = []
    y = 64
    for name, cad, color, frac in rows:
        x = 220 + frac * 560
        bars.append(
            f'<text x="200" y="{y+18}" text-anchor="end" font-size="13" font-weight="700" fill="{DARK}">{name}</text>'
            f'<line x1="220" y1="{y+13}" x2="800" y2="{y+13}" stroke="{LIGHT}" stroke-width="1"/>'
            f'<circle cx="{x:.0f}" cy="{y+13}" r="8" fill="{color}"/>'
            f'<text x="{x+16:.0f}" y="{y+18}" font-size="12" fill="{GREY}">{cad}</text>'
        )
        y += 40
    return f"""
<figure class="diagram" role="img" aria-labelledby="d3">
  <figcaption id="d3">Figure 3 — Automated workflow cadence (n8n → webhook)</figcaption>
  <svg viewBox="0 0 880 320" preserveAspectRatio="xMidYMid meet">
    <text x="220" y="40" font-size="12" font-weight="700" fill="{GREY}">HOURLY</text>
    <text x="500" y="40" font-size="12" font-weight="700" fill="{GREY}">DAILY</text>
    <text x="740" y="40" font-size="12" font-weight="700" fill="{GREY}">WEEKLY</text>
    {''.join(bars)}
  </svg>
</figure>"""


def diagram_memory() -> str:
    layers = [
        ("Layer 1 — Obsidian vault", "Durable human knowledge; topic pages, volatility tiers, git-tagged mutations.", BLUE),
        ("Layer 2 — Auto-memory", "Claude working notes; feedback, preferences, references. Shared across repos via OneDrive.", TEAL),
        ("Layer 3 — GitNexus", "Code-structure index; impact analysis before edits.", GREY),
        ("Layer 4 — Auto Dream", "Consolidation pass; disabled by default.", LIGHT),
    ]
    blocks = []
    y = 56
    for title, desc, color in layers:
        text_fill = DARK if color == LIGHT else WHITE
        blocks.append(
            f'<rect x="40" y="{y}" width="16" height="72" fill="{color}"/>'
            f'<rect x="56" y="{y}" width="824" height="72" fill="{OFF_WHITE}" stroke="{LIGHT}" stroke-width="1"/>'
            f'<rect x="56" y="{y}" width="824" height="72" fill="none" stroke="{LIGHT}" stroke-width="1"/>'
            f'<text x="76" y="{y+30}" font-size="14" font-weight="700" fill="{DARK}">{title}</text>'
            f'<text x="76" y="{y+54}" font-size="12" fill="{GREY}">{desc}</text>'
        )
        y += 84
    return f"""
<figure class="diagram" role="img" aria-labelledby="d4">
  <figcaption id="d4">Figure 4 — Four-layer memory architecture</figcaption>
  <svg viewBox="0 0 920 400" preserveAspectRatio="xMidYMid meet">
    {''.join(blocks)}
  </svg>"""+ "\n</figure>"


# ── Reusable HTML pieces ────────────────────────────────────────────────────

def kpi(value: str, label: str) -> str:
    return f'<div class="kpi"><div class="kpi-num">{value}</div><div class="kpi-lbl">{label}</div></div>'


def section(num: str, title: str, body: str) -> str:
    return f"""
<section class="sec">
  <div class="sec-head"><span class="sec-bar"></span><h2>{num}&nbsp;&nbsp;{title}</h2></div>
  {body}
</section>"""


# ── Document body ───────────────────────────────────────────────────────────

def build_html() -> str:
    routing_rows = [
        ("Relevance scoring", "Gemini 2.5 Flash-Lite", "High-volume 0–1 domain classification; non-reasoning, returns clean JSON, lowest price."),
        ("Deep-research verifier", "Gemini 2.5 Flash-Lite", "Fact-checks research articles; most source-faithful in 2026 testing."),
        ("Cross-page synthesis", "Gemini 2.5 Flash-Lite", "Short relation classification between related notes."),
        ("Lint contradiction", "Gemini 2.5 Flash-Lite", "Semantic comparison of two notes."),
        ("Repo review", "Claude Sonnet 4.6", "Code understanding plus nuanced improvement judgment."),
        ("Topic refresh", "Claude Sonnet 4.6", "Needs the Anthropic server-side web-search tool."),
        ("Auto deep research", "Claude Sonnet 4.6", "Needs web search; cheaper than Opus with negligible quality loss on routine runs."),
        ("Manual deep research", "Claude Opus 4.7", "Operator-initiated, highest quality."),
    ]
    routing_html = "".join(
        f'<tr><td>{t}</td><td><strong>{m}</strong></td><td>{w}</td></tr>' for t, m, w in routing_rows
    )

    workflow_rows = [
        ("Hourly mail poll", "/poll", "every hour"),
        ("Hourly GitHub scan", "/github-scan", "every hour"),
        ("Daily wiki lint", "/lint", "daily 02:00 PT"),
        ("Daily repo review", "/repo-review", "daily 03:00 PT"),
        ("Weekly topic refresh", "/refresh-topics", "Monday 04:00 PT"),
        ("Weekly model refresh", "/model-refresh", "Monday 05:00 PT"),
    ]
    workflow_html = "".join(
        f'<tr><td>{n}</td><td><code>{e}</code></td><td>{c}</td></tr>' for n, e, c in workflow_rows
    )

    toc = [
        ("1", "Executive Summary"),
        ("2", "Platform Architecture"),
        ("3", "Knowledge Ingestion"),
        ("4", "AI Agents &amp; Model Routing"),
        ("5", "Automation &amp; Harnesses"),
        ("6", "Skills &amp; Hooks"),
        ("7", "Memory Architecture"),
        ("8", "Data Platform"),
        ("9", "Configuration &amp; Secrets"),
        ("10", "Consumer Access"),
        ("11", "Operations &amp; Spend Optimization"),
    ]
    toc_html = "".join(
        f'<div class="toc-row"><span class="toc-num">{n}</span><span class="toc-title">{t}</span></div>'
        for n, t in toc
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@700;800&display=swap');
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: 'Open Sans','Segoe UI',Roboto,Arial,sans-serif; color: {GREY}; font-size: 11.5pt; line-height: 1.55; }}
h1,h2,h3 {{ font-family: 'Plus Jakarta Sans','Open Sans','Segoe UI',sans-serif; color: {BLUE}; margin: 0; }}
p {{ margin: 0 0 10px; }}
code {{ font-family: 'JetBrains Mono',Consolas,monospace; font-size: 9.5pt; background: {OFF_WHITE}; padding: 1px 4px; border-radius: 3px; color: {DARK}; }}
strong {{ color: {DARK}; }}
.page-break {{ page-break-before: always; padding: 0 0.6in; }}

/* Cover */
.cover {{ height: 9.1in; display: flex; flex-direction: column; }}
.cover-bar-top {{ height: 10px; background: {BLUE}; }}
.cover-bar-bottom {{ height: 10px; background: {ORANGE}; margin-top: auto; }}
.cover-body {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 0 0.6in; }}
.cover img.logo {{ width: 320px; margin-bottom: 30px; }}
.cover-divider {{ width: 90px; height: 4px; background: {ORANGE}; margin: 22px 0; }}
.cover h1 {{ font-size: 40pt; color: {DARK}; line-height: 1.1; letter-spacing: -0.5px; }}
.cover .sub {{ font-size: 15pt; color: {BLUE}; font-weight: 700; margin-top: 12px; }}
.cover .meta {{ margin-top: 28px; color: {GREY}; font-size: 11pt; }}
.cover .meta b {{ color: {DARK}; }}
.cover .conf {{ margin-top: 26px; font-size: 9pt; letter-spacing: 2px; color: {ORANGE}; font-weight: 700; }}

/* TOC */
.toc h2 {{ font-size: 20pt; margin-bottom: 18px; }}
.toc-row {{ display: flex; align-items: baseline; padding: 9px 0; border-bottom: 1px solid {LIGHT}; }}
.toc-num {{ width: 42px; color: {ORANGE}; font-weight: 800; font-family: 'Plus Jakarta Sans',sans-serif; }}
.toc-title {{ color: {DARK}; font-weight: 600; font-size: 12pt; }}

/* Sections */
.sec {{ margin: 0 0 18px; }}
.sec-head {{ display: flex; align-items: center; gap: 12px; margin: 16px 0 12px; }}
.sec-bar {{ width: 6px; height: 26px; background: {ORANGE}; border-radius: 2px; display: inline-block; }}
.sec h2 {{ font-size: 17pt; }}
h3 {{ font-size: 12.5pt; color: {DARK}; margin: 14px 0 6px; }}

ul {{ margin: 4px 0 12px; padding-left: 20px; }}
li {{ margin: 3px 0; }}

table {{ width: 100%; border-collapse: collapse; margin: 8px 0 14px; font-size: 10pt; }}
th {{ background: {BLUE}; color: {WHITE}; text-align: left; padding: 7px 10px; font-weight: 700; }}
td {{ padding: 6px 10px; border-bottom: 1px solid {LIGHT}; vertical-align: top; }}
tr:nth-child(even) td {{ background: {OFF_WHITE}; }}

.kpi-row {{ display: flex; gap: 12px; margin: 6px 0 16px; }}
.kpi {{ flex: 1; background: {OFF_WHITE}; border: 1px solid {LIGHT}; border-radius: 8px; padding: 14px 8px; text-align: center; }}
.kpi-num {{ font-size: 22pt; font-weight: 800; color: {BLUE}; font-family: 'Plus Jakarta Sans',sans-serif; line-height: 1; }}
.kpi-lbl {{ font-size: 8.5pt; color: {GREY}; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}

.callout {{ border-left: 4px solid {TEAL}; background: {OFF_WHITE}; padding: 10px 14px; border-radius: 0 6px 6px 0; margin: 12px 0; font-size: 10.5pt; }}
.callout.orange {{ border-left-color: {ORANGE}; }}

.diagram {{ margin: 14px 0 18px; padding: 14px; background: {WHITE}; border: 1px solid {LIGHT}; border-radius: 8px; page-break-inside: avoid; }}
.diagram figcaption {{ font-size: 9.5pt; font-weight: 700; color: {BLUE}; margin-bottom: 8px; }}
.diagram svg {{ width: 100%; height: auto; }}

.about {{ background: {DARK}; color: {WHITE}; border-radius: 10px; padding: 22px 26px; margin-top: 18px; }}
.about h3 {{ color: {WHITE}; margin-top: 0; }}
.about a, .about b {{ color: {CHARTREUSE}; }}
.about p {{ color: #C9CBD3; }}
</style></head>
<body>

<!-- COVER -->
<div class="cover">
  <div class="cover-bar-top"></div>
  <div class="cover-body">
    <img class="logo" src="{LOGO_COLOR}" alt="Technijian">
    <div class="cover-divider"></div>
    <h1>My Cortex</h1>
    <div class="sub">AI Knowledge Engine — System Specification</div>
    <div class="meta">
      <p><b>Version</b> 1.0 &nbsp;·&nbsp; <b>Date</b> {TODAY}</p>
      <p><b>Prepared by</b> Technijian Engineering</p>
    </div>
    <div class="conf">CONFIDENTIAL — INTERNAL TECHNICAL DOCUMENT</div>
  </div>
  <div class="cover-bar-bottom"></div>
</div>

<!-- TOC -->
<div class="page-break toc">
  <h2>Contents</h2>
  {toc_html}
  <div class="callout" style="margin-top:18px">This document describes the <strong>as-built</strong> My Cortex platform — its architecture, agents, automation, memory, data platform, and the model-routing strategy that keeps quality high while holding spend low.</div>
</div>

<!-- 1 Executive Summary -->
<div class="page-break">
{section("1", "Executive Summary", f'''
<p>My Cortex is a self-improving knowledge engine that turns Technijian's inbound research stream into a structured, queryable brain. It continuously ingests Microsoft 365 mail and curated web feeds across three AI domains — <strong>agent orchestration</strong>, <strong>SEO agents</strong>, and <strong>tech-support agents</strong> — scores each item for relevance, writes it into an Obsidian vault and SQL Server 2025 in a single transaction, conducts autonomous deep research, and reviews itself on a weekly cadence.</p>
<p>The platform is built and running today. Ingestion, embeddings, deep research, repository review, wiki lint, topic refresh, and model refresh all operate unattended through a webhook service driven by scheduled automation.</p>
<div class="kpi-row">
  {kpi("3", "AI domains tracked")}
  {kpi("18", "database tables")}
  {kpi("6", "automated workflows")}
  {kpi("4", "memory layers")}
</div>
<p>A central design goal is <strong>high-quality analysis at the lowest defensible price</strong>. Every model call routes through one function that selects the right model per task and falls back to a known-good model on any provider error. A weekly job re-checks the model landscape and proposes cheaper or newer options for human approval.</p>
''')}
</div>

<!-- 2 Architecture -->
<div class="page-break">
{section("2", "Platform Architecture", f'''
<p>My Cortex is organized as a pipeline. Sources are normalized by source-specific extractors, scored for relevance, then written once to both the vault and the database. Enrichment steps — deep research, cross-page synthesis, and lint — run after the write and feed their results back into the same stores.</p>
{diagram_architecture()}
<p>All long-running work is fronted by a FastAPI webhook service. Scheduling is handled by n8n, which calls the service on a fixed cadence; a Windows scheduled task keeps the service running across reboots. Human-facing timestamps are recorded in America/Los_Angeles.</p>
''')}
</div>

<!-- 3 Ingestion -->
<div class="page-break">
{section("3", "Knowledge Ingestion", f'''
<h3>Mail</h3>
<p>The mail watcher reads the <code>knowledge@technijian.com</code> shared mailbox through Microsoft Graph using certificate-based application authentication — no device login. Each processed message is moved to a <strong>Processed</strong> subfolder. Inbound links are cleaned of security-banner and signature noise before they become tracked sources.</p>
<h3>Feeds</h3>
<p>An hourly scan reviews GitHub trending across four AI categories, keeps the top results by stars, removes anything already seen, and adds genuinely new repositories. Feed definitions live in a declarative configuration file.</p>
<h3>Extractors</h3>
<p>One module handles each source type: article, PDF, arXiv, YouTube, TikTok, Twitter, Reddit, Hacker News, and GitHub. Audio and video are transcribed locally on the CPU. Every item is then scored 0–1 against the three domains; the scores decide whether the item is kept and whether deep research is triggered.</p>
''')}
</div>

<!-- 4 Agents & Model Routing -->
<div class="page-break">
{section("4", "AI Agents &amp; Model Routing", f'''
<p>Every model call passes through a single routing function. A logical task name is resolved to a provider and model from one configuration file, with an automatic fallback so an unattended run survives a provider outage. Providers are either Anthropic (required for the built-in web-search tool) or any OpenAI-compatible service, reached through one shared request path.</p>
{diagram_model_routing()}
<h3>Task assignments</h3>
<table>
  <thead><tr><th style="width:26%">Task</th><th style="width:28%">Model</th><th>Why</th></tr></thead>
  <tbody>{routing_html}</tbody>
</table>
<div class="callout orange">Short, high-volume, factual tasks run on a fast non-reasoning model for the lowest price. Quality-critical and web-search tasks run on Claude. Every cheap task falls back to Claude Haiku 4.5 if its primary provider fails.</div>
''')}
</div>

<!-- 5 Automation -->
<div class="page-break">
{section("5", "Automation &amp; Harnesses", f'''
<p>The webhook service exposes one endpoint per workflow, protected by a shared secret. n8n triggers each endpoint on schedule and emails the operator if a run does not report success.</p>
{diagram_workflows()}
<table>
  <thead><tr><th>Workflow</th><th>Endpoint</th><th>Cadence</th></tr></thead>
  <tbody>{workflow_html}</tbody>
</table>
<p>Each workflow also has a command-line equivalent for manual runs and testing.</p>
''')}
</div>

<!-- 6 Skills & Hooks -->
<div class="page-break">
{section("6", "Skills &amp; Hooks", f'''
<p>The repository ships eight Claude Code slash-command skills for vault maintenance: review, consolidate, contradictions, graduate, impact, sync, vault-status, and volatility.</p>
<p>Six hooks automate upkeep: vault retrieval on each prompt, topic consolidation when a session ends, a health-dashboard rebuild, code-impact checks before edits, preference extraction, and re-indexing.</p>
''')}
</div>

<!-- 7 Memory -->
<div class="page-break">
{section("7", "Memory Architecture", f'''
<p>Knowledge persists across four layers, each with a clear boundary. Durable facts live in the vault; Claude's working notes live in auto-memory; code structure is indexed separately; a consolidation pass is available but off by default.</p>
{diagram_memory()}
<p>Vault writes pass through a single writer that mirrors each note into the database in the same transaction. The vault propagates between machines through OneDrive, so the pipeline does not commit pipeline-written notes itself.</p>
''')}
</div>

<!-- 8 Data Platform -->
<div class="page-break">
{section("8", "Data Platform", f'''
<p>The store is SQL Server 2025 with native vector and JSON support. A versioned migration sequence defines the schema, tracked in a migrations table. There are eighteen tables and seven stored procedures.</p>
<h3>Key capabilities</h3>
<ul>
  <li>Note and pattern embeddings are 1,536-dimension vectors, generated <strong>server-side</strong> through the database's built-in embedding function — never in Python.</li>
  <li>Vector search is wrapped in a stored procedure because the embedding call cannot be inlined inside a distance expression.</li>
  <li>Text columns are decoded as UTF-16 to preserve multi-byte characters such as the em-dash.</li>
  <li>Connection access is centralized; no module issues raw database calls of its own.</li>
</ul>
<div class="callout">Tables span sources, notes, authors, processed mail and links, feed items, relevance scores, patterns, deep-research runs, synthesis runs, system reviews, proposed and autonomous changes, benchmark snapshots, tracked libraries, and the migration ledger.</div>
''')}
</div>

<!-- 9 Configuration & Secrets -->
<div class="page-break">
{section("9", "Configuration &amp; Secrets", f'''
<p>Behavior is governed by declarative configuration: domain definitions and thresholds, tracked feeds, the reviewed-repository allowlist, refresh themes, pipeline settings, and the central model-routing file.</p>
<h3>Secrets</h3>
<p>No keys, tokens, passwords, or certificates are stored in the repository. Every credential is read at run time from the OneDrive key vault; the environment file holds only non-secret configuration and is excluded from version control. An explicit environment variable can override the vault for testing.</p>
<div class="callout orange">This boundary is enforced in code and documented in the project guidance so every future change keeps secrets in the vault, not the repository.</div>
''')}
</div>

<!-- 10 Consumer Access -->
<div class="page-break">
{section("10", "Consumer Access", f'''
<p>Other Technijian repositories consume the brain through a drop-in prompt that gives any Claude Code project a daily self-improvement loop against the vault. Consumer repositories need read access to the shared vault through OneDrive — not direct database access — which keeps the integration simple and safe.</p>
<p>A companion document records the cross-repository access details and the daily check that surfaces newly added knowledge to each consuming project.</p>
''')}
</div>

<!-- 11 Operations & Cost -->
<div class="page-break">
{section("11", "Operations &amp; Spend Optimization", f'''
<p>A weekly model-refresh job protects both reliability and price. First it pings every routed model to confirm it still answers — catching retired model names, authentication problems, or unfunded accounts before they affect a real run. Then it researches the current market for newer or cheaper models that match or beat each task's quality, and writes a proposal for human review.</p>
<p>Model routing is treated as a controlled change: the job proposes, but a person edits the routing file to accept. This keeps "use the newest, cheaper model" a deliberate decision rather than a silent change to an unattended system.</p>
<div class="callout">Recent outcomes from this discipline: high-volume scoring moved to a fast non-reasoning model; verification moved to the most source-faithful low-price model; and a deprecated model alias was pinned to a stable version before it could disrupt a scheduled run.</div>
<div class="about">
  <h3>About Technijian</h3>
  <p>Founded in 2000, Technijian delivers managed IT services, cybersecurity, cloud solutions, compliance support, and AI-driven development for small and mid-sized businesses. With offices in Irvine, California and India, our dedicated pod model provides 24/7 support from a team that knows your infrastructure inside and out.</p>
  <p><b>Technijian</b> &nbsp;·&nbsp; 18 Technology Dr., Ste 141, Irvine, CA 92618 &nbsp;·&nbsp; 949.379.8499 &nbsp;·&nbsp; technijian.com</p>
</div>
''')}
</div>

</body></html>"""


def header_template() -> str:
    return f"""<div style="width:100%; font-size:8px; padding:0 0.6in; font-family:'Open Sans',sans-serif; color:{GREY};">
      <div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid {LIGHT}; padding-bottom:4px;">
        <img src="{LOGO_COLOR}" style="height:18px;">
        <span style="color:{GREY};">My Cortex — System Specification</span>
      </div>
    </div>"""


def footer_template() -> str:
    return f"""<div style="width:100%; font-size:7.5px; padding:0 0.6in; font-family:'Open Sans',sans-serif; color:{GREY};">
      <div style="display:flex; justify-content:space-between; border-top:1px solid {LIGHT}; padding-top:4px;">
        <span>Technijian &nbsp;·&nbsp; 18 Technology Dr., Ste 141, Irvine, CA 92618 &nbsp;·&nbsp; technijian.com</span>
        <span>CONFIDENTIAL &nbsp;·&nbsp; Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
      </div>
    </div>"""


def main() -> None:
    html = build_html()
    debug_html = OUT.with_suffix(".html")
    debug_html.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(OUT),
            format="Letter",
            print_background=True,
            display_header_footer=True,
            header_template=header_template(),
            footer_template=footer_template(),
            margin={"top": "0.9in", "bottom": "0.7in", "left": "0in", "right": "0in"},
        )
        browser.close()
    print(f"PDF written: {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
