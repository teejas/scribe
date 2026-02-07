from __future__ import annotations

from scribe.db import RecordingMetadata
from scribe.summarizer import Summary


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    hrs, remainder = divmod(total, 3600)
    mins, secs = divmod(remainder, 60)
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _get_utterances(response: dict) -> list[dict] | None:
    """Extract utterances from Deepgram response."""
    results = response.get("results", {})
    return results.get("utterances")


def _get_transcript_text(response: dict) -> str:
    """Extract plain transcript text as fallback when utterances aren't available."""
    channels = response.get("results", {}).get("channels", [])
    if channels:
        alternatives = channels[0].get("alternatives", [])
        if alternatives:
            return alternatives[0].get("transcript", "")
    return ""


def _count_speakers(utterances: list[dict]) -> int:
    speakers = {u.get("speaker", 0) for u in utterances}
    return len(speakers)


def format_transcript(
    response: dict,
    metadata: RecordingMetadata,
    title: str | None = None,
    summary: Summary | None = None,
) -> str:
    """Convert a Deepgram response into HTML for Apple Notes."""
    display_title = title or metadata.title
    date_str = metadata.date.strftime("%b %-d, %Y")
    duration_str = _format_duration(metadata.duration_seconds)
    utterances = _get_utterances(response)

    if utterances and _count_speakers(utterances) > 1:
        return _format_multi_speaker(utterances, display_title, date_str, duration_str, summary)
    elif utterances:
        return _format_single_speaker(utterances, display_title, date_str, duration_str, summary)
    else:
        text = _get_transcript_text(response)
        return _format_plain_text(text, display_title, date_str, duration_str, summary)


def _summary_html(summary: Summary | None) -> list[str]:
    if not summary:
        return []
    lines = [f"<p>{summary.summary}</p>"]
    for heading, items in [
        ("Key Points", summary.key_points),
        ("Action Items", summary.action_items),
        ("Decisions", summary.decisions),
        ("Open Questions", summary.open_questions),
    ]:
        if items:
            lines.append(f"<h2>{heading}</h2>")
            lines.append("<ul>")
            for item in items:
                lines.append(f"<li>{item}</li>")
            lines.append("</ul>")
    lines.append("<hr>")
    return lines


def _format_multi_speaker(
    utterances: list[dict], title: str, date_str: str, duration_str: str,
    summary: Summary | None = None,
) -> str:
    num_speakers = _count_speakers(utterances)
    lines = [
        f"<h1>{title} - {date_str}</h1>",
        f"<p><i>Duration: {duration_str} | Speakers: {num_speakers}</i></p>",
        *_summary_html(summary),
        "<hr>",
    ]
    for u in utterances:
        speaker = u.get("speaker", 0) + 1  # 0-indexed → 1-indexed
        text = u.get("transcript", "").strip()
        if text:
            lines.append(f"<p><b>Speaker {speaker}:</b> {text}</p>")
    return "\n".join(lines)


def _format_single_speaker(
    utterances: list[dict], title: str, date_str: str, duration_str: str,
    summary: Summary | None = None,
) -> str:
    lines = [
        f"<h1>{title} - {date_str}</h1>",
        f"<p><i>Duration: {duration_str}</i></p>",
        *_summary_html(summary),
        "<hr>",
    ]
    for u in utterances:
        text = u.get("transcript", "").strip()
        if text:
            lines.append(f"<p>{text}</p>")
    return "\n".join(lines)


def _format_plain_text(
    text: str, title: str, date_str: str, duration_str: str,
    summary: Summary | None = None,
) -> str:
    lines = [
        f"<h1>{title} - {date_str}</h1>",
        f"<p><i>Duration: {duration_str}</i></p>",
        *_summary_html(summary),
        "<hr>",
    ]
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if paragraph:
            lines.append(f"<p>{paragraph}</p>")
    return "\n".join(lines)


def format_transcript_markdown(
    response: dict,
    metadata: RecordingMetadata,
    title: str | None = None,
    summary: Summary | None = None,
) -> str:
    """Convert a Deepgram response into Markdown for file output."""
    display_title = title or metadata.title
    date_str = metadata.date.strftime("%b %-d, %Y")
    duration_str = _format_duration(metadata.duration_seconds)
    utterances = _get_utterances(response)

    if utterances and _count_speakers(utterances) > 1:
        return _format_multi_speaker_md(utterances, display_title, date_str, duration_str, summary)
    elif utterances:
        return _format_single_speaker_md(utterances, display_title, date_str, duration_str, summary)
    else:
        text = _get_transcript_text(response)
        return _format_plain_text_md(text, display_title, date_str, duration_str, summary)


def _summary_md(summary: Summary | None) -> list[str]:
    if not summary:
        return []
    lines = ["", summary.summary]
    for heading, items in [
        ("Key Points", summary.key_points),
        ("Action Items", summary.action_items),
        ("Decisions", summary.decisions),
        ("Open Questions", summary.open_questions),
    ]:
        if items:
            lines.append("")
            lines.append(f"## {heading}")
            lines.append("")
            for item in items:
                lines.append(f"- {item}")
    lines.append("")
    lines.append("---")
    return lines


def _format_multi_speaker_md(
    utterances: list[dict], title: str, date_str: str, duration_str: str,
    summary: Summary | None = None,
) -> str:
    num_speakers = _count_speakers(utterances)
    lines = [
        f"# {title} - {date_str}",
        "",
        f"*Duration: {duration_str} | Speakers: {num_speakers}*",
        *_summary_md(summary),
        "",
        "---",
        "",
    ]
    for u in utterances:
        speaker = u.get("speaker", 0) + 1
        text = u.get("transcript", "").strip()
        if text:
            lines.append(f"**Speaker {speaker}:** {text}")
            lines.append("")
    return "\n".join(lines)


def _format_single_speaker_md(
    utterances: list[dict], title: str, date_str: str, duration_str: str,
    summary: Summary | None = None,
) -> str:
    lines = [
        f"# {title} - {date_str}",
        "",
        f"*Duration: {duration_str}*",
        *_summary_md(summary),
        "",
        "---",
        "",
    ]
    for u in utterances:
        text = u.get("transcript", "").strip()
        if text:
            lines.append(text)
            lines.append("")
    return "\n".join(lines)


def _format_plain_text_md(
    text: str, title: str, date_str: str, duration_str: str,
    summary: Summary | None = None,
) -> str:
    lines = [
        f"# {title} - {date_str}",
        "",
        f"*Duration: {duration_str}*",
        *_summary_md(summary),
        "",
        "---",
        "",
    ]
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if paragraph:
            lines.append(paragraph)
            lines.append("")
    return "\n".join(lines)
