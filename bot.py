#!/usr/bin/env python3
"""
Telegram Live Stream Bot
Manages and starts live streams using Stream Keys and RTMP server URLs
"""

import json
import os
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ChatType

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8762735192:AAFpaA7ydn8yFo5tOpZFCLcDucb95BF-UzA")
RTMP_SERVER = os.getenv("RTMP_SERVER", "rtmps://dc4-1.rtmp.t.me/s/")
DATA_FILE = "streams_data.json"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# Conversation states
WAITING_FOR_STREAM_NAME = 1
WAITING_FOR_STREAM_KEY = 2

# Admin user IDs (you can add more)
ADMIN_IDS = set()

# Global variables
group_id = None
streams = {}


def load_data():
    """Load streams data from file."""
    global streams
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r") as f:
            streams = json.load(f)
    else:
        streams = {}


def save_data():
    """Save streams data to file."""
    with open(DATA_FILE, "w") as f:
        json.dump(streams, f, indent=2)


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in ADMIN_IDS


async def set_admin_menu(application: Application):
    """Set admin menu button with commands."""
    admin_commands = [
        BotCommand("add_stream", "➕ Add a new stream"),
        BotCommand("remove_stream", "❌ Remove a stream"),
        BotCommand("list_admin", "📋 View all streams (admin)"),
        BotCommand("set_group", "🎯 Set the group for streaming"),
        BotCommand("help", "❓ Show help"),
    ]
    
    user_commands = [
        BotCommand("list_streams", "🎬 View available streams"),
        BotCommand("start_live", "▶️ Start a live stream"),
        BotCommand("stop_live", "⏹️ Stop live stream"),
        BotCommand("help", "❓ Show help"),
    ]
    
    # Set default commands for all users
    await application.bot.set_my_commands(user_commands)
    
    # Set admin commands with scope
    from telegram import BotCommandScopeAllPrivateChats
    await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeAllPrivateChats())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    user = update.effective_user
    chat = update.effective_chat
    
    # Add user as admin if first time
    if not ADMIN_IDS and chat.type == ChatType.PRIVATE:
        ADMIN_IDS.add(user.id)
        
        # Set admin menu button
        menu_button = MenuButtonCommands()
        await context.bot.set_chat_menu_button(user_id=user.id, menu_button=menu_button)
        
        await update.message.reply_text(
            f"✅ {user.first_name}, you are now the bot admin!\n\n"
            "🔧 Admin menu is now available in the toolbar.\n\n"
            "Use /help to see available commands."
        )
    elif chat.type == ChatType.PRIVATE:
        # Check if user is admin and set menu
        if is_admin(user.id):
            menu_button = MenuButtonCommands()
            await context.bot.set_chat_menu_button(user_id=user.id, menu_button=menu_button)
        
        await update.message.reply_text(
            f"👋 Hello {user.first_name}!\n\n"
            "Use /help to see available commands."
        )
    else:
        await update.message.reply_text(
            "🎬 Live Stream Bot is ready!\n"
            "Use /help to see available commands."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command."""
    user_id = update.effective_user.id
    
    if is_admin(user_id):
        help_text = """
🎬 **Live Stream Bot - Admin Commands**

**Stream Management:**
/add_stream - ➕ Add a new stream (name + key)
/remove_stream - ❌ Remove a stream
/list_admin - 📋 View all streams (admin only)

**Group Configuration:**
/set_group - 🎯 Set the group for streaming

**Streaming:**
/start_live [stream_name] - ▶️ Start a live stream
/stop_live - ⏹️ Stop current live stream

**Other:**
/help - ❓ Show this message

**Examples:**
1. /add_stream Gaming 3816417855:CN-jzYmObaLnaBl8gBa6Ag
2. /start_live Gaming
3. /remove_stream Gaming
"""
    else:
        help_text = """
🎬 **Live Stream Bot - User Commands**

**Available Commands:**
/list_streams - 🎬 View available streams
/start_live [stream_name] - ▶️ Start a live stream
/stop_live - ⏹️ Stop current live stream
/help - ❓ Show this message

**Example:**
1. /list_streams
2. /start_live Gaming
"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the group ID for streaming."""
    global group_id
    
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("❌ This command must be used in the group!")
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Only admins can use this command!")
        return
    
    group_id = update.effective_chat.id
    await update.message.reply_text(
        f"✅ Group ID set to: `{group_id}`\n"
        "The bot is now ready to manage live streams in this group!",
        parse_mode="Markdown"
    )


async def add_stream_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new stream."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Only admins can add streams!")
        return
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_add")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📝 Enter the stream name (e.g., 'Gaming', 'Music', 'Talk'):",
        reply_markup=reply_markup
    )
    return WAITING_FOR_STREAM_NAME


