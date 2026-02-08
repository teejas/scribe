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
        """Multi speaker should use 'meeting transcript' context."""
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
