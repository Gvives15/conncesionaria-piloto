import os
import sys
from openai import OpenAI

# Intento de leer variables, o fallar
api_key = os.getenv("OPENAI_API_KEY")
prompt_id = os.getenv("LLM_CLASSIFIER_PROMPT_ID")

print(f"--- MANUAL AUTH TEST ---")
if not api_key:
    print("FATAL: OPENAI_API_KEY not set in environment.")
    sys.exit(1)

print(f"API Key present: {api_key[:15]}...{api_key[-4:]}")
print(f"Prompt ID: {prompt_id}")

client = OpenAI(api_key=api_key)

try:
    print("Attempting client.responses.create (version=7)...")
    response = client.responses.create(
        prompt={
            "id": prompt_id or "pmpt_dummy",
            "version": "7"
        },
        input=[{"role": "user", "content": "Test"}],
        text={"format": {"type": "text"}}
    )
    print("SUCCESS: Connection established.")
    print(response)
except Exception as e:
    print(f"ERROR: {e}")
    # Force exit code 0 to avoid docker compose error noise, we captured the error text
    sys.exit(0)
