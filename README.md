# pwsec

Telegram bot (Kurigram/Pyrogram) for the escrow groups.

## Features
- **Join requests:** DMs anyone who requests to join with safety reminders and link buttons. Set `AUTO_APPROVE=true` to also approve them.
- **Filters:** when a saved trigger appears in a message (any capitals, whole word), the bot replies with the saved text or picture (formatting kept). If the trigger message is a reply to someone else's message, the bot replies to that original message instead. Stored in `filters.json` (or `FILTERS_FILE`).
- **Tag notifications:** DMs users when they are @mentioned in a group (text or media captions), with a "Go to message" button. Rate-limited per tagger (`TAG_LIMIT` per `TAG_WINDOW_SECONDS`).

## Commands (groups only)
| Command | Who | What it does |
|---|---|---|
| `/filter <trigger> <reply>` | Admins | Saves an auto-reply. Use quotes for multi-word triggers: `/filter "how to buy" Read the pin`. Reply to a message/picture with `/filter <trigger>` (or send a picture with `/filter <trigger>` as caption) to save that instead |
| `/filters` | Admins | Lists saved filters in the group |
| `/stop <trigger>` | Admins | Deletes a filter |
| `/kickall` | Owner / admins with "Ban users" | Asks for confirmation, then removes every non-admin member |

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in API_ID, API_HASH, BOT_TOKEN
python pwsec.py
```
The bot must be an admin in your groups (with "Ban users" for `/kickall`, "Invite users" for join requests), and Privacy Mode must be disabled in @BotFather.
