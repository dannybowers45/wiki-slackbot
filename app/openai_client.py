import os
from typing import Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


class OpenAIClientError(Exception):
    """Raised when the OpenAI client cannot fulfill a request."""


class OpenAIClient:
    """Lightweight wrapper around OpenAI's Responses API."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._client: Optional[AsyncOpenAI] = None
        self._supports_responses: Optional[bool] = None

    def _ensure_client(self) -> AsyncOpenAI:
        if not self.api_key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured.")

        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        if self._supports_responses is None and self._client is not None:
            self._supports_responses = hasattr(self._client, "responses")
        return self._client

    async def close(self) -> None:
        """Close the underlying OpenAI HTTP client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._supports_responses = None

    async def summarize(
        self,
        *,
        topic: str,
        content: str,
        url: str,
        context: Optional[str] = None
    ) -> str:
        """Summarize raw Wikipedia content into concise prose."""
        client = self._ensure_client()

        context_section = (
            f"Recent conversation context to keep in mind:\n{context}\n\n"
            if context else ""
        )

        prompt = (
            "You are an editor turning Wikipedia notes into a friendly answer.\n"
            "Instructions:\n"
            "1. Write 5-10 sentences in plain language that answer the user's question.\n"
            "2. Base the answer only on the provided lines from Wikipedia.\n"
            "3. Avoid markdown unless needed for clarity.\n"
            f"User question: {topic}\n"
            f"{context_section}"
            "Wikipedia lines:\n"
            f"{content}\n"
        )

        try:
            if self._supports_responses:
                response = await client.responses.create(
                    model=self.model,
                    input=prompt,
                    temperature=0.4,
                )
                summary = (response.output_text or "").strip()
            else:
                chat = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You rewrite Wikipedia notes into clear summaries."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.4,
                )
                summary = (chat.choices[0].message.content or "").strip()
        except Exception as exc:
            raise OpenAIClientError(f"OpenAI request failed: {exc}") from exc

        if not summary:
            raise OpenAIClientError("OpenAI returned an empty response.")

        return summary


openai_client = OpenAIClient()
