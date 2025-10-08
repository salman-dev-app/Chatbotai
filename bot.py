# bot.py - GemBot Smart Auto Mode (private-only, multilingual intent detection)
import os
import json
import logging
import asyncio
import time
from collections import defaultdict, deque
from io import BytesIO

# Optional Pillow import (if not available we continue but image verification skipped)
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

import google.generativeai as genai

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Config
# -------------------------
DATA_FILE = 'data.json'
MEMORY_MAX = 3  # per-user memory size (last N messages)
COOLDOWN_SECONDS = 1.0  # simple per-user cooldown to avoid spam

# Simple translations for responses
TRANSLATIONS = {
    'en': {
        'welcome': "👋 Welcome! Send me a message and I'll help — I can generate images, summarize, rewrite, or chat.",
        'image_generating': "🖼️ Generating image... please wait.",
        'image_ready': "✅ Here's your image.",
        'image_analysis': "🔎 Image analysis:",
        'api_error': "Sorry, I'm facing an issue with the AI service. Please try again later.",
        'safety_block': "I couldn't process that request due to safety guidelines.",
        'usage_hint': "Tip: you can ask in English or Bengali. e.g. 'create a cute cat image', 'ছবি বানাও', 'Summarize: ...', 'Rewrite: ...'",
        'private_only': "I only work in private chats. Please message me directly."
    },
    'bn': {
        'welcome': "👋 স্বাগতম! আমাকে একটি মেসেজ পাঠান — আমি ছবি বানাতে, সারসংক্ষেপ করতে, রিরাইট করতে, বা সাধারণ চ্যাট করতে পারি।",
        'image_generating': "🖼️ ইমেজ তৈরি করা হচ্ছে... একটু অপেক্ষা করুন।",
        'image_ready': "✅ আপনার ইমেজ :",
        'image_analysis': "🔎 ইমেজ বিশ্লেষণ:",
        'api_error': "দুঃখিত, এআই সার্ভিসে ত্রুটি হচ্ছে। পরে চেষ্টা করুন।",
        'safety_block': "নিরাপত্তা নীতির কারণে অনুরোধটি প্রক্রিয়াকরণ করা যায়নি।",
        'usage_hint': "আপনি বাংলা/ইংরেজিতে লিখতে পারেন। উদাহরণ: 'ছবি বানাও', 'create a cat image', 'Summarize: ...', 'Rewrite: ...'",
        'private_only': "আমি শুধু প্রাইভেট চ্যাটে কাজ করি। অনুগ্রহ করে সরাসরি মেসেজ করুন।"
    }
}

def ttext(lang: str, key: str, **kwargs) -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key).format(**kwargs)

