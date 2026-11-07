# pwsec.py
import asyncio
import html
import os
import time
from collections import defaultdict, deque

from dotenv import load_dotenv
from pyrogram import Client, enums, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

TAG_LIMIT = int(os.getenv("TAG_LIMIT", "5"))
TAG_WINDOW_SECONDS = int(os.getenv("TAG_WINDOW_SECONDS", "60"))
# ====================

app = Client("join_request_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

ADMIN_STATUSES = (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR)

_bot_id = None
_tag_history = defaultdict(deque)
_kickall_running = set()


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


async def with_flood_wait(func, *args, **kwargs):
    while True:
        try:
            return await func(*args, **kwargs)
        except FloodWait as e:
            print(f"FloodWait: sleeping {e.value}s")
            await asyncio.sleep(e.value + 1)


@app.on_chat_join_request()
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


@app.on_message(filters.command("kickall") & filters.group)
async def kick_all_members(client: Client, message: Message):
    """Ask for confirmation before kicking all non-admin members (admins with ban rights only)"""
    chat = message.chat
    user = message.from_user

    if not user:
        await message.reply_text("❌ Anonymous admins can't use /kickall. Turn off 'Remain anonymous' and try again.")
        return

    print(f"[COMMAND] /kickall received in {chat.title} from {user.id}")

    try:
        if not await can_ban(client, chat.id, user.id):
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
            [InlineKeyboardButton("✅ Yes, remove all members", callback_data=f"kickall:yes:{user.id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"kickall:no:{user.id}")],
        ]
    )
    await message.reply_text(
        "⚠️ <b>This will remove ALL non-admin members from this group.</b>\n\nAre you sure?",
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML,
    )


@app.on_callback_query(filters.regex(r"^kickall:(yes|no):(\d+)$"))
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
        if not await can_ban(client, chat.id, admin_id):
            await query.answer("You no longer have 'Ban users' permission.", show_alert=True)
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


@app.on_message(filters.group & (filters.text | filters.caption), group=1)
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


if DEBUG:
    @app.on_message(filters.group, group=2)
    async def debug_all_messages(client: Client, message: Message):
        print(f"[DEBUG] Message in {message.chat.title if message.chat else 'Unknown'} (id {message.id})")


if __name__ == "__main__":
    print("Starting pwsec bot...")
    print("IMPORTANT: Make sure the bot has 'Privacy Mode' DISABLED in @BotFather")
    print("           and the bot is an admin in your groups!")
    app.run()
