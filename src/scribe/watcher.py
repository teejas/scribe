import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# Wait for file size to stabilize before processing
DEBOUNCE_INTERVAL = 2.0  # seconds between size checks
DEBOUNCE_CHECKS = 3  # number of consecutive stable checks required


class _RecordingHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[str], None]):
        self._callback = callback

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        if not event.src_path.endswith(".m4a"):
            return
        logger.info("New recording detected: %s", Path(event.src_path).name)
        self._wait_for_stable(event.src_path)
        self._callback(event.src_path)

    def _wait_for_stable(self, file_path: str) -> None:
        """Wait until the file size stops changing (recording finished)."""
        stable_count = 0
        last_size = -1
        while stable_count < DEBOUNCE_CHECKS:
            try:
                current_size = os.path.getsize(file_path)
            except OSError:
                time.sleep(DEBOUNCE_INTERVAL)
                continue
            if current_size == last_size:
                stable_count += 1
            else:
                stable_count = 0
            last_size = current_size
            time.sleep(DEBOUNCE_INTERVAL)
        logger.debug("File stabilized: %s (%d bytes)", Path(file_path).name, last_size)


def start_watching(watch_dir: str, callback: Callable[[str], None]) -> Observer:
    """Start watching a directory for new .m4a files.

    Returns the Observer so the caller can stop it on shutdown.
    The callback is called with the absolute path of each new stable .m4a file.
    """
    handler = _RecordingHandler(callback)
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=False)
    observer.start()
    logger.info("Watching for new recordings in %s", watch_dir)
    return observer
