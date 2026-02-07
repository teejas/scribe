from datetime import datetime, timezone

from scribe.db import RecordingMetadata
from scribe.formatter import format_transcript, format_transcript_markdown
from scribe.summarizer import Summary


def _make_metadata(title="Test Recording", duration=125.0):
    return RecordingMetadata(
        title=title,
        date=datetime(2025, 2, 5, 14, 30, 0, tzinfo=timezone.utc),
        duration_seconds=duration,
    )


def _make_response(utterances, num_channels=1):
    """Build a minimal Deepgram-like response dict."""
    return {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": " ".join(
                                u["transcript"] for u in utterances
                            )
                        }
                    ]
                }
            ],
            "utterances": utterances,
        }
    }


def test_single_speaker_format():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello this is a test."},
        {"speaker": 0, "transcript": "Another sentence here."},
    ])
    html = format_transcript(response, _make_metadata())
    assert "<h1>Test Recording - Feb 5, 2025</h1>" in html
    assert "Duration: 2:05" in html
    assert "Speaker" not in html  # single speaker, no labels
    assert "Hello this is a test." in html
    assert "Another sentence here." in html


def test_multi_speaker_format():
    response = _make_response([
        {"speaker": 0, "transcript": "Good morning."},
        {"speaker": 1, "transcript": "Hi there."},
        {"speaker": 0, "transcript": "Shall we begin?"},
    ])
    html = format_transcript(response, _make_metadata())
    assert "Speakers: 2" in html
    assert "<b>Speaker 1:</b> Good morning." in html
    assert "<b>Speaker 2:</b> Hi there." in html


def test_plain_text_fallback():
    response = {
        "results": {
            "channels": [
                {"alternatives": [{"transcript": "Just plain text here."}]}
            ],
        }
    }
    html = format_transcript(response, _make_metadata())
    assert "Just plain text here." in html


def test_duration_formatting():
    meta_short = _make_metadata(duration=65.0)
    response = _make_response([{"speaker": 0, "transcript": "Test."}])
    html = format_transcript(response, meta_short)
    assert "Duration: 1:05" in html

    meta_long = _make_metadata(duration=3661.0)
    html = format_transcript(response, meta_long)
    assert "Duration: 1:01:01" in html


def test_empty_utterances_use_transcript():
    response = {
        "results": {
            "channels": [
                {"alternatives": [{"transcript": "Fallback text."}]}
            ],
            "utterances": [],
        }
    }
    html = format_transcript(response, _make_metadata())
    assert "Fallback text." in html


# Markdown format tests


def test_single_speaker_markdown():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello this is a test."},
        {"speaker": 0, "transcript": "Another sentence here."},
    ])
    md = format_transcript_markdown(response, _make_metadata())
    assert "# Test Recording - Feb 5, 2025" in md
    assert "*Duration: 2:05*" in md
    assert "Speaker" not in md
    assert "Hello this is a test." in md


def test_multi_speaker_markdown():
    response = _make_response([
        {"speaker": 0, "transcript": "Good morning."},
        {"speaker": 1, "transcript": "Hi there."},
    ])
    md = format_transcript_markdown(response, _make_metadata())
    assert "Speakers: 2" in md
    assert "**Speaker 1:** Good morning." in md
    assert "**Speaker 2:** Hi there." in md
    assert "---" in md


# Summary integration tests


def _make_summary(
    title="AI-Generated Title",
    summary_text="This is a summary of the recording.",
    key_points=None,
    action_items=None,
    decisions=None,
    open_questions=None,
):
    return Summary(
        title=title,
        summary=summary_text,
        key_points=key_points or ["First key point", "Second key point"],
        action_items=action_items or [],
        decisions=decisions or [],
        open_questions=open_questions or [],
    )


def test_html_with_summary_and_title():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello this is a test."},
    ])
    s = _make_summary()
    html = format_transcript(
        response, _make_metadata(),
        title=s.title,
        summary=s,
    )
    assert "<h1>AI-Generated Title - Feb 5, 2025</h1>" in html
    assert "This is a summary of the recording." in html
    assert "<h2>Key Points</h2>" in html
    assert "<li>First key point</li>" in html
    assert "<li>Second key point</li>" in html
    assert "Test Recording" not in html  # original title replaced


def test_html_renders_all_summary_sections():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello."},
    ])
    s = _make_summary(
        key_points=["point 1"],
        action_items=["action 1"],
        decisions=["decision 1"],
        open_questions=["question 1"],
    )
    html = format_transcript(response, _make_metadata(), title=s.title, summary=s)
    assert "<h2>Key Points</h2>" in html
    assert "<li>point 1</li>" in html
    assert "<h2>Action Items</h2>" in html
    assert "<li>action 1</li>" in html
    assert "<h2>Decisions</h2>" in html
    assert "<li>decision 1</li>" in html
    assert "<h2>Open Questions</h2>" in html
    assert "<li>question 1</li>" in html


def test_html_omits_empty_summary_sections():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello."},
    ])
    s = _make_summary(key_points=["only key points"], action_items=[], decisions=[], open_questions=[])
    html = format_transcript(response, _make_metadata(), title=s.title, summary=s)
    assert "<h2>Key Points</h2>" in html
    assert "Action Items" not in html
    assert "Decisions" not in html
    assert "Open Questions" not in html


def test_markdown_with_summary_and_title():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello this is a test."},
    ])
    s = _make_summary()
    md = format_transcript_markdown(
        response, _make_metadata(),
        title=s.title,
        summary=s,
    )
    assert "# AI-Generated Title - Feb 5, 2025" in md
    assert "This is a summary of the recording." in md
    assert "## Key Points" in md
    assert "- First key point" in md
    assert "- Second key point" in md
    assert "Test Recording" not in md


def test_markdown_renders_all_summary_sections():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello."},
    ])
    s = _make_summary(
        key_points=["point 1"],
        action_items=["action 1"],
        decisions=["decision 1"],
        open_questions=["question 1"],
    )
    md = format_transcript_markdown(response, _make_metadata(), title=s.title, summary=s)
    assert "## Key Points" in md
    assert "- point 1" in md
    assert "## Action Items" in md
    assert "- action 1" in md
    assert "## Decisions" in md
    assert "- decision 1" in md
    assert "## Open Questions" in md
    assert "- question 1" in md


def test_html_without_summary_unchanged():
    response = _make_response([
        {"speaker": 0, "transcript": "Hello."},
    ])
    html_no_summary = format_transcript(response, _make_metadata())
    html_none = format_transcript(response, _make_metadata(), title=None, summary=None)
    assert html_no_summary == html_none


def test_multi_speaker_html_with_summary():
    response = _make_response([
        {"speaker": 0, "transcript": "Good morning."},
        {"speaker": 1, "transcript": "Hi there."},
    ])
    s = _make_summary(title="Team Standup", summary_text="Discussed sprint progress.")
    html = format_transcript(
        response, _make_metadata(),
        title=s.title,
        summary=s,
    )
    assert "<h1>Team Standup - Feb 5, 2025</h1>" in html
    assert "Discussed sprint progress." in html
    assert "Speakers: 2" in html
