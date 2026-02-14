import os
import sys

# Ensure we're running from project root for config loading
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

from backend.utils.llm_client import get_llm_client, LLMRequest

client = get_llm_client()
print(f"Client type: {type(client).__name__}")

response = client.generate(LLMRequest(
    prompt="What is 2+2?",
    max_tokens=100
))

print(f"Response: {response.content}")
print(f"Latency: {response.latency:.2f}s")