async def add_stream_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get stream name."""
    stream_name = update.message.text.strip()
    
    if stream_name in streams:
        await update.message.reply_text(f"❌ Stream '{stream_name}' already exists!")
        return ConversationHandler.END
    
    context.user_data["stream_name"] = stream_name
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_add")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Stream name: `{stream_name}`\n\n"
        "Now enter the Stream Key (e.g., 3816417855:CN-jzYmObaLnaBl8gBa6Ag):",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return WAITING_FOR_STREAM_KEY


async def add_stream_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get stream key and save."""
    stream_key = update.message.text.strip()
    stream_name = context.user_data.get("stream_name")
    
    if not stream_key or ":" not in stream_key:
        await update.message.reply_text("❌ Invalid stream key format! Must contain ':'")
        return WAITING_FOR_STREAM_KEY
    
    streams[stream_name] = stream_key
    save_data()
    
    keyboard = [[InlineKeyboardButton("📋 View All Streams", callback_data="view_all")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Stream '{stream_name}' added successfully!\n\n"
        f"Stream Key: `{stream_key}`",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def remove_stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a stream."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Only admins can remove streams!")
        return
    
    if not streams:
        await update.message.reply_text("📭 No streams to remove!")
        return
    
    if not context.args:
        # Show list of streams to remove
        keyboard = []
        for stream_name in streams.keys():
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {stream_name}",
                    callback_data=f"remove_{stream_name}"
                )
            ])
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Select a stream to remove:",
            reply_markup=reply_markup
        )
        return
    
    stream_name = " ".join(context.args)
    
    if stream_name not in streams:
        await update.message.reply_text(f"❌ Stream '{stream_name}' not found!")
        return
    
    del streams[stream_name]
    save_data()
    await update.message.reply_text(f"✅ Stream '{stream_name}' removed!")


