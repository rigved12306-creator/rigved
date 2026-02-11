# JARVIS-style AI Assistant

This repository includes a lightweight terminal-based assistant inspired by JARVIS, now with direct Google lookup support.

## Features
- Interactive command loop
- Built-in utility commands (`time`, `date`, `system`, `run <command>`)
- Web lookup command (`google <query>`) for live search snippets
- Optional OpenAI-backed responses when `OPENAI_API_KEY` is set
- Fallback behavior when no API key is configured

## Run
```bash
python3 jarvis.py
```

## Commands
- `help`: show built-in commands
- `time`, `date`, `system`
- `run <command>`: run a shell command
- `google <query>`: search Google and return top snippets
- `exit` / `quit`

## Optional environment variables
- `OPENAI_API_KEY`: enables cloud AI responses
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`

## Example
```text
$ python3 jarvis.py
JARVIS online. Say 'help' to see commands, or ask me anything.
You > google latest python version
JARVIS > Here is what I found on Google for: latest python version
1. ...
```
