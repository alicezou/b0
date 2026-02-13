import logging
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import re
from .config import TELEGRAM_BOT_TOKEN
from .agent import Agent

logger = logging.getLogger(__name__)

# Store agents by user_id
user_agents = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    workspace = context.bot_data.get("workspace", ".")

    if user_id not in user_agents:
        logger.info(f"Initializing new agent for user {user_id}")
        user_agents[user_id] = Agent(workspace=workspace, purpose=f"Telegram Chat with User {user_id}")
    
    agent = user_agents[user_id]
    
    # Show typing status
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    
    response = await agent.chat(user_text)
    
    # Simple escape for non-markdown parts would be ideal, but for now we try to send as is
    # or with a light escape. Most robust way is usually MarkdownV2 with specific escaping.
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=response,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except:
        # Fallback to plain text if markdown parsing fails
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

def run_bot(workspace: str = "."):
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Error: TELEGRAM_BOT_TOKEN not set in environment or .env")
        return

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.bot_data["workspace"] = workspace
    
    handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(handler)
    
    logger.info("Telegram bot is running...")
    application.run_polling()
