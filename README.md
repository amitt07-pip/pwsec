# pwsec

Telegram bot (Kurigram/Pyrogram) for the escrow groups.

## Features
- **Join requests:** DMs anyone who requests to join with safety reminders and link buttons. Set `AUTO_APPROVE=true` to also approve them.
- **Tag notifications:** DMs users when they are @mentioned in a group (text or media captions), with a "Go to message" button. Rate-limited per tagger (`TAG_LIMIT` per `TAG_WINDOW_SECONDS`).

## Commands (groups only)
| Command | Who | What it does |
|---|---|---|
| `/kickall` | Owner / admins with "Ban users" | Asks for confirmation, then removes every non-admin member |

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in API_ID, API_HASH, BOT_TOKEN
python pwsec.py
```
The bot must be an admin in your groups (with "Ban users" for `/kickall`, "Invite users" for join requests), and Privacy Mode must be disabled in @BotFather.
