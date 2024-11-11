import os
import logging
import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
)

load_dotenv()

AUTHORIZED_USERS = os.getenv('AUTHORIZED_USERS').split(',')

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message with an inline button to show machine status."""
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
        [InlineKeyboardButton("Show Machine Status", callback_data='show_status')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Welcome! Please choose an option:', reply_markup=reply_markup)

async def free_machine(context: ContextTypes.DEFAULT_TYPE):
    """Free the machine and notify the user when the cycle is complete."""
    job = context.job
    machine_name = job.data['machine_name']
    user_id = job.data['user_id']
    username = job.data['username']
    machines = context.bot_data['machines']
    machine_info = machines.get(machine_name)
    if machine_info:
        machine_info['status'] = 'free'
        machine_info.pop('end_time', None)
        machine_info.pop('user_id', None)
        machine_info.pop('username', None)

        # Send a message to the user
        await context.bot.send_message(
            chat_id=user_id,
            text=f"{machine_name} is now free. Your cycle is complete."
        )
        logger.info(f"Machine {machine_name} is now free. Notified user @{username}.")

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button click."""
    query = update.callback_query
    user = query.from_user
    username = user.username
    callback_data = query.data

    # Log the username and action
    logger.info(f"User @{username} clicked button with data '{callback_data}'.")

    # Check if user is authorized
    if username not in AUTHORIZED_USERS:
        await query.answer()
        await query.edit_message_text(text="Access Denied.")
        logger.warning(f"Unauthorized button click by @{username}.")
        return

    await query.answer()

    if callback_data == 'show_status':
        # Build the status message
        machines = context.bot_data['machines']
        status_message = "Machine Statuses:\n\n"
        for machine_name, machine_info in machines.items():
            status = machine_info['status']
            if status == 'free':
                status_message += f"{machine_name}: Free\n"
            elif status == 'broken':
                status_message += f"{machine_name}: Broken\n"
            else:
                # Assume status is occupied and calculate remaining time
                end_time = machine_info['end_time']
                remaining_time = int((end_time - datetime.datetime.now()).total_seconds() / 60)
                if remaining_time <= 0:
                    remaining_time = 0
                status_message += f"{machine_name}: Occupied for {remaining_time} more minutes\n"

        # Provide buttons to start a machine
        keyboard = []
        for machine_name, machine_info in machines.items():
            if machine_info['status'] == 'free':
                # Add a button to start this machine
                keyboard.append([InlineKeyboardButton(f"Start {machine_name}", callback_data=f"start_{machine_name}")])
        if not keyboard:
            keyboard = [[InlineKeyboardButton("No machines available", callback_data="no_action")]]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=status_message, reply_markup=reply_markup)

    elif callback_data.startswith('start_'):
        # User wants to start a machine
        machine_name = callback_data[len('start_'):]
        machines = context.bot_data['machines']
        machine_info = machines.get(machine_name)
        if machine_info is None:
            await query.edit_message_text(text="Invalid machine.")
            return
        if machine_info['status'] != 'free':
            await query.edit_message_text(text=f"{machine_name} is not available.")
            return

        # Determine duration based on machine type
        if 'Washer' in machine_name:
            duration_minutes = 1
        elif 'Dryer' in machine_name:
            duration_minutes = 1
        else:
            await query.edit_message_text(text="Unknown machine type.")
            return

        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        machine_info['status'] = 'occupied'
        machine_info['end_time'] = end_time
        machine_info['user_id'] = user.id
        machine_info['username'] = username

        # Schedule a job to free the machine and notify the user
        job_queue = context.job_queue
        job_queue.run_once(
            free_machine,
            duration_minutes * 60,
            context={
                'machine_name': machine_name,
                'user_id': user.id,
                'username': username
            }
        )

        await query.edit_message_text(
            text=f"You have started {machine_name}. It will be occupied for {duration_minutes} minutes."
        )

    elif callback_data == 'no_action':
        await query.answer()
    else:
        await query.edit_message_text(text="Unknown action.")
