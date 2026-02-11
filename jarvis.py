#!/usr/bin/env python3
"""A lightweight, terminal-based JARVIS-style assistant with web lookup and utilities."""

from __future__ import annotations

import ast
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
from pathlib import Path
from typing import Any


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
        self.history: list[str] = []
        self.todo_file = Path("jarvis_todos.json")

    def greet(self) -> str:
        return (
            f"{self.name} online. Say 'help' to see commands, "
            "or ask me anything."
        )

    def handle(self, user_text: str) -> str:
        cleaned = user_text.strip()
        lower = cleaned.lower()
        if cleaned:
            self.history.append(cleaned)

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
                  - wiki <topic>: short Wikipedia summary
                  - calc <expression>: safe calculator (e.g., calc 12*(3+4))
                  - todo add <task>: save a todo task
                  - todo list: show saved tasks
                  - todo clear: remove all tasks
                  - history: show recent prompts in this session
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

        if lower == "history":
            return self._show_history()

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

        if lower.startswith("wiki "):
            topic = cleaned[5:].strip()
            if not topic:
                return "Please provide a topic after 'wiki'."
            return self._wiki_summary(topic) or "I couldn't find a Wikipedia summary right now."

        if lower.startswith("calc "):
            expression = cleaned[5:].strip()
            if not expression:
                return "Please provide an expression after 'calc'."
            return self._calculate(expression)

        if lower.startswith("todo "):
            return self._handle_todo(cleaned[5:].strip())

        llm_reply = self._ask_openai(cleaned)
        if llm_reply:
            return llm_reply

        google_reply = self._google_answer(cleaned)
        if google_reply:
            return google_reply

        return self._offline_fallback(cleaned)

    def _show_history(self) -> str:
        if not self.history:
            return "No prompts in this session yet."
        recent = self.history[-10:]
        lines = ["Recent prompts:"]
        for idx, item in enumerate(recent, start=1):
            lines.append(f"{idx}. {item}")
        return "\n".join(lines)

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

    def _wiki_summary(self, topic: str) -> str | None:
        encoded = urllib.parse.quote(topic)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "jarvis-assistant/1.0"},
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError):
            return None

        extract = body.get("extract")
        title = body.get("title")
        if not extract:
            return None

        heading = f"Wikipedia: {title}" if title else "Wikipedia summary"
        return f"{heading}\n{extract}"

    def _calculate(self, expression: str) -> str:
        try:
            tree = ast.parse(expression, mode="eval")
            value = self._eval_ast(tree.body)
        except (ValueError, SyntaxError, ZeroDivisionError):
            return "Invalid expression. Use numbers and operators like + - * / ** ( )."
        return f"Result: {value}"

    def _eval_ast(self, node: ast.AST) -> float:
        operators: dict[type[ast.AST], Any] = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
            ast.Pow: lambda a, b: a**b,
            ast.Mod: lambda a, b: a % b,
        }

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = self._eval_ast(node.operand)
            return val if isinstance(node.op, ast.UAdd) else -val

        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            left = self._eval_ast(node.left)
            right = self._eval_ast(node.right)
            return operators[type(node.op)](left, right)

        raise ValueError("Unsupported expression")

    def _handle_todo(self, raw: str) -> str:
        if not raw:
            return "Use: todo add <task> | todo list | todo clear"

        lower = raw.lower()
        if lower == "list":
            items = self._read_todos()
            if not items:
                return "No todo items yet."
            lines = ["Todo items:"]
            for idx, item in enumerate(items, start=1):
                lines.append(f"{idx}. {item}")
            return "\n".join(lines)

        if lower == "clear":
            self._write_todos([])
            return "All todo items cleared."

        if lower.startswith("add "):
            task = raw[4:].strip()
            if not task:
                return "Please provide a task after 'todo add'."
            items = self._read_todos()
            items.append(task)
            self._write_todos(items)
            return f"Added todo: {task}"

        return "Use: todo add <task> | todo list | todo clear"

    def _read_todos(self) -> list[str]:
        if not self.todo_file.exists():
            return []
        try:
            data = json.loads(self.todo_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, list):
            return []

        return [str(item) for item in data]

    def _write_todos(self, items: list[str]) -> None:
        self.todo_file.write_text(json.dumps(items, indent=2), encoding="utf-8")

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
            "I can help with planning, coding support, shell commands, web lookup, quick math, and todos. "
            "Use 'help' to see everything I can do."
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
