from google import genai
from utils.config import GOOGLE_API_KEY
import json
import os

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


class Blueprint:
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model = "gemini-2.5-flash"

    def _load_prompt(self, filename: str) -> str:
        with open(os.path.join(PROMPTS_DIR, filename), "r", encoding="utf-8") as f:
            return f.read()

    def _strip_fences(self, raw: str) -> str:
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return raw.strip()

    def create(self, brief: dict) -> dict:
        system_prompt = self._load_prompt("root_agent_prompt.txt")
        user_message = json.dumps(brief, indent=2)
        full_prompt = f"{system_prompt}\n\nClient Brief:\n{user_message}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt
        )

        raw = self._strip_fences(response.text.strip())
        return json.loads(raw)
