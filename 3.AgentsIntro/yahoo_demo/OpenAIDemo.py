from openai import OpenAI
import os 

client = OpenAI(api_key=os.environ.get("OPEN_AI_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is Apple's stock ticker and current price?"}]
)

print(response.choices[0].message.content)