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
    """Generate a title and summary from transcript text using GPT-4o.

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
        f"You are an expert analyst summarizing a {context}. "
        f"Duration: {duration_min} minutes. Speakers: {speaker_count}.\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        f"Your job is to extract the SALIENT POINTS — the concrete, specific "
        f"information that someone would actually want to reference later. "
        f"Think about what makes this {note_type} worth remembering.\n\n"
        f"Examples of salient points (extract whatever applies):\n"
        f"- Specific plans, schedules, dates, or timelines agreed upon\n"
        f"- Names, places, recommendations, or references mentioned\n"
        f"- Numbers, amounts, prices, or quantities discussed\n"
        f"- Opinions, preferences, or positions expressed by participants\n"
        f"- Problems identified and solutions proposed\n"
        f"- Commitments or promises made\n\n"
        f"Rules:\n"
        f"- summary: A rich 3-5 sentence synopsis that captures the substance "
        f"of the {note_type}, not just the topic. Include specifics.\n"
        f"- key_points: 3-8 specific, concrete bullet points. Each should "
        f"contain real information from the conversation — names, dates, "
        f"numbers, specifics. Never write vague points like 'discussed the project'.\n"
        f"- action_items: concrete next-steps with owners and deadlines if mentioned. Empty list if none.\n"
        f"- decisions: explicit decisions or agreements reached. Empty list if none.\n"
        f"- open_questions: unresolved questions or disagreements. Empty list if none.\n\n"
        f"Respond with JSON only, no markdown formatting.\n"
        f'{{"title": "concise descriptive title (max 60 chars)", '
        f'"summary": "3-5 sentence substantive summary", '
        f'"key_points": ["specific point with concrete details", ...], '
        f'"action_items": ["action with owner/deadline if known", ...], '
        f'"decisions": ["specific decision or agreement", ...], '
        f'"open_questions": ["unresolved question", ...]}}'
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1500,
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
