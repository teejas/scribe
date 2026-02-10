import json
from unittest.mock import MagicMock, patch

import pytest

from scribe.summarizer import Summary, summarize


def _mock_openai_response(content: str) -> MagicMock:
    """Build a mock OpenAI chat completion response."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


class TestSummarize:
    def test_single_speaker_prompt(self):
        """Single speaker should use 'voice note' context."""
        expected = {
            "title": "My Voice Note",
            "summary": "A brief summary.",
            "key_points": ["point one"],
            "action_items": [],
            "decisions": [],
            "open_questions": [],
        }
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            result = summarize("Hello world", 120.0, 1, "fake-key")

            assert result == Summary(
                title="My Voice Note", summary="A brief summary.",
                key_points=["point one"], action_items=[], decisions=[], open_questions=[],
            )
            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "voice note" in prompt
            assert "Speakers: 1" in prompt

    def test_multi_speaker_prompt(self):
        """Multi speaker should use 'meeting transcript' context and per-person instruction."""
        expected = {
            "title": "Team Standup",
            "summary": "Discussed sprint progress.",
            "key_points": ["sprint is on track"],
            "action_items": ["Alice to update docs"],
            "decisions": ["ship on Friday"],
            "open_questions": ["what about testing?"],
        }
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            result = summarize("Speaker 1 said hello", 600.0, 3, "fake-key")

            assert result == Summary(
                title="Team Standup", summary="Discussed sprint progress.",
                key_points=["sprint is on track"], action_items=["Alice to update docs"],
                decisions=["ship on Friday"], open_questions=["what about testing?"],
            )
            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "meeting transcript" in prompt
            assert "Speakers: 3" in prompt
            assert "MUST capture every person" in prompt

    def test_title_truncated_to_60_chars(self):
        """Titles longer than 60 chars should be truncated."""
        long_title = "A" * 80
        expected = {"title": long_title, "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            result = summarize("Some text", 60.0, 1, "fake-key")
            assert len(result.title) == 60

    def test_handles_markdown_code_fences(self):
        """LLM sometimes wraps JSON in code fences — should be handled."""
        expected = {"title": "My Note", "summary": "A summary."}
        fenced = f"```json\n{json.dumps(expected)}\n```"
        mock_response = _mock_openai_response(fenced)

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            result = summarize("Some text", 60.0, 1, "fake-key")
            assert result == Summary(
                title="My Note", summary="A summary.",
                key_points=[], action_items=[], decisions=[], open_questions=[],
            )

    def test_api_error_propagates(self):
        """API errors should propagate so caller can handle fallback."""
        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                summarize("Some text", 60.0, 1, "fake-key")

    def test_uses_gpt4o_model(self):
        """Should call GPT-4o specifically."""
        expected = {"title": "Note", "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            summarize("Some text", 60.0, 1, "fake-key")

            call_args = client.chat.completions.create.call_args
            assert call_args.kwargs["model"] == "gpt-4.1"

    def test_long_recording_scales_key_points_and_max_tokens(self):
        """Recordings >5 min should get 5-15 key_points range and higher max_tokens."""
        expected = {"title": "Long Meeting", "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            summarize("Some long text", 600.0, 1, "fake-key")

            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "5-15" in prompt
            assert call_args.kwargs["max_tokens"] == 2500

    def test_short_recording_uses_default_key_points_and_max_tokens(self):
        """Recordings <=5 min should use 3-8 key_points and 1500 max_tokens."""
        expected = {"title": "Short Note", "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            summarize("Some text", 120.0, 1, "fake-key")

            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "3-8" in prompt
            assert call_args.kwargs["max_tokens"] == 1500

    def test_keyterms_included_in_prompt(self):
        """When keyterms are provided, they should appear in the prompt."""
        expected = {"title": "Note", "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            summarize("Some text", 60.0, 1, "fake-key", keyterms=["Sri", "Prasanna", "Appian"])

            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "Sri" in prompt
            assert "Prasanna" in prompt
            assert "Appian" in prompt
            assert "Known people and terms" in prompt

    def test_no_keyterms_no_reference_line(self):
        """When no keyterms, the 'Known people' line should not appear."""
        expected = {"title": "Note", "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            summarize("Some text", 60.0, 1, "fake-key")

            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "Known people and terms" not in prompt

    def test_garbled_name_instruction_present(self):
        """Prompt should instruct to flag unclear names with [?]."""
        expected = {"title": "Note", "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            summarize("Some text", 60.0, 1, "fake-key")

            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "[?]" in prompt

    def test_single_speaker_no_meeting_instruction(self):
        """Single speaker should NOT include per-person meeting instruction."""
        expected = {"title": "Note", "summary": "Summary."}
        mock_response = _mock_openai_response(json.dumps(expected))

        with patch("scribe.summarizer.OpenAI") as MockClient:
            client = MockClient.return_value
            client.chat.completions.create.return_value = mock_response

            summarize("Some text", 60.0, 1, "fake-key")

            call_args = client.chat.completions.create.call_args
            prompt = call_args.kwargs["messages"][0]["content"]
            assert "MUST capture every person" not in prompt
