import logging
import secrets
import string
import uuid
import base64
import re
from pathlib import Path
import telegramify_markdown
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from .config import TELEGRAM_BOT_TOKEN
from .agent import Agent
from .auth import AuthManager

from importlib import resources
logger = logging.getLogger(__name__)
user_agents = {}
user_modes = {} # "cmd", "coach", "coach_pending_goal"
user_buffers = {} # uid -> {'photos': [], 'caption': '', 'job': Job}

def format_response(text: str) -> str:
    return telegramify_markdown.markdownify(text)

def get_missing_coach_fields(profile_path: Path) -> list[str]:
    if not profile_path.exists():
        return ["Current Stats", "Goal", "Activity Level", "Supplements"]
    content = profile_path.read_text()
    missing = []
    fields = {
        "Current Stats": r"[\*\-] \*\*Current Stats[:]?\*\*[:]? (.+)",
        "Goal": r"[\*\-] \*\*Goal[:]?\*\*[:]? (.+)",
        "Activity Level": r"[\*\-] \*\*Activity Level[:]?\*\*[:]? (.+)",
        "Supplements": r"[\*\-] \*\*Supplements[:]?\*\*[:]? (.+)"
    }
    for label, pattern in fields.items():
        match = re.search(pattern, content)
        if not (match and match.group(1).strip()):
            missing.append(label)
    return missing

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth_mgr = context.bot_data.get("auth_manager")
    uid = update.effective_user.id
    
    if auth_mgr.is_authorized(uid):
        await update.message.reply_text("Already authenticated.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /auth <token>")
        return
    
    token = context.args[0]
    priv = auth_mgr.authorize(uid, token)
    
    if priv:
        await update.message.reply_text(f"Authenticated as {priv}!")
    else:
        await update.message.reply_text("Invalid or already used token.")

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
    
    # Check if all fields exist in profile
    profile_path = Path(workspace) / f"USER-{uid}.md"
    missing_fields = get_missing_coach_fields(profile_path)
    
    if missing_fields:
        user_modes[uid] = "coach_pending_goal"
        fields_str = ", ".join(missing_fields)
        await update.message.reply_text(f"Coach mode activated! But first, I need your Bodybuilding Profile & Goals. Missing: {fields_str}. Please provide the missing information (you can do it one by one).")
    else:
        user_modes[uid] = "coach"
        await update.message.reply_text("Coach mode activated. Send me photos of your meals!")

async def exit_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not user_modes.get(uid, "").startswith("coach"):
        await update.message.reply_text("Not in coach mode.")
        return
    
    await reset(update, context)

async def process_meal(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    uid = job.user_id
    chat_id = job.chat_id
    buffer = user_buffers.get(uid)
    if not buffer:
        return
    
    photos = buffer['photos']
    caption = buffer['caption']
    del user_buffers[uid]
    
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    
    # Analyze all images together
    mode = user_modes.get(uid)
    default_caption = "Analyze this meal." if mode == "coach" else "Analyze these images."
    content = [{"type": "text", "text": caption or default_caption}]
    for base64_img in photos:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}})
    
    response = await user_agents[uid].chat(content)
    
    try:
        await context.bot.send_message(
            chat_id=chat_id, 
            text=format_response(response),
            parse_mode=constants.ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.warning(f"Failed to send markdown message: {e}")
        await context.bot.send_message(chat_id=chat_id, text=response)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, auth_mgr = update.effective_user.id, context.bot_data.get("auth_manager")
    if not auth_mgr.is_authorized(uid):
        await update.message.reply_text("Auth required.")
        return

    workspace = context.bot_data.get("workspace", ".")
    if uid not in user_agents:
        user_agents[uid] = Agent(workspace=workspace, purpose=f"Chat {uid}", user_id=str(uid))
    
    if user_modes.get(uid) == "coach_pending_goal":
        if update.message.text:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
            profile_path = Path(workspace) / f"USER-{uid}.md"
            missing_before = get_missing_coach_fields(profile_path)
            
            prompt = f"The user is providing profile information: {update.message.text}. Use your write_profile tool to update their profile under 'My Bodybuilding Profile & Goals:'. The fields are: Current Stats, Goal, Activity Level, and Supplements. Only update the fields provided. Then, if any of these 4 fields are still missing (Missing: {', '.join(missing_before)}), acknowledge what you received and ask for the remaining ones. If all are filled, confirm you are ready for meal images."
            response = await user_agents[uid].chat(prompt)
            
            missing_after = get_missing_coach_fields(profile_path)
            if not missing_after:
                user_modes[uid] = "coach"
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=format_response(response),
                parse_mode=constants.ParseMode.MARKDOWN_V2
            )
            return
        else:
            await update.message.reply_text("Please provide your profile information as text first.")
            return

    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_bytes).decode('utf-8')
        caption = update.message.caption or ""
        
        if uid not in user_buffers:
            user_buffers[uid] = {'photos': [], 'caption': '', 'job': None}
        
        buffer = user_buffers[uid]
        buffer['photos'].append(base64_image)
        if caption:
            buffer['caption'] = (buffer['caption'] + " " + caption).strip()
            
        if buffer['job']:
            buffer['job'].schedule_removal()
        
        buffer['job'] = context.job_queue.run_once(process_meal, 10.0, user_id=uid, chat_id=update.effective_chat.id)
        return
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
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

    auth_mgr = AuthManager(workspace)
    modified = False
    while len(auth_mgr.admin_tokens) < 2:
        auth_mgr.admin_tokens.append(str(uuid.uuid4()))
        modified = True
    while len(auth_mgr.user_tokens) < 3:
        auth_mgr.user_tokens.append(str(uuid.uuid4()))
        modified = True
    
    if modified:
        auth_mgr._save_tokens()
    
    if auth_mgr.tokens:
        print("\nAVAILABLE AUTH TOKENS:")
        for t in auth_mgr.admin_tokens:
            print(f"- {t} (ADMIN)")
        for t in auth_mgr.user_tokens:
            print(f"- {t} (USER)")
        print()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.bot_data.update({"workspace": workspace, "auth_manager": auth_mgr})
    
    app.add_handler(CommandHandler("auth", auth))
    app.add_handler(CommandHandler("new", reset))
    app.add_handler(CommandHandler("coach", coach))
    app.add_handler(CommandHandler("b0", exit_coach))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & (~filters.COMMAND), handle_message))
    app.run_polling()
