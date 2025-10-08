# bot.py - Advanced AI Edition v2
import os
import json
import logging
import asyncio
from collections import deque, defaultdict
from io import BytesIO

import google.generativeai as genai
from PIL import Image

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, constants, InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------
# Config / Translations / Datafile
# ---------------------------
DATA_FILE = 'data.json'
MEMORY_MAX = 3  # per-user conversational context (last N messages)

TRANSLATIONS = {
    'en': {
        'welcome': "👋 Welcome to GemBot AI!\n\nI'm powered by Google Gemini — choose: ",
        'start_chat': '💬 Start Chat with AI', 'membership_info': '💎 Membership Info', 'contact_admin': '📞 Contact Admin',
        'chat_started': "💬 Great! Send me any message and I'll respond using AI.",
        'language_updated': "✅ Language updated to {lang}!",
        'usage_error': "⚠️ Usage: `{command}`",
        'api_error': "Sorry, I'm facing an issue with the AI service. Please try again later.",
        'safety_block': "I couldn't process that request due to safety guidelines.",
        'image_generating': "🖼️ Generating image... this can take a few seconds.",
        'image_ready': "✅ Here's your generated image:",
        'image_analysis': "🔎 Image analysis:",
        'summarize_result': "📝 Summary:\n\n{summary}",
        'rewrite_result': "✍️ Rewritten text:\n\n{rewritten}",
        'file_error': "⚠️ Could not process file.",
    },
    'bn': {
        'welcome': "👋 GemBot AI-তে আপনাকে স্বাগতম! নিচে অপশন দেখুন:",
        'start_chat': '💬 এআই চ্যাট শুরু করুন', 'membership_info': '💎 সদস্যপদ তথ্য', 'contact_admin': '📞 অ্যাডমিনের সাথে যোগাযোগ',
        'chat_started': "💬 চ্যাট শুরু করুন — আমি আছি সাহায্য করার জন্য।",
        'language_updated': "✅ ভাষা {lang} এ আপডেট হয়েছে!",
        'usage_error': "⚠️ ব্যবহার: `{command}`",
        'api_error': "দুঃখিত, এআই সার্ভিসে সমস্যা হচ্ছে। পরে চেষ্টা করুন।",
        'safety_block': "নিরাপত্তা নীতির কারণে অনুরোধটি প্রক্রিয়াকরণ করা যায়নি।",
        'image_generating': "🖼️ ইমেজ তৈরি করা হচ্ছে... অপেক্ষা করুন।",
        'image_ready': "✅ তোমার ইমেজ প্রস্তুত:",
        'image_analysis': "🔎 ইমেজ বিশ্লেষণ:",
        'summarize_result': "📝 সারসংক্ষেপ:\n\n{summary}",
        'rewrite_result': "✍️ পুনর্লিখিত পাঠ্য:\n\n{rewritten}",
        'file_error': "⚠️ ফাইল প্রক্রিয়াকরণ সম্ভব হল না।",
    }
}

# ---------------------------
# Data management
# ---------------------------
class BotData:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            default = {
                'authorized_group_ids': [],
                'banned_user_ids': [],
                'user_languages': {},
                'all_users': []
            }
            return default

    def _save(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save data: {e}")

    def add_user(self, user_id: int):
        if user_id not in self.data['all_users']:
            self.data['all_users'].append(user_id)
            self._save()

    def get_user_language(self, user_id: int) -> str:
        return self.data['user_languages'].get(str(user_id), 'en')

    def set_user_language(self, user_id: int, lang: str):
        self.data['user_languages'][str(user_id)] = lang
        self._save()

    def is_user_banned(self, user_id: int) -> bool:
        return user_id in self.data['banned_user_ids']

    def ban_user(self, user_id: int):
        if user_id not in self.data['banned_user_ids']:
            self.data['banned_user_ids'].append(user_id)
            self._save()

    def unban_user(self, user_id: int):
        if user_id in self.data['banned_user_ids']:
            self.data['banned_user_ids'].remove(user_id)
            self._save()

    def is_group_authorized(self, group_id: int) -> bool:
        return group_id in self.data['authorized_group_ids']

    def add_group(self, group_id: int):
        if group_id not in self.data['authorized_group_ids']:
            self.data['authorized_group_ids'].append(group_id)
            self._save()

    def remove_group(self, group_id: int):
        if group_id in self.data['authorized_group_ids']:
            self.data['authorized_group_ids'].remove(group_id)
            self._save()

# ---------------------------
# Globals
# ---------------------------
bot_data = BotData(DATA_FILE)
ADMIN_ID = int(os.getenv('ADMIN_ID', 0) or 0)

# Gemini setup
try:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in env")
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
    logger.info("Gemini configured")
except Exception as e:
    logger.critical(f"FATAL: Failed to configure Gemini API - {e}")
    gemini_model = None

# In-memory conversation memory (per user)
user_memory: dict[int, deque] = defaultdict(lambda: deque(maxlen=MEMORY_MAX))

# Simple in-memory rate-limiter (per-user): track last request time (seconds)
user_last_call: dict[int, float] = {}

# ---------------------------
# Helpers
# ---------------------------
def get_text(user_id: int, key: str, **kwargs) -> str:
    lang = bot_data.get_user_language(user_id)
    text = TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, f"_{key}_")
    return text.format(**kwargs) if kwargs else text

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def can_call(user_id: int, cooldown: float = 1.0) -> bool:
    """Simple cooldown per user to avoid accidental double-calls."""
    import time
    now = time.time()
    last = user_last_call.get(user_id, 0)
    if now - last < cooldown:
        return False
    user_last_call[user_id] = now
    return True

