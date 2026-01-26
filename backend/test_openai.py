import os
from openai import OpenAI

try:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("No API key found")
        exit()
    client = OpenAI(api_key=api_key)
    client.models.list()
    print("OpenAI Connection Success!")
except Exception as e:
    print(f"Failed connection to OpenAI ({e})")
