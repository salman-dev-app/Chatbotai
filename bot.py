# bot.py — Simple Gemini Bot (Private Only, 3 Buttons UI)
import os
import logging
import asyncio
from io import BytesIO
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    InputFile, 
    constants
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)
import google.generativeai as genai

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Gemini Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("⚠️ GEMINI_API_KEY missing in environment!")
genai.configure(api_key=GEMINI_API_KEY)
text_model = genai.GenerativeModel("gemini-2.0-flash")

# --- Telegram Setup ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("⚠️ TELEGRAM_BOT_TOKEN missing in environment!")

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu buttons."""
    keyboard = [
        [InlineKeyboardButton("🖼️ Generate Image", callback_data="generate_image")],
        [InlineKeyboardButton("💬 Chat with AI", callback_data="chat_ai")],
        [InlineKeyboardButton("ℹ️ About Bot", callback_data="about")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "🤖 **Welcome to GemBot AI!**\n\n"
        "I can generate images 🖼️ or chat 💬 with you instantly.\n\n"
        "Choose an option below 👇"
    )

    await update.message.reply_text(
        welcome_text, 
        parse_mode=constants.ParseMode.MARKDOWN, 
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    query = update.callback_query
    await query.answer()

    if query.data == "generate_image":
        await query.message.reply_text("✏️ Send me a prompt — what image do you want me to create?")
        context.user_data["mode"] = "image"

    elif query.data == "chat_ai":
        await query.message.reply_text("💬 Send me any message — I’ll reply intelligently!")
        context.user_data["mode"] = "chat"

    elif query.data == "about":
        about_text = (
            "🌐 **GemBot AI**\n"
            "Powered by Google Gemini.\n\n"
            "✨ Features:\n"
            "• Image Generation\n"
            "• Smart Chat Replies\n\n"
            "👨‍💻 Developer: [Salman](https://github.com/salman-dev-app)\n"
            "🔒 Works only in private chat."
        )
        await query.message.reply_text(about_text, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages for both modes."""
    if update.effective_chat.type != "private":
        await update.message.reply_text("🚫 I only work in private chats.")
        return

    user_mode = context.user_data.get("mode", "chat")
    user_text = update.message.text

    if user_mode == "image":
        await update.message.reply_text("🎨 Generating your image, please wait...")
        try:
            # Try Gemini image generation
            if hasattr(genai, "Image"):
                image = genai.Image.generate(prompt=user_text)
                import base64
                image_data = base64.b64decode(image.data[0].b64_json)
                bio = BytesIO(image_data)
                bio.seek(0)
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=InputFile(bio, filename="result.png"),
                    caption="✅ Here's your generated image!"
                )
            else:
                await update.message.reply_text("⚠️ Image generation not supported on this server.")
        except Exception as e:
            logger.error("Image generation error: %s", e)
            await update.message.reply_text("❌ Failed to generate image. Please try again later.")
        return

    # --- Chat mode ---
    await update.message.chat.send_action(constants.ChatAction.TYPING)
    try:
        response = await asyncio.to_thread(text_model.generate_content, user_text)
        reply = response.text if hasattr(response, "text") else str(response)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error("Chat error: %s", e)
        await update.message.reply_text("❌ AI service error, please try again later.")

async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """If added to a group, leave automatically."""
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            await update.effective_chat.leave()
            return

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added_to_group))

    logger.info("✅ GemBot AI started (Private Only)")
    app.run_polling()

if __name__ == "__main__":
    main()
