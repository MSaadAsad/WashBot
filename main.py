import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message with an inline button."""
    keyboard = [
        [InlineKeyboardButton("Click me!", callback_data='button_click')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Please click the button:', reply_markup=reply_markup)

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button click."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Button clicked!")

def main():
    """Start the bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click_handler))

    application.run_polling()

if __name__ == '__main__':
    main()
