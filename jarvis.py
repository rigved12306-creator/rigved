#!/usr/bin/env python3
"""A lightweight, terminal-based JARVIS-style assistant with web lookup and utilities."""

from __future__ import annotations

import ast
import base64
import datetime as dt
import hashlib
import html
import json
import binascii
import os
import platform
import re
import secrets
import subprocess
import textwrap
import time
import uuid
from collections import Counter
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
        self.notes_file = Path("jarvis_notes.json")
        self.stopwatch_started_at: float | None = None

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
                  - timer <seconds>: countdown timer
                  - weather <city>: quick weather (wttr.in)
                  - note add <text>: save a personal note
                  - note list: show saved notes
                  - note clear: remove all notes
                  - joke: random one-liner joke
                  - quote: motivational quote
                  - uuid: generate a unique id
                  - password <length>: secure password generator
                  - convert <value> <from> <to>: unit conversion (c/f, km/mi, kg/lb)
                  - random fact: quick interesting fact
                  - hash <text>: SHA256 hash
                  - base64 encode <text> | base64 decode <text>
                  - json pretty <json>: format JSON text
                  - text stats <text>: character/word stats
                  - text reverse <text>: reverse text
                  - stopwatch start|stop: simple session stopwatch
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

        if lower.startswith("timer "):
            raw_seconds = cleaned[6:].strip()
            return self._timer(raw_seconds)

        if lower.startswith("weather "):
            city = cleaned[8:].strip()
            if not city:
                return "Please provide a city after 'weather'."
            return self._weather(city)

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

        if lower.startswith("note "):
            return self._handle_notes(cleaned[5:].strip())

        if lower == "joke":
            return self._joke()

        if lower == "quote":
            return self._quote()

        if lower == "uuid":
            return f"UUID: {uuid.uuid4()}"

        if lower.startswith("password "):
            raw_len = cleaned[9:].strip()
            return self._password(raw_len)

        if lower.startswith("convert "):
            raw = cleaned[8:].strip()
            return self._convert(raw)

        if lower == "random fact":
            return self._random_fact()

        if lower.startswith("hash "):
            text = cleaned[5:].strip()
            if not text:
                return "Please provide text after 'hash'."
            return self._hash_text(text)

        if lower.startswith("base64 "):
            return self._base64_tool(cleaned[7:].strip())

        if lower.startswith("json pretty "):
            raw = cleaned[12:].strip()
            return self._json_pretty(raw)

        if lower.startswith("text stats "):
            raw = cleaned[11:]
            return self._text_stats(raw)

        if lower.startswith("text reverse "):
            raw = cleaned[13:]
            return self._text_reverse(raw)

        if lower.startswith("stopwatch "):
            raw = cleaned[10:].strip()
            return self._stopwatch(raw)

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

    def _timer(self, raw_seconds: str) -> str:
        try:
            seconds = int(raw_seconds)
        except ValueError:
            return "Timer expects whole seconds, e.g. 'timer 10'."

        if seconds <= 0:
            return "Timer must be greater than 0 seconds."
        if seconds > 600:
            return "For safety, max timer is 600 seconds (10 minutes)."

        time.sleep(seconds)
        return f"⏰ Timer complete after {seconds} seconds."

    def _weather(self, city: str) -> str:
        encoded = urllib.parse.quote_plus(city)
        url = f"https://wttr.in/{encoded}?format=3"
        req = urllib.request.Request(url, headers={"User-Agent": "jarvis-assistant/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                output = response.read().decode("utf-8", errors="ignore").strip()
        except urllib.error.URLError:
            return "Weather lookup failed right now. Try again later."

        if not output:
            return "Weather lookup returned no data."

        return f"Weather: {output}"

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

    def _handle_notes(self, raw: str) -> str:
        if not raw:
            return "Use: note add <text> | note list | note clear"

        lower = raw.lower()
        if lower == "list":
            notes = self._read_notes()
            if not notes:
                return "No notes yet."
            lines = ["Notes:"]
            for idx, item in enumerate(notes, start=1):
                lines.append(f"{idx}. {item}")
            return "\n".join(lines)

        if lower == "clear":
            self._write_notes([])
            return "All notes cleared."

        if lower.startswith("add "):
            note = raw[4:].strip()
            if not note:
                return "Please provide note text after 'note add'."
            notes = self._read_notes()
            notes.append(note)
            self._write_notes(notes)
            return f"Saved note: {note}"

        return "Use: note add <text> | note list | note clear"


    def _joke(self) -> str:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "I would tell you a UDP joke, but you might not get it.",
            "There are 10 kinds of people: those who understand binary and those who do not.",
            "Debugging: being the detective in a crime movie where you are also the murderer.",
        ]
        return f"😄 {secrets.choice(jokes)}"

    @staticmethod
    def _quote() -> str:
        quotes = [
            "Small steps every day lead to big results.",
            "Discipline beats motivation when motivation fades.",
            "Done is better than perfect when learning.",
            "Consistency compounds faster than intensity.",
        ]
        return f"💡 {secrets.choice(quotes)}"

    @staticmethod
    def _password(raw_len: str) -> str:
        try:
            length = int(raw_len)
        except ValueError:
            return "Password expects a number, e.g. 'password 16'."

        if length < 8:
            return "Use at least 8 characters for a safer password."
        if length > 128:
            return "Max password length is 128."

        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+"
        generated = "".join(secrets.choice(alphabet) for _ in range(length))
        return f"Generated password: {generated}"


    @staticmethod
    def _convert(raw: str) -> str:
        parts = raw.split()
        if len(parts) != 3:
            return "Use: convert <value> <from> <to> (e.g., convert 10 km mi)"

        value_raw, from_unit, to_unit = parts
        from_unit = from_unit.lower()
        to_unit = to_unit.lower()

        try:
            value = float(value_raw)
        except ValueError:
            return "Value must be a number, e.g. convert 10 km mi"

        converters = {
            ("c", "f"): lambda x: (x * 9 / 5) + 32,
            ("f", "c"): lambda x: (x - 32) * 5 / 9,
            ("km", "mi"): lambda x: x * 0.621371,
            ("mi", "km"): lambda x: x / 0.621371,
            ("kg", "lb"): lambda x: x * 2.20462,
            ("lb", "kg"): lambda x: x / 2.20462,
        }

        key = (from_unit, to_unit)
        if key not in converters:
            return "Supported conversions: c↔f, km↔mi, kg↔lb"

        converted = converters[key](value)
        return f"{value:g} {from_unit} = {converted:.3f} {to_unit}"

    @staticmethod
    def _random_fact() -> str:
        facts = [
            "Octopuses have three hearts and blue blood.",
            "Bananas are berries, but strawberries are not.",
            "The first computer bug was an actual moth in 1947.",
            "Honey never spoils when stored properly.",
        ]
        return f"📘 {secrets.choice(facts)}"


    @staticmethod
    def _hash_text(text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"SHA256: {digest}"

    @staticmethod
    def _base64_tool(raw: str) -> str:
        if not raw:
            return "Use: base64 encode <text> OR base64 decode <text>"

        if raw.startswith("encode "):
            plain = raw[7:]
            if not plain:
                return "Please provide text to encode."
            out = base64.b64encode(plain.encode("utf-8")).decode("utf-8")
            return f"base64: {out}"

        if raw.startswith("decode "):
            encoded = raw[7:].strip()
            if not encoded:
                return "Please provide base64 text to decode."
            try:
                out = base64.b64decode(encoded, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                return "Invalid base64 input."
            return f"decoded: {out}"

        return "Use: base64 encode <text> OR base64 decode <text>"

    @staticmethod
    def _json_pretty(raw: str) -> str:
        if not raw:
            return "Please provide JSON after 'json pretty'."

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return "Invalid JSON input."

        return json.dumps(data, indent=2, ensure_ascii=False)


    @staticmethod
    def _text_reverse(raw: str) -> str:
        if not raw.strip():
            return "Please provide text after 'text reverse'."
        return raw[::-1]

    @staticmethod
    def _text_stats(raw: str) -> str:
        text = raw.strip()
        if not text:
            return "Please provide text after 'text stats'."

        words = [w for w in text.split() if w]
        chars = len(text)
        lines = text.count("\n") + 1
        letters_only = [c.lower() for c in text if c.isalpha()]
        top = Counter(letters_only).most_common(3)
        top_str = ", ".join(f"{ch}:{count}" for ch, count in top) if top else "n/a"

        return (
            f"chars={chars}, words={len(words)}, lines={lines}, "
            f"top_letters={top_str}"
        )

    def _stopwatch(self, raw: str) -> str:
        cmd = raw.lower()
        if cmd == "start":
            self.stopwatch_started_at = time.time()
            return "⏱️ Stopwatch started."

        if cmd == "stop":
            if self.stopwatch_started_at is None:
                return "Stopwatch was not started. Use 'stopwatch start' first."
            elapsed = time.time() - self.stopwatch_started_at
            self.stopwatch_started_at = None
            return f"⏱️ Stopwatch: {elapsed:.2f} seconds."

        return "Use: stopwatch start | stopwatch stop"

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

    def _read_notes(self) -> list[str]:
        if not self.notes_file.exists():
            return []
        try:
            data = json.loads(self.notes_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, list):
            return []

        return [str(item) for item in data]

    def _write_notes(self, items: list[str]) -> None:
        self.notes_file.write_text(json.dumps(items, indent=2), encoding="utf-8")

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
            "I can help with planning, coding support, shell commands, web lookup, quick math, todos, notes, weather, jokes, quotes, passwords, conversions, facts, hashes, base64, JSON formatting, text tools, and stopwatch timing. "
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
