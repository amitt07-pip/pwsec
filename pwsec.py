# join_request_bot.py
import asyncio
from pyrogram import Client, enums, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# ====== CONFIG ======
import os

API_ID = int(os.getenv("API_ID", "26360975"))
API_HASH = os.getenv("API_HASH", "6de01e30d62ce2220eea62c17485e7f7")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8224526821:AAFzB_QxKazN70rsHxohWq9ze5inh2oC0io")
INVITE_LINK_1 = os.getenv("INVITE_LINK_1", "")
INVITE_LINK_2 = os.getenv("INVITE_LINK_2", "")
# ====================

app = Client("join_request_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_chat_join_request()
async def handle_join_request(client, join_request):
    user = join_request.from_user
    chat = join_request.chat

    # Get full name (first name + last name if available)
    full_name = user.first_name or ""
    if user.last_name:
        full_name = f"{full_name} {user.last_name}".strip()
    
    text = (
        f"**Hey {full_name}**\n\n"
        f"**You've requested to join official Crypto escrow group**\n\n"
        f"**Please remind these things-**\n\n"
        "• make sure to check admins username carefully before making any payment\n\n"
        "• Make sure to Re- verify escrow group from main group of @escrow_pagal\n\n"
        "• Dont be in hurry wait and observe escrow group activities if you found anything wrong report it to @pw_manager"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Escrow link", url="https://t.me/+GDQdTcMu5bkwOGY1")],
            [InlineKeyboardButton("Facing issue", url="https://t.me/pw_supportbot")],
            [InlineKeyboardButton("Main channel", url="https://t.me/escrow_pagal")],
            [InlineKeyboardButton("👉🏻 Go to the chat", url="https://t.me/+W2PxpjFlku0yMzFl")]
        ]
    )

    try:
        # Attempt to send DM
        await client.send_message(chat_id=user.id, text=text, reply_markup=keyboard, parse_mode=enums.ParseMode.MARKDOWN)
        print(f"Sent DM to {user.id} ({user.first_name}) for join request to {chat.title}")
    except Exception as e:
        # Common errors: Bot blocked by user, user hasn't started bot, privacy restriction.
        print(f"Could not DM user {user.id}: {e}")

    # OPTIONAL: Auto-approve the request after sending the DM.
    # Uncomment the next two lines if you want automatic approval.
    # try:
    #     await client.approve_chat_join_request(chat_id=chat.id, user_id=user.id)
    #     print(f"Auto-approved {user.id} into {chat.title}")
    # except Exception as e:
    #     print(f"Could not auto-approve {user.id}: {e}")

@app.on_message(filters.group & filters.text)
async def handle_mention(client, message: Message):
    """Handle when users are tagged/mentioned in groups"""
    chat = message.chat
    tagger = message.from_user
    
    # Skip if message is from bot itself or if there are no entities
    if not tagger or not message.entities:
        return
    
    # Check if message contains any user mentions
    has_mention = any(
        entity.type in [enums.MessageEntityType.MENTION, enums.MessageEntityType.TEXT_MENTION] 
        for entity in message.entities
    )
    
    if not has_mention:
        return
    
    # Get the message link
    # For public groups/channels, use username; for private, use chat_id
    if chat.username:
        message_link = f"https://t.me/{chat.username}/{message.id}"
    else:
        # For private groups, create link with chat_id
        message_link = f"https://t.me/c/{str(chat.id)[4:]}/{message.id}"
    
    # Get tagger's username or first name
    tagger_display = f"@{tagger.username}" if tagger.username else tagger.first_name
    
    # Find all mentioned users
    for entity in message.entities:
        if entity.type == enums.MessageEntityType.MENTION:
            # Extract username from message text (includes the @)
            username = message.text[entity.offset:entity.offset + entity.length]
            print(f"User mentioned via @username: {username}")
            
            # Try to get user by username and send notification
            try:
                # Remove @ from username
                username_clean = username.lstrip("@")
                mentioned_user = await client.get_users(username_clean)
                
                # Format the message with bold and underline (using HTML for proper formatting)
                text = (
                    f"<b><u>You have been tagged</u></b>\n\n"
                    f"<b>• From:</b> {tagger_display}\n"
                    f"<b>• Group:</b> {chat.title}"
                )
                
                keyboard = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("👉🏻 Go to message", url=message_link)]
                    ]
                )
                
                await client.send_message(
                    chat_id=mentioned_user.id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=enums.ParseMode.HTML
                )
                print(f"Sent tag notification to {mentioned_user.id} ({mentioned_user.first_name}) from {chat.title}")
            except Exception as e:
                print(f"Could not send tag notification for {username}: {e}")
            
        elif entity.type == enums.MessageEntityType.TEXT_MENTION:
            # User mentioned without public username (clicked from profile)
            mentioned_user = entity.user
            
            # Format the message with bold and underline (using HTML for proper formatting)
            text = (
                f"<b><u>You have been tagged</u></b>\n\n"
                f"<b>• From:</b> {tagger_display}\n"
                f"<b>• Group:</b> {chat.title}"
            )
            
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("👉🏻 Go to message", url=message_link)]
                ]
            )
            
            try:
                await client.send_message(
                    chat_id=mentioned_user.id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=enums.ParseMode.HTML
                )
                print(f"Sent tag notification to {mentioned_user.id} ({mentioned_user.first_name}) from {chat.title}")
            except Exception as e:
                print(f"Could not send tag notification to {mentioned_user.id}: {e}")

