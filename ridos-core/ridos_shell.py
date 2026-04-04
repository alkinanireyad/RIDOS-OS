#!/usr/bin/env python3
"""RIDOS OS AI Shell - Interactive AI Terminal"""
import os, sys, subprocess, json, socket
import urllib.request

API_KEY_FILE = os.path.expanduser("~/.ridos/api_key")
API_URL = "https://api.anthropic.com/v1/messages"

R="\033[0m"; P="\033[35m"; C="\033[36m"; G="\033[32m"; Y="\033[33m"

BANNER = f"""
{P}╔══════════════════════════════════════╗
║     RIDOS OS AI Shell v1.0           ║
║     Baghdad Edition                  ║
║     Type 'help' for commands         ║
╚══════════════════════════════════════╝{R}
"""

def get_api_key():
    if os.path.exists(API_KEY_FILE):
        return open(API_KEY_FILE).read().strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")

def ask_claude(question):
    key = get_api_key()
    if not key:
        return f"{Y}[OFFLINE] No API key found.\nSet it: mkdir -p ~/.ridos && echo 'sk-ant-...' > ~/.ridos/api_key{R}"
    try:
        data = json.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 1024,
            "system": "You are RIDOS OS AI assistant for IT professionals. Be concise and helpful.",
            "messages": [{"role": "user", "content": question}]
        }).encode()
        req = urllib.request.Request(API_URL, data=data, headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["content"][0]["text"]
    except Exception as e:
        return f"{Y}[OFFLINE] {e}{R}"

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return r.stdout + r.stderr, r.returncode
    except Exception as e:
        return str(e), 1

def main():
    print(BANNER)
    key = get_api_key()
    if key:
        print(f"{G}AI: Online and ready{R}")
    else:
        print(f"{Y}AI: No API key - set with: echo 'YOUR_KEY' > ~/.ridos/api_key{R}")
    print(f"{C}Type Linux commands, questions, or 'exit' to quit{R}\n")

    while True:
        try:
            user_input = input(f"{P}ridos-ai> {R}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{P}Goodbye!{R}")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            print(f"{P}Goodbye! | مع السلامة{R}")
            break

        if user_input.lower() == "help":
            print(f"""
{C}Commands:{R}
  Any Linux command  - runs it directly
  Any question       - asks AI
  exit / quit        - close shell
  clear              - clear screen
  setkey KEY         - set API key
""")
            continue

        if user_input.lower() == "clear":
            os.system("clear")
            continue

        if user_input.startswith("setkey "):
            key = user_input[7:].strip()
            os.makedirs(os.path.dirname(API_KEY_FILE), exist_ok=True)
            open(API_KEY_FILE, 'w').write(key)
            print(f"{G}API key saved!{R}")
            continue

        # Try as Linux command first
        output, code = run_cmd(user_input)
        if output.strip():
            print(f"{C}{output}{R}")
            if code != 0:
                print(f"{Y}Command failed (code {code}). Asking AI for help...{R}")
                answer = ask_claude(f"Linux command failed: '{user_input}'\nError: {output}\nHow to fix?")
                print(f"\n{G}{answer}{R}")
        else:
            # Treat as a question
            print(f"{Y}Asking AI...{R}")
            answer = ask_claude(user_input)
            print(f"\n{G}{answer}{R}")

if __name__ == "__main__":
    main()
