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
- Fun utilities (`joke`, `quote`, `uuid`, `password <length>`, `random fact`)
- Unit conversion (`convert <value> <from> <to>`)
- Utility tools (`hash <text>`, `base64 encode/decode`, `json pretty <json>`)
- Text helpers (`text stats`, `text reverse`) and `stopwatch start/stop`
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
- `joke` / `quote` / `uuid`
- `password <length>`: generate secure random password
- `convert <value> <from> <to>`: supports `c/f`, `km/mi`, `kg/lb`
- `random fact`: quick interesting fact
- `hash <text>`: SHA256 hash of text
- `base64 encode <text>` / `base64 decode <text>`
- `json pretty <json>`: format JSON text
- `text stats <text>` / `text reverse <text>`
- `stopwatch start` / `stopwatch stop`
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
You > password 16
JARVIS > Generated password: ...
You > quote
JARVIS > 💡 ...
You > convert 10 km mi
JARVIS > 10 km = 6.214 mi
You > hash hello
JARVIS > SHA256: ...
You > text stats hello jarvis
JARVIS > chars=12, words=2, lines=1, top_letters=...
```