@app.on_message(filters.group)
async def debug_all_messages(client, message: Message):
    """Debug: Log all group messages to see if bot receives anything"""
    print(f"[DEBUG] Message received in {message.chat.title if message.chat else 'Unknown'}: {message.text[:50] if message.text else 'No text'}")

@app.on_message(filters.command("test") & filters.group)
async def test_command(client, message: Message):
    """Test if bot receives commands"""
    print(f"[TEST] Command received!")
    await message.reply_text("✅ Bot is receiving commands!")

@app.on_message(filters.command("kickall") & filters.group)
async def kick_all_members(client, message: Message):
    """Kick all members from the group except admins (Admin-only command)"""
    print(f"[COMMAND] /kickall received in {message.chat.title} from {message.from_user.first_name}")
    chat = message.chat
    user = message.from_user
    
    # Check if the command issuer is an admin
    try:
        member = await client.get_chat_member(chat.id, user.id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
            await message.reply_text("❌ You must be an admin to use this command.")
            return
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return
    
    # Send confirmation message
    await message.reply_text("🔄 Starting to remove all members... This may take a while.")
    
    kicked_count = 0
    failed_count = 0
    admin_count = 0
    
    try:
        # Get all chat members
        async for member in client.get_chat_members(chat.id):
            # Skip if member is admin, owner, or creator
            if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.CREATOR]:
                admin_count += 1
                continue
            
            # Skip if member is the bot itself
            if member.user.is_bot and member.user.id == (await client.get_me()).id:
                continue
            
            # Try to kick/ban and then unban the member
            try:
                await client.ban_chat_member(chat.id, member.user.id)
                await client.unban_chat_member(chat.id, member.user.id)
                kicked_count += 1
                print(f"Kicked {member.user.id} ({member.user.first_name}) from {chat.title}")
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
            except Exception as e:
                failed_count += 1
                print(f"Failed to kick {member.user.id}: {e}")
    
    except Exception as e:
        await message.reply_text(f"❌ Error during member removal: {str(e)}")
        print(f"Error in kickall command: {e}")
        return
    
    # Send summary
    summary = (
        f"✅ <b>Kickall Complete</b>\n\n"
        f"👥 Members removed: {kicked_count}\n"
        f"👑 Admins kept: {admin_count}\n"
        f"❌ Failed: {failed_count}"
    )
    await message.reply_text(summary, parse_mode=enums.ParseMode.HTML)
    print(f"Kickall completed in {chat.title}: {kicked_count} removed, {admin_count} admins kept, {failed_count} failed")

if __name__ == "__main__":
    print("Starting join_request_bot...")
    print(f"Monitoring mentions and join requests...")
    print("IMPORTANT: Make sure the bot has 'Privacy Mode' DISABLED in @BotFather")
    print("           and the bot is an admin in your groups!")
    app.run()
