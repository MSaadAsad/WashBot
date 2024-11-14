import os
import datetime
from dotenv import load_dotenv
from pyairtable import Api

# Load environment variables
load_dotenv()

AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')
ADMIN_USERNAMES = os.getenv('ADMIN_USERS', '').split(',')

# Valid actions and machines (for validation)
VALID_ACTIONS = [
    'Start Cycle',
    'Set Free',
    'Set Broken',
    'Set Cycle',
    'Refresh Status'
]

VALID_MACHINES = [
    'Ground Floor Wash',
    'Ground Floor Dry',
    'Floor 1 Wash 1',
    'Floor 1 Wash 2',
    'Floor 1 Dry 1',
    'Floor 1 Dry 2',
    'None'
]

api = Api(AIRTABLE_API_KEY)
table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

def log_action(username: str, action: str, machine: str, duration: int = None):
    """
    Log an action to Airtable
    
    Parameters:
    - username: Used only to check admin status
    - action: Must be one of VALID_ACTIONS
    - machine: Must be one of VALID_MACHINES
    - duration: Integer value for cycle duration (optional)
    """
    try:
        # Validate action and machine
        if action not in VALID_ACTIONS:
            raise ValueError(f"Invalid action: {action}. Must be one of {VALID_ACTIONS}")
        if machine not in VALID_MACHINES:
            raise ValueError(f"Invalid machine: {machine}. Must be one of {VALID_MACHINES}")

        record = {
            "Timestamp": datetime.datetime.now().isoformat(),
            "IsAdmin": username in ADMIN_USERNAMES,
            "Action": str(action),
            "Machine": str(machine),
            "Duration": duration if duration is not None else 0
        }
        
        # Print the record being sent for debugging
        print(f"Sending record to Airtable: {record}")
        
        table.create(record)
        print(f"Successfully logged action: {action} on {machine}")
        
    except Exception as e:
        print(f"Failed to log to Airtable: {e}")

if __name__ == "__main__":
    # Test different scenarios
    print("Testing Airtable Logger...")
    
    # Test viewing status (admin)
    print("\nTesting with admin:")
    log_action(
        username=ADMIN_USERNAMES[0],
        action="Start Cycle",
        machine="Ground Floor Wash",
        duration=45
    )
    
    # Test different actions
    print("\nTesting different actions:")
    test_actions = [
        (ADMIN_USERNAMES[0], "Set Broken", "Floor 1 Dry 1", None),
        ("regular_user", "Start Cycle", "Floor 1 Wash 2", 60),
        (ADMIN_USERNAMES[0], "Set Free", "Ground Floor Dry", None)
    ]
    
    for username, action, machine, duration in test_actions:
        log_action(username, action, machine, duration)
    
    print("\nTest complete!") 
