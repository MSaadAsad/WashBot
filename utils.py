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
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import asyncio

# Load environment variables
load_dotenv()

# Constants
AUTHORIZED_USERS = os.getenv('AUTHORIZED_USERS', '').split(',')
SELECTING_MACHINE = 1
SELECTING_STATUS = 2
ENTERING_TIME = 3

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
        await update.message.reply_text("❌ <b>Access Denied.</b>", parse_mode="HTML")
        logger.warning(f"Unauthorized access attempt by @{username}.")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Show Machine Statuses", callback_data='show_status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = (
        f"👋 <b>Welcome, @{username}!</b>\n\n"
        "Please choose an option below to manage the machines."
    )

    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode="HTML")

async def show_machine_statuses(chat_id, context: ContextTypes.DEFAULT_TYPE, message=None):
    """Display the current machine statuses with improved UI."""
    machines = context.bot_data.get('machines', {})
    status_lines = []
    keyboard = []

    for machine, info in machines.items():
        status = info.get('status', 'unknown').lower()
        if status == 'free':
            status_lines.append(f"✅ <b>{machine}</b>: Free")
            keyboard.append([InlineKeyboardButton(f"▶️ Start {machine}", callback_data=f"start_{machine}")])
        elif status == 'occupied':
            end_time = info.get('end_time')
            remaining = (end_time - datetime.datetime.now()).total_seconds() / 60 if end_time else 0
            remaining = max(int(remaining), 0)
            status_lines.append(f"⏳ <b>{machine}</b>: Occupied ({remaining} min left)")
        elif status == 'broken':
            status_lines.append(f"❌ <b>{machine}</b>: Broken")

    status_message = "⚙️ <b>Machine Statuses:</b>\n\n" + "\n".join(status_lines)
    keyboard.append([InlineKeyboardButton("🔧 Modify Status", callback_data="modify_status")])
    keyboard.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="refresh_status")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        await message.edit_text(text=status_message, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await context.bot.send_message(chat_id=chat_id, text=status_message, reply_markup=reply_markup, parse_mode="HTML")

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button clicks."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    username = user.username
    callback_data = query.data

    if username not in AUTHORIZED_USERS:
        await query.edit_message_text("❌ <b>Access Denied.</b>", parse_mode="HTML")
        logger.warning(f"Unauthorized button click by @{username}.")
        return

    if callback_data in ['show_status', 'refresh_status']:
        await show_machine_statuses(query.message.chat_id, context, query.message)
        return
    
    if callback_data == 'modify_status':
        await show_machine_selection(update, context)
        return

    if callback_data.startswith('start_'):
        await handle_machine_start(query, context, user)

async def handle_machine_start(query, context: ContextTypes.DEFAULT_TYPE, user):
    """Handle starting a machine."""
    machine_name = query.data.split('start_')[1]
    machines = context.bot_data.setdefault('machines', {})
    machine = machines.get(machine_name)

    if not machine:
        await query.edit_message_text("⚠️ <b>Selected machine does not exist.</b>", parse_mode="HTML")
        return

    if machine['status'] != 'free':
        await handle_unavailable_machine(query, machine_name, machine)
        return

    duration = get_machine_duration(machine_name)
    await set_machine_occupied(query, context, machine_name, duration, user)

def get_machine_duration(machine_name):
    """Get the duration for a machine type."""
    duration_map = {
        'Washer': 25,  # Standard wash cycle
        'Dryer': 60,    # Standard dry cycle
    }
    machine_type = next((key for key in duration_map if key.lower() in machine_name.lower()), 'Unknown')
    return duration_map.get(machine_type, 2)

async def handle_unavailable_machine(query, machine_name, machine):
    """Handle when a machine is unavailable."""
    status = machine['status']
    if status == 'occupied':
        end_time = machine.get('end_time')
        remaining = (end_time - datetime.datetime.now()).total_seconds() / 60 if end_time else 0
        remaining = max(int(remaining), 0)
        message = f"⏳ <b>{machine_name}</b> is currently occupied for another <b>{remaining} minutes</b>."
    else:
        message = f" <b>{machine_name}</b> is currently <b>{status}</b>."
    await query.edit_message_text(message, parse_mode="HTML")

async def set_machine_occupied(query, context, machine_name, duration, user):
    """Set a machine as occupied."""
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
    context.bot_data['machines'][machine_name] = {
        'status': 'occupied',
        'end_time': end_time,
        'user_id': user.id,
        'username': user.username
    }

    context.job_queue.run_once(
        free_machine,
        when=duration * 60,
        data={
            'machine_name': machine_name,
            'user_id': user.id,
            'username': user.username
        }
    )

    confirmation = (
        f"✅ <b>{machine_name}</b> has been started.\n"
        f"🕒 It will be free in <b>{duration} minutes</b>."
    )
    await query.edit_message_text(confirmation, parse_mode="HTML")
    logger.info(f"Started {machine_name} for @{user.username} for {duration} minutes.")
    
    await show_machine_statuses(query.message.chat_id, context, query.message)

async def free_machine(context: ContextTypes.DEFAULT_TYPE):
    """Free the machine and notify the user."""
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
            notification = await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 <b>{machine_name}</b> is now free. Your cycle is complete.",
                parse_mode="HTML"
            )

            await asyncio.sleep(24*60*60)
            await context.bot.delete_message(chat_id=user_id, message_id=notification.message_id)
            logger.info(f"Deleted notification message for @{username} after 10 seconds.")

        except Exception as e:
            logger.error(f"Failed to send or delete notification for @{username}: {e}")

