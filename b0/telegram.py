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
        return ["Current Stats", "Goal", "Activity Level", "Supplements", "Health Conditions"]
    content = profile_path.read_text()
    missing = []
    fields = {
        "Current Stats": r"[\*\-] \*\*Current Stats[:]?\*\*[:]? (.+)",
        "Goal": r"[\*\-] \*\*Goal[:]?\*\*[:]? (.+)",
        "Activity Level": r"[\*\-] \*\*Activity Level[:]?\*\*[:]? (.+)",
        "Supplements": r"[\*\-] \*\*Supplements[:]?\*\*[:]? (.+)",
        "Health Conditions": r"[\*\-] \*\*Health Conditions[:]?\*\*[:]? (.+)"
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
    username = update.effective_user.username or update.effective_user.first_name or "unknown"
    priv = auth_mgr.authorize(uid, token, username)
    ident = auth_mgr.get_identifier(uid)
    
    if priv:
        await update.message.reply_text(f"Authenticated as {priv}! Your identifier is {ident}. There is a coach mode available via /coach.")
    else:
        await update.message.reply_text("Invalid or already used token.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, auth_mgr = update.effective_user.id, context.bot_data.get("auth_manager")
    if not auth_mgr.is_authorized(uid):
        await update.message.reply_text("Auth required.")
        return
    
    workspace = context.bot_data.get("workspace", ".")
    ident = auth_mgr.get_identifier(uid)
    user_agents[ident] = Agent(workspace=workspace, purpose=f"Chat {ident}", user_id=ident)
    user_modes[ident] = "normal"
    await update.message.reply_text("Returned to normal mode. There is a coach mode available via /coach.")

async def coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid, auth_mgr = update.effective_user.id, context.bot_data.get("auth_manager")
    if not auth_mgr.is_authorized(uid):
        await update.message.reply_text("Auth required.")
        return
    
    workspace = context.bot_data.get("workspace", ".")
    ident = auth_mgr.get_identifier(uid)
    # Initialize coach agent with special system prompt
    coach_agent = Agent(workspace=workspace, purpose=f"Coach {ident}", user_id=ident)
    
    coach_prompt = resources.files("b0.templates").joinpath("COACH.md").read_text()
    coach_agent.messages.append({"role": "system", "content": coach_prompt})
    
    user_agents[ident] = coach_agent
    
    # Check if all fields exist in profile
    profile_path = Path(workspace) / f"USER-{ident}.md"
    missing_fields = get_missing_coach_fields(profile_path)
    
    if missing_fields:
        user_modes[ident] = "coach_pending_goal"
        fields_str = ", ".join(missing_fields)
        text = f"Coach mode activated! But first, I need your Bodybuilding Profile & Goals. Missing: {fields_str}. Please provide the missing information (you can do it one by one)."
        
        # If the agent has a language preference, translate the system message
        if coach_agent.detected_lang and coach_agent.detected_lang.lower() not in ["english", "en"]:
            translation_prompt = f"Translate the following system message into {coach_agent.detected_lang}. Keep it professional and helpful:\n\n{text}"
            translated_text = await coach_agent.chat(translation_prompt)
            await update.message.reply_text(format_response(translated_text), parse_mode=constants.ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(text)
    else:
        user_modes[ident] = "coach"
        text = "Coach mode activated. Send me photos of your meals!"
        
        if coach_agent.detected_lang and coach_agent.detected_lang.lower() not in ["english", "en"]:
            translation_prompt = f"Translate the following system message into {coach_agent.detected_lang}. Keep it professional and helpful:\n\n{text}"
            translated_text = await coach_agent.chat(translation_prompt)
            await update.message.reply_text(format_response(translated_text), parse_mode=constants.ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(text)

async def exit_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    auth_mgr = context.bot_data.get("auth_manager")
    ident = auth_mgr.get_identifier(uid)
    if not user_modes.get(ident, "").startswith("coach"):
        await update.message.reply_text("Not in coach mode.")
        return
    
    await reset(update, context)

async def process_meal(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    ident = job.user_id # Note: user_id of the job will be set to composite ident
    chat_id = job.chat_id
    buffer = user_buffers.get(ident)
    if not buffer:
        return
    
    photos = buffer['photos']
    caption = buffer['caption']
    del user_buffers[ident]
    
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    
    # Analyze all images together
    mode = user_modes.get(ident)
    default_caption = "Analyze this meal." if mode == "coach" else "Analyze these images."
    content = [{"type": "text", "text": caption or default_caption}]
    for base64_img in photos:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}})
    
    response = await user_agents[ident].chat(content)
    
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
    ident = auth_mgr.get_identifier(uid)
    if ident not in user_agents:
        agent = Agent(workspace=workspace, purpose=f"Chat {ident}", user_id=ident)
        # Session start hint for Normal Mode
        if user_modes.get(ident) != "coach":
            agent.messages.append({
                "role": "system",
                "content": (
                    "A new session has started. Be a professional assistant.\n\n"
                    "CORE RULES:\n"
                    "1. Always observe the 'Preferred Language' in the user's profile and respond in that language.\n"
                    "2. If the user speaks a different language or requests one, immediately update the 'Preferred Language' field using update_profile_field.\n"
                    "3. Proactively update other profile fields whenever you learn new personal facts.\n"
                    "4. Do NOT proactively mention bodybuilding goals or health status in this Normal Mode. "
                    "Only mention that a specialized /coach mode is available for bodybuilding and meal analysis."
                )
            })
        user_agents[ident] = agent
    
    if user_modes.get(ident) == "coach_pending_goal":
        if update.message.text:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
            profile_path = Path(workspace) / f"USER-{ident}.md"
            missing_before = get_missing_coach_fields(profile_path)
            
            prompt = f"The user is providing profile information: {update.message.text}. Use your write_profile tool to update their profile under 'My Bodybuilding Profile & Goals:'. The fields are: Current Stats, Goal, Activity Level, Supplements, and Health Conditions. Only update the fields provided. Then, if any of these 5 fields are still missing (Missing: {', '.join(missing_before)}), acknowledge what you received and ask for the remaining ones. If all are filled, confirm you are ready for meal images."
            response = await user_agents[ident].chat(prompt)
            
            missing_after = get_missing_coach_fields(profile_path)
            if not missing_after:
                user_modes[ident] = "coach"
            
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
        
        if ident not in user_buffers:
            user_buffers[ident] = {'photos': [], 'caption': '', 'job': None}
        
        buffer = user_buffers[ident]
        buffer['photos'].append(base64_image)
        if caption:
            buffer['caption'] = (buffer['caption'] + " " + caption).strip()
            
        if buffer['job']:
            buffer['job'].schedule_removal()
        
        buffer['job'] = context.job_queue.run_once(process_meal, 10.0, user_id=ident, chat_id=update.effective_chat.id)
        return
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
        response = await user_agents[ident].chat(update.message.text)
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
