import os
import json
from dotenv import load_dotenv
import litellm

# Load secrets from .env
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

class RiffsAgent:
    """
    Autonomous AI Practice & Sketching Partner for Musicians.
    Harness manages context, tool sinks, part-locking, and turns.
    """
    def __init__(self, model_id: str = "anthropic/claude-sonnet-5-5"):
        self.model_id = model_id
        self.api_key = ANTHROPIC_API_KEY
        self.max_tokens = 4096
        self.session_state = {
            "locked_tracks": [],
            "take_history": [],
            "current_key": "Am",
            "current_bpm": 120
        }
        
        self.system_prompt = (
            "You are RIFFs, an autonomous AI practice and sketching co-producer for musicians.\n"
            "You write the notes first (the recipe before the cake), then render them into realistic acoustic multisamples.\n"
            "Key capabilities:\n"
            "- Ingest typed chord progressions ('Am - F - C - G') or Nashville Numbers ('1 - 4 - 5 - 1')\n"
            "- Provide accurate chord charts, 6-string guitar tabs, and staff notation\n"
            "- Support part-locking (lock bass 🔒, re-roll drums)\n"
            "- Support musician practice mode with count-in and speed trainer\n"
            "Scope Boundaries:\n"
            "- Strictly instrumental riffs (no lyrics, no vocals)\n"
            "- Refuse literal requests to copy commercial songs note-for-note."
        )

    def run_turn(self, user_prompt: str):
        """Execute a single conversational turn with the model."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = litellm.completion(
            model=self.model_id,
            messages=messages,
            api_key=self.api_key,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content

if __name__ == "__main__":
    agent = RiffsAgent()
    print("RIFFs Agent Harness initialized with", agent.model_id)
