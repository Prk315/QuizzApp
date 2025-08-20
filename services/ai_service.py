import os, json
from openai import OpenAI

class AIService:
    def __init__(self):
        # Explicitly pass the API key to avoid proxy-related issues
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def generate_exam_json(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Calls the Chat Completions API and requests STRICT JSON via response_format.
        Returns a Python dict.
        """
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        content = resp.choices[0].message.content
        return json.loads(content)
