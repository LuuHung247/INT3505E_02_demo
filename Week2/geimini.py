from google import genai
from google.genai import types


client = genai.Client(api_key="AIzaSyB9SBxikNUZiSzBqBYWpFk7oo2AZn9A_4w")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain how AI works in a few words",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
    ),
)
print(response.text)