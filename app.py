import requests

API_URL = "http://127.0.0.1:8000/chat"


def main():
    print("Local AI Tool-Calling Agent")
    print("Type 'exit' to stop.\n")

    while True:
        question = input("You: ").strip()

        if question.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if not question:
            continue

        try:
            response = requests.post(
                API_URL,
                json={"question": question},
                timeout=180
            )

            if response.status_code == 200:
                result = response.json()

                print("\nAgent:", result.get("answer", "No answer"))

                tools = result.get("tools_used", [])
                if tools:
                    print("Tools used:", ", ".join(tools))

                print()
            else:
                print("Error:", response.text, "\n")

        except requests.RequestException as exc:
            print("Could not connect to the API:", exc)
            print("Start the API using: uvicorn api:app --reload\n")


if __name__ == "__main__":
    main()