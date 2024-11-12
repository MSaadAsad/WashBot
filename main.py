import os
import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)
from utils import start, button_click_handler

def main():
    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)

    # Get the Telegram bot token from environment variables
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in environment variables.")
        exit(1)

    logger.info("Starting the Telegram bot...")

    """Start the bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    # Initialize machines
    application.bot_data['machines'] = {
        'Ground Floor Washer 🌊': {'status': 'free'},
        'Ground Floor Dryer ☀️ ': {'status': 'broken'},
        'Upper Floor Washer 1️⃣ 🌊': {'status': 'free'},
        'Upper Floor Washer 2️⃣ 🌊': {'status': 'free'},
        'Upper Floor Dryer 1️⃣ ☀️': {'status': 'free'},
        'Upper Floor Dryer 2️⃣ ☀️': {'status': 'broken'},
    }

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click_handler))

    logger.info("Handlers added. Starting polling...")

    try:
        application.run_polling()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        exit(1)

    logger.info("Polling has stopped. Exiting application.")

if __name__ == '__main__':
    main()
