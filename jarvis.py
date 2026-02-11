#!/usr/bin/env python3
"""A lightweight, terminal-based JARVIS-style assistant."""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
import subprocess
import textwrap
import urllib.error
import urllib.request


SYSTEM_PROMPT = (
    "You are JARVIS, a concise and helpful AI assistant. "
    "Prioritize actionable answers, ask clarifying questions when needed, "
    "and stay respectful."
)


class Jarvis:
    def __init__(self) -> None:
        self.name = "JARVIS"
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")

    def greet(self) -> str:
        return (
            f"{self.name} online. Say 'help' to see commands, "
            "or ask me anything."
        )

    def handle(self, user_text: str) -> str:
        cleaned = user_text.strip()
        lower = cleaned.lower()

        if not cleaned:
            return "I didn't catch that."

        if lower in {"help", "commands"}:
            return textwrap.dedent(
                """
                Built-in commands:
                  - time: current local time
                  - date: current local date
                  - system: OS and Python details
                  - run <command>: run a shell command
                  - exit / quit: leave the assistant

                Everything else is handled as a general AI prompt.
                Set OPENAI_API_KEY to enable cloud intelligence.
                """
            ).strip()

        if lower == "time":
            return dt.datetime.now().strftime("It is %H:%M:%S.")

        if lower == "date":
            return dt.datetime.now().strftime("Today is %A, %B %d, %Y.")

        if lower == "system":
            return (
                f"OS: {platform.system()} {platform.release()} | "
                f"Python: {platform.python_version()}"
            )

        if lower.startswith("run "):
            command = cleaned[4:].strip()
            if not command:
                return "Please provide a command after 'run'."
            return self._run_shell(command)

        llm_reply = self._ask_openai(cleaned)
        if llm_reply:
            return llm_reply

        return self._offline_fallback(cleaned)

    def _run_shell(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            return "Command timed out after 20 seconds."

        output = (result.stdout or "") + (result.stderr or "")
        output = output.strip() or "(no output)"
        return f"exit={result.returncode}\n{output}"

    def _ask_openai(self, prompt: str) -> str | None:
        if not self.api_key:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.5,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None

        choices = body.get("choices")
        if not choices:
            return None

        return choices[0].get("message", {}).get("content")

    @staticmethod
    def _offline_fallback(prompt: str) -> str:
        lower = prompt.lower()
        if "who are you" in lower or "your name" in lower:
            return "I'm JARVIS, your local AI assistant."
        if "hello" in lower or "hi" in lower:
            return "Hello. How can I assist you today?"
        if "plan" in lower:
            return "Sure—tell me your goal, deadline, and constraints; I'll draft a plan."
        return (
            "I can help with planning, coding support, shell commands, and quick answers. "
            "Set OPENAI_API_KEY for full AI responses."
        )


def main() -> None:
    jarvis = Jarvis()
    print(jarvis.greet())

    while True:
        try:
            user_input = input("You > ")
        except (EOFError, KeyboardInterrupt):
            print("\nJARVIS > Shutting down. Goodbye.")
            break

        if user_input.strip().lower() in {"exit", "quit"}:
            print("JARVIS > Goodbye.")
            break

        print(f"JARVIS > {jarvis.handle(user_input)}")


if __name__ == "__main__":
    main()
