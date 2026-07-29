import os
from openai import OpenAI


def get_ai_client():

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable missing"
        )

    return OpenAI(
        api_key=api_key
    )


def ask_ai(
    system_prompt,
    user_prompt
):

    client = get_ai_client()


    response = client.chat.completions.create(

        model="gpt-5-mini",

        messages=[

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }

        ],

        temperature=0.2

    )


    return response.choices[0].message.content