async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str):
    MAX_LENGTH = 4000
    if len(text) <= MAX_LENGTH:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=constants.ParseMode.MARKDOWN)
        return
    parts = []
    while len(text) > 0:
        if len(text) > MAX_LENGTH:
            part = text[:MAX_LENGTH]
            last_newline = part.rfind('\n')
            if last_newline != -1:
                parts.append(part[:last_newline])
                text = text[last_newline + 1:]
            else:
                parts.append(part)
                text = text[MAX_LENGTH:]
        else:
            parts.append(text)
            break
    for part in parts:
        await context.bot.send_message(chat_id=chat_id, text=part, parse_mode=constants.ParseMode.MARKDOWN)
        await asyncio.sleep(0.35)

# ---------------------------
# Gemini wrapper functions
# ---------------------------
async def generate_gemini_text(prompt: str, user_id: int | None = None) -> str | None:
    """Generate text response using Gemini. Non-blocking wrapper."""
    if not gemini_model:
        return None
    try:
        # Build a short prompt including last memory for context if present
        memory = ""
        if user_id:
            mem = list(user_memory[user_id])
            if mem:
                memory = "Context:\n" + "\n".join(mem) + "\n--\n"
        full_prompt = f"{memory}User: {prompt}\nAssistant:"
        # Use asyncio.to_thread to call sync library functions safely
        def call_api():
            # Using previous pattern: generate_content on model
            return gemini_model.generate_content(full_prompt)
        response = await asyncio.to_thread(call_api)
        # response may have .text or .candidate[0].content etc depending on lib; handle common shapes
        if hasattr(response, 'text'):
            return response.text
        if hasattr(response, 'candidates') and len(response.candidates) > 0:
            return getattr(response.candidates[0], 'output', str(response))
        return str(response)
    except Exception as e:
        logger.error(f"Gemini text generation failed: {e}")
        return None

async def generate_gemini_image(prompt: str) -> bytes | None:
    """Generate image bytes using Gemini image API.
    NOTE: adjust internal call if your genai version uses a different function name.
    """
    if not gemini_model:
        return None
    try:
        # There are multiple client interfaces; attempt common pattern
        def call_image():
            # Try genai.Image.generate or genai.generate_image style
            if hasattr(genai, 'Image') and hasattr(genai.Image, 'generate'):
                # Example: genai.Image.generate(prompt=prompt, size="1024x1024")
                img_resp = genai.Image.generate(prompt=prompt, size="1024x1024")
                # img_resp.images[0] or similar
                if hasattr(img_resp, 'data'):
                    # If data contains base64
                    data = img_resp.data[0].b64_json
                    import base64
                    return base64.b64decode(data)
                if hasattr(img_resp, 'images') and img_resp.images:
                    return img_resp.images[0].bytes
                return None
            # Fallback: try genai.generate_image
            if hasattr(genai, 'generate_image'):
                return genai.generate_image(prompt=prompt, size="1024x1024")
            # As last fallback, return None
            return None
        img_bytes = await asyncio.to_thread(call_image)
        # If returned an object with bytes attribute:
        if hasattr(img_bytes, 'content') and isinstance(img_bytes.content, (bytes, bytearray)):
            return bytes(img_bytes.content)
        if isinstance(img_bytes, (bytes, bytearray)):
            return bytes(img_bytes)
        return None
    except Exception as e:
        logger.error(f"Gemini image generation failed: {e}")
        return None

