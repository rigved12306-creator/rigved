# JARVIS-style AI Assistant

This repository includes a lightweight terminal-based assistant inspired by JARVIS, with web lookup and handy local tools.

## Features
- Interactive command loop
- Built-in utility commands (`time`, `date`, `system`, `run <command>`)
- Web lookup command (`google <query>`) for live search snippets
- Wikipedia summaries (`wiki <topic>`)
- Safe calculator (`calc <expression>`)
- Simple persistent todo list (`todo add/list/clear`)
- Personal notes (`note add/list/clear`)
- Session history (`history`)
- Quick weather lookup (`weather <city>`)
- Countdown timer (`timer <seconds>`)
- Optional OpenAI-backed responses when `OPENAI_API_KEY` is set

## Run
```bash
python3 jarvis.py
```

## Commands
- `help`: show built-in commands
- `time`, `date`, `system`
- `run <command>`: run a shell command
- `google <query>`: search Google and return top snippets
- `wiki <topic>`: fetch a short Wikipedia summary
- `calc <expression>`: evaluate math expressions safely
- `todo add <task>` / `todo list` / `todo clear`
- `note add <text>` / `note list` / `note clear`
- `history`: show recent prompts in this session
- `weather <city>`: quick weather summary
- `timer <seconds>`: waits and notifies when finished
- `exit` / `quit`

## Optional environment variables
- `OPENAI_API_KEY`: enables cloud AI responses
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`

## Example
```text
$ python3 jarvis.py
JARVIS online. Say 'help' to see commands, or ask me anything.
You > calc 12*(3+4)
JARVIS > Result: 84.0
You > todo add finish project update
JARVIS > Added todo: finish project update
You > todo list
JARVIS > Todo items:
1. finish project update
You > weather delhi
JARVIS > Weather: Delhi: +34°C, Haze
```
