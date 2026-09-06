from google import genai

from ..config import Settings
from ..retry import genai_retry


class GenaiClient:
    def __init__(self, settings: Settings):
        self._client = genai.Client(api_key=settings.gemini_api_key)

    @genai_retry()
    def generate_json(
        self,
        model: str,
        input,
        response_schema: dict,
        system_instruction: str | None = None,
    ):
        kwargs = {}
        if system_instruction is not None:
            kwargs["system_instruction"] = system_instruction

        return self._client.interactions.create(
            model=model,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": response_schema,
            },
            input=input,
            **kwargs,
        )
