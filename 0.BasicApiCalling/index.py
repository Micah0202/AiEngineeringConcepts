from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI() # OpenAI class is used to create a client object


response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "user",
            "content": "Write a simple poem about a dog"
        }
    ]
)

print(response.choices[0].message.content)