async def list_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all streams (admin only)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Only admins can use this command!")
        return
    
    if not streams:
        await update.message.reply_text("📭 No streams added yet!")
        return
    
    message = "📋 **All Streams (Admin View):**\n\n"
    for i, (name, key) in enumerate(streams.items(), 1):
        message += f"{i}. **{name}**\n   Key: `{key}`\n\n"
    
    keyboard = [[InlineKeyboardButton("➕ Add New Stream", callback_data="add_new")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def list_streams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available streams."""
    if not streams:
        await update.message.reply_text("📭 No streams available!")
        return
    
    keyboard = []
    for stream_name in streams.keys():
        keyboard.append([
            InlineKeyboardButton(
                f"▶️ {stream_name}",
                callback_data=f"start_{stream_name}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎬 **Available Streams:**\n\nClick to view stream details:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def start_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a live stream."""
    global group_id
    
    if not group_id:
        await update.message.reply_text("❌ Group not configured! Admin must run /set_group in the group first.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /start_live [stream_name]\n"
            "Example: /start_live Gaming\n\n"
            "Use /list_streams to see available streams."
        )
        return
    
    stream_name = " ".join(context.args)
    
    if stream_name not in streams:
        await update.message.reply_text(f"❌ Stream '{stream_name}' not found!")
        return
    
    stream_key = streams[stream_name]
    
    try:
        # Start the live stream
        await context.bot.send_message(
            chat_id=group_id,
            text=f"🎬 **Starting Live Stream: {stream_name}**\n\n"
                 f"Server: `{RTMP_SERVER}`\n"
                 f"Stream Key: `{stream_key}`\n\n"
                 "Use your streaming app to connect and start broadcasting!",
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            f"✅ Live stream '{stream_name}' started in the group!\n\n"
            f"Server: `{RTMP_SERVER}`\n"
            f"Stream Key: `{stream_key}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error starting stream: {str(e)}")


async def stop_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop the live stream."""
    global group_id
    
    if not group_id:
        await update.message.reply_text("❌ Group not configured!")
        return
    
    try:
        await context.bot.send_message(
            chat_id=group_id,
            text="⏹️ **Live Stream Stopped**\n\nThank you for watching!"
        )
        
        await update.message.reply_text("✅ Live stream stopped!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error stopping stream: {str(e)}")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Handle stream start
    if query.data.startswith("start_"):
        stream_name = query.data.replace("start_", "")
        stream_key = streams.get(stream_name)
        
        if not stream_key:
            await query.edit_message_text("❌ Stream not found!")
            return
        
        keyboard = [[
            InlineKeyboardButton("🎬 Start This Stream", callback_data=f"confirm_start_{stream_name}"),
            InlineKeyboardButton("❌ Back", callback_data="back_to_list")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎬 **Stream: {stream_name}**\n\n"
            f"Server: `{RTMP_SERVER}`\n"
            f"Stream Key: `{stream_key}`\n\n"
            "Click below to start this stream in the group!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Handle confirm start
    elif query.data.startswith("confirm_start_"):
        stream_name = query.data.replace("confirm_start_", "")
        stream_key = streams.get(stream_name)
        
        if not stream_key:
            await query.edit_message_text("❌ Stream not found!")
            return
        
        try:
            # Start the live stream
            await context.bot.send_message(
                chat_id=group_id,
                text=f"🎬 **Starting Live Stream: {stream_name}**\n\n"
                     f"Server: `{RTMP_SERVER}`\n"
                     f"Stream Key: `{stream_key}`\n\n"
                     "Use your streaming app to connect and start broadcasting!",
                parse_mode="Markdown"
            )
            
            await query.edit_message_text(
                f"✅ Live stream '{stream_name}' started in the group!\n\n"
                f"Server: `{RTMP_SERVER}`\n"
                f"Stream Key: `{stream_key}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error starting stream: {str(e)}")
    
    # Handle remove stream
    elif query.data.startswith("remove_"):
        stream_name = query.data.replace("remove_", "")
        
        if not is_admin(user_id):
            await query.answer("❌ Only admins can remove streams!", show_alert=True)
            return
        
        if stream_name in streams:
            del streams[stream_name]
            save_data()
            await query.edit_message_text(f"✅ Stream '{stream_name}' removed!")
        else:
            await query.edit_message_text("❌ Stream not found!")
    
    # Handle back to list
    elif query.data == "back_to_list":
        keyboard = []
        for stream_name in streams.keys():
            keyboard.append([
                InlineKeyboardButton(
                    f"▶️ {stream_name}",
                    callback_data=f"start_{stream_name}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎬 **Available Streams:**\n\nClick to view stream details:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Handle view all
    elif query.data == "view_all":
        if not streams:
            await query.edit_message_text("📭 No streams added yet!")
            return
        
        message = "📋 **All Streams (Admin View):**\n\n"
        for i, (name, key) in enumerate(streams.items(), 1):
            message += f"{i}. **{name}**\n   Key: `{key}`\n\n"
        
        keyboard = [[InlineKeyboardButton("➕ Add New Stream", callback_data="add_new")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Handle cancel
    elif query.data == "cancel" or query.data == "cancel_add":
        await query.edit_message_text("❌ Cancelled!")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation."""
    await update.message.reply_text("❌ Cancelled!")
    return ConversationHandler.END


def main():
    """Start the bot."""
    load_data()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("set_group", set_group))
    application.add_handler(CommandHandler("list_admin", list_admin))
    application.add_handler(CommandHandler("list_streams", list_streams))
    application.add_handler(CommandHandler("start_live", start_live))
    application.add_handler(CommandHandler("stop_live", stop_live))
    application.add_handler(CommandHandler("remove_stream", remove_stream))
    
    # Add conversation handler for adding streams
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add_stream", add_stream_start)],
        states={
            WAITING_FOR_STREAM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_stream_name)
            ],
            WAITING_FOR_STREAM_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_stream_key)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(button_callback)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Set up admin menu on startup
    async def post_init(app):
        await set_admin_menu(app)
    
    application.post_init = post_init
    
    # Start the bot
    print("🤖 Bot started! Press Ctrl+C to stop.")
    application.run_polling()


if __name__ == "__main__":
    main()
