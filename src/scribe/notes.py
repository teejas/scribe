import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def create_note(title: str, html_body: str, folder: str = "Scribe", account: str = "iCloud") -> bool:
    """Create a note in Apple Notes via osascript.

    Writes HTML to a temp file to avoid AppleScript string injection issues
    from transcript content containing quotes or backslashes.
    """
    _ensure_folder(folder, account)

    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False)
        tmp.write(html_body)
        tmp.close()

        script = f'''
            set htmlFile to POSIX file "{tmp.name}"
            set htmlContent to read htmlFile as «class utf8»
            tell application "Notes"
                tell account "{account}"
                    make new note at folder "{folder}" with properties {{name:"{_escape_applescript(title)}", body:htmlContent}}
                end tell
            end tell
        '''
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.error("osascript failed: %s", result.stderr.strip())
            return False

        logger.info("Created note: %s", title)
        return True

    except subprocess.TimeoutExpired:
        logger.error("osascript timed out creating note: %s", title)
        return False
    except Exception as e:
        logger.error("Failed to create note: %s", e)
        return False
    finally:
        if tmp:
            Path(tmp.name).unlink(missing_ok=True)


def _ensure_folder(folder: str, account: str) -> None:
    """Create the target folder in Apple Notes if it doesn't exist."""
    script = f'''
        tell application "Notes"
            tell account "{account}"
                if not (exists folder "{folder}") then
                    make new folder with properties {{name:"{folder}"}}
                end if
            end tell
        end tell
    '''
    subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True, text=True, timeout=15,
    )


def _escape_applescript(s: str) -> str:
    """Escape a string for safe use inside AppleScript double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify_error(message: str) -> None:
    """Send a macOS notification for processing errors."""
    script = f'display notification "{_escape_applescript(message)}" with title "Scribe"'
    subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
