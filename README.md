# Scribe

A macOS daemon that watches for new Apple Voice Memos recordings, transcribes them with speaker diarization via Deepgram, and saves formatted notes to Apple Notes.

Optionally generates a descriptive title and summary using GPT-4o-mini, replacing the generic Voice Memos title.

## How it works

```
Voice Memos (.m4a) → Deepgram transcription → [Optional: GPT-4o-mini summary] → Apple Notes + Markdown
```

1. Watches the Voice Memos directory for new `.m4a` files
2. Reads recording metadata (title, date, duration) from the Voice Memos SQLite database
3. Sends audio to Deepgram for transcription with speaker diarization
4. Optionally generates a title and summary via OpenAI
5. Formats the transcript as HTML (for Apple Notes) and Markdown (for file output)
6. Creates a note in Apple Notes and saves a `.md` file to disk
7. Tracks processed files in a local SQLite ledger to avoid reprocessing

Multi-speaker recordings get speaker labels automatically. Single-speaker recordings are formatted as plain prose.

## Prerequisites

- macOS Sequoia or Sonoma
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A [Deepgram](https://deepgram.com) API key (free $200 credit on signup)
- **Full Disk Access** granted to your terminal (System Settings > Privacy & Security > Full Disk Access)
- First run will prompt for Automation permission to control Apple Notes

## Setup

```sh
git clone <repo-url> && cd scribe
cp .env.example .env
# Edit .env with your API keys
uv sync
```

### Configuration (.env)

```sh
DEEPGRAM_API_KEY=your_key_here       # Required
OPENAI_API_KEY=your_key_here         # Optional — enables LLM title/summary generation
SCRIBE_NOTES_FOLDER=Scribe           # Apple Notes folder name (created if missing)
SCRIBE_NOTES_ACCOUNT=iCloud          # Apple Notes account
SCRIBE_OUTPUT_DIR=~/path/to/markdown  # Optional — saves .md files here
DEEPGRAM_BASE_URL=                   # Optional — for self-hosted Deepgram
```

If `OPENAI_API_KEY` is not set, summarization is skipped and the original Voice Memos title is used.

## Running

### Watch mode (foreground)

Watches for new recordings and processes them as they appear:

```sh
uv run scribe
```

### Watch mode (background)

```sh
uv run scribe &
```

### Backfill existing recordings

Process all existing Voice Memos that haven't been transcribed yet:

```sh
uv run scribe --backfill
```

### Retry failed recordings

```sh
uv run scribe --retry-failed
```

### Running as a launchd daemon

For auto-start on login with automatic restart on crash, use the included plist template:

1. Edit `com.scribe.watcher.plist` — replace the `UV_PATH`, `PROJECT_DIR`, and `HOME_DIR` placeholders with your actual paths
2. Copy and load:

```sh
cp com.scribe.watcher.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.scribe.watcher.plist
```

To stop:

```sh
launchctl unload ~/Library/LaunchAgents/com.scribe.watcher.plist
```

## Logs

All logs are written to `~/.scribe/scribe.log` and stdout. Processing failures also trigger a macOS notification.

## Tests

```sh
uv run pytest -v
```

## Cost

- **Deepgram**: ~$0.0077/min. A 30-min recording costs ~$0.23.
- **OpenAI** (GPT-4o-mini): ~$0.001 per recording. Negligible.
