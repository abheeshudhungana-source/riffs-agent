import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if not os.getenv("ANTHROPIC_API_KEY"):
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "ANTHROPIC_API_KEY":
                        os.environ["ANTHROPIC_API_KEY"] = v.strip().strip("'").strip('"')

try:
    import litellm
except ImportError:
    litellm = None

# Test Claude connection using LiteLLM per coach instructions
def test_claude_connection():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Missing ANTHROPIC_API_KEY in .env file. Please check your setup.")
        return False
    print("Testing connection to Anthropic Claude (anthropic/claude-sonnet-5-5)...")
    if litellm is None:
        print("❌ ERROR: litellm is not installed.")
        return False
    try:
        params = {"max_tokens": 4096}
        response = litellm.completion(
            model="anthropic/claude-sonnet-5-5",
            messages=[
                {"role": "user", "content": "Hello! Please give a brief 1-sentence greeting confirming you are ready to assist with the RIFFs agent project."}
            ],
            api_key=api_key,
            **params
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
