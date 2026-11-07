# pwsec

Telegram bot (Kurigram/Pyrogram) for the escrow groups.

## Features
- **Join requests:** DMs anyone who requests to join with safety reminders and link buttons. Set `AUTO_APPROVE=true` to also approve them.
- **Filters:** when a message starts with a saved trigger (any capitals, whole word; `hello there` fires `hello`, `say hello` doesn't; the longest matching trigger wins), the bot replies with the saved text or picture (formatting kept). If the trigger message is a reply to someone else's message, the bot replies to that original message instead. Stored in `filters.json` (or `FILTERS_FILE`).
- **Tag notifications:** DMs users when they are @mentioned in a group (text or media captions), with a "Go to message" button. Rate-limited per tagger (`TAG_LIMIT` per `TAG_WINDOW_SECONDS`).

## Allowed group
The bot only works in `ALLOWED_CHAT_ID` (default `-1002510674423`) and automatically leaves any other group or channel it is added to. The owner's `/admin`, `/unadmin`, `/admins` also work in the bot's DM.

## Who is an admin
- **Bot owner** (`OWNER_ID`, default `6643621069`): full access everywhere. Anonymous group admins are treated as the owner.
- **Bot admins** added by the owner with `/admin` (saved in `admins.json`).
- **Telegram group admins** of that group (for `/kickall`: owner or admins with "Ban users").

## Commands
`/admin`, `/unadmin`, `/admins` work in the allowed group and in the bot's DM; the rest work in the allowed group only.

| Command | Who | What it does |
|---|---|---|
| `/start` (bot DM) | Bot owner | Dashboard: status, uptime, ping, bot permissions in the allowed group, filter/admin counts, activity since start, Refresh button |
| `/admin @username` / `/admin <user id>` / reply with `/admin` | Bot owner | Makes that user a bot admin (can use all admin commands in every group) |
| `/unadmin @username` / `<user id>` / reply | Bot owner | Removes a bot admin |
| `/admins` | Bot owner | Lists bot admins |
| `/filter <trigger> <reply>` | Admins | Saves an auto-reply. Use quotes for multi-word triggers: `/filter "how to buy" Read the pin`. Reply to a message/picture with `/filter <trigger>` (or send a picture with `/filter <trigger>` as caption) to save that instead |
| `/filters` | Admins | Lists saved filters in the group |
| `/stop <trigger>` | Admins | Deletes a filter |
| `/kickall` | Bot owner, bot admins, group owner, group admins with "Ban users" | Asks for confirmation, then removes every non-admin member |

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in API_ID, API_HASH, BOT_TOKEN
python pwsec.py
```
The bot must be an admin in your groups (with "Ban users" for `/kickall`, "Invite users" for join requests), and Privacy Mode must be disabled in @BotFather.
