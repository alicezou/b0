import logging
import secrets
import string
import base64
import telegramify_markdown
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from .config import TELEGRAM_BOT_TOKEN
from .agent import Agent
from .auth import AuthManager

from importlib import resources
logger = logging.getLogger(__name__)
user_agents = {}
user_modes = {} # "cmd" or "coach"

def format_response(text: str) -> str:
    return telegramify_markdown.markdownify(text)

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pwd, auth_mgr = context.bot_data.get("password"), context.bot_data.get("auth_manager")
    uid = update.effective_user.id
    
    if auth_mgr.is_authorized(uid):
        await update.message.reply_text("Already authenticated.")
        return

    if not context.args or context.args[0] != pwd:
        await update.message.reply_text("Usage: /auth <password>")
        return
    
    priv = auth_mgr.authorize(uid)
    await update.message.reply_text(f"Authenticated as {priv}!")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, auth_mgr = update.effective_user.id, context.bot_data.get("auth_manager")
    if not auth_mgr.is_authorized(uid):
        await update.message.reply_text("Auth required.")
        return
    
    workspace = context.bot_data.get("workspace", ".")
    user_agents[uid] = Agent(workspace=workspace, purpose=f"Chat {uid}", user_id=str(uid))
    user_modes[uid] = "normal"
    await update.message.reply_text("Context flushed and returned to normal mode.")

async def coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, auth_mgr = update.effective_user.id, context.bot_data.get("auth_manager")
    if not auth_mgr.is_authorized(uid):
        await update.message.reply_text("Auth required.")
        return
    
    workspace = context.bot_data.get("workspace", ".")
    # Initialize coach agent with special system prompt
    coach_agent = Agent(workspace=workspace, purpose=f"Coach {uid}", user_id=str(uid))
    
    coach_prompt = resources.files("b0.templates").joinpath("COACH.md").read_text()
    coach_agent.messages.append({"role": "system", "content": coach_prompt})
    
    user_agents[uid] = coach_agent
    user_modes[uid] = "coach"
    await update.message.reply_text("Coach mode activated. Send me photos of your meals!")

async def exit_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if user_modes.get(uid) != "coach":
        await update.message.reply_text("Not in coach mode.")
        return
    
    await reset(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, auth_mgr = update.effective_user.id, context.bot_data.get("auth_manager")
    if not auth_mgr.is_authorized(uid):
        await update.message.reply_text("Auth required.")
        return

    workspace = context.bot_data.get("workspace", ".")
    if uid not in user_agents:
        user_agents[uid] = Agent(workspace=workspace, purpose=f"Chat {uid}", user_id=str(uid))
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    
    if update.message.photo:
        # Get the largest photo
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        
        caption = update.message.caption or ("Analyze this meal." if user_modes.get(uid) == "coach" else "Analyze this image.")
        content = [
            {"type": "text", "text": caption},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
        response = await user_agents[uid].chat(content)
    else:
        response = await user_agents[uid].chat(update.message.text)
    
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=format_response(response),
            parse_mode=constants.ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.warning(f"Failed to send markdown message: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

async def post_init(app):
    await app.bot.set_my_commands([
        ("auth", "Authorize"), 
        ("new", "Reset"),
        ("coach", "Bodybuilding Coach Mode"),
        ("b0", "Exit Coach Mode")
    ])

def run_bot(workspace: str = "."):
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return

    pwd = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    print(f"\nAUTH PASSWORD: {pwd}\n")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.bot_data.update({"workspace": workspace, "password": pwd, "auth_manager": AuthManager(workspace)})
    
    app.add_handler(CommandHandler("auth", auth))
    app.add_handler(CommandHandler("new", reset))
    app.add_handler(CommandHandler("coach", coach))
    app.add_handler(CommandHandler("b0", exit_coach))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & (~filters.COMMAND), handle_message))
    app.run_polling()
