from flask import Flask
import threading
import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)

from utils import start, button_click_handler

flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "Telegram Bot is running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def main():

    # Load environment variables from .env file
    load_dotenv()

    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

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

    threading.Thread(target=run_flask).start()

    application.run_polling()

if __name__ == '__main__':
    main()
