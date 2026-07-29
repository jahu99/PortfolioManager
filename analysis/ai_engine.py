import ollama


MODEL = "llama3.2:3b"


def generate_ai_response(prompt):

    try:

        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )


        return response["message"]["content"]


    except Exception as e:

        print(
            f"Local AI error: {e}"
        )

        return ""