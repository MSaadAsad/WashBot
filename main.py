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

    """Start the bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    # Initialize machines
    application.bot_data['machines'] = {
        'Ground Floor Washer': {'status': 'free'},
        'Ground Floor Dryer': {'status': 'free'},
        'Upper Floor Washer 1': {'status': 'free'},
        'Upper Floor Washer 2': {'status': 'free'},
        'Upper Floor Dryer 1': {'status': 'free'},
        'Upper Floor Dryer 2': {'status': 'broken'},
    }

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click_handler))

    application.run_polling()

if __name__ == '__main__':
    main()
