python
import os
import json
import logging
import asyncio
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
        'help_text': "📖 **How to Use This Bot**\n\n**Private Chat:**\nJust send me any message!\n\n**In Groups:**\nUse the command `/ask <your question>` to get a response from me.",
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
        # Add your other Bengali translations here
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
        await asyncio.sleep(0.5)

async def generate_gemini_response(prompt: str) -> str | None:
    """Runs the synchronous Gemini API call in a separate thread to avoid blocking."""
    if not gemini_model: return None
    try:
        response = await asyncio.to_thread(gemini_model.generate_content, prompt)
        return response.text if response.parts else "" # Return empty string for safety block
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return None

# --- ইউজার কমান্ড হ্যান্ডলার ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if bot_data.is_user_banned(user_id): return
    bot_data.add_user(user_id)
    keyboard = [[InlineKeyboardButton(get_text(user_id, 'start_chat'), callback_data='start_chat')],
                [InlineKeyboardButton(get_text(user_id, 'membership_info'), callback_data='membership_info')],
                [InlineKeyboardButton(get_text(user_id, 'contact_admin'), url='https://t.me/otakuosenpai')]]
    await update.message.reply_text(get_text(user_id, 'welcome'), reply_markup=InlineKeyboardMarkup(keyboard))
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if bot_data.is_user_banned(user_id): return
    keyboard = [[InlineKeyboardButton('🇬🇧 English', callback_data='set_lang_en')],
                [InlineKeyboardButton('🇧🇩 বাংলা', callback_data='set_lang_bn')]]
    await update.message.reply_text(get_text(user_id, 'choose_language'), reply_markup=InlineKeyboardMarkup(keyboard))
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if bot_data.is_user_banned(user_id): return
    await update.message.reply_text(get_text(user_id, 'help_text'), parse_mode=constants.ParseMode.MARKDOWN)
async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if bot_data.is_user_banned(user_id): return
    await update.message.reply_text(get_text(user_id, 'myinfo_text', user_id=user_id, language=bot_data.get_user_language(user_id)))
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if bot_data.is_user_banned(user_id): return
    await update.message.reply_text(get_text(user_id, 'about_text'), parse_mode=constants.ParseMode.MARKDOWN)

# --- অ্যাডমিন কমান্ড হ্যান্ডলার ---
async def admin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(get_text(user_id, 'admin_only'))
        return False
    return True
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    await update.message.reply_text(get_text(update.effective_user.id, 'admin_help'), parse_mode=constants.ParseMode.MARKDOWN)
async def addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args: await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/addgroup <group_id>')); return
    try:
        group_id = int(context.args[0])
        bot_data.add_group(group_id)
        await update.message.reply_text(get_text(update.effective_user.id, 'group_added', group_id=group_id))
    except ValueError: await update.message.reply_text("Invalid Group ID.")
async def removegroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args: await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/removegroup <group_id>')); return
    try:
        group_id = int(context.args[0])
        bot_data.remove_group(group_id)
        await update.message.reply_text(get_text(update.effective_user.id, 'group_removed', group_id=group_id))
    except ValueError: await update.message.reply_text("Invalid Group ID.")
async def listgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    groups = bot_data.data['authorized_group_ids']
    if not groups: await update.message.reply_text(get_text(update.effective_user.id, 'no_groups')); return
    await update.message.reply_text(get_text(update.effective_user.id, 'group_list', count=len(groups), groups="\n".join(map(str, groups))))
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args: await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/ban <user_id>')); return
    try:
        user_id = int(context.args[0])
        bot_data.ban_user(user_id)
        await update.message.reply_text(get_text(update.effective_user.id, 'user_banned', user_id=user_id))
    except ValueError: await update.message.reply_text("Invalid User ID.")
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    if not context.args: await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/unban <user_id>')); return
    try:
        user_id = int(context.args[0])
        bot_data.unban_user(user_id)
        await update.message.reply_text(get_text(update.effective_user.id, 'user_unbanned', user_id=user_id))
    except ValueError: await update.message.reply_text("Invalid User ID.")
async def listbanned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    users = bot_data.data['banned_user_ids']
    if not users: await update.message.reply_text(get_text(update.effective_user.id, 'no_banned')); return
    await update.message.reply_text(get_text(update.effective_user.id, 'banned_list', count=len(users), users="\n".join(map(str, users))))
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    await update.message.reply_text(get_text(update.effective_user.id, 'stats_text',
        users=len(bot_data.data['all_users']),
        groups=len(bot_data.data['authorized_group_ids']),
        banned=len(bot_data.data['banned_user_ids'])))
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_check(update, context): return
    message_to_send = " ".join(context.args)
    if not message_to_send: await update.message.reply_text(get_text(update.effective_user.id, 'usage_error', command='/broadcast <message>')); return
    context.user_data['broadcast_message'] = message_to_send
    keyboard = [[InlineKeyboardButton("Yes, Send", callback_data='broadcast_confirm_yes'), InlineKeyboardButton("No, Cancel", callback_data='broadcast_confirm_no')]]
    await update.message.reply_text(get_text(update.effective_user.id, 'broadcast_confirm', count=len(bot_data.data['all_users']), message=message_to_send), reply_markup=InlineKeyboardMarkup(keyboard))

