import os
import logging
import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import json
import traceback

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
        # Send completion notification
        msg = f"✅ {machine_name} cycle is complete! Please collect your laundry."
        await context.bot.send_message(chat_id=user_id, text=msg)
        logger.info(f"Machine {machine_name} cycle complete. Notified @{username}.")

        # Update machine status
        machine_info['status'] = 'free'
        machine_info.pop('end_time', None)
        machine_info.pop('user_id', None)
        machine_info.pop('username', None)
        
        # Save the updated state
        save_machine_states(context.bot_data['machines'])

async def notify_almost_done(context: ContextTypes.DEFAULT_TYPE):
    """Send notification when 5 minutes remain."""
    job = context.job
    machine_name = job.data['machine_name']
    user_id = job.data['user_id']
    username = job.data['username']
    
    msg = (f"⏰ {machine_name} will complete in 5 minutes!\n"
           f"Please be ready to collect your laundry soon.")
    
    await context.bot.send_message(chat_id=user_id, text=msg)
    logger.info(f"Sent 5-minute warning for {machine_name} to @{username}")

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks for machine status and control."""
    query = update.callback_query
    user = query.from_user
    username = user.username
    callback_data = query.data

    logger.info(f"User @{username} clicked '{callback_data}'.")

    # Authorization check
    if username not in AUTHORIZED_USERS:
        await query.answer()
        await query.edit_message_text(text="Access Denied.")
        logger.warning(f"Unauthorized button click by @{username}.")
        return

    await query.answer()

    if callback_data == 'show_status':
        await handle_status_display(query, context)
    elif callback_data.startswith('start_'):
        await handle_machine_start(query, user, context)
    elif callback_data == 'no_action':
        await query.answer()
    else:
        await query.edit_message_text(text="Unknown action.")


async def handle_status_display(query, context):
    """Display the status of all machines with interactive buttons."""
    machines = context.bot_data['machines']
    status_message = "🏢 Laundry Status:\n\n"
    
    # Group machines by floor
    ground_floor = "1️⃣ Ground Floor:\n"
    upper_floor = "\n2️⃣ Upper Floor:\n"
    
    for machine_name, machine_info in machines.items():
        status = machine_info['status']
        machine_emoji = "🌊" if 'Washer' in machine_name else "🔥"  # Washer/Dryer emoji
        status_icon = get_machine_status_icon(status)
        
        # Build status line
        if status == 'free':
            status_line = f"{machine_emoji} {status_icon} Available\n"
        elif status == 'broken':
            status_line = f"{machine_emoji} {status_icon} Out of Order\n"
        else:
            # Show remaining time for occupied machines
            end_time = machine_info['end_time']
            time_delta = end_time - datetime.datetime.now()
            remaining_minutes = max(0, int(time_delta.total_seconds() / 60))
            status_line = (
                f"{machine_emoji} {status_icon} Busy - "
                f"{remaining_minutes} min remaining\n"
            )
        
        # Add to appropriate floor section
        if 'Ground Floor' in machine_name:
            ground_floor += status_line
        else:
            upper_floor += status_line

    status_message += ground_floor + upper_floor

    # Create buttons for available machines
    keyboard = []
    for machine_name, machine_info in machines.items():
        if machine_info['status'] == 'free':
            machine_emoji = "🌊" if 'Washer' in machine_name else "🔥"
            floor_num = "1️⃣" if 'Ground Floor' in machine_name else "2️⃣"
            display_name = machine_name.replace('Ground Floor', 'GF').replace('Upper Floor', 'UF')
            keyboard.append([
                InlineKeyboardButton(
                    f"{machine_emoji} Start {floor_num} {display_name}",
                    callback_data=f"start_{machine_name}"
                )
            ])
    
    # Add refresh button
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh Status", callback_data="show_status")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=status_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def handle_machine_start(query, user, context):
    """Handle the starting of a machine cycle."""
    try:
        machine_name = query.data[len('start_'):]
        machines = context.bot_data['machines']
        machine_info = machines.get(machine_name)

        # Validate machine availability
        if machine_info is None:
            await query.edit_message_text(text="❌ Error: Invalid machine selected.")
            return
        if machine_info['status'] != 'free':
            await query.edit_message_text(
                text=f"❌ {machine_name} is currently not available."
            )
            return

        # Set cycle duration based on machine type
        duration_minutes = get_cycle_duration(machine_name)
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)

        # Update machine status
        machine_info.update({
            'status': 'occupied',
            'end_time': end_time,
            'user_id': user.id,
            'username': user.username
        })

        # Save state before scheduling notifications
        save_machine_states(context.bot_data['machines'])

        # Schedule notifications
        job_data = {
            'machine_name': machine_name,
            'user_id': user.id,
            'username': user.username
        }

        # Schedule completion notification
        context.job_queue.run_once(
            free_machine,
            duration_minutes * 60,
            data=job_data,
            name=f"complete_{machine_name}_{user.id}"
        )

        # Schedule 5-minute warning
        if duration_minutes > 5:
            context.job_queue.run_once(
                notify_almost_done,
                (duration_minutes - 5) * 60,
                data=job_data,
                name=f"warning_{machine_name}_{user.id}"
            )

        # Send immediate confirmation
        await context.bot.send_message(
            chat_id=user.id,
            text=f"✅ Started {machine_name}\n"
                 f"⏱️ Duration: {duration_minutes} minutes\n"
                 f"🔄 Will complete at: {end_time.strftime('%I:%M %p')}"
        )

        # Update the button message
        keyboard = [
            [InlineKeyboardButton("🔄 View All Machines", callback_data="show_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=f"✅ Successfully started {machine_name}!",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in handle_machine_start: {str(e)}")
        await query.edit_message_text(
            text="❌ An error occurred while starting the machine. "
                 "Please try again or contact support."
        )


def get_machine_status_icon(status):
    """Return appropriate emoji for machine status."""
    return {
        'free': '✅',
        'occupied': '⏳',
        'broken': '⚠️'
    }.get(status, '❓')


def get_cycle_duration(machine_name):
    """Return the cycle duration based on machine type."""
    if 'Washer' in machine_name:
        return 1  # 26 minutes for washing cycle
    elif 'Dryer' in machine_name:
        return 60  # 60 minutes for drying cycle
    return 30  # default duration

def save_machine_states(machines):
    """Saves current machine states to a JSON file."""
    try:
        # Convert datetime objects to string for JSON serialization
        machine_states = {}
        for machine_name, info in machines.items():
            machine_states[machine_name] = info.copy()
            if 'end_time' in machine_states[machine_name]:
                machine_states[machine_name]['end_time'] = info['end_time'].isoformat()

        with open('machine_states.json', 'w') as f:
            json.dump(machine_states, f)
        logger.info("Machine states saved successfully")
    except Exception as e:
        logger.error(f"Error saving machine states: {e}")

def load_machine_states():
    """Loads saved machine states from JSON file."""
    try:
        with open('machine_states.json', 'r') as f:
            machine_states = json.load(f)
            
        # Convert string timestamps back to datetime objects
        for info in machine_states.values():
            if 'end_time' in info:
                info['end_time'] = datetime.datetime.fromisoformat(info['end_time'])
                
        return machine_states
    except FileNotFoundError:
        logger.info("No saved machine states found, using defaults")
        return {
            'Ground Floor Washer': {'status': 'free'},
            'Ground Floor Dryer': {'status': 'free'},
            'Upper Floor Washer 1': {'status': 'free'},
            'Upper Floor Washer 2': {'status': 'free'},
            'Upper Floor Dryer 1': {'status': 'free'},
            'Upper Floor Dryer 2': {'status': 'broken'},
        }
    except Exception as e:
        logger.error(f"Error loading machine states: {e}")
        return {}

async def send_startup_notification(context: ContextTypes.DEFAULT_TYPE):
    """Send notification to admin when bot starts"""
    admin_id = os.getenv('ADMIN_USER_ID')
    if admin_id:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text="🟢 Laundry bot has started/restarted"
            )
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")
