# we will try to fethc the stock price  and stock ticker of apple 

from openai import OpenAI
import os 

from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPEN_AI_KEY"))

#will  need  to give gpt a tool 
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "What is Apple's stock ticker and current price?"}]
)

print(response.choices[0].message.content)