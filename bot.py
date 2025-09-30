import os
import json
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
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
        'welcome': "👋 Welcome to GemBot AI!\n\nI'm powered by Google Gemini and can help you with any questions. Choose an option below:",
        'start_chat': '💬 Start Chat with AI', 'membership_info': '💎 Membership Info', 'contact_admin': '📞 Contact Admin',
        'membership_text': "💎 **Membership Information**\n\nTo use this bot in your group, contact the admin (@otakuosenpai) for authorization.",
        'help_text': "📖 **How to Use This Bot**\n\n**Available Commands:**\n/start - Main menu\n/language - Change language\n/help - Show this message\n/myinfo - View your info\n/about - About this bot\n\n**Chat:** Just send me any message!",
        'myinfo_text': "👤 **Your Information**\n\nUser ID: `{user_id}`\nSelected Language: `{language}`",
        'about_text': "🤖 **About This Bot**\n\nAI assistant powered by Google Gemini.\nMade with ❤️ by MD Salman",
        'choose_language': "🌐 Choose your preferred language:", 'language_updated': "✅ Language updated to {lang}!",
        'chat_started': "💬 Great! Send me any message and I'll respond using AI.", 'banned': "⛔ You are banned from using this bot.",
        'admin_only': "⚠️ This command is for admins only.", 'group_added': "✅ Group `{group_id}` has been authorized!",
        'group_removed': "✅ Group `{group_id}` has been unauthorized!", 'group_list': "📋 **Authorized Groups** ({count}):\n\n`{groups}`",
        'no_groups': "No authorized groups yet.", 'user_banned': "✅ User `{user_id}` has been banned!",
        'user_unbanned': "✅ User `{user_id}` has been unbanned!", 'banned_list': "🚫 **Banned Users** ({count}):\n\n`{users}`",
        'no_banned': "No banned users.", 'stats_text': "📊 **Bot Statistics**\n\nTotal Users: {users}\nAuthorized Groups: {groups}\nBanned Users: {banned}",
        'broadcast_confirm': "📢 Send this message to {count} users?\n\n`{message}`", 'broadcast_sent': "✅ Broadcast sent to {count} users!",
        'broadcast_cancelled': "❌ Broadcast cancelled.", 'group_unauthorized': "⚠️ This group is not authorized. Contact @otakuosenpai for access. The bot will now leave.",
        'admin_help': "🔧 **Admin Panel**\n\n/addgroup `<id>`\n/removegroup `<id>`\n/listgroups\n/ban `<user_id>`\n/unban `<user_id>`\n/listbanned\n/broadcast `<msg>`\n/stats",
        'api_error': "Sorry, I'm facing an issue with the AI service. Please try again later.", 'safety_block': "I couldn't process that request due to safety guidelines.",
        'usage_error': "⚠️ Usage: `{command}`"
    },
    'bn': {
        'welcome': "👋 GemBot AI-তে স্বাগতম!\n\nআমি গুগল জেমিনি দ্বারা চালিত এবং যেকোনো প্রশ্নে আপনাকে সাহায্য করতে পারি। নিচের একটি অপশন বেছে নিন:",
        'start_chat': '💬 এআই চ্যাট শুরু করুন', 'membership_info': '💎 সদস্যপদ তথ্য', 'contact_admin': '📞 অ্যাডমিনের সাথে যোগাযোগ',
        'language_updated': "✅ ভাষা {lang} তে পরিবর্তিত হয়েছে!",
        # ... (এখানে আপনার সম্পূর্ণ বাংলা অনুবাদ যোগ করুন) ...
    }
}

