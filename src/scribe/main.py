import argparse
import logging
import os
import signal
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from scribe.db import VOICE_MEMOS_DIR, get_recording_metadata
from scribe.formatter import format_transcript, format_transcript_markdown
from scribe.ledger import Ledger
from scribe.notes import create_note, notify_error
from scribe.summarizer import summarize
from scribe.transcriber import transcribe
from scribe.watcher import start_watching

logger = logging.getLogger("scribe")

LOG_DIR = Path.home() / ".scribe"
LOG_FILE = LOG_DIR / "scribe.log"


@dataclass
class Config:
    api_key: str
    notes_folder: str
    notes_account: str
    output_dir: Path | None
    deepgram_base_url: str | None
    openai_api_key: str | None


def _setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root = logging.getLogger("scribe")
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def _save_markdown(markdown: str, title: str, date_str: str, output_dir: Path) -> None:
    """Save markdown transcript to the output directory."""
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip()
    filename = f"{date_str} - {safe_title}.md"
    out_path = output_dir / filename
    out_path.write_text(markdown, encoding="utf-8")
    logger.info("Saved markdown: %s", out_path)


def _process_file(file_path: str, ledger: Ledger, cfg: Config) -> None:
    """Run the full pipeline for a single recording."""
    if ledger.is_processed(file_path):
        logger.debug("Already processed, skipping: %s", Path(file_path).name)
        return

    if not ledger.is_known(file_path):
        ledger.mark_pending(file_path)

    ledger.mark_processing(file_path)
    name = Path(file_path).name

    try:
        # 1. Get metadata
        metadata = get_recording_metadata(file_path)
        logger.info("Processing: %s (%s)", metadata.title, name)

        # 2. Transcribe
        response = transcribe(cfg.api_key, file_path, base_url=cfg.deepgram_base_url)

        # 3. Summarize (optional — requires OPENAI_API_KEY)
        generated_title = None
        generated_summary = None
        if cfg.openai_api_key:
            try:
                from scribe.formatter import _get_utterances, _count_speakers, _get_transcript_text

                utterances = _get_utterances(response)
                if utterances:
                    transcript_text = " ".join(
                        u.get("transcript", "").strip() for u in utterances if u.get("transcript", "").strip()
                    )
                    speaker_count = _count_speakers(utterances)
                else:
                    transcript_text = _get_transcript_text(response)
                    speaker_count = 1

                if transcript_text:
                    result = summarize(
                        transcript_text, metadata.duration_seconds, speaker_count, cfg.openai_api_key
                    )
                    generated_title = result.title
                    generated_summary = result.summary
                    logger.info("Generated title: %s", generated_title)
            except Exception as e:
                logger.warning("Summarization failed, using original title: %s", e)

        # 4. Format
        note_title = generated_title or metadata.title
        html = format_transcript(response, metadata, title=generated_title, summary=generated_summary)

        # 5. Save to Apple Notes
        success = create_note(note_title, html, folder=cfg.notes_folder, account=cfg.notes_account)
        if not success:
            raise RuntimeError("Apple Notes creation failed")

        # 6. Save markdown to output directory
        if cfg.output_dir:
            markdown = format_transcript_markdown(
                response, metadata, title=generated_title, summary=generated_summary
            )
            date_str = metadata.date.strftime("%Y-%m-%d")
            _save_markdown(markdown, note_title, date_str, cfg.output_dir)

        # 7. Done
        ledger.mark_done(file_path)
        logger.info("Done: %s", note_title)

    except Exception as e:
        error_msg = str(e)
        ledger.mark_failed(file_path, error_msg)
        logger.error("Failed to process %s: %s", name, error_msg)
        notify_error(f"Failed: {name}")


def _backfill(ledger: Ledger, cfg: Config) -> None:
    """Process all existing Voice Memos recordings that haven't been processed."""
    watch_dir = str(VOICE_MEMOS_DIR)
    m4a_files = sorted(Path(watch_dir).glob("*.m4a"))
    new_count = 0
    for f in m4a_files:
        fp = str(f)
        if not ledger.is_known(fp):
            ledger.mark_pending(fp)
            new_count += 1
    logger.info("Backfill: found %d new recordings out of %d total", new_count, len(m4a_files))

    for fp in ledger.get_pending():
        _process_file(fp, ledger, cfg)


def _retry_failed(ledger: Ledger, cfg: Config) -> None:
    """Re-process all previously failed recordings."""
    count = ledger.reset_failed()
    logger.info("Retrying %d failed recordings", count)
    for fp in ledger.get_pending():
        _process_file(fp, ledger, cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scribe: Voice Memos → Apple Notes")
    parser.add_argument("--backfill", action="store_true", help="Process all existing recordings")
    parser.add_argument("--retry-failed", action="store_true", help="Retry previously failed recordings")
    args = parser.parse_args()

    load_dotenv()
    _setup_logging()

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("DEEPGRAM_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    output_dir = None
    output_dir_str = os.getenv("SCRIBE_OUTPUT_DIR")
    if output_dir_str:
        output_dir = Path(output_dir_str).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Markdown output directory: %s", output_dir)

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.info("OPENAI_API_KEY not set — summarization disabled.")

    cfg = Config(
        api_key=api_key,
        notes_folder=os.getenv("SCRIBE_NOTES_FOLDER", "Scribe"),
        notes_account=os.getenv("SCRIBE_NOTES_ACCOUNT", "iCloud"),
        output_dir=output_dir,
        deepgram_base_url=os.getenv("DEEPGRAM_BASE_URL"),
        openai_api_key=openai_api_key,
    )

    if cfg.deepgram_base_url:
        logger.info("Using self-hosted Deepgram at %s", cfg.deepgram_base_url)

    watch_dir = str(VOICE_MEMOS_DIR)
    if not Path(watch_dir).exists():
        logger.error("Voice Memos directory not found: %s", watch_dir)
        logger.error("Ensure Voice Memos has been opened at least once and Full Disk Access is granted.")
        sys.exit(1)

    ledger = Ledger()

    if args.backfill:
        _backfill(ledger, cfg)
        return

    if args.retry_failed:
        _retry_failed(ledger, cfg)
        return

    # Watch mode: run until interrupted
    def on_new_recording(file_path: str) -> None:
        _process_file(file_path, ledger, cfg)

    observer = start_watching(watch_dir, on_new_recording)

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down...")
        observer.stop()
        observer.join()
        ledger.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Scribe is running. Press Ctrl+C to stop.")
    observer.join()
