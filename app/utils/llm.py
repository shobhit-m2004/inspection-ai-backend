import json
from typing import Any

from openai import OpenAI

from app.core.config import get_settings

settings = get_settings()


def try_llm_json(prompt: str) -> dict[str, Any] | None:
    if not settings.openai_api_key:
        return None

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            messages=[
                {'role': 'system', 'content': 'You are a careful extraction assistant. Output valid JSON only.'},
                {'role': 'user', 'content': prompt},
            ],
            response_format={'type': 'json_object'},
        )
        content = response.choices[0].message.content or '{}'
        return json.loads(content)
    except Exception:
        return None
