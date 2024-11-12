import os
import logging
import datetime
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
)
import asyncio

# Load environment variables
load_dotenv()

AUTHORIZED_USERS = os.getenv('AUTHORIZED_USERS', '').split(',')

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    username = user.username

    if username not in AUTHORIZED_USERS:
        await update.message.reply_text("❌ *Access Denied.*")
        logger.warning(f"Unauthorized access attempt by @{username}.")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Show Machine Statuses", callback_data='show_status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = (
        f"👋 *Welcome, @{username}!*\n\n"
        "Please choose an option below to manage the machines."
    )

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def show_machine_statuses(chat_id, context: ContextTypes.DEFAULT_TYPE, message=None):
    """Display the current machine statuses with improved UI.
    
    If 'message' is provided, edit that message. Otherwise, send a new one.
    """
    machines = context.bot_data.get('machines', {})
    status_lines = []
    keyboard = []

    for machine, info in machines.items():
        status = info.get('status', 'unknown').lower()
        if status == 'free':
            status_lines.append(f"✅ *{machine}*: Free")
            keyboard.append([InlineKeyboardButton(f"▶️ Start {machine}", callback_data=f"start_{machine}")])
        elif status == 'occupied':
            end_time = info.get('end_time')
            remaining = (end_time - datetime.datetime.now()).total_seconds() / 60 if end_time else 0
            remaining = max(int(remaining), 0)
            status_lines.append(f"⏳ *{machine}*: Occupied ({remaining} min left)")
        elif status == 'broken':
            status_lines.append(f"❌ *{machine}*: Broken")

    status_message = "⚙️ *Machine Statuses:*\n\n" + "\n".join(status_lines)

    # Add a refresh button
    keyboard.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_status")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        # Edit the existing message
        await message.edit_text(
            text=status_message,
            reply_markup=reply_markup,
        )
    else:
        # Send a new message
        await context.bot.send_message(
            chat_id=chat_id,
            text=status_message,
            reply_markup=reply_markup,
        )

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button clicks."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    username = user.username
    callback_data = query.data

    if username not in AUTHORIZED_USERS:
        await query.edit_message_text("❌ *Access Denied.*")
        logger.warning(f"Unauthorized button click by @{username}.")
        return

    if callback_data == 'show_status' or callback_data == 'refresh_status':
        # Pass the current message to edit it instead of sending a new one
        await show_machine_statuses(
            chat_id=query.message.chat_id,
            context=context,
            message=query.message
        )

    elif callback_data.startswith('start_'):
        machine_name = callback_data.split('start_')[1]
        machines = context.bot_data.setdefault('machines', {})
        machine = machines.get(machine_name)

        if not machine:
            await query.edit_message_text("⚠️ *Selected machine does not exist.*")
            return

        if machine['status'] != 'free':
            status = machine['status']
            if status == 'occupied':
                end_time = machine.get('end_time')
                remaining = (end_time - datetime.datetime.now()).total_seconds() / 60 if end_time else 0
                remaining = max(int(remaining), 0)
                message = f"⏳ *{machine_name}* is currently occupied for another *{remaining} minutes*."
            else:
                message = f"❌ *{machine_name}* is currently *{status}*."
            await query.edit_message_text(message)
            return

        # Define machine durations
        duration_map = {
            'Washer': 0.3,  # minutes
            'Dryer': 0.4,
        }

        # Determine machine type and duration
        machine_type = 'Unknown'
        for key in duration_map.keys():
            if key.lower() in machine_name.lower():
                machine_type = key
                break

        duration = duration_map.get(machine_type, 2)  # default to 2 minutes

        # Update machine status
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        machines[machine_name] = {
            'status': 'occupied',
            'end_time': end_time,
            'user_id': user.id,
            'username': username
        }

        # Schedule job to free the machine
        context.job_queue.run_once(
            free_machine,
            when=duration * 60,  # convert minutes to seconds
            data={
                'machine_name': machine_name,
                'user_id': user.id,
                'username': username
            }
        )

        confirmation = (
            f"✅ *{machine_name}* has been started.\n"
            f"🕒 It will be free in *{duration} minutes*."
        )
        await query.edit_message_text(confirmation)
        logger.info(f"Started {machine_name} for @{username} for {duration} minutes.")

        # Update the statuses immediately by editing the same message
        await show_machine_statuses(
            chat_id=query.message.chat_id,
            context=context,
            message=query.message
        )

async def free_machine(context: ContextTypes.DEFAULT_TYPE):
    """Free the machine and notify the user, then delete the notification after a delay."""
    job_data = context.job.data
    machine_name = job_data['machine_name']
    user_id = job_data['user_id']
    username = job_data['username']

    machines = context.bot_data.get('machines', {})
    machine = machines.get(machine_name)

    if machine and machine['status'] == 'occupied':
        machines[machine_name] = {'status': 'free'}
        logger.info(f"Machine {machine_name} is now free. Notified @{username}.")

        try:
            # Send the notification message and capture the Message object
            notification = await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 *{machine_name}* is now free. Your cycle is complete.",
            )

            delete_delay = 10  # For example, 30 seconds

            # Wait for the specified delay
            await asyncio.sleep(delete_delay)

            # Attempt to delete the message
            await context.bot.delete_message(
                chat_id=user_id,
                message_id=notification.message_id
            )
            logger.info(f"Deleted notification message for @{username} after {delete_delay} seconds.")

        except Exception as e:
            logger.error(f"Failed to send or delete notification for @{username}: {e}")
