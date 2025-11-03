from typing import List

import openai
from openai import OpenAI

from config import get_settings


class EmbeddingService:
    def __init__(self, model: str = "text-embedding-3-small"):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model

    def embed_text(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except openai.BadRequestError as e:
            # Fallback for token limit errors: hard-truncate and retry once
            if hasattr(e, "code") or "max_tokens_per_request" in str(e):
                truncated = [t[:256] for t in texts]
                response = self.client.embeddings.create(
                    model=self.model,
                    input=truncated,
                )
                return [item.embedding for item in response.data]
            raise