# --- ডেটা ম্যানেজমেন্ট ক্লাস ---
class BotData:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self._load()
    def _load(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'authorized_group_ids': [], 'banned_user_ids': [], 'user_languages': {}, 'all_users': []}
    def _save(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f: json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e: logger.error(f"Failed to save data: {e}")
    def add_user(self, user_id: int):
        if user_id not in self.data['all_users']: self.data['all_users'].append(user_id); self._save()
    def get_user_language(self, user_id: int) -> str: return self.data['user_languages'].get(str(user_id), 'en')
    def set_user_language(self, user_id: int, lang: str): self.data['user_languages'][str(user_id)] = lang; self._save()
    def is_user_banned(self, user_id: int) -> bool: return user_id in self.data['banned_user_ids']
    def ban_user(self, user_id: int):
        if user_id not in self.data['banned_user_ids']: self.data['banned_user_ids'].append(user_id); self._save()
    def unban_user(self, user_id: int):
        if user_id in self.data['banned_user_ids']: self.data['banned_user_ids'].remove(user_id); self._save()
    def is_group_authorized(self, group_id: int) -> bool: return group_id in self.data['authorized_group_ids']
    def add_group(self, group_id: int):
        if group_id not in self.data['authorized_group_ids']: self.data['authorized_group_ids'].append(group_id); self._save()
    def remove_group(self, group_id: int):
        if group_id in self.data['authorized_group_ids']: self.data['authorized_group_ids'].remove(group_id); self._save()

# --- গ্লোবাল ভ্যারিয়েবল এবং ক্লায়েন্ট সেটআপ ---
bot_data = BotData(DATA_FILE)
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
try:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEY: raise ValueError("GEMINI_API_KEY not found")
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
def is_admin(user_id: int) -> bool: return user_id == ADMIN_ID

# --- ইউজার কমান্ড হ্যান্ডলার ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (আপনার আগের start ফাংশন)
# ... (বাকি সব ইউজার কমান্ডের ফাংশন: language_command, help_command, myinfo_command, about_command)

# --- অ্যাডমিন কমান্ড হ্যান্ডলার ---
async def admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # ... (আপনার আগের admin_check ফাংশন)
# ... (বাকি সব অ্যাডমিন কমান্ডের ফাংশন: admin_command, addgroup, removegroup, listgroups, ban, unban, listbanned, stats, broadcast)

# --- বাটন হ্যান্ডলার ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (আপনার আগের button_callback ফাংশন)

# --- মেসেজ হ্যান্ডলার (নতুন লজিক সহ) ---
async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    message = update.message

    # ব্যক্তিগত চ্যাটে সবসময় উত্তর দেবে
    if chat.type == 'private':
        if bot_data.is_user_banned(user_id): return
        bot_data.add_user(user_id)
    
    # গ্রুপের জন্য শর্তসাপেক্ষে উত্তর দেবে
    elif chat.type in ['group', 'supergroup']:
        if not bot_data.is_group_authorized(chat.id): return
        if bot_data.is_user_banned(user_id): return

        bot_username = context.bot.username
        text = message.text.lower() if message.text else ""
        
        trigger_keywords = ['!ask', '/ask', 'ai', 'assistant', 'bot']
        
        is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id
        is_mentioned = f'@{bot_username.lower()}' in text
        starts_with_keyword = any(text.startswith(keyword) for keyword in trigger_keywords)

        if not (is_reply_to_bot or is_mentioned or starts_with_keyword):
            return

        original_question = message.text
        for keyword in trigger_keywords:
            if original_question.lower().startswith(keyword):
                original_question = original_question[len(keyword):].strip()
                break
        original_question = original_question.replace(f'@{bot_username}', '').strip()
        
        if not original_question: return # যদি কীওয়ার্ড বা মেনশনের পর কোনো লেখা না থাকে

        message.text = original_question # মূল প্রশ্নটি দিয়ে message.text আপডেট করা
    
    else: return # অন্য কোনো চ্যাট টাইপ হলে কিছু করবে না

    if not gemini_model:
        await message.reply_text(get_text(user_id, 'api_error'))
        return

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action=constants.ChatAction.TYPING)
        response = gemini_model.generate_content(message.text)
        
        if not response.parts:
            await message.reply_text(get_text(user_id, 'safety_block'))
            return
            
        await message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        await message.reply_text(get_text(user_id, 'api_error'))

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (আপনার আগের bot_added_to_group ফাংশন)

# --- মূল ফাংশন ---
def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not all([token, ADMIN_ID, GEMINI_API_KEY]):
        logger.critical("FATAL ERROR: Required environment variables are missing!"); return

    application = Application.builder().token(token).build()
    
    # সমস্ত কমান্ড এবং হ্যান্ডলার এখানে সঠিকভাবে যোগ করা আছে
    # ... (আপনার আগের main ফাংশনের application.add_handler(...) অংশটি)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', language_command))
    application.add_handler(CommandHandler('help', help_command))
    # ... (বাকি সব কমান্ড)
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added_to_group))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting with updated group message logic...")
    application.run_polling()

if __name__ == '__main__':
    main()
