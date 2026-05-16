"""
Continuous mail poller. Polls the Brain folder on a configurable interval.

    uv run python scripts/poll.py
    uv run python scripts/poll.py --once          # single pass then exit
    uv run python scripts/poll.py --interval 60   # poll every 60 s
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Force UTF-8 on stdout (Windows defaults to CP1252 which dies on emoji)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import argparse
import structlog
structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

from cortex.config import get_settings, get_yaml_config
from cortex.mail.watcher import MailWatcher
from cortex.mail.link_extractor import extract_links
from cortex.extractors.article import extract as extract_article
from cortex.relevance.scorer import score as score_relevance, is_relevant
from cortex.db import repositories as repo
from cortex.vault.writer import write_inbox_note

log = structlog.get_logger(__name__)


def process_message(
    watcher: MailWatcher,
    msg: dict,
    on_processed: str,
    label_name: str,
    processed_folder_id: str | None,
) -> int:
    """Process one email message. Returns count of notes written."""
    message_id = msg["message_id"]

    if repo.is_email_processed(message_id):
        # DB knows about it but it's still unread/in-inbox -> finish the mailbox-side cleanup
        log.info("poll.email.skip_already_processed", subject=msg["subject"][:80])
        try:
            watcher.mark_read(message_id)
            if on_processed == "move" and processed_folder_id:
                watcher.move_message(message_id, processed_folder_id)
        except Exception as exc:
            log.warning("poll.email.cleanup_failed", error=str(exc))
        return 0

    links = extract_links(msg["body_html"])
    log.info("poll.email.links", subject=msg["subject"], count=len(links))

    # Record the email up front so links can FK to it
    email_id = repo.record_email(
        message_id=message_id,
        sender=msg["sender"],
        subject=msg["subject"],
        received_at=msg["received_at"],
        body_preview=(msg.get("body_html") or "")[:1000],
    )

    notes_written = 0
    for link in links:
        if repo.is_link_processed(link.url):
            log.debug("poll.link.skip_duplicate", url=link.url)
            continue

        content = None
        if link.link_type == "article":
            content = extract_article(link.url)

        if not content:
            repo.record_link(
                original_url=link.url, source_type=link.link_type, email_id=email_id
            )
            log.warning("poll.link.extract_failed", url=link.url, type=link.link_type)
            continue

        link_id = repo.record_link(
            original_url=link.url, source_type=content.source_type, email_id=email_id
        )
        scores = score_relevance(content.title, content.body_markdown)
        source_id = repo.upsert_source(
            source_url=link.url,
            source_type=content.source_type,
            title=content.title,
            author=content.author,
            published_at=content.published_at,
            body_markdown=content.body_markdown,
            metadata=content.metadata,
            link_id=link_id,
            canonical_url=content.canonical_url,
            extractor=content.metadata.get("extractor"),
        )
        repo.record_relevance_scores(source_id, scores)
        vault_path, note_id = write_inbox_note(content, source_id, scores)
        notes_written += 1
        log.info(
            "poll.link.done",
            url=link.url,
            note_id=note_id,
            relevant=is_relevant(scores),
        )

    # Mark processed in mailbox
    watcher.mark_read(message_id)
    if on_processed == "label":
        watcher.apply_label(message_id, label_name)
    elif on_processed == "move" and processed_folder_id:
        watcher.move_message(message_id, processed_folder_id)
        log.info("poll.email.moved_to_processed", subject=msg["subject"][:80])

    return notes_written


def run_poll(watcher: MailWatcher, cfg: dict, processed_folder_id: str | None) -> int:
    mail_cfg = cfg.get("mail", {})
    on_processed = mail_cfg.get("on_processed", "label")
    label_name = mail_cfg.get("label_name", "Processed")
    max_per_poll = mail_cfg.get("max_per_poll", 20)

    total_notes = 0
    for msg in watcher.poll(max_messages=max_per_poll):
        total_notes += process_message(
            watcher, msg, on_processed, label_name, processed_folder_id
        )

    log.info("poll.cycle.done", notes_written=total_notes)
    return total_notes


def main() -> None:
    parser = argparse.ArgumentParser(description="Cortex mail poller")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle then exit")
    parser.add_argument("--interval", type=int, default=0, help="Override poll interval seconds")
    args = parser.parse_args()

    cfg = get_yaml_config()
    mail_cfg = cfg.get("mail", {})
    interval = args.interval or mail_cfg.get("poll_interval_seconds", 300)

    watcher = MailWatcher()

    # If on_processed == 'move', resolve (or create) the destination folder once
    processed_folder_id = None
    if mail_cfg.get("on_processed") == "move":
        parent = mail_cfg.get("source_folder", get_settings().m365_folder)
        processed_name = mail_cfg.get("processed_folder", "Processed")
        processed_folder_id = watcher.ensure_child_folder(parent, processed_name)
        log.info("poll.processed_folder_ready", parent=parent, child=processed_name)

    log.info("poll.start", interval_seconds=interval, once=args.once)

    run_poll(watcher, cfg, processed_folder_id)

    if args.once:
        return

    while True:
        log.info("poll.sleeping", seconds=interval)
        time.sleep(interval)
        run_poll(watcher, cfg, processed_folder_id)


if __name__ == "__main__":
    main()
