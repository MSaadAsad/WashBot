import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
AUTHORIZED_USERS = os.getenv('AUTHORIZED_USERS').split(',')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message with an inline button."""
    user = update.effective_user
    username = user.username

    # Log the username
    logger.info(f"User @{username} initiated the /start command.")

    # Check if user is authorized
    if username not in AUTHORIZED_USERS:
        await update.message.reply_text("Access Denied.")
        logger.warning(f"Unauthorized access attempt by @{username}.")
        return

    keyboard = [
        [InlineKeyboardButton("Click me!", callback_data='button_click')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Please click the button:', reply_markup=reply_markup)

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button click."""
    query = update.callback_query
    user = query.from_user
    username = user.username

    # Log the username
    logger.info(f"User @{username} clicked the button.")

    # Check if user is authorized
    if username not in AUTHORIZED_USERS:
        await query.answer()
        await query.edit_message_text(text="Access Denied.")
        logger.warning(f"Unauthorized button click by @{username}.")
        return

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
