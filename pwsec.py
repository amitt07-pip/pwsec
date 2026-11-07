# pwsec.py
import asyncio
import html
import json
import os
import re
import time
from collections import defaultdict, deque

from dotenv import load_dotenv
from pyrogram import Client, enums, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity

load_dotenv()

# ====== CONFIG ======
def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable {name} (set it in .env)")
    return value


API_ID = int(_require_env("API_ID"))
API_HASH = _require_env("API_HASH")
BOT_TOKEN = _require_env("BOT_TOKEN")

ESCROW_LINK = os.getenv("INVITE_LINK_1") or "https://t.me/+GDQdTcMu5bkwOGY1"
CHAT_LINK = os.getenv("INVITE_LINK_2") or "https://t.me/+W2PxpjFlku0yMzFl"
SUPPORT_LINK = os.getenv("SUPPORT_LINK") or "https://t.me/pw_supportbot"
MAIN_CHANNEL_LINK = os.getenv("MAIN_CHANNEL_LINK") or "https://t.me/escrow_pagal"

AUTO_APPROVE = os.getenv("AUTO_APPROVE", "false").lower() in ("1", "true", "yes")

TAG_LIMIT = int(os.getenv("TAG_LIMIT", "5"))
TAG_WINDOW_SECONDS = int(os.getenv("TAG_WINDOW_SECONDS", "60"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILTERS_FILE = os.getenv("FILTERS_FILE") or os.path.join(BASE_DIR, "filters.json")
ADMINS_FILE = os.getenv("ADMINS_FILE") or os.path.join(BASE_DIR, "admins.json")
OWNER_ID = int(os.getenv("OWNER_ID") or "6643621069")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID") or "-1002510674423")
# ====================

app = Client("join_request_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

ADMIN_STATUSES = (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR)


async def _in_allowed_chat(_, __, update) -> bool:
    message = update.message if isinstance(update, CallbackQuery) else update
    chat = getattr(message, "chat", None)
    return bool(chat and chat.id == ALLOWED_CHAT_ID)


allowed_chat = filters.create(_in_allowed_chat)

_bot_id = None
_tag_history = defaultdict(deque)
_kickall_running = set()


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        print(f"Could not load {path}: {e}")
        return default


def save_json(path: str, data) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def save_filters() -> None:
    save_json(FILTERS_FILE, _filters)


def save_bot_admins() -> None:
    save_json(ADMINS_FILE, sorted(_bot_admins))


_filters = load_json(FILTERS_FILE, {})
_bot_admins = set(load_json(ADMINS_FILE, []))


async def get_bot_id(client: Client) -> int:
    global _bot_id
    if _bot_id is None:
        _bot_id = (await client.get_me()).id
    return _bot_id


def display_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    full_name = " ".join(part for part in (user.first_name, user.last_name) if part)
    return html.escape(full_name or str(user.id))


def message_link(message: Message):
    chat = message.chat
    if chat.username:
        return f"https://t.me/{chat.username}/{message.id}"
    chat_id = str(chat.id)
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{message.id}"
    return None


def tag_allowed(tagger_id: int) -> bool:
    now = time.monotonic()
    history = _tag_history[tagger_id]
    while history and now - history[0] > TAG_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= TAG_LIMIT:
        return False
    history.append(now)
    return True


async def can_ban(client: Client, chat_id: int, user_id: int) -> bool:
    member = await client.get_chat_member(chat_id, user_id)
    if member.status == enums.ChatMemberStatus.OWNER:
        return True
    return (
        member.status == enums.ChatMemberStatus.ADMINISTRATOR
        and bool(member.privileges and member.privileges.can_restrict_members)
    )


def is_anonymous_admin(message: Message) -> bool:
    return bool(message.sender_chat and message.sender_chat.id == message.chat.id)


def is_owner(message: Message) -> bool:
    """The bot owner, or an anonymous group admin (treated as the owner)."""
    return is_anonymous_admin(message) or bool(message.from_user and message.from_user.id == OWNER_ID)


def is_bot_admin(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in _bot_admins


async def is_admin(client: Client, message: Message) -> bool:
    if is_owner(message):
        return True
    if not message.from_user:
        return False
    if is_bot_admin(message.from_user.id):
        return True
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ADMIN_STATUSES


async def can_kickall(client: Client, chat_id: int, user_id: int) -> bool:
    return is_bot_admin(user_id) or await can_ban(client, chat_id, user_id)


def parse_trigger(args: str):
    """Split '"multi word" rest' or 'word rest' into (trigger, rest)."""
    args = args.strip()
    if args[:1] in ('"', "“"):
        match = re.match(r'^["“](.+?)["”]\s*(.*)$', args, re.S)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    parts = args.split(None, 1)
    if not parts:
        return "", ""
    return parts[0], parts[1].strip() if len(parts) > 1 else ""


def command_args(message: Message) -> str:
    text = message.text or message.caption or ""
    parts = text.split(None, 1)
    return parts[1] if len(parts) > 1 else ""


def media_file_id(message: Message):
    if not message.media:
        return None
    media = getattr(message, message.media.value, None)
    return getattr(media, "file_id", None)


ENTITY_FIELDS = ("url", "language", "custom_emoji_id", "expandable")


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def serialize_entities(entities) -> list:
    result = []
    for entity in entities or []:
        if entity.type in (enums.MessageEntityType.BOT_COMMAND, enums.MessageEntityType.TEXT_MENTION):
            continue
        data = {"type": entity.type.name, "offset": entity.offset, "length": entity.length}
        for field in ENTITY_FIELDS:
            value = getattr(entity, field, None)
            if value is not None:
                data[field] = value
        result.append(data)
    return result


def shift_entities(entities, start: int) -> list:
    shifted = []
    for data in serialize_entities(entities):
        if data["offset"] >= start:
            data["offset"] -= start
            shifted.append(data)
    return shifted


def deserialize_entities(entities) -> list:
    result = []
    for data in entities or []:
        try:
            result.append(
                MessageEntity(
                    type=enums.MessageEntityType[data["type"]],
                    offset=data["offset"],
                    length=data["length"],
                    **{field: data[field] for field in ENTITY_FIELDS if field in data},
                )
            )
        except Exception as e:
            print(f"Skipping invalid saved entity {data}: {e}")
    return result


def trigger_matches(trigger: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", text, re.IGNORECASE) is not None


async def with_flood_wait(func, *args, **kwargs):
    while True:
        try:
            return await func(*args, **kwargs)
        except FloodWait as e:
            print(f"FloodWait: sleeping {e.value}s")
            await asyncio.sleep(e.value + 1)


@app.on_chat_join_request(allowed_chat)
async def handle_join_request(client: Client, join_request):
    user = join_request.from_user
    chat = join_request.chat

    full_name = html.escape(" ".join(part for part in (user.first_name, user.last_name) if part))

    text = (
        f"<b>Hey {full_name}</b>\n\n"
        "<b>You've requested to join the official Crypto escrow group</b>\n\n"
        "<b>Please remember these things:</b>\n\n"
        "• Make sure to check admins' usernames carefully before making any payment\n\n"
        "• Make sure to re-verify the escrow group from the main group of @escrow_pagal\n\n"
        "• Don't be in a hurry. Wait and observe the escrow group's activities; "
        "if you find anything wrong, report it to @pw_manager"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Escrow link", url=ESCROW_LINK)],
            [InlineKeyboardButton("Facing issue", url=SUPPORT_LINK)],
            [InlineKeyboardButton("Main channel", url=MAIN_CHANNEL_LINK)],
            [InlineKeyboardButton("👉🏻 Go to the chat", url=CHAT_LINK)],
        ]
    )

    try:
        await client.send_message(chat_id=user.id, text=text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
        print(f"Sent DM to {user.id} for join request to {chat.title}")
    except Exception as e:
        print(f"Could not DM user {user.id}: {e}")

    if AUTO_APPROVE:
        try:
            await client.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
            print(f"Auto-approved {user.id} into {chat.title}")
        except Exception as e:
            print(f"Could not auto-approve {user.id}: {e}")


@app.on_message(filters.command("filter") & allowed_chat)
async def add_filter(client: Client, message: Message):
    """/filter <trigger> <reply>, or reply to a message/picture with /filter <trigger> (admins only)"""
    try:
        if not await is_admin(client, message):
            await message.reply_text("❌ Only admins can use this command.")
            return
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return

    full_text = str(message.text or message.caption or "")
    trigger, reply_text = parse_trigger(command_args(message))
    source = message.reply_to_message
    file_id = None
    entities = []

    if reply_text:
        start = len(full_text.rstrip()) - len(reply_text)
        entities = shift_entities(message.entities or message.caption_entities, utf16_len(full_text[:start]))

    if source:
        file_id = media_file_id(source)
        if not reply_text:
            reply_text = str(source.text or source.caption or "")
            entities = serialize_entities(source.entities or source.caption_entities)
    elif message.media:
        file_id = media_file_id(message)

    usage = (
        "<b>Usage:</b>\n"
        "<code>/filter hello Welcome to the group!</code>\n"
        "<code>/filter \"multi word trigger\" Reply text</code>\n"
        "Or reply to a message/picture with <code>/filter hello</code>"
    )
    if not trigger or (not reply_text and not file_id):
        await message.reply_text(usage, parse_mode=enums.ParseMode.HTML)
        return

    if source and file_id is None and source.media and not reply_text:
        await message.reply_text("❌ That type of message can't be saved as a filter.")
        return

    chat_filters = _filters.setdefault(str(message.chat.id), {})
    chat_filters[trigger.lower()] = {
        "trigger": trigger,
        "text": reply_text,
        "entities": entities,
        "file_id": file_id,
    }
    save_filters()
    await message.reply_text(f"✅ Filter saved for <b>{html.escape(trigger)}</b>", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("filters") & allowed_chat)
async def list_filters(client: Client, message: Message):
    """List saved filters in this group (admins only)"""
    try:
        if not await is_admin(client, message):
            await message.reply_text("❌ Only admins can use this command.")
            return
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return

    chat_filters = _filters.get(str(message.chat.id), {})
    if not chat_filters:
        await message.reply_text("No filters saved in this group.")
        return
    lines = "\n".join(f"• <code>{html.escape(f['trigger'])}</code>" for f in chat_filters.values())
    await message.reply_text(f"<b>Filters in this group:</b>\n{lines}", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("stop") & allowed_chat)
async def stop_filter(client: Client, message: Message):
    """/stop <trigger> removes a filter (admins only)"""
    try:
        if not await is_admin(client, message):
            await message.reply_text("❌ Only admins can use this command.")
            return
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return

    trigger, _ = parse_trigger(command_args(message))
    if not trigger:
        await message.reply_text("<b>Usage:</b> <code>/stop hello</code>", parse_mode=enums.ParseMode.HTML)
        return

    chat_filters = _filters.get(str(message.chat.id), {})
    if chat_filters.pop(trigger.lower(), None) is None:
        await message.reply_text(f"❌ No filter named <b>{html.escape(trigger)}</b>", parse_mode=enums.ParseMode.HTML)
        return
    if not chat_filters:
        _filters.pop(str(message.chat.id), None)
    save_filters()
    await message.reply_text(f"🗑 Filter <b>{html.escape(trigger)}</b> removed", parse_mode=enums.ParseMode.HTML)


async def resolve_target(client: Client, message: Message):
    """User from a replied-to message, or from /cmd @username / user id. Returns (user_id, label) or (None, None)."""
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        return user.id, display_name(user)

    arg = command_args(message).strip().split(None, 1)
    if not arg:
        return None, None
    arg = arg[0]
    if arg.lstrip("-").isdigit():
        return int(arg), f"<code>{arg}</code>"
    try:
        user = await client.get_users(arg.lstrip("@"))
    except Exception as e:
        print(f"Could not resolve {arg}: {e}")
        return None, None
    if isinstance(user, list) or not user:
        return None, None
    return user.id, display_name(user)


@app.on_message(filters.command("admin") & (allowed_chat | filters.private))
async def add_bot_admin(client: Client, message: Message):
    """/admin @username | user id | reply (bot owner only)"""
    if not is_owner(message):
        await message.reply_text("❌ Only the bot owner can use this command.")
        return

    user_id, label = await resolve_target(client, message)
    if user_id is None:
        await message.reply_text(
            "<b>Usage:</b> <code>/admin @username</code>, <code>/admin 123456789</code>, or reply to a message with <code>/admin</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    if is_bot_admin(user_id):
        await message.reply_text(f"ℹ️ {label} is already an admin.", parse_mode=enums.ParseMode.HTML)
        return

    _bot_admins.add(user_id)
    save_bot_admins()
    await message.reply_text(f"✅ {label} is now an admin.", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("unadmin") & (allowed_chat | filters.private))
async def remove_bot_admin(client: Client, message: Message):
    """/unadmin @username | user id | reply (bot owner only)"""
    if not is_owner(message):
        await message.reply_text("❌ Only the bot owner can use this command.")
        return

    user_id, label = await resolve_target(client, message)
    if user_id is None:
        await message.reply_text(
            "<b>Usage:</b> <code>/unadmin @username</code>, <code>/unadmin 123456789</code>, or reply to a message with <code>/unadmin</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return
    if user_id not in _bot_admins:
        await message.reply_text(f"❌ {label} is not an admin added with /admin.", parse_mode=enums.ParseMode.HTML)
        return

    _bot_admins.discard(user_id)
    save_bot_admins()
    await message.reply_text(f"🗑 {label} is no longer an admin.", parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("admins") & (allowed_chat | filters.private))
async def list_bot_admins(client: Client, message: Message):
    """List admins added with /admin (bot owner only)"""
    if not is_owner(message):
        await message.reply_text("❌ Only the bot owner can use this command.")
        return

    lines = [f"👑 <code>{OWNER_ID}</code> (owner)"] + [f"• <code>{user_id}</code>" for user_id in sorted(_bot_admins)]
    await message.reply_text("<b>Bot admins:</b>\n" + "\n".join(lines), parse_mode=enums.ParseMode.HTML)


@app.on_message(filters.command("kickall") & allowed_chat)
async def kick_all_members(client: Client, message: Message):
    """Ask for confirmation before kicking all non-admin members (admins with ban rights only)"""
    chat = message.chat
    admin_id = OWNER_ID if is_anonymous_admin(message) else (message.from_user.id if message.from_user else None)

    if admin_id is None:
        return

    print(f"[COMMAND] /kickall received in {chat.title} from {admin_id}")

    try:
        if not await can_kickall(client, chat.id, admin_id):
            await message.reply_text("❌ You must be an admin with 'Ban users' permission to use this command.")
            return
        if not await can_ban(client, chat.id, await get_bot_id(client)):
            await message.reply_text("❌ I need to be an admin with 'Ban users' permission to do this.")
            return
    except Exception as e:
        print(f"Error checking admin status: {e}")
        await message.reply_text("❌ Could not check permissions. Try again later.")
        return

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Yes, remove all members", callback_data=f"kickall:yes:{admin_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"kickall:no:{admin_id}")],
        ]
    )
    await message.reply_text(
        "⚠️ <b>This will remove ALL non-admin members from this group.</b>\n\nAre you sure?",
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_callback_query(filters.regex(r"^kickall:(yes|no):(\d+)$") & allowed_chat)
async def kickall_confirm(client: Client, query: CallbackQuery):
    action, admin_id = query.matches[0].group(1), int(query.matches[0].group(2))
    message = query.message
    chat = message.chat

    if query.from_user.id != admin_id:
        await query.answer("This button isn't for you.", show_alert=True)
        return

    if action == "no":
        await message.edit_text("❎ Kickall cancelled.")
        await query.answer()
        return

    if chat.id in _kickall_running:
        await query.answer("Kickall is already running in this group.", show_alert=True)
        return

    try:
        if not await can_kickall(client, chat.id, admin_id):
            await query.answer("You no longer have permission to do this.", show_alert=True)
            return
    except Exception as e:
        print(f"Error checking admin status: {e}")
        await query.answer("Could not check permissions. Try again later.", show_alert=True)
        return

    _kickall_running.add(chat.id)
    await message.edit_text("🔄 Removing all members... This may take a while.")
    await query.answer()

    kicked_count = 0
    failed_count = 0
    admin_count = 0

    try:
        to_kick = []
        async for member in client.get_chat_members(chat.id):
            if member.status in ADMIN_STATUSES:
                admin_count += 1
            elif member.user:
                to_kick.append(member.user.id)

        for user_id in to_kick:
            try:
                await with_flood_wait(client.ban_chat_member, chat.id, user_id)
                await with_flood_wait(client.unban_chat_member, chat.id, user_id)
                kicked_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                failed_count += 1
                print(f"Failed to kick {user_id}: {e}")
    except Exception as e:
        await message.reply_text(f"❌ Error during member removal: {html.escape(str(e))}", parse_mode=enums.ParseMode.HTML)
        print(f"Error in kickall: {e}")
        return
    finally:
        _kickall_running.discard(chat.id)

    summary = (
        f"✅ <b>Kickall Complete</b>\n\n"
        f"👥 Members removed: {kicked_count}\n"
        f"👑 Admins kept: {admin_count}\n"
        f"❌ Failed: {failed_count}"
    )
    await message.reply_text(summary, parse_mode=enums.ParseMode.HTML)
    print(f"Kickall completed in {chat.title}: {kicked_count} removed, {admin_count} admins kept, {failed_count} failed")


@app.on_message(allowed_chat & (filters.text | filters.caption), group=1)
async def handle_mention(client: Client, message: Message):
    """DM users when they are tagged in a group"""
    chat = message.chat
    tagger = message.from_user
    text = message.text or message.caption
    entities = message.entities or message.caption_entities

    if not tagger or tagger.is_bot or not entities or text.startswith("/"):
        return

    bot_id = await get_bot_id(client)
    notified = set()
    link = message_link(message)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👉🏻 Go to message", url=link)]]) if link else None
    notify_text = (
        f"<b><u>You have been tagged</u></b>\n\n"
        f"<b>• From:</b> {display_name(tagger)}\n"
        f"<b>• Group:</b> {html.escape(chat.title or '')}"
    )

    for entity in entities:
        mentioned_user = None
        try:
            if entity.type == enums.MessageEntityType.MENTION:
                username = text[entity.offset:entity.offset + entity.length].lstrip("@")
                mentioned_user = await client.get_users(username)
            elif entity.type == enums.MessageEntityType.TEXT_MENTION:
                mentioned_user = entity.user
        except Exception as e:
            print(f"Could not resolve mention: {e}")
            continue

        if not mentioned_user or isinstance(mentioned_user, list):
            continue
        if mentioned_user.id in notified or mentioned_user.id in (tagger.id, bot_id) or mentioned_user.is_bot:
            continue
        if not tag_allowed(tagger.id):
            print(f"Tag rate limit hit for {tagger.id}")
            return

        notified.add(mentioned_user.id)
        try:
            await client.send_message(
                chat_id=mentioned_user.id,
                text=notify_text,
                reply_markup=keyboard,
                parse_mode=enums.ParseMode.HTML,
            )
            print(f"Sent tag notification to {mentioned_user.id} from {chat.title}")
        except Exception as e:
            print(f"Could not send tag notification to {mentioned_user.id}: {e}")


@app.on_message(allowed_chat & (filters.text | filters.caption), group=2)
async def reply_filters(client: Client, message: Message):
    """Reply with a saved filter when its trigger appears in a message.
    If the trigger message is itself a reply, answer the message it replied to."""
    chat_filters = _filters.get(str(message.chat.id))
    text = message.text or message.caption
    if not chat_filters or not text or text.startswith("/"):
        return
    if message.from_user and message.from_user.is_bot:
        return

    target = message.reply_to_message or message

    for saved in chat_filters.values():
        if not trigger_matches(saved["trigger"], text):
            continue
        entities = deserialize_entities(saved.get("entities"))
        try:
            if saved.get("file_id"):
                await target.reply_cached_media(
                    saved["file_id"],
                    caption=saved.get("text") or "",
                    caption_entities=entities or None,
                    parse_mode=enums.ParseMode.DISABLED,
                )
            else:
                await target.reply_text(
                    saved["text"],
                    entities=entities or None,
                    parse_mode=enums.ParseMode.DISABLED,
                )
        except Exception as e:
            print(f"Could not send filter '{saved['trigger']}' in {message.chat.id}: {e}")
        return


if __name__ == "__main__":
    print("Starting pwsec bot...")
    print("IMPORTANT: Make sure the bot has 'Privacy Mode' DISABLED in @BotFather")
    print("           and the bot is an admin in your groups!")
    app.run()
