import logging
import re
import secrets
import string
import telegramify_markdown
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from .config import TELEGRAM_BOT_TOKEN
from .agent import Agent

logger = logging.getLogger(__name__)

# Store agents by user_id
user_agents = {}
# Authorized user IDs
authorized_users = set()

def format_response(text: str) -> str:
    """Converts standard Markdown to Telegram's MarkdownV2 using telegramify-markdown."""
    return telegramify_markdown.markdownify(text)

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = context.bot_data.get("password")
    if not context.args:
        await update.message.reply_text("Usage: /auth <password>")
        return
        
    if context.args[0] != password:
        await update.message.reply_text("Invalid password.")
        return
    
    authorized_users.add(update.effective_user.id)
    await update.message.reply_text("Authenticated successfully! You can now chat with the bot.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authorized_users:
        await update.message.reply_text("Please authenticate first using /auth <password>")
        return
    
    workspace = context.bot_data.get("workspace", ".")
    logger.info(f"Resetting agent for user {user_id}")
    
    # Flush current context and re-initialize
    user_agents[user_id] = Agent(workspace=workspace, purpose=f"Telegram Chat with User {user_id}", user_id=str(user_id))
    
    await update.message.reply_text("Context flushed. New agent session started and templates reloaded.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in authorized_users:
        await update.message.reply_text("Please authenticate first using /auth <password>")
        return

    user_text = update.message.text
    workspace = context.bot_data.get("workspace", ".")

    if user_id not in user_agents:
        logger.info(f"Initializing new agent for user {user_id}")
        user_agents[user_id] = Agent(workspace=workspace, purpose=f"Telegram Chat with User {user_id}", user_id=str(user_id))
    
    agent = user_agents[user_id]
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    response = await agent.chat(user_text)
    formatted_response = format_response(response)
    
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=formatted_response,
            parse_mode=constants.ParseMode.MARKDOWN_V2
        )
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

async def post_init(application):
    await application.bot.set_my_commands([
        ("auth", "Authenticate: /auth <password>"),
        ("new", "Reset agent session and reload templates"),
    ])

def run_bot(workspace: str = "."):
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Error: TELEGRAM_BOT_TOKEN not set in environment or .env")
        return

    # Generate a random alphanumeric password
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for _ in range(12))
    print(f"\n========================================\nTELEGRAM BOT AUTH PASSWORD: {password}\n========================================\n")

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    application.bot_data["workspace"] = workspace
    application.bot_data["password"] = password
    
    application.add_handler(CommandHandler("auth", auth))
    application.add_handler(CommandHandler("new", reset))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Telegram bot is running...")
    application.run_polling()
