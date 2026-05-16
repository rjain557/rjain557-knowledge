"""YouTube extractor: youtube-transcript-api primary, yt-dlp+whisper fallback."""

from __future__ import annotations

import re
import structlog

from cortex.extractors.base import ExtractedContent
from cortex.extractors._media import download_audio, transcribe

log = structlog.get_logger(__name__)


def extract(url: str) -> ExtractedContent | None:
    log.info("extractor.youtube.start", url=url)
    video_id = _extract_video_id(url)
    if not video_id:
        log.warning("extractor.youtube.no_video_id", url=url)
        return None

    # Get metadata via yt-dlp (cheap)
    meta = _get_metadata(url)
    title = (meta or {}).get("title") or f"YouTube {video_id}"
    author = (meta or {}).get("uploader") or (meta or {}).get("channel")

    # Try fast path: caption API
    transcript = _fetch_transcript(video_id)

    # Fallback: download audio + whisper
    if not transcript or len(transcript) < 100:
        log.info("extractor.youtube.fallback_whisper", video_id=video_id)
        audio = download_audio(url)
        if audio:
            transcript = transcribe(audio) or ""

    body_parts = [f"# {title}", ""]
    if author:
        body_parts.append(f"**Channel:** {author}")
    if meta and meta.get("description"):
        body_parts += ["", "## Description", meta["description"][:2000]]
    if transcript:
        body_parts += ["", "## Transcript", transcript]

    body = "\n".join(body_parts).strip()
    if len(body) < 50:
        return None

    return ExtractedContent(
        source_url=url,
        source_type="youtube",
        canonical_url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        body_markdown=body,
        author=author,
        metadata={"extractor": "youtube", "video_id": video_id,
                  "duration": (meta or {}).get("duration")},
        transcript=transcript,
    )


# ── Internals ─────────────────────────────────────────────────────────────────

def _extract_video_id(url: str) -> str | None:
    for pat in (r"v=([A-Za-z0-9_-]{11})",
                r"youtu\.be/([A-Za-z0-9_-]{11})",
                r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _fetch_transcript(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(seg["text"] for seg in transcript)
    except Exception as exc:
        log.debug("extractor.youtube.no_captions", video_id=video_id, error=str(exc))
        return None


def _get_metadata(url: str) -> dict | None:
    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:
        log.debug("extractor.youtube.meta_failed", error=str(exc))
        return None
