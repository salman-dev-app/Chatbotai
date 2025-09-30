import os
import json
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- লগিং সেটআপ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ডেটা ফাইল এবং অনুবাদ ---
DATA_FILE = 'data.json'
TRANSLATIONS = {
    'en': {
        'welcome': "👋 Welcome! I'm an AI assistant powered by Google Gemini.",
        'api_error': "Sorry, I'm facing an issue with the AI service. Please try again later.",
        'safety_block': "I couldn't process that request due to safety guidelines.",
        'banned': "⛔ You are banned from using this bot.",
        'admin_only': "⚠️ This command is for admins only.",
        'group_unauthorized': "⚠️ This group is not authorized. Contact the admin for access. The bot will now leave.",
        # আপনি এখানে আরও টেক্সট যোগ করতে পারেন
    },
    'bn': {
        'welcome': "👋 স্বাগতম! আমি গুগল জেমিনি দ্বারা চালিত একজন এআই সহায়ক।",
        'api_error': "দুঃখিত, এআই পরিষেবাতে একটি সমস্যা হচ্ছে। অনুগ্রহ করে পরে আবার চেষ্টা করুন।",
        'safety_block': "নিরাপত্তা নির্দেশিকার কারণে আমি আপনার অনুরোধটি প্রসেস করতে পারিনি।",
        'banned': "⛔ আপনাকে এই বট ব্যবহার থেকে নিষিদ্ধ করা হয়েছে।",
        'admin_only': "⚠️ এই কমান্ড শুধুমাত্র অ্যাডমিনদের জন্য।",
        'group_unauthorized': "⚠️ এই গ্রুপটি অনুমোদিত নয়। অনুমোদনের জন্য অ্যাডমিনের সাথে যোগাযোগ করুন। বট এখন এই গ্রুপ থেকে বেরিয়ে যাবে।",
        # আপনি এখানে আরও টেক্সট যোগ করতে পারেন
    }
}

# --- ডেটা ম্যানেজমেন্ট ক্লাস ---
class BotData:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'authorized_group_ids': [], 'banned_user_ids': [], 'user_languages': {}, 'all_users': []}

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

    def is_user_banned(self, user_id: int) -> bool:
        return user_id in self.data['banned_user_ids']

    def is_group_authorized(self, group_id: int) -> bool:
        return group_id in self.data['authorized_group_ids']

# --- গ্লোবাল ভ্যারিয়েবল এবং ক্লায়েন্ট সেটআপ ---
bot_data = BotData(DATA_FILE)
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

try:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found")
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    logger.critical(f"FATAL: Failed to configure Gemini API - {e}")
    gemini_model = None

# --- হেল্পার ফাংশন ---
def get_text(user_id: int, key: str, **kwargs) -> str:
    lang = bot_data.get_user_language(user_id)
    text = TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, f"_{key}_")
    return text.format(**kwargs) if kwargs else text

# --- মেসেজ হ্যান্ডলার ---
async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type == 'group' and not bot_data.is_group_authorized(chat_id): return
    if bot_data.is_user_banned(user_id): return
    
    bot_data.add_user(user_id)

    if not gemini_model:
        await update.message.reply_text(get_text(user_id, 'api_error'))
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        response = gemini_model.generate_content(update.message.text)
        if not response.parts:
             await update.message.reply_text(get_text(user_id, 'safety_block'))
             return
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        await update.message.reply_text(get_text(user_id, 'api_error'))

# --- স্টার্ট কমান্ড ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_data.add_user(user_id)
    await update.message.reply_text(get_text(user_id, 'welcome'))

# --- মূল ফাংশন ---
def main():
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not all([TELEGRAM_TOKEN, ADMIN_ID, GEMINI_API_KEY]):
        logger.critical("FATAL ERROR: Required environment variables are missing!")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))
    
    logger.info("Bot is starting with Gemini API...")
    application.run_polling()

if __name__ == '__main__':
    main()
