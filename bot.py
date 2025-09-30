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
# এই অংশে আপনার পুরোনো কোড থেকে সম্পূর্ণ TRANSLATIONS ডিকশনারিটি কপি করে পেস্ট করুন।
# এটি আপনার সমস্ত বাটন এবং মেসেজের টেক্সট নিয়ন্ত্রণ করবে।
TRANSLATIONS = {
    'en': {
        'welcome': "👋 Welcome to the AI Assistant Bot!\n\nI'm powered by Google Gemini and can help you with any questions. Choose an option below:",
        'start_chat': '💬 Start Chat with AI',
        'membership_info': '💎 Membership Info',
        'contact_admin': '📞 Contact Admin',
        'membership_text': "💎 **Membership Information**\n\nTo use this bot in your group:\n\n1. Contact the admin for membership\n2. Provide your group ID\n3. Wait for authorization\n4. Add the bot to your group\n\nOnce authorized, all group members can chat with the AI!\n\nContact: @otakuosenpai",
        'help_text': "📖 **How to Use This Bot**\n\n**Available Commands:**\n/start - Main menu\n/language - Change language\n/help - Show this message\n/myinfo - View your info\n/about - About this bot\n\n**Chat:** Just send me any message!",
        'myinfo_text': "👤 **Your Information**\n\nUser ID: {user_id}\nSelected Language: {language}",
        'about_text': "🤖 **About This Bot**\n\nAI assistant powered by Google Gemini.\nMade with ❤️ by MD Salman",
        'choose_language': "🌐 Choose your preferred language:",
        'language_updated': "✅ Language updated to English!",
        'chat_started': "💬 Great! Send me any message and I'll respond using AI.",
        'banned': "⛔ You are banned from using this bot.",
        'admin_only': "⚠️ This command is for admins only.",
        'group_added': "✅ Group `{group_id}` has been authorized!",
        'group_removed': "✅ Group `{group_id}` has been unauthorized!",
        'group_list': "📋 **Authorized Groups** ({count}):\n\n{groups}",
        'no_groups': "No authorized groups yet.",
        'user_banned': "✅ User `{user_id}` has been banned!",
        'user_unbanned': "✅ User `{user_id}` has been unbanned!",
        'banned_list': "🚫 **Banned Users** ({count}):\n\n{users}",
        'no_banned': "No banned users.",
        'stats_text': "📊 **Bot Statistics**\n\nTotal Users: {users}\nAuthorized Groups: {groups}\nBanned Users: {banned}",
        'broadcast_confirm': "📢 Send this message to {count} users?\n\n`{message}`",
        'broadcast_sent': "✅ Broadcast sent to {count} users!",
        'broadcast_cancelled': "❌ Broadcast cancelled.",
        'group_unauthorized': "⚠️ This group is not authorized. Contact @otakuosenpai for access. The bot will now leave.",
        'admin_help': "🔧 **Admin Panel**\n\n/addgroup <id>\n/removegroup <id>\n/listgroups\n/ban <user_id>\n/unban <user_id>\n/listbanned\n/broadcast <msg>\n/stats",
        'api_error': "Sorry, I'm facing an issue with the AI service. Please try again later.",
        'safety_block': "I couldn't process that request due to safety guidelines.",
    },
    'bn': {
        # ... (এখানে আপনার সম্পূর্ণ বাংলা অনুবাদ যোগ করুন) ...
    }
}


