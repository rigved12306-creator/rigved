# JARVIS-style AI Assistant

This repository now includes a lightweight, terminal-based assistant inspired by JARVIS.

## Features
- Interactive command loop
- Built-in utility commands (`time`, `date`, `system`, `run <command>`)
- Optional OpenAI-backed responses when `OPENAI_API_KEY` is set
- Offline fallback behavior when no API key is configured

## Run
```bash
python3 jarvis.py
```

## Optional environment variables
- `OPENAI_API_KEY`: enables cloud AI responses
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`

## Example
```text
$ python3 jarvis.py
JARVIS online. Say 'help' to see commands, or ask me anything.
You > help
JARVIS > Built-in commands:
  - time: current local time
  ...
```
