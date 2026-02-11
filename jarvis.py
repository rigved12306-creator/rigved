#!/usr/bin/env python3
"""A lightweight, terminal-based JARVIS-style assistant with web lookup."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import platform
import re
import subprocess
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


SYSTEM_PROMPT = (
    "You are JARVIS, a concise and helpful AI assistant. "
    "Prioritize actionable answers, ask clarifying questions when needed, "
    "and stay respectful."
)


class _GoogleResultParser(HTMLParser):
    """Very small parser to capture titles/snippets from Google result blocks."""

    def __init__(self) -> None:
        super().__init__()
        self.in_h3 = False
        self.title_parts: list[str] = []
        self.snippet_parts: list[str] = []
        self.capture_snippet = False
        self.results: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: v or "" for k, v in attrs}

        if tag == "h3":
            self.in_h3 = True
            self.title_parts = []
            self.snippet_parts = []

        cls = attrs_dict.get("class", "")
        if tag == "div" and any(key in cls for key in ("VwiC3b", "s3v9rd", "lEBKkf")):
            self.capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self.in_h3 = False
        if tag == "div" and self.capture_snippet:
            self.capture_snippet = False
            title = " ".join(self.title_parts).strip()
            snippet = " ".join(self.snippet_parts).strip()
            if title and snippet:
                self.results.append((title, snippet))

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self.in_h3:
            self.title_parts.append(cleaned)
        elif self.capture_snippet:
            self.snippet_parts.append(cleaned)


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
                  - google <query>: web search via Google
                  - exit / quit: leave the assistant

                Everything else is handled as a general AI prompt.
                If OPENAI_API_KEY is not set, JARVIS will try Google snippets.
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

        if lower.startswith("google "):
            query = cleaned[7:].strip()
            if not query:
                return "Please provide a query after 'google'."
            return self._google_answer(query) or "I could not fetch Google results right now."

        llm_reply = self._ask_openai(cleaned)
        if llm_reply:
            return llm_reply

        google_reply = self._google_answer(cleaned)
        if google_reply:
            return google_reply

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

    def _google_answer(self, query: str) -> str | None:
        snippets = self._google_search(query)
        if not snippets:
            return None

        lines = [f"Here is what I found on Google for: {query}"]
        for idx, (title, snippet) in enumerate(snippets, start=1):
            lines.append(f"{idx}. {title} — {snippet}")

        return "\n".join(lines)

    def _google_search(self, query: str, max_results: int = 3) -> list[tuple[str, str]]:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}&hl=en"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                html_text = response.read().decode("utf-8", errors="ignore")
        except urllib.error.URLError:
            return []

        parser = _GoogleResultParser()
        parser.feed(html_text)
        parsed = parser.results

        if not parsed:
            parsed = self._regex_google_fallback(html_text)

        clean_results: list[tuple[str, str]] = []
        seen: set[str] = set()
        for title, snippet in parsed:
            t = html.unescape(title).strip()
            s = html.unescape(snippet).strip()
            key = f"{t}::{s}"
            if t and s and key not in seen:
                clean_results.append((t, s))
                seen.add(key)
            if len(clean_results) >= max_results:
                break

        return clean_results

    @staticmethod
    def _regex_google_fallback(raw_html: str) -> list[tuple[str, str]]:
        title_matches = re.findall(r"<h3[^>]*>(.*?)</h3>", raw_html, flags=re.S)
        snippet_matches = re.findall(
            r'<div class="(?:VwiC3b|s3v9rd|lEBKkf)[^"]*"[^>]*>(.*?)</div>',
            raw_html,
            flags=re.S,
        )

        results: list[tuple[str, str]] = []
        for title, snippet in zip(title_matches, snippet_matches):
            title_text = re.sub(r"<[^>]+>", " ", title)
            snippet_text = re.sub(r"<[^>]+>", " ", snippet)
            title_text = " ".join(title_text.split())
            snippet_text = " ".join(snippet_text.split())
            if title_text and snippet_text:
                results.append((title_text, snippet_text))
        return results

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
            "I can help with planning, coding support, shell commands, quick answers, and Google search. "
            "Use 'google <query>' for explicit web lookup."
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