# --- ডেটা ম্যানেজমেন্ট ক্লাস (সম্পূর্ণ সংস্করণ) ---
class BotData:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = self._load()

    def _load(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'authorized_group_ids': [], 'banned_user_ids': [], 'user_languages': {}, 'all_users': [], 'broadcast_confirmations': {}}

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

    def set_user_language(self, user_id: int, language: str):
        self.data['user_languages'][str(user_id)] = language
        self._save()

    def is_user_banned(self, user_id: int) -> bool:
        return user_id in self.data['banned_user_ids']

    def ban_user(self, user_id: int):
        if user_id not in self.data['banned_user_ids']: self.data['banned_user_ids'].append(user_id); self._save()

    def unban_user(self, user_id: int):
        if user_id in self.data['banned_user_ids']: self.data['banned_user_ids'].remove(user_id); self._save()

    def is_group_authorized(self, group_id: int) -> bool:
        return group_id in self.data['authorized_group_ids']

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
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
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
    user_id = update.effective_user.id
    if bot_data.is_user_banned(user_id): return
    bot_data.add_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton(get_text(user_id, 'start_chat'), callback_data='start_chat')],
        [InlineKeyboardButton(get_text(user_id, 'membership_info'), callback_data='membership_info')],
        [InlineKeyboardButton(get_text(user_id, 'contact_admin'), url='https://t.me/otakuosenpai')]
    ]
    await update.message.reply_text(get_text(user_id, 'welcome'), reply_markup=InlineKeyboardMarkup(keyboard))

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if bot_data.is_user_banned(user_id): return
    keyboard = [
        [InlineKeyboardButton('🇬🇧 English', callback_data='set_lang_en')],
        [InlineKeyboardButton('🇧🇩 বাংলা', callback_data='set_lang_bn')]
    ]
    await update.message.reply_text(get_text(user_id, 'choose_language'), reply_markup=InlineKeyboardMarkup(keyboard))

# ... (help_command, myinfo_command, about_command এখানে যোগ করুন) ...


# --- অ্যাডমিন কমান্ড হ্যান্ডলার ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(get_text(update.effective_user.id, 'admin_help'))

# ... (addgroup, removegroup, listgroups, ban, unban, listbanned, broadcast, stats কমান্ডগুলো এখানে যোগ করুন) ...


# --- বাটন এবং মেসেজ হ্যান্ডলার ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == 'start_chat':
        await query.edit_message_text(get_text(user_id, 'chat_started'))
    elif data == 'membership_info':
        await query.edit_message_text(get_text(user_id, 'membership_text'))
    elif data.startswith('set_lang_'):
        lang = data.split('_')[-1]
        bot_data.set_user_language(user_id, lang)
        await query.edit_message_text(get_text(user_id, 'language_updated'))
    # ... (broadcast এর জন্য button_callback লজিক যোগ করুন)

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    
    if chat.type == 'group' and not bot_data.is_group_authorized(chat.id): return
    if bot_data.is_user_banned(user_id): return
    if chat.type == 'private': bot_data.add_user(user_id)
    if not gemini_model: await update.message.reply_text(get_text(user_id, 'api_error')); return

    try:
        await context.bot.send_chat_action(chat_id=chat.id, action='typing')
        response = gemini_model.generate_content(update.message.text)
        if not response.parts:
            await update.message.reply_text(get_text(user_id, 'safety_block'))
            return
        await update.message.reply_text(response.text, reply_to_message_id=update.message.message_id)
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        await update.message.reply_text(get_text(user_id, 'api_error'))

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not bot_data.is_group_authorized(chat_id):
        try:
            await context.bot.send_message(chat_id=chat_id, text=get_text(0, 'group_unauthorized'))
            await context.bot.leave_chat(chat_id)
        except Exception as e:
            logger.error(f"Error leaving unauthorized group {chat_id}: {e}")


# --- মূল ফাংশন ---
def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not all([token, ADMIN_ID, GEMINI_API_KEY]):
        logger.critical("FATAL ERROR: Required environment variables are missing!")
        return

    application = Application.builder().token(token).build()

    # ইউজার কমান্ড
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', language_command))
    # ... (অন্যান্য ইউজার কমান্ড)

    # অ্যাডমিন কমান্ড
    application.add_handler(CommandHandler('admin', admin_command))
    # ... (অন্যান্য অ্যাডমিন কমান্ড)

    # হ্যান্ডলার
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added_to_group))

    logger.info("Bot starting with ALL features and Gemini API...")
    application.run_polling()

if __name__ == '__main__':
    main()
