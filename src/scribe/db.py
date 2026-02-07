import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Apple epoch is Jan 1, 2001 00:00:00 UTC; offset from Unix epoch
APPLE_EPOCH_OFFSET = 978307200

# Sequoia / Sonoma path. Older macOS versions use different paths — see PLAN.md.
VOICE_MEMOS_DIR = Path.home() / "Library" / "Group Containers" / "group.com.apple.VoiceMemos.shared" / "Recordings"
CLOUD_RECORDINGS_DB = VOICE_MEMOS_DIR / "CloudRecordings.db"


@dataclass
class RecordingMetadata:
    title: str
    date: datetime
    duration_seconds: float


def _apple_timestamp_to_datetime(apple_ts: float) -> datetime:
    unix_ts = apple_ts + APPLE_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc)


def _format_fallback_title(file_path: str) -> str:
    """Generate a title from filename + modification date when DB lookup fails."""
    p = Path(file_path)
    mod_time = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return f"Voice Memo - {mod_time.strftime('%b %-d, %Y %-I:%M %p')}"


def get_recording_metadata(
    file_path: str,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> RecordingMetadata:
    """Look up recording metadata from Voice Memos DB.

    Retries because the watcher may detect the file before Voice Memos
    commits the DB row. Falls back to filename-based metadata if no match.
    """
    relative_name = Path(file_path).name

    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(
                f"file:{CLOUD_RECORDINGS_DB}?mode=ro", uri=True
            )
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT ZCUSTOMLABEL, ZENCRYPTEDTITLE, ZDATE, ZDURATION "
                "FROM ZCLOUDRECORDING WHERE ZPATH LIKE ?",
                (f"%{relative_name}",),
            ).fetchone()
            conn.close()

            if row is not None:
                title = row["ZCUSTOMLABEL"] or row["ZENCRYPTEDTITLE"] or _format_fallback_title(file_path)
                date = _apple_timestamp_to_datetime(row["ZDATE"])
                duration = row["ZDURATION"] or 0.0
                return RecordingMetadata(title=title, date=date, duration_seconds=duration)

        except sqlite3.OperationalError as e:
            logger.warning("DB read attempt %d failed: %s", attempt + 1, e)

        if attempt < max_retries - 1:
            logger.debug("No DB match for %s, retrying in %.1fs...", relative_name, retry_delay)
            time.sleep(retry_delay)

    # Fallback: no DB match after retries
    logger.info("No DB match for %s, using fallback title", relative_name)
    p = Path(file_path)
    mod_time = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return RecordingMetadata(
        title=_format_fallback_title(file_path),
        date=mod_time,
        duration_seconds=0.0,
    )
