import ollama
import traceback


# ---------------------------------
# Ollama Model Configuration
# ---------------------------------

MODEL = "llama3.1:latest"


# ---------------------------------
# AI Response Generator
# ---------------------------------

def generate_ai_response(prompt):

    try:

        print("OLLAMA CALL STARTED")

        response = ollama.chat(

            model=MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            options={

                "temperature": 0.2,

                "num_predict": 300,

                "top_p": 0.9

            }

        )


        print("OLLAMA RESPONSE RECEIVED")


        return response["message"]["content"]



    except KeyboardInterrupt:


        print(
            "AI generation interrupted"
        )


        return (
            "AI analysis unavailable - generation interrupted"
        )



    except Exception as e:


        print(
            f"AI ENGINE ERROR: {e}"
        )


        traceback.print_exc()


        return (
            "AI analysis unavailable"
        )



# ---------------------------------
# Health Check
# ---------------------------------

def test_ai_engine():

    try:

        print(
            "Testing Ollama model:",
            MODEL
        )


        response = ollama.chat(

            model=MODEL,

            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly: AI OK"
                }
            ],

            options={
                "temperature": 0.2,
                "num_predict": 10
            }

        )


        return response["message"]["content"]


    except Exception as e:


        return (
            f"AI engine unavailable: {e}"
        )



# ---------------------------------
# Main Test
# ---------------------------------

if __name__ == "__main__":

    print(
        test_ai_engine()
    )