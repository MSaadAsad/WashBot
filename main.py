import os
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)

from utils import (
    start,
    button_click_handler,
    load_machine_states,
)


def main():
    """Start the bot."""
    # Load environment variables from .env file
    load_dotenv()

    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    # Initialize application
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Initialize machines from saved state or defaults
    application.bot_data['machines'] = load_machine_states()

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_click_handler))

    # Start the bot
    print("🚀 Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
