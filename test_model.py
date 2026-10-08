import os
from dotenv import load_dotenv
import litellm

# 1. Load environment variables from .env
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("Missing ANTHROPIC_API_KEY in .env file. Please check your setup.")

# 2. Test Claude connection using LiteLLM per coach instructions
def test_claude_connection():
    print("Testing connection to Anthropic Claude (anthropic/claude-sonnet-5-5)...")
    try:
        response = litellm.completion(
            model="anthropic/claude-sonnet-5-5",
            messages=[
                {"role": "user", "content": "Hello! Please give a brief 1-sentence greeting confirming you are ready to assist with the RIFFs agent project."}
            ],
            api_key=api_key,
            max_tokens=4096
        )
        reply = response.choices[0].message.content
        print("\n--- Claude Response ---")
        print(reply)
        print("-----------------------\n")
        print(" SUCCESS: Claude is connected and operational!")
        return True
    except Exception as e:
        print(f"\n❌ ERROR connecting to Claude: {e}")
        return False

if __name__ == "__main__":
    test_claude_connection()
