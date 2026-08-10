from turtle import mode
from openai import OpenAI
from dotenv import load_dotenv
from system_prompt import SYSTEM_PROMPT
import sys 




load_dotenv()

try:
    client = OpenAI()
except Exception as e:
    print(f"Error creating OpenAI client: {e}")
    sys.exit(1)


def main():
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]


    print("-"*50)
    print("TaskBuddy: Hey There! What's on your mind?")
    print("           Dump you tasks here, and I'll organize them for you!")
    print("-"*50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                print("\nTaskBuddy: Goodbye!")
                break 
            
            if not user_input.strip():
                continue 

            messages.append({ "role": "user", "content": user_input })

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )

            reply = response.choices[0].message.content

            print(f"\nTaskBuddy: {reply}")

            messages.append({ "role": "assistant", "content": reply })
 

            
        except KeyboardInterrupt:
            print("\nTaskBuddy: Goodbye!")
            break 
        except Exception as e:
            print("\nAn error occurred: {e}")
            break


if __name__ == "__main__":
    main()