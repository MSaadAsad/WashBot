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

async def show_machine_statuses(chat_id, context):
    """Display the current machine statuses."""
    machines = context.bot_data['machines']
    status_message = "⚙️ **Machine Statuses:**\n\n"
    keyboard = []

    # Build the status message and buttons
    for machine_name, machine_info in machines.items():
        status = machine_info['status']
        if status == 'free':
            status_message += f"✅ {machine_name}: Free \n"
            keyboard.append([InlineKeyboardButton(f"Start {machine_name}", callback_data=f"start_{machine_name}")])
        elif status == 'broken':
            status_message += f"❌ {machine_name}: Broken\n"
        elif status == 'occupied':
            end_time = machine_info['end_time']
            remaining_time = int((end_time - datetime.datetime.now()).total_seconds() / 60)
            if remaining_time <= 0:
                remaining_time = 0
            occupied_by = machine_info.get('username', 'someone')
            status_message += f"⏳ {machine_name}: Occupied by @{occupied_by} for {remaining_time} more minutes\n"

    # If no machines are available to start, show a message
    if not any(machine['status'] == 'free' for machine in machines.values()):
        keyboard = [[InlineKeyboardButton("No machines available", callback_data="no_action")]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send or edit the message with the updated status
    await context.bot.send_message(chat_id=chat_id, text=status_message, reply_markup=reply_markup)


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

        # Show the updated machine statuses
        await show_machine_statuses(user_id, context)


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
        await show_machine_statuses(query.message.chat_id, context)

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
            error_message = "⚠️ Invalid machine selected."
            await query.edit_message_text(text=error_message)

            return
        if machine_info['status'] != 'free':
            occupied_by = machine_info.get('username', 'someone')
            end_time = machine_info.get('end_time')
            if end_time:
                end_time_str = end_time.strftime('%H:%M')
                error_message = f"⚠️ {machine_name} is currently occupied until {end_time_str}."
            else:
                error_message = f"⚠️ {machine_name} is currently occupied."
            await query.edit_message_text(text=error_message)

            return

        # Determine duration based on machine type
        if 'Washer' in machine_name:
            duration_minutes = 2  # Adjust the duration as needed
        elif 'Dryer' in machine_name:
            duration_minutes = 3  # Adjust the duration as needed
        else:
            error_message = "⚠️ Unknown machine type."
            await query.edit_message_text(text=error_message)

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
            data={
                'machine_name': machine_name,
                'user_id': user.id,
                'username': username
            }
        )

        # Send a confirmation message back to the user
        confirmation_message = f"✅ You have started {machine_name}. It will be occupied for {duration_minutes} minutes ⏳"
        await query.edit_message_text(text=confirmation_message)
        await query.message.reply_text(confirmation_message)

        # Log the action
        logger.info(f"Started {machine_name} for {duration_minutes} minutes.")

        # Show the updated machine statuses
        status_message = "⚙️ Machine Statuses:\n\n"
        keyboard = []
        for machine_name, machine_info in machines.items():
            status = machine_info['status']
            if status == 'free':
                status_message += f"✅ {machine_name}: Free \n"
                keyboard.append([InlineKeyboardButton(f"Start {machine_name}", callback_data=f"start_{machine_name}")])
            elif status == 'broken':
                status_message += f"❌ {machine_name}: Broken\n"
            elif status == 'occupied':
                end_time = machine_info['end_time']
                remaining_time = int((end_time - datetime.datetime.now()).total_seconds() / 60)
                if remaining_time <= 0:
                    remaining_time = 0
                occupied_by = machine_info.get('username', 'someone')
                status_message += f"⏳ {machine_name}: Occupied by @{occupied_by} for {remaining_time} more minutes\n"
    
        # If no machines are available to start, show a message
        if not keyboard:
            keyboard = [[InlineKeyboardButton("No machines available", callback_data="no_action")]]
    
        reply_markup = InlineKeyboardMarkup(keyboard)
    
        # Edit the message to display the updated status
        await query.message.reply_text(text=status_message, reply_markup=reply_markup)
