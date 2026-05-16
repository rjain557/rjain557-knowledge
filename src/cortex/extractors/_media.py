"""Shared audio download + whisper transcription helpers."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

_WHISPER_MODEL = None


def download_audio(url: str, max_duration: int = 7200) -> Optional[Path]:
    """Download audio-only to a temp wav. Returns path or None on failure."""
    try:
        from yt_dlp import YoutubeDL
        tmpdir = Path(tempfile.mkdtemp(prefix="cortex_media_"))
        out_template = str(tmpdir / "audio.%(ext)s")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "quiet": True, "no_warnings": True,
            "noplaylist": True,
            "match_filter": _duration_filter(max_duration),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",
            }],
        }
        with YoutubeDL(opts) as ydl:
            ydl.download([url])

        files = list(tmpdir.glob("audio.*"))
        if not files:
            log.warning("media.download.no_output", url=url)
            return None
        return files[0]
    except Exception as exc:
        log.warning("media.download.failed", url=url, error=str(exc)[:200])
        return None


def transcribe(audio_path: Path, model_size: str = "base.en") -> Optional[str]:
    """Transcribe an audio file via faster-whisper. CPU int8."""
    try:
        global _WHISPER_MODEL
        if _WHISPER_MODEL is None:
            from faster_whisper import WhisperModel
            log.info("whisper.loading_model", model=model_size)
            _WHISPER_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")

        segments, info = _WHISPER_MODEL.transcribe(str(audio_path), beam_size=1)
        text = " ".join(seg.text.strip() for seg in segments)
        log.info("whisper.transcribed",
                 audio=audio_path.name, language=info.language,
                 duration=round(info.duration, 1), chars=len(text))
        # Clean up
        shutil.rmtree(audio_path.parent, ignore_errors=True)
        return text.strip()
    except Exception as exc:
        log.warning("whisper.failed", error=str(exc)[:200])
        shutil.rmtree(audio_path.parent, ignore_errors=True)
        return None


def _duration_filter(max_seconds: int):
    def f(info):
        d = info.get("duration") or 0
        if d > max_seconds:
            return f"video too long ({d}s > {max_seconds}s)"
        return None
    return f
