import json
import logging
from dataclasses import dataclass

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class Summary:
    title: str
    summary: str
    key_points: list[str]
    action_items: list[str]
    decisions: list[str]
    open_questions: list[str]


def summarize(
    transcript_text: str,
    duration_seconds: float,
    speaker_count: int,
    api_key: str,
) -> Summary:
    """Generate a title and summary from transcript text using GPT-4o-mini.

    Returns a Summary with the generated title and summary text.
    Raises on API errors — caller is responsible for fallback.
    """
    if speaker_count > 1:
        context = "meeting transcript"
        note_type = "meeting"
    else:
        context = "voice note"
        note_type = "voice note"

    duration_min = int(duration_seconds / 60)

    prompt = (
        f"You are summarizing a {context}. "
        f"Duration: {duration_min} minutes. Speakers: {speaker_count}.\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        f"Respond with JSON only, no markdown formatting.\n"
        f"Rules:\n"
        f"- key_points: 3-6 specific, substantive bullet points (not vague).\n"
        f"- action_items: concrete next-steps with owners if mentioned. Empty list if none.\n"
        f"- decisions: explicit decisions made during the {note_type}. Empty list if none.\n"
        f"- open_questions: unresolved questions raised. Empty list if none.\n\n"
        f'{{"title": "concise descriptive title (max 60 chars)", '
        f'"summary": "2-4 sentence summary of this {note_type}", '
        f'"key_points": ["point 1", "point 2", ...], '
        f'"action_items": ["action 1", ...], '
        f'"decisions": ["decision 1", ...], '
        f'"open_questions": ["question 1", ...]}}'
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )

    content = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    parsed = json.loads(content)
    return Summary(
        title=parsed["title"][:60],
        summary=parsed["summary"],
        key_points=parsed.get("key_points", []),
        action_items=parsed.get("action_items", []),
        decisions=parsed.get("decisions", []),
        open_questions=parsed.get("open_questions", []),
    )