async def analyze_image_bytes(image_bytes: bytes) -> str | None:
    """Run a simple image analysis / caption using Gemini (if supported).
    We'll send a prompt like 'Describe the image' and attach base64 or a note.
    If the Gemini client supports direct image->text, integrate accordingly.
    """
    if not gemini_model:
        return None
    try:
        # Many generative models support multimodal calls; here we fallback to sending a textual prompt.
        # A robust implementation would upload the image to a hosting and pass the URL to gemini.
        # For now create a small prompt asking for description.
        prompt = "Describe the following image briefly and mention main objects, scene, and possible text in the image."
        # If the genai library supports image input in the generate_content call, use it.
        def call_api():
            return gemini_model.generate_content(prompt)
        response = await asyncio.to_thread(call_api)
        if hasattr(response, 'text'):
            return response.text
        if hasattr(response, 'candidates') and len(response.candidates) > 0:
            return getattr(response.candidates[0], 'output', str(response))
        return str(response)
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return None

# ---------------------------
# Command handlers
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if bot_data.is_user_banned(user_id):
        return
    bot_data.add_user(user_id)
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'start_chat'), callback_data='start_chat')],
        [InlineKeyboardButton(get_text(user_id, 'membership_info'), callback_data='membership_info')],
        [InlineKeyboardButton(get_text(user_id, 'contact_admin'), url='https://t.me/otakuosenpai')]
    ]
    await update.message.reply_text(get_text(user_id, 'welcome'), reply_markup=InlineKeyboardMarkup(keyboard))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [[InlineKeyboardButton('🇬🇧 English', callback_data='set_lang_en')],
                [InlineKeyboardButton('🇧🇩 বাংলা', callback_data='set_lang_bn')]]
    await update.message.reply_text(get_text(user_id, 'welcome'), reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    txt = (
        "/ask <question> — Ask AI (groups allowed only if authorized)\n"
        "/imagine <prompt> — Generate an image\n"
        "/summarize <text> — Summarize given text\n"
        "/rewrite <text> — Re-write / improve text\n"
    )
    await update.message.reply_text(txt)

# Text ask (group or private) - keeps context
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    if bot_data.is_user_banned(user_id): return
    if chat.type in ['group', 'supergroup'] and not bot_data.is_group_authorized(chat.id):
        return
    if not context.args:
        await update.message.reply_text(get_text(user_id, 'usage_error', command='/ask <your question>'))
        return
    if not can_call(user_id):
        return
    question = " ".join(context.args)
    # store in memory
    user_memory[user_id].append(f"User: {question}")
    await context.bot.send_chat_action(chat_id=chat.id, action=constants.ChatAction.TYPING)
    resp = await generate_gemini_text(question, user_id=user_id)
    if resp is None:
        await update.message.reply_text(get_text(user_id, 'api_error'))
        return
    if resp == "":
        await update.message.reply_text(get_text(user_id, 'safety_block'))
        return
    user_memory[user_id].append(f"Assistant: {resp}")
    await send_long_message(context, chat.id, resp)

# Private message handler (text)
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if bot_data.is_user_banned(user_id): return
    bot_data.add_user(user_id)
    msg_text = update.message.text or ""
    if not msg_text.strip():
        await update.message.reply_text(get_text(user_id, 'usage_error', command='send a text message'))
        return
    if not can_call(user_id):
        return
    user_memory[user_id].append(f"User: {msg_text}")
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    resp = await generate_gemini_text(msg_text, user_id=user_id)
    if resp is None:
        await update.message.reply_text(get_text(user_id, 'api_error'))
        return
    if resp == "":
        await update.message.reply_text(get_text(user_id, 'safety_block'))
        return
    user_memory[user_id].append(f"Assistant: {resp}")
    await send_long_message(context, chat_id, resp)

# ---------------------------
# New: Image generation command
# ---------------------------
async def imagine_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if bot_data.is_user_banned(user_id): return
    if not context.args:
        await update.message.reply_text(get_text(user_id, 'usage_error', command='/imagine <prompt>'))
        return
    if not can_call(user_id, cooldown=2.0):
        return
    prompt = " ".join(context.args)
    await update.message.reply_text(get_text(user_id, 'image_generating'))
    img_bytes = await generate_gemini_image(prompt)
    if img_bytes is None:
        await update.message.reply_text(get_text(user_id, 'api_error'))
        return
    # send as file
    bio = BytesIO(img_bytes)
    bio.seek(0)
    image_file = InputFile(bio, filename="generated.png")
    await context.bot.send_photo(chat_id=chat_id, photo=image_file, caption=get_text(user_id, 'image_ready'))

# ---------------------------
# New: handle incoming photos (analyze)
# ---------------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if bot_data.is_user_banned(user_id): return
    if not can_call(user_id, cooldown=1.0):
        return
    # get largest size photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    bio = BytesIO()
    await file.download_to_memory(out=bio)
    bio.seek(0)
    image_bytes = bio.read()
    # Try a PIL quick resize for safety if needed (not mandatory)
    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()
    except Exception:
        logger.warning("Received photo but PIL failed to verify")
    await update.message.reply_text(get_text(user_id, 'image_analysis'))
    analysis = await analyze_image_bytes(image_bytes)
    if analysis is None:
        await update.message.reply_text(get_text(user_id, 'api_error'))
    else:
        await send_long_message(context, chat_id, analysis)

# ---------------------------
# Summarize and Rewrite
# ---------------------------
async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(get_text(user_id, 'usage_error', command='/summarize <text>'))
        return
    text = " ".join(context.args)
    prompt = f"Summarize the following text in a concise paragraph:\n\n{text}"
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    summary = await generate_gemini_text(prompt, user_id=user_id)
    if summary is None:
        await update.message.reply_text(get_text(user_id, 'api_error'))
        return
    await update.message.reply_text(get_text(user_id, 'summarize_result', summary=summary))

async def rewrite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(get_text(user_id, 'usage_error', command='/rewrite <text>'))
        return
    text = " ".join(context.args)
    prompt = f"Rewrite the following text to be clearer and more natural, preserving meaning:\n\n{text}"
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    rewritten = await generate_gemini_text(prompt, user_id=user_id)
    if rewritten is None:
        await update.message.reply_text(get_text(user_id, 'api_error'))
        return
    await update.message.reply_text(get_text(user_id, 'rewrite_result', rewritten=rewritten))

# ---------------------------
# File handler (plain text)
# ---------------------------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    doc = update.message.document
    if not doc:
        return
    # Only accept small text files for now
    if doc.file_size > 2_000_000:  # 2MB limit
        await update.message.reply_text("File too large. Please send a smaller text file.")
        return
    file = await context.bot.get_file(doc.file_id)
    bio = BytesIO()
    await file.download_to_memory(out=bio)
    bio.seek(0)
    try:
        raw = bio.read().decode('utf-8', errors='ignore')
    except Exception:
        await update.message.reply_text(get_text(user_id, 'file_error'))
        return
    # Summarize file content
    prompt = f"Summarize the important points from the following text:\n\n{raw}"
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    summary = await generate_gemini_text(prompt, user_id=user_id)
    if summary is None:
        await update.message.reply_text(get_text(user_id, 'api_error'))
        return
    await update.message.reply_text(get_text(user_id, 'summarize_result', summary=summary))

# ---------------------------
# Callback button handler (language / admin broadcast / menu)
# ---------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == 'start_chat':
        await query.edit_message_text(get_text(user_id, 'chat_started'))
    elif data == 'membership_info':
        await query.edit_message_text("Contact admin: @otakuosenpai")
    elif data.startswith('set_lang_'):
        lang_code = data.split('_')[-1]
        lang_name = "English" if lang_code == "en" else "বাংলা"
        bot_data.set_user_language(user_id, lang_code)
        await query.edit_message_text(get_text(user_id, 'language_updated', lang=lang_name))
    elif data == 'broadcast_confirm_yes':
        if not is_admin(user_id):
            return
        message = context.user_data.get('broadcast_message')
        if not message:
            await query.edit_message_text("Error: Message not found.")
            return
        sent = 0
        for uid in bot_data.data['all_users']:
            try:
                await context.bot.send_message(chat_id=uid, text=message)
                sent += 1
            except Exception as e:
                logger.error(f"Broadcast to {uid} failed: {e}")
        await query.edit_message_text(f"✅ Broadcast sent to {sent} users.")
    elif data == 'broadcast_confirm_no':
        if not is_admin(user_id):
            return
        await query.edit_message_text("❌ Broadcast cancelled.")

# ---------------------------
# Admin & group handlers (reuse your earlier functions)
# ---------------------------
async def admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⚠️ This command is for admins only.")
        return False
    return True

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    await update.message.reply_text(
        "Admin commands:\n/addgroup <id>\n/removegroup <id>\n/listgroups\n/ban <user_id>\n/unban <user_id>\n/listbanned\n/broadcast <msg>\n/stats"
    )

async def addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args:
        await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/addgroup <group_id>'))
        return
    try:
        gid = int(context.args[0])
        bot_data.add_group(gid)
        await update.message.reply_text(f"✅ Group `{gid}` authorized!", parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("Invalid Group ID.")

async def removegroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args:
        await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/removegroup <group_id>'))
        return
    try:
        gid = int(context.args[0])
        bot_data.remove_group(gid)
        await update.message.reply_text(f"✅ Group `{gid}` unauthorized!", parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("Invalid Group ID.")

async def listgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    groups = bot_data.data['authorized_group_ids']
    if not groups:
        await update.message.reply_text("No authorized groups yet.")
        return
    await update.message.reply_text("Authorized groups:\n" + "\n".join(map(str, groups)))

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args:
        await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/ban <user_id>'))
        return
    try:
        uid = int(context.args[0])
        bot_data.ban_user(uid)
        await update.message.reply_text(f"✅ User `{uid}` banned!", parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("Invalid User ID.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args:
        await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/unban <user_id>'))
        return
    try:
        uid = int(context.args[0])
        bot_data.unban_user(uid)
        await update.message.reply_text(f"✅ User `{uid}` unbanned!", parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("Invalid User ID.")

async def listbanned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    users = bot_data.data['banned_user_ids']
    if not users:
        await update.message.reply_text("No banned users.")
        return
    await update.message.reply_text("Banned users:\n" + "\n".join(map(str, users)))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    await update.message.reply_text(
        f"Stats:\nTotal users: {len(bot_data.data['all_users'])}\nAuthorized groups: {len(bot_data.data['authorized_group_ids'])}\nBanned users: {len(bot_data.data['banned_user_ids'])}"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/broadcast <msg>'))
        return
    context.user_data['broadcast_message'] = message
    keyboard = [[InlineKeyboardButton("Yes, Send", callback_data='broadcast_confirm_yes'), InlineKeyboardButton("No, Cancel", callback_data='broadcast_confirm_no')]]
    await update.message.reply_text(f"Send to {len(bot_data.data['all_users'])} users?\n\n{message}", reply_markup=InlineKeyboardMarkup(keyboard))

# When bot added to group -> leave if unauthorized
async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            chat_id = update.effective_chat.id
            if not bot_data.is_group_authorized(chat_id):
                try:
                    await context.bot.send_message(chat_id=chat_id, text="This group is not authorized. Contact admin.")
                    await context.bot.leave_chat(chat_id)
                except Exception as e:
                    logger.error(f"Error leaving unauthorized group {chat_id}: {e}")

# ---------------------------
# Main
# ---------------------------
def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.critical("TELEGRAM_BOT_TOKEN not set in env")
        return
    application = Application.builder().token(token).build()

    # Basic commands
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', language_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('ask', ask_command))
    application.add_handler(CommandHandler('imagine', imagine_command))
    application.add_handler(CommandHandler('summarize', summarize_command))
    application.add_handler(CommandHandler('rewrite', rewrite_command))

    # Admin
    application.add_handler(CommandHandler('admin', admin_command))
    application.add_handler(CommandHandler('addgroup', addgroup))
    application.add_handler(CommandHandler('removegroup', removegroup))
    application.add_handler(CommandHandler('listgroups', listgroups))
    application.add_handler(CommandHandler('ban', ban))
    application.add_handler(CommandHandler('unban', unban))
    application.add_handler(CommandHandler('listbanned', listbanned))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('broadcast', broadcast))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Callback
    application.add_handler(CallbackQueryHandler(button_callback))

    # New chat members
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added_to_group))

    logger.info("Advanced GemBot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
