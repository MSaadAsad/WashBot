import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)
from utils import start, button_click_handler

def main():
    # Load environment variables from .env file
    load_dotenv()

    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    PORT = int(os.environ.get('PORT', 8443))
    APP_URL = os.getenv('APP_URL')  # Your Heroku app URL

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

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click_handler))

    # Start webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{APP_URL}/{TOKEN}"
    )

if __name__ == '__main__':
    main()
