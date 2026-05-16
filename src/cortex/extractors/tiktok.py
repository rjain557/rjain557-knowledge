"""TikTok extractor: yt-dlp + faster-whisper. Caption + transcript become the body."""

from __future__ import annotations

import structlog

from cortex.extractors.base import ExtractedContent
from cortex.extractors._media import download_audio, transcribe

log = structlog.get_logger(__name__)


def extract(url: str) -> ExtractedContent | None:
    log.info("extractor.tiktok.start", url=url)

    meta = _get_metadata(url)
    if not meta:
        log.warning("extractor.tiktok.meta_failed", url=url)
        return None

    title = meta.get("title") or meta.get("description") or f"TikTok {meta.get('id','')}"
    author = meta.get("uploader") or meta.get("creator")
    caption = meta.get("description") or ""
    duration = meta.get("duration")
    canonical = meta.get("webpage_url") or url

    # Download audio + transcribe
    transcript = ""
    audio = download_audio(url)
    if audio:
        transcript = transcribe(audio) or ""

    body_parts = [f"# {title[:200]}", ""]
    if author:
        body_parts.append(f"**Creator:** @{author}")
    if duration:
        body_parts.append(f"**Duration:** {duration}s")
    if caption:
        body_parts += ["", "## Caption", caption]
    if transcript:
        body_parts += ["", "## Transcript", transcript]

    body = "\n".join(body_parts).strip()
    if len(body) < 30:
        return None

    return ExtractedContent(
        source_url=url,
        source_type="tiktok",
        canonical_url=canonical,
        title=title[:200],
        body_markdown=body,
        author=author,
        transcript=transcript,
        metadata={"extractor": "tiktok+yt-dlp+whisper",
                  "tiktok_id": meta.get("id"), "duration": duration,
                  "view_count": meta.get("view_count")},
    )


def _get_metadata(url: str) -> dict | None:
    try:
        from yt_dlp import YoutubeDL
        opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                "extractor_args": {"tiktok": {"webpage_url_basename": "video"}}}
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        log.warning("extractor.tiktok.meta_error", url=url, error=str(exc)[:200])
        return None