# --- গ্রুপ এবং ব্যক্তিগত চ্যাটের জন্য হ্যান্ডলার ---
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, chat = update.effective_user.id, update.effective_chat
    if bot_data.is_user_banned(user_id): return
    if chat.type in ['group', 'supergroup'] and not bot_data.is_group_authorized(chat.id): return
    if not context.args:
        await update.message.reply_text(get_text(user_id, 'usage_error', command='/ask <your question>'))
        return
    question = " ".join(context.args)
    
    await context.bot.send_chat_action(chat_id=chat.id, action=constants.ChatAction.TYPING)
    response_text = await generate_gemini_response(question)
    
    if response_text is not None and response_text != "":
        await send_long_message(context, chat.id, response_text)
    elif response_text == "":
        await update.message.reply_text(get_text(user_id, 'safety_block'))
    else:
        await update.message.reply_text(get_text(user_id, 'api_error'))

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, chat_id = update.effective_user.id, update.effective_chat.id
    if bot_data.is_user_banned(user_id): return
    bot_data.add_user(user_id)

    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)
    response_text = await generate_gemini_response(update.message.text)
    
    if response_text is not None and response_text != "":
        await send_long_message(context, chat_id, response_text)
    elif response_text == "":
        await update.message.reply_text(get_text(user_id, 'safety_block'))
    else:
        await update.message.reply_text(get_text(user_id, 'api_error'))

# --- অন্যান্য হ্যান্ডলার ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == 'start_chat': await query.edit_message_text(get_text(user_id, 'chat_started'))
    elif data == 'membership_info': await query.edit_message_text(get_text(user_id, 'membership_text'), parse_mode=constants.ParseMode.MARKDOWN)
    elif data.startswith('set_lang_'):
        lang_code = data.split('_')[-1]
        lang_name = "English" if lang_code == "en" else "বাংলা"
        bot_data.set_user_language(user_id, lang_code)
        await query.edit_message_text(get_text(user_id, 'language_updated', lang=lang_name))
    elif data == 'broadcast_confirm_yes':
        if not is_admin(user_id): return
        message = context.user_data.get('broadcast_message')
        if not message: await query.edit_message_text("Error: Message not found."); return
        sent_count = 0
        for uid in bot_data.data['all_users']:
            try: await context.bot.send_message(chat_id=uid, text=message); sent_count += 1
            except Exception as e: logger.error(f"Broadcast failed for user {uid}: {e}")
        await query.edit_message_text(get_text(user_id, 'broadcast_sent', count=sent_count))
    elif data == 'broadcast_confirm_no':
        if not is_admin(user_id): return
        await query.edit_message_text(get_text(user_id, 'broadcast_cancelled'))
async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            chat_id = update.effective_chat.id
            if not bot_data.is_group_authorized(chat_id):
                try:
                    await context.bot.send_message(chat_id=chat_id, text=get_text(0, 'group_unauthorized'))
                    await context.bot.leave_chat(chat_id)
                except Exception as e: logger.error(f"Error leaving unauthorized group {chat_id}: {e}")

# --- মূল ফাংশন ---
def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not all([token, ADMIN_ID, GEMINI_API_KEY]):
        logger.critical("FATAL ERROR: Required environment variables are missing!"); return
    application = Application.builder().token(token).build()
    
    # ইউজার কমান্ড
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', language_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('myinfo', myinfo_command))
    application.add_handler(CommandHandler('about', about_command))

    # অ্যাডমিন কমান্ড
    application.add_handler(CommandHandler('admin', admin_command))
    application.add_handler(CommandHandler('addgroup', addgroup))
    application.add_handler(CommandHandler('removegroup', removegroup))
    application.add_handler(CommandHandler('listgroups', listgroups))
    application.add_handler(CommandHandler('ban', ban))
    application.add_handler(CommandHandler('unban', unban))
    application.add_handler(CommandHandler('listbanned', listbanned))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler('stats', stats))

    # গ্রুপে ব্যবহারের জন্য বিশেষ কমান্ড
    application.add_handler(CommandHandler('ask', ask_command))
    
    # শুধুমাত্র ব্যক্তিগত চ্যাটের মেসেজ হ্যান্ডেল করার জন্য
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_private_message))
    
    # অন্যান্য হ্যান্ডলার
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added_to_group))

    logger.info("Bot starting with non-blocking API calls and final features...")
    application.run_polling()

if __name__ == '__main__':
    main()