# -------------------------
# Data management (simple JSON)
# -------------------------
class BotData:
    def __init__(self, file_path=DATA_FILE):
        self.file_path = file_path
        self._load()

    def _load(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except Exception:
            self.data = {
                'all_users': []
            }
            self._save()

    def _save(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save data.json: %s", e)

    def add_user(self, user_id: int):
        if user_id not in self.data['all_users']:
            self.data['all_users'].append(user_id)
            self._save()

# Initialize data
bot_data = BotData()

# -------------------------
# Gemini setup (flexible)
# -------------------------
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # model name for text generative model; adjust if you use another
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        logger.info("Gemini configured")
    except Exception as e:
        logger.error("Failed to configure genai: %s", e)
        gemini_model = None
else:
    gemini_model = None
    logger.warning("GEMINI_API_KEY not set; AI features will not work until set.")

# -------------------------
# In-memory state
# -------------------------
user_memory = defaultdict(lambda: deque(maxlen=MEMORY_MAX))  # per-user last N messages
user_last_call = {}  # cooldown tracking

# -------------------------
# Intent detection keywords (English + Bengali)
# Modify/extend lists as needed
# -------------------------
IMG_KEYWORDS = [
    'image', 'img', 'picture', 'photo', 'draw', 'generate', 'create', 'paint', 'imagegen',
    'ছবি', 'চিত্র', 'ইমেজ', 'পেইন্ট', 'নকশা', 'ব্যান্দ্যান'  # last token is placeholder if needed
]
SUMMARIZE_KEYWORDS = ['summarize', 'summary', 'summarise', 'সারাংশ', 'সংক্ষেপ', 'মোটকথা']
REWRITE_KEYWORDS = ['rewrite', 'rephrase', 'improve', 'polish', 'reword', 'লিখন 개선', 'পুনর্লিখন', 'সুন্দরভাবে']

# -------------------------
# Helpers
# -------------------------
def detect_intent(text: str) -> str:
    """Return intent: 'image', 'summarize', 'rewrite', or 'chat'."""
    if not text or not text.strip():
        return 'chat'
    txt = text.lower()
    # check image first
    for kw in IMG_KEYWORDS:
        if kw in txt:
            return 'image'
    for kw in SUMMARIZE_KEYWORDS:
        if kw in txt:
            return 'summarize'
    for kw in REWRITE_KEYWORDS:
        if kw in txt:
            return 'rewrite'
    # fallback: if long text (>300 chars) maybe user wants summarize; but we default to chat
    if len(txt) > 800:
        # treat as summarize if phrases like "summarize" absent - but don't force; default chat
        return 'chat'
    return 'chat'

def can_call(user_id: int, cooldown: float = COOLDOWN_SECONDS) -> bool:
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
    start = 0
    while start < len(text):
        end = start + MAX_LENGTH
        await context.bot.send_message(chat_id=chat_id, text=text[start:end], parse_mode=constants.ParseMode.MARKDOWN)
        start = end
        await asyncio.sleep(0.2)

# -------------------------
# Gemini wrapper functions (flexible - handle different response shapes)
# -------------------------
async def generate_gemini_text(prompt: str, user_id: int | None = None) -> str | None:
    if not gemini_model:
        return None
    # include memory context if present
    try:
        memory = ""
        if user_id:
            mem = list(user_memory[user_id])
            if mem:
                memory = "Conversation history:\n" + "\n".join(mem) + "\n\n"
        full_prompt = f"{memory}User: {prompt}\nAssistant:"
        def call_api():
            return gemini_model.generate_content(full_prompt)
        resp = await asyncio.to_thread(call_api)
        # handle common attributes
        if hasattr(resp, 'text') and resp.text:
            return resp.text
        # sometimes resp.candidates or resp.candidates[0].output
        if hasattr(resp, 'candidates') and len(resp.candidates) > 0:
            cand = resp.candidates[0]
            # some libs use 'content' or 'output'
            if hasattr(cand, 'content'):
                return cand.content
            if hasattr(cand, 'output'):
                return cand.output
            return str(cand)
        return str(resp)
    except Exception as e:
        logger.error("Gemini text generation failed: %s", e)
        return None

async def generate_gemini_image(prompt: str) -> bytes | None:
    """Attempt to generate an image via genai. This function tries multiple common patterns."""
    if not gemini_model:
        return None
    try:
        def call_image():
            # If genai.Image.generate interface exists
            if hasattr(genai, 'Image') and hasattr(genai.Image, 'generate'):
                img_resp = genai.Image.generate(prompt=prompt, size="1024x1024")
                # try common attributes
                if hasattr(img_resp, 'data') and img_resp.data:
                    b64 = getattr(img_resp.data[0], 'b64_json', None)
                    if b64:
                        import base64
                        return base64.b64decode(b64)
                if hasattr(img_resp, 'images') and img_resp.images:
                    # some SDKs provide bytes as .bytes or .content
                    first = img_resp.images[0]
                    if hasattr(first, 'bytes'):
                        return first.bytes
                    if hasattr(first, 'content'):
                        return first.content
                return None
            # Fallback common function name
            if hasattr(genai, 'generate_image'):
                resp = genai.generate_image(prompt=prompt, size="1024x1024")
                # resp handling similar to above
                if isinstance(resp, (bytes, bytearray)):
                    return bytes(resp)
                if hasattr(resp, 'content'):
                    return resp.content
                return None
            return None
        img_bytes = await asyncio.to_thread(call_image)
        if isinstance(img_bytes, (bytes, bytearray)):
            return bytes(img_bytes)
        return None
    except Exception as e:
        logger.error("Gemini image generation failed: %s", e)
        return None

async def analyze_image_bytes(image_bytes: bytes) -> str | None:
    """Simple image analysis - this function currently uses a textual prompt.
    If Gemini supports multimodal inputs, you can improve it to pass the image directly.
    """
    if not gemini_model:
        return None
    try:
        # We can't attach binary directly in many clients; so give a generic prompt.
        prompt = (
            "You are an assistant that describes images. Provide a concise description of main objects, scene, "
            "colors, and any readable text if present. Example: 'A brown cat sitting on a sofa, sunlight from left.'\n\n"
            "Describe the image in short paragraphs."
        )
        # Ideally pass image via URL or multimodal input; here we call text generation to produce a description.
        def call_api():
            return gemini_model.generate_content(prompt)
        resp = await asyncio.to_thread(call_api)
        if hasattr(resp, 'text'):
            return resp.text
        if hasattr(resp, 'candidates') and resp.candidates:
            cand = resp.candidates[0]
            if hasattr(cand, 'content'):
                return cand.content
            if hasattr(cand, 'output'):
                return cand.output
            return str(cand)
        return str(resp)
    except Exception as e:
        logger.error("Image analysis failed: %s", e)
        return None

# -------------------------
# Bot Handlers
# -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = 'bn' if (user and user.language_code and user.language_code.startswith('bn')) else 'en'
    await update.message.reply_text(ttext(lang, 'welcome') + "\n\n" + ttext(lang, 'usage_hint'))

# When bot is added to a group — leave immediately (we don't work in groups)
async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                chat_id = update.effective_chat.id
                try:
                    # polite message then leave
                    await context.bot.send_message(chat_id=chat_id, text="This bot works only in private chats. Leaving the group.")
                except Exception:
                    pass
                try:
                    await context.bot.leave_chat(chat_id)
                except Exception as e:
                    logger.error("Failed to leave group %s: %s", chat_id, e)
    except Exception as e:
        logger.error("Error in bot_added_to_group: %s", e)

# Handle incoming photos (user sent image) -> analyze image
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ensure private chat only
    if update.effective_chat.type != 'private':
        # ignore or optionally notify user to DM the bot
        try:
            await update.message.reply_text(ttext('en', 'private_only'))
        except Exception:
            pass
        return

    user_id = update.effective_user.id
    if not can_call(user_id):
        return
    bot_data.add_user(user_id)

    # download largest photo
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        bio = BytesIO()
        await file.download_to_memory(out=bio)
        bio.seek(0)
        img_bytes = bio.read()
    except Exception as e:
        logger.error("Failed to download photo: %s", e)
        await update.message.reply_text(ttext('en', 'api_error'))
        return

    # optional PIL verification
    if PIL_AVAILABLE:
        try:
            Image.open(BytesIO(img_bytes)).verify()
        except Exception:
            logger.warning("PIL verify failed for uploaded image")

    await update.message.reply_text(ttext('en', 'image_analysis'))
    analysis = await analyze_image_bytes(img_bytes)
    if analysis is None:
        await update.message.reply_text(ttext('en', 'api_error'))
    else:
        await send_long_message(context, update.effective_chat.id, analysis)

# Unified text handler: detect intent and act accordingly
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only respond in private chats
    if update.effective_chat.type != 'private':
        # optionally tell user to DM the bot
        try:
            await update.message.reply_text(ttext('en', 'private_only'))
        except Exception:
            pass
        return

    user = update.effective_user
    user_id = user.id
    text = (update.message.text or "").strip()
    if not text:
        return

    if not can_call(user_id):
        return

    # Save user to DB
    bot_data.add_user(user_id)

    # Determine language hint for responses
    lang = 'bn' if ('বাংলা' in text or any(ch in text for ch in "অআইঈউঊএঐওঔকখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহড়ঢ়য়") ) else (user.language_code[:2] if user.language_code else 'en')
    # Append to memory
    user_memory[user_id].append(f"User: {text}")

    # detect intent
    intent = detect_intent(text)

    if intent == 'image':
        # for image prompt, we try to remove common lead words like "create", "generate", "ছবি" to build a clean prompt
        prompt = text
        # send feedback
        await update.message.reply_text(ttext(lang, 'image_generating'))
        img_bytes = await generate_gemini_image(prompt)
        if img_bytes is None:
            await update.message.reply_text(ttext(lang, 'api_error'))
            return
        bio = BytesIO(img_bytes)
        bio.seek(0)
        fname = "generated.png"
        try:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=InputFile(bio, filename=fname), caption=ttext(lang, 'image_ready'))
        except Exception as e:
            logger.error("Failed sending generated image: %s", e)
            # fallback: try send as document
            try:
                bio.seek(0)
                await context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(bio, filename=fname))
            except Exception as e2:
                logger.error("Failed to send image fallback: %s", e2)
                await update.message.reply_text(ttext(lang, 'api_error'))
        # Add assistant output to memory
        user_memory[user_id].append("Assistant: [generated an image]")
        return

    if intent == 'summarize':
        # extract content to summarize: remove the keyword if present
        # naive: split on colon or 'summarize' word
        content = text
        # try to extract after ':' if used
        if ':' in text:
            parts = text.split(':', 1)
            if len(parts) > 1 and parts[1].strip():
                content = parts[1].strip()
        prompt = f"Summarize the following text in concise bullet points or a short paragraph:\n\n{content}"
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
        summary = await generate_gemini_text(prompt, user_id=user_id)
        if summary is None:
            await update.message.reply_text(ttext(lang, 'api_error'))
            return
        user_memory[user_id].append(f"Assistant: {summary}")
        await send_long_message(context, update.effective_chat.id, ttext(lang, 'summarize_result', summary=summary) if 'summarize_result' in TRANSLATIONS.get(lang, {}) else summary)
        return

    if intent == 'rewrite':
        # extract content similar to summarize
        content = text
        if ':' in text:
            parts = text.split(':', 1)
            if len(parts) > 1 and parts[1].strip():
                content = parts[1].strip()
        prompt = f"Rewrite the following text to be clearer and more natural while preserving meaning:\n\n{content}"
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
        rewritten = await generate_gemini_text(prompt, user_id=user_id)
        if rewritten is None:
            await update.message.reply_text(ttext(lang, 'api_error'))
            return
        user_memory[user_id].append(f"Assistant: {rewritten}")
        await send_long_message(context, update.effective_chat.id, ttext(lang, 'rewrite_result', rewritten=rewritten) if 'rewrite_result' in TRANSLATIONS.get(lang, {}) else rewritten)
        return

    # Default: general chat
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)
    resp = await generate_gemini_text(text, user_id=user_id)
    if resp is None:
        await update.message.reply_text(ttext(lang, 'api_error'))
        return
    if resp == "":
        await update.message.reply_text(ttext(lang, 'safety_block'))
        return
    user_memory[user_id].append(f"Assistant: {resp}")
    await send_long_message(context, update.effective_chat.id, resp)

# Simple admin command to show count of users (optional)
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # restricted to bot owner? for simplicity allow only if from same account that created bot
    sender = update.effective_user
    if sender and sender.id:
        # send count
        await update.message.reply_text(f"Total users: {len(bot_data.data.get('all_users', []))}")

# -------------------------
# Main
# -------------------------
def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.critical("TELEGRAM_BOT_TOKEN not set in environment")
        return
    application = Application.builder().token(token).build()

    # Commands
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('stats', stats_command))

    # Only handle private messages for text and photos
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))

    # If bot is added to group: leave
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added_to_group))
    # Also ignore documents and others in groups (no handlers for group types)

    logger.info("GemBot Smart Auto Mode starting (private-only).")
    application.run_polling()

if __name__ == '__main__':
    main()
