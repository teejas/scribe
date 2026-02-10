import logging
import time
from pathlib import Path

from deepgram import DeepgramClient
from deepgram.environment import DeepgramClientEnvironment

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0  # seconds


def _create_client(api_key: str, base_url: str | None = None) -> DeepgramClient:
    # SDK v5 has telemetry opt-out enabled by default (telemetry_opt_out=True)
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["environment"] = DeepgramClientEnvironment(
            base=base_url, production=base_url, agent=base_url,
        )
    return DeepgramClient(**kwargs)


def transcribe(
    api_key: str,
    file_path: str,
    base_url: str | None = None,
    keyterms: list[str] | None = None,
) -> dict:
    """Transcribe an audio file via Deepgram with diarization.

    Returns the raw Deepgram response as a dict.
    Retries on transient failures (429, 5xx) with exponential backoff.
    """
    client = _create_client(api_key, base_url)
    audio_data = Path(file_path).read_bytes()

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            logger.info("Transcribing %s (attempt %d/%d)", Path(file_path).name, attempt + 1, MAX_RETRIES)
            # mip_opt_out only relevant for Deepgram hosted API, not self-hosted
            transcribe_kwargs = dict(
                request=audio_data,
                model="nova-3",
                diarize=True,
                smart_format=True,
                utterances=True,
                punctuate=True,
            )
            if keyterms:
                transcribe_kwargs["keyterm"] = keyterms
            if not base_url:
                transcribe_kwargs["mip_opt_out"] = True
            response = client.listen.v1.media.transcribe_file(**transcribe_kwargs)
            logger.info("Transcription complete for %s", Path(file_path).name)
            return response.model_dump()
        except Exception as e:
            last_error = e
            error_str = str(e)
            is_retryable = "429" in error_str or "500" in error_str or "502" in error_str or "503" in error_str
            if is_retryable and attempt < MAX_RETRIES - 1:
                backoff = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Transient error transcribing %s: %s. Retrying in %.1fs...",
                    Path(file_path).name, e, backoff,
                )
                time.sleep(backoff)
            else:
                break

    raise RuntimeError(f"Transcription failed after {MAX_RETRIES} attempts: {last_error}")