# Status modification handlers
async def show_machine_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show machine selection buttons for status modification."""
    query = update.callback_query
    machines = context.bot_data.get('machines', {})
    keyboard = []
    
    for machine in machines.keys():
        keyboard.append([InlineKeyboardButton(machine, callback_data=f"select_machine_{machine}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_modification")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Select a machine to modify its status:", reply_markup=reply_markup)
    return SELECTING_MACHINE

async def show_status_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show status options for the selected machine."""
    query = update.callback_query
    await query.answer()
    
    machine_name = query.data.replace("select_machine_", "")
    context.user_data['selected_machine'] = machine_name
    
    # Get current machine status
    machine_info = context.bot_data.get('machines', {}).get(machine_name, {})
    current_status = machine_info.get('status', 'unknown')
    
    # Create status buttons
    keyboard = [
        [InlineKeyboardButton("✅ Set as Free", callback_data="set_status_free")],
        [InlineKeyboardButton("❌ Set as Broken", callback_data="set_status_broken")],
        # Time buttons in descending order, 2 per row
        [
            InlineKeyboardButton("⏳ 60 min", callback_data="set_time_60"),
            InlineKeyboardButton("⏳ 50 min", callback_data="set_time_50")
        ],
        [
            InlineKeyboardButton("⏳ 45 min", callback_data="set_time_45"),
            InlineKeyboardButton("⏳ 40 min", callback_data="set_time_40")
        ],
        [
            InlineKeyboardButton("⏳ 35 min", callback_data="set_time_35"),
            InlineKeyboardButton("⏳ 30 min", callback_data="set_time_30")
        ],
        [
            InlineKeyboardButton("⏳ 25 min", callback_data="set_time_25"),
            InlineKeyboardButton("⏳ 20 min", callback_data="set_time_20")
        ],
        [
            InlineKeyboardButton("⏳ 15 min", callback_data="set_time_15"),
            InlineKeyboardButton("⏳ 10 min", callback_data="set_time_10")
        ],
        [
            InlineKeyboardButton("⏳ 5 min", callback_data="set_time_5"),
            InlineKeyboardButton("↩️ Back", callback_data="modify_status")
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = (
        f"Machine: <b>{machine_name}</b>\n"
        f"Current Status: <b>{current_status.upper()}</b>\n\n"
        f"Choose new status:"
    )
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    return SELECTING_STATUS

async def handle_status_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the status selection for a machine."""
    query = update.callback_query
    await query.answer()
    
    machine_name = context.user_data.get('selected_machine')
    action = query.data
    
    if action == "set_status_free":
        context.bot_data['machines'][machine_name] = {'status': 'free'}
        await show_machine_statuses(query.message.chat_id, context, query.message)
        return ConversationHandler.END
    
    elif action == "set_status_broken":
        context.bot_data['machines'][machine_name] = {'status': 'broken'}
        await show_machine_statuses(query.message.chat_id, context, query.message)
        return ConversationHandler.END
    
    elif action.startswith("set_time_"):
        try:
            duration = int(action.split("_")[-1])
            end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
            
            context.bot_data['machines'][machine_name] = {
                'status': 'occupied',
                'end_time': end_time,
                'user_id': query.from_user.id,
                'username': query.from_user.username
            }
            
            # Schedule the machine to be freed
            context.job_queue.run_once(
                free_machine,
                when=duration * 60,
                data={
                    'machine_name': machine_name,
                    'user_id': query.from_user.id,
                    'username': query.from_user.username
                }
            )
            
            # Show confirmation and update status
            await query.edit_message_text(
                f"✅ Set <b>{machine_name}</b> as occupied for {duration} minutes.",
                parse_mode="HTML"
            )
            
            await show_machine_statuses(query.message.chat_id, context, query.message)
            return ConversationHandler.END
            
        except ValueError as e:
            logger.error(f"Error processing time selection: {e}")
            await query.edit_message_text(
                "⚠️ An error occurred while setting the time.",
                parse_mode="HTML"
            )
            return ConversationHandler.END

async def cancel_modification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the status modification process."""
    query = update.callback_query
    await query.answer()
    await show_machine_statuses(query.message.chat_id, context, query.message)
    return ConversationHandler.END

def get_status_modification_handler():
    """Create and return the ConversationHandler for status modification."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_machine_selection, pattern="^modify_status$")
        ],
        states={
            SELECTING_MACHINE: [
                CallbackQueryHandler(show_status_options, pattern="^select_machine_"),
                CallbackQueryHandler(cancel_modification, pattern="^cancel_modification$")
            ],
            SELECTING_STATUS: [
                CallbackQueryHandler(handle_status_selection, pattern="^set_status_"),
                CallbackQueryHandler(handle_status_selection, pattern="^set_time_"),  # Make sure this pattern matches
                CallbackQueryHandler(show_machine_selection, pattern="^modify_status$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_modification, pattern="^cancel_modification$")
        ],
        allow_reentry=True
    )
    
