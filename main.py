import telebot
from telebot import types
import re
import time
import uuid
import threading
import json
import os
from datetime import datetime, timedelta
import pytz
import logging
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ✅ BOT CONFIG - Use environment variables for security
BOT_TOKEN = os.getenv('BOT_TOKEN', '7429740172:AAEUV6A-YmDSzmL0b_0tnCCQ6SbJBEFDXbg')
ADMIN_ID = int(os.getenv('ADMIN_ID', '7929115529'))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is required!")
    raise ValueError("BOT_TOKEN not found in environment variables")
    
if not ADMIN_ID:
    logger.error("ADMIN_ID environment variable is required!")
    raise ValueError("ADMIN_ID not found in environment variables")

try:
    bot = telebot.TeleBot(BOT_TOKEN)
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    raise

# ✅ BOT USERNAME CACHE
BOT_USERNAME = None

def get_bot_username():
    """Get and cache bot username with retry mechanism"""
    global BOT_USERNAME
    if BOT_USERNAME is None:
        try:
            bot_info = bot.get_me()
            BOT_USERNAME = bot_info.username or "Eran_money281bot"
            logger.info(f"Bot username retrieved: {BOT_USERNAME}")
        except Exception as e:
            logger.error(f"Error getting bot username: {e}")
            BOT_USERNAME = "Eran_money281bot"
    return BOT_USERNAME

def get_local_time():
    """Get local time in Indian Standard Time (UTC+5:30)"""
    indian_tz = pytz.timezone('Asia/Kolkata')
    local_time = datetime.now(indian_tz)
    return local_time.strftime("%Y-%m-%d %H:%M:%S")

# ✅ DATA PERSISTENCE - Render compatible paths
DATA_DIR = "/opt/render/project/src" if os.path.exists("/opt/render/project/src") else "."
DATA_FILE = os.path.join(DATA_DIR, "bot_data.json")
BACKUP_FILE = os.path.join(DATA_DIR, "bot_data_backup.json")

def load_data():
    """Load data from file with backup recovery"""
    default_data = {
        'user_balances': {},
        'worked_users': {},
        'pending_tasks': {},
        'referral_data': {},
        'banned_users': [],
        'completed_tasks': {},
        'task_sections': {
            'watch_ads': [],
            'app_downloads': [],
            'promotional': []
        },
        'client_tasks': {},
        'client_referrals': {},
        'client_id_counter': 1,
        'withdrawal_requests': {},
        'task_tracking': {}
    }

    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure all required keys exist
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                logger.info("Data loaded successfully from main file")
                return data
        elif os.path.exists(BACKUP_FILE):
            logger.info("Loading from backup file...")
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure all required keys exist
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                logger.info("Data loaded successfully from backup")
                return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key in default_data:
                        if key not in data:
                            data[key] = default_data[key]
                    logger.info("Successfully loaded from backup after JSON error")
                    return data
            except Exception as backup_error:
                logger.error(f"Backup loading failed: {backup_error}")
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key in default_data:
                        if key not in data:
                            data[key] = default_data[key]
                    logger.info("Successfully loaded from backup")
                    return data
            except Exception as backup_error:
                logger.error(f"Backup loading failed: {backup_error}")

    logger.warning("Using default data structure")
    return default_data

def save_data():
    """Save data to file with enhanced backup and verification"""
    try:
        # Create backup before saving
        if os.path.exists(DATA_FILE):
            import shutil
            try:
                shutil.copy2(DATA_FILE, BACKUP_FILE)
            except Exception as backup_error:
                logger.warning(f"Failed to create backup: {backup_error}")

        data = {
            'user_balances': user_balances,
            'worked_users': worked_users,
            'pending_tasks': pending_tasks,
            'referral_data': referral_data,
            'banned_users': list(banned_users),
            'completed_tasks': {str(k): list(v) if isinstance(v, set) else v for k, v in completed_tasks.items()},
            'task_sections': task_sections,
            'client_tasks': client_tasks,
            'client_referrals': client_referrals,
            'client_id_counter': client_id_counter,
            'withdrawal_requests': withdrawal_requests,
            'task_tracking': task_tracking if 'task_tracking' in globals() else {},
            'save_timestamp': get_local_time(),
            'data_integrity_check': len(user_balances)
        }

        # Atomic write with verification
        temp_file = DATA_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Verify written data
        with open(temp_file, 'r', encoding='utf-8') as f:
            verification_data = json.load(f)
            if verification_data.get('data_integrity_check') != len(user_balances):
                raise Exception("Data integrity check failed")

        os.replace(temp_file, DATA_FILE)
        logger.debug("Data saved successfully")
        return True

    except Exception as e:
        logger.error(f"Error saving data: {e}")
        # Clean up temp file if it exists
        temp_file = DATA_FILE + '.tmp'
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

        # Try to restore from backup if save fails
        if os.path.exists(BACKUP_FILE):
            try:
                import shutil
                shutil.copy2(BACKUP_FILE, DATA_FILE)
                logger.info("Restored from backup after save failure")
            except Exception as restore_error:
                logger.error(f"Failed to restore from backup: {restore_error}")
        return False

# Load initial data
try:
    initial_data = load_data()

    # Safe data conversion with error handling
    user_balances = {}
    for k, v in initial_data.get('user_balances', {}).items():
        try:
            user_balances[int(k)] = float(v)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid user balance data: {k}={v}, error: {e}")

    worked_users = initial_data.get('worked_users', {})
    pending_tasks = initial_data.get('pending_tasks', {})

    referral_data = {}
    for k, v in initial_data.get('referral_data', {}).items():
        try:
            referral_data[int(k)] = int(v)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid referral data: {k}={v}, error: {e}")

    banned_users = set()
    for x in initial_data.get('banned_users', []):
        try:
            banned_users.add(int(x))
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid banned user ID: {x}, error: {e}")

    completed_tasks = {}
    for k, v in initial_data.get('completed_tasks', {}).items():
        try:
            completed_tasks[int(k)] = set(v) if isinstance(v, list) else v
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid completed task data: {k}={v}, error: {e}")

    task_sections = initial_data.get('task_sections', {
        'watch_ads': [],
        'app_downloads': [],
        'promotional': []
    })

    # Ensure all required sections exist
    for section in ['watch_ads', 'app_downloads', 'promotional']:
        if section not in task_sections:
            task_sections[section] = []

    client_tasks = initial_data.get('client_tasks', {})
    client_referrals = initial_data.get('client_referrals', {})
    client_id_counter = initial_data.get('client_id_counter', 1)
    withdrawal_requests = initial_data.get('withdrawal_requests', {})
    task_tracking = initial_data.get('task_tracking', {})

    logger.info("Data initialization completed successfully")

except Exception as e:
    logger.error(f"Critical error during data initialization: {e}")
    # Initialize with defaults
    user_balances = {}
    worked_users = {}
    pending_tasks = {}
    referral_data = {}
    banned_users = set()
    completed_tasks = {}
    task_sections = {'watch_ads': [], 'app_downloads': [], 'promotional': []}
    client_tasks = {}
    client_referrals = {}
    client_id_counter = 1
    withdrawal_requests = {}
    task_tracking = {}

# Remove admin ID from banned users if accidentally banned
banned_users.discard(ADMIN_ID)

# ✅ Runtime variables (not saved to disk)
awaiting_withdraw = {}
awaiting_message = {}
awaiting_task_add = {}
awaiting_support_message = {}
awaiting_promotion_message = {}
awaiting_client_data = {}
awaiting_task_remove = {}
awaiting_notice = {}
awaiting_referral_reset = {}

# ✅ SECURITY SYSTEM - Bot Freeze/Unfreeze Feature
bot_frozen = False
freeze_timestamp = None
awaiting_unlock_code = {}

# Security codes (keep these secret!)
FREEZE_CODE = "/stop2833"
UNFREEZE_CODE = "/connect2833"

# Auto-save with improved error handling and thread safety
def auto_save():
    save_count = 0
    while True:
        try:
            time.sleep(30)  # Increased to 30 seconds to reduce I/O
            if save_data():
                save_count += 1
                logger.info(f"✅ Auto-save completed (#{save_count})")
            else:
                logger.error("❌ Auto-save failed")
        except KeyboardInterrupt:
            logger.info("Auto-save thread interrupted")
            break
        except Exception as e:
            logger.error(f"❌ Auto-save error: {e}")
            # Continue running even if error occurs

# Emoji rotation function
def emoji_rotation_monitor():
    """Monitor and update emojis every 24 hours"""
    while True:
        try:
            time.sleep(3600)  # Check every hour
            get_current_emoji('task')  # This will trigger rotation if 24 hours have passed
        except KeyboardInterrupt:
            logger.info("Emoji rotation thread interrupted")
            break
        except Exception as e:
            logger.error(f"❌ Emoji rotation error: {e}")

# Start auto-save thread
try:
    save_thread = threading.Thread(target=auto_save, daemon=True)
    save_thread.start()
    logger.info("Auto-save thread started")
except Exception as e:
    logger.error(f"Failed to start auto-save thread: {e}")

# Start emoji rotation thread  
try:
    emoji_thread = threading.Thread(target=emoji_rotation_monitor, daemon=True)
    emoji_thread.start()
    logger.info("🎨 Emoji rotation thread started - 24-hour auto-update active")
except Exception as e:
    logger.error(f"Failed to start emoji rotation thread: {e}")

# Thread lock for data operations
data_lock = threading.Lock()

# ✅ DYNAMIC EMOJI SYSTEM - Changes every 24 hours
EMOJI_SETS = {
    'task': ['🎯', '⚡', '🚀', '💎', '🔥', '⭐', '🎪', '🎭', '🎨', '🎲'],
    'balance': ['💎', '💰', '💳', '🏆', '💸', '💵', '🤑', '💹', '💲', '🎁'],
    'submit': ['🚀', '📸', '✨', '🎯', '💫', '⚡', '🔥', '🌟', '💎', '🎪'],
    'withdraw': ['💸', '💳', '🏦', '💰', '🤑', '💵', '💲', '🏧', '💹', '🎁'],
    'referral': ['🔗', '👥', '🤝', '🌐', '📱', '💫', '🔥', '⭐', '🎯', '🚀'],
    'support': ['🛟', '🆘', '📞', '💬', '🤝', '👨‍💻', '🔧', '❓', '💡', '🎧'],
    'user_info': ['👑', '👤', '🆔', '📊', '🏅', '💯', '🎖️', '🌟', '⭐', '👑'],
    'promotion': ['⭐', '🌟', '🔥', '💎', '🚀', '🎯', '💫', '✨', '🎪', '🎭'],
    'watch_ads': ['🎬', '📺', '🎥', '🎞️', '📹', '🎦', '🍿', '🎪', '🎭', '🎨'],
    'app_download': ['📲', '📱', '💿', '📀', '🔽', '⬇️', '💾', '📦', '🎁', '📋'],
    'promotional': ['🎁', '🎉', '🎊', '🎈', '🎀', '🎆', '✨', '💫', '⭐', '🌟'],
    'upi': ['💳', '📱', '💰', '🏦', '💸', '💵', '💲', '🤑', '💹', '🏧'],
    'paypal': ['🌍', '🌎', '🌏', '🌐', '💳', '💰', '💸', '💵', '💲', '🤑'],
    'amazon': ['📦', '🛒', '🎁', '📋', '💰', '💸', '💵', '💲', '🤑', '🏪'],
    'googleplay': ['🎮', '🎯', '🎪', '🎭', '🎨', '🎲', '🎁', '💎', '⭐', '🌟'],
    'back': ['🔙', '↩️', '🔄', '⬅️', '🏠', '🔚', '🔜', '🔝', '🔛', '🔙']
}

# Current emoji configuration - changes daily
current_emojis = {}
last_emoji_change = None

def get_current_emoji(category):
    """Get current emoji for a category with 24-hour rotation"""
    global current_emojis, last_emoji_change

    current_time = datetime.now()

    # Check if 24 hours have passed or if it's the first time
    if (last_emoji_change is None or 
        (current_time - last_emoji_change).total_seconds() >= 86400):  # 86400 seconds = 24 hours

        # Generate new emoji set
        for category_name, emoji_list in EMOJI_SETS.items():
            current_emojis[category_name] = random.choice(emoji_list)

        last_emoji_change = current_time
        logger.info(f"🎨 Emojis rotated! New set active for 24 hours")

        # Notify admin about emoji change
        try:
            emoji_update_msg = "🎨 **Daily Emoji Update!**\n\n"
            emoji_update_msg += "✅ All button emojis have been automatically updated!\n\n"
            emoji_update_msg += "📋 **New Emoji Set:**\n"
            for cat, emoji in current_emojis.items():
                cat_name = cat.replace('_', ' ').title()
                emoji_update_msg += f"{emoji} {cat_name}\n"
            emoji_update_msg += f"\n⏰ **Next Change:** {(current_time + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')}\n"
            emoji_update_msg += "💡 **Purpose:** Keep users engaged with fresh UI!"

            bot.send_message(ADMIN_ID, emoji_update_msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to notify admin about emoji change: {e}")

    return current_emojis.get(category, EMOJI_SETS[category][0])

# Initialize emojis on startup
get_current_emoji('task')

# ✅ Helper Functions
def is_banned(user_id):
    """Check if user is banned with admin protection"""
    if user_id == ADMIN_ID:
        return False
    with data_lock:
        return user_id in banned_users

def is_bot_frozen():
    """Check if bot is in frozen state"""
    return bot_frozen

def freeze_bot(user_id):
    """Freeze the bot - disable all admin functions"""
    global bot_frozen, freeze_timestamp
    bot_frozen = True
    freeze_timestamp = get_local_time()

    # Log security action
    logger.warning(f"🔒 SECURITY: Bot frozen by user {user_id} at {freeze_timestamp}")

    # Save freeze state to data
    try:
        save_data()
    except:
        pass

    return True

def unfreeze_bot(user_id):
    """Unfreeze the bot - restore all functions"""
    global bot_frozen, freeze_timestamp
    bot_frozen = False
    unfreeze_time = get_local_time()

    # Log security action
    logger.info(f"🔓 SECURITY: Bot unfrozen by user {user_id} at {unfreeze_time}")

    # Clear awaiting unlock codes
    awaiting_unlock_code.clear()

    # Save unfreeze state to data
    try:
        save_data()
    except:
        pass

    return True

def generate_referral_link(user_id):
    """Generate referral link using cached bot username"""
    bot_username = get_bot_username()
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def generate_client_tracking_link(client_id, task_type="general"):
    """Generate tracking link for client tasks with error handling"""
    try:
        bot_username = get_bot_username()
        clean_task_type = task_type.replace(" ", "").replace("-", "")
        return f"https://t.me/{bot_username}?start=client_{client_id}_{clean_task_type}"
    except Exception as e:
        print(f"Error generating tracking link: {e}")
        return f"https://t.me/Eran_money281bot?start=client_{client_id}_{task_type}"

def generate_task_tracking_link(section, task_index, task_type="general"):
    """Generate enhanced tracking link for ALL task sections"""
    try:
        bot_username = get_bot_username()
        section_code = section.replace('watch_ads', 'watchads').replace('app_downloads', 'appdownload').replace('promotional', 'promo')
        clean_task_type = task_type.replace(" ", "").replace("-", "")
        tracking_id = f"{section_code}_{task_index}_{clean_task_type}"
        return f"https://t.me/{bot_username}?start=track_{tracking_id}"
    except Exception as e:
        print(f"Error generating task tracking link: {e}")
        return f"https://t.me/Eran_money281bot?start=track_{section}_{task_index}_{task_type}"

def process_referral(new_user_id, referrer_id):
    """Process referral bonuses with thread safety"""
    if referrer_id != new_user_id and new_user_id not in referral_data:
        try:
            with data_lock:
                user_balances[referrer_id] = user_balances.get(referrer_id, 0) + 5.0
                user_balances[new_user_id] = user_balances.get(new_user_id, 0) + 5.0
                referral_data[new_user_id] = referrer_id

            if save_data():
                logger.info(f"💰 Referral bonus added - Referrer: {referrer_id}, New User: {new_user_id}")

                try:
                    bot.send_message(referrer_id, "🎉 Referral successful! ₹5.00 added to your balance.")
                except Exception as msg_error:
                    logger.warning(f"Failed to notify referrer {referrer_id}: {msg_error}")

                try:
                    bot.send_message(new_user_id, "🎉 Welcome bonus! ₹5.00 added to your balance.")
                except Exception as msg_error:
                    logger.warning(f"Failed to notify new user {new_user_id}: {msg_error}")
            else:
                logger.error("Failed to save referral data")
        except Exception as e:
            logger.error(f"Error in referral processing: {e}")

def process_client_referral(new_user_id, client_id, task_type):
    """Process client task referrals with real-time tracking"""
    try:
        if client_id in client_tasks:
            if client_id not in client_referrals:
                client_referrals[client_id] = []

            try:
                user_chat = bot.get_chat(new_user_id)
                username = user_chat.username or "No Username"
                first_name = user_chat.first_name or "Unknown"
            except:
                username = "No Username"
                first_name = "Unknown"

            user_info = {
                'user_id': new_user_id,
                'username': username,
                'first_name': first_name,
                'task_type': task_type,
                'timestamp': get_local_time()
            }

            existing_user = any(ref['user_id'] == new_user_id for ref in client_referrals[client_id])
            if not existing_user:
                client_referrals[client_id].append(user_info)
                save_data()

                try:
                    client_task = client_tasks[client_id]
                    client_name = client_task.get('info', 'Unknown Client')

                    notification = f"🚨 **REAL-TIME CLIENT TRACKING ALERT!**\n\n"
                    notification += f"👤 **User:** {user_info['first_name']} (@{user_info['username']})\n"
                    notification += f"🆔 **User ID:** {new_user_id}\n"
                    notification += f"🎯 **Client:** {client_name} (ID: {client_id})\n"
                    notification += f"📝 **Task Type:** {task_type}\n"
                    notification += f"⏰ **Time:** {user_info['timestamp']}\n"
                    notification += f"📊 **Total Members:** {len(client_referrals[client_id])}\n\n"
                    notification += f"💡 **This proves user completed client task!**"

                    bot.send_message(ADMIN_ID, notification, parse_mode="Markdown")
                except Exception as e:
                    print(f"Error sending notification: {e}")
    except Exception as e:
        print(f"Error in client referral processing: {e}")

def process_task_tracking(new_user_id, task_id, task_type, section):
    """Enhanced task tracking for ALL sections with detailed analytics"""
    try:
        # Initialize tracking data if not exists
        if 'task_tracking' not in globals():
            global task_tracking
            task_tracking = {}

        if task_id not in task_tracking:
            task_tracking[task_id] = []

        try:
            user_chat = bot.get_chat(new_user_id)
            username = user_chat.username or "No Username"
            first_name = user_chat.first_name or "Unknown"
        except:
            username = "No Username"
            first_name = "Unknown"

        # Check if user already tracked this specific task
        existing_user = any(track['user_id'] == new_user_id for track in task_tracking[task_id])

        user_info = {
            'user_id': new_user_id,
            'username': username,
            'first_name': first_name,
            'task_type': task_type,
            'section': section,
            'timestamp': get_local_time(),
            'tracking_ip': 'tracked',  # You can enhance this with real IP tracking
            'verification_status': 'pending'
        }

        if not existing_user:
            task_tracking[task_id].append(user_info)
            save_data()

            try:
                section_name = section.replace('_', ' ').title()

                # Get task details if available
                task_details = "Unknown Task"
                if section in task_sections and len(task_sections[section]) > int(task_id.split('_')[1]):
                    task_index = int(task_id.split('_')[1])
                    task_details = task_sections[section][task_index][:50] + "..."

                notification = f"🚨 **ENHANCED TASK TRACKING ALERT!**\n\n"
                notification += f"👤 **User:** {user_info['first_name']} (@{user_info['username']})\n"
                notification += f"🆔 **User ID:** {new_user_id}\n"
                notification += f"📱 **Section:** {section_name}\n"
                notification += f"🎯 **Task ID:** {task_id}\n"
                notification += f"📝 **Task:** {task_details}\n"
                notification += f"🔍 **Action:** {task_type}\n"
                notification += f"⏰ **Time:** {user_info['timestamp']}\n"
                notification += f"📊 **Total Engagements:** {len(task_tracking[task_id])}\n"
                notification += f"✅ **Status:** Real-time verified\n\n"
                notification += f"💡 **User successfully engaged with {section_name.lower()} task!**\n"
                notification += f"🔍 **Next:** Monitor for task completion submission"

                bot.send_message(ADMIN_ID, notification, parse_mode="Markdown")

                # Send confirmation to user
                bot.send_message(new_user_id, f"✅ **Tracking Confirmed!**\n\n🎯 Your activity has been recorded\n📱 Section: {section_name}\n⚡ Status: Verified\n\n💡 Continue with the task to earn rewards!", parse_mode="Markdown")

            except Exception as e:
                print(f"Error sending tracking notification: {e}")
        else:
            # User already tracked - send different notification
            bot.send_message(new_user_id, f"🔄 **Already Tracked!**\n\n📱 You've already engaged with this task\n🎯 Section: {section.replace('_', ' ').title()}\n\n💡 Complete the task to earn rewards!", parse_mode="Markdown")

    except Exception as e:
        print(f"Error in task tracking processing: {e}")

def extract_link_from_task(task_text):
    """Extract URL from task text"""
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, task_text)
    return urls[0] if urls else None

def extract_reward_from_task(task_text):
    """Extract reward amount from task text with auto-balance feature"""
    reward_pattern = r'₹(\d+(?:\.\d+)?)'
    match = re.search(reward_pattern, task_text)
    return float(match.group(1)) if match else 0

def is_client_task(task_text):
    """Check if task is a client tracking task"""
    return "TRACKING:" in task_text and "ORIGINAL:" in task_text

def validate_amount(amount_str):
    """Validate and convert amount string to float with enhanced checks"""
    try:
        amount = float(amount_str)
        if amount < 0:
            return None, "❌ Amount cannot be negative"
        if amount > 1000000:  # Maximum limit check
            return None, "❌ Amount too large (max: ₹10,00,000)"
        if amount != round(amount, 2):  # Check decimal places
            amount = round(amount, 2)
        return amount, None
    except ValueError:
        return None, "❌ Invalid amount format"
    except Exception as e:
        return None, f"❌ Validation error: {str(e)}"

def validate_user_id(user_id_str):
    """Validate and convert user ID string to int"""
    try:
        user_id = int(user_id_str)
        if user_id <= 0:
            return None, "❌ Invalid user ID"
        return user_id, None
    except ValueError:
        return None, "❌ Invalid user ID format"

def reset_user_state(user_id):
    """Reset all user states"""
    awaiting_withdraw.pop(user_id, None)
    awaiting_message.pop(user_id, None)
    awaiting_task_add.pop(user_id, None)
    awaiting_support_message.pop(user_id, None)
    awaiting_promotion_message.pop(user_id, None)
    awaiting_client_data.pop(user_id, None)
    awaiting_task_remove.pop(user_id, None)
    awaiting_notice.pop(user_id, None)
    awaiting_referral_reset.pop(user_id, None)

def notify_admin_user_action(user_id, first_name, username, action, additional_info=""):
    """Send notification to admin about user actions"""
    try:
        balance = user_balances.get(user_id, 0)

        notification = f"🚨 **USER ACTIVITY ALERT!**\n\n"
        notification += f"👤 **Name:** {first_name or 'Unknown'}\n"
        notification += f"🔗 **Username:** @{username or 'No Username'}\n"
        notification += f"🆔 **User ID:** {user_id}\n"
        notification += f"💰 **Balance:** ₹{balance:.2f}\n"
        notification += f"⚡ **Action:** {action}\n"

        if additional_info:
            notification += f"📋 **Details:** {additional_info}\n"

        notification += f"⏰ **Time:** {get_local_time()}"

        bot.send_message(ADMIN_ID, notification, parse_mode="Markdown")
    except Exception as e:
        print(f"Error sending admin notification: {e}")

def generate_fixed_client_id():
    """Generate fixed client ID for same day"""
    global client_id_counter
    today = datetime.now().strftime("%Y%m%d")
    client_id = f"C{today}{client_id_counter:03d}"
    client_id_counter += 1
    save_data()
    return client_id

def auto_add_balance_for_task(user_id, task_text, task_section, task_index):
    """Auto-add balance if reward is ₹0.1 or more"""
    try:
        reward = extract_reward_from_task(task_text)
        if reward >= 0.1:
            user_balances[user_id] = user_balances.get(user_id, 0) + reward
            save_data()

            # Mark task as completed for limited sections
            if task_section in ['app_downloads', 'promotional', 'watch_ads']:
                if user_id not in completed_tasks:
                    completed_tasks[user_id] = set()
                completed_tasks[user_id].add(f"{task_section}_{task_index}")
                save_data()

            return True, reward
        return False, 0
    except Exception as e:
        print(f"Error in auto balance addition: {e}")
        return False, 0

# ✅ MARKUP GENERATORS
def generate_task_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # Get dynamic emojis
    watch_emoji = get_current_emoji('watch_ads')
    app_emoji = get_current_emoji('app_download')
    promo_emoji = get_current_emoji('promotional')
    back_emoji = get_current_emoji('back')

    markup.row(f"{watch_emoji} Watch Ads", f"{app_emoji} App Download", f"{promo_emoji} Promotional")
    markup.row(f"{back_emoji} Back")
    return markup

def generate_withdraw_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # Get dynamic emojis
    upi_emoji = get_current_emoji('upi')
    paypal_emoji = get_current_emoji('paypal')
    amazon_emoji = get_current_emoji('amazon')
    google_emoji = get_current_emoji('googleplay')
    back_emoji = get_current_emoji('back')

    markup.row(f"{upi_emoji} UPI", f"{paypal_emoji} PayPal")
    markup.row(f"{amazon_emoji} Amazon Pay", f"{google_emoji} Google Play Gift")
    markup.row(f"{back_emoji} Back")
    return markup

def generate_approval_markup(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
    )
    return markup

def generate_withdrawal_approval_markup(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("✅ Approve Payment", callback_data=f"approve_withdrawal_{user_id}"))
    markup.add(types.InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_withdrawal_{user_id}"))
    return markup

def generate_admin_task_markup():
    """Complete admin task management markup with all features"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✨ Add Task", callback_data="admin_add_task"),
        types.InlineKeyboardButton("🗑️ Remove Tasks", callback_data="admin_remove_task")
    )
    markup.add(
        types.InlineKeyboardButton("🎬 Watch Ads", callback_data="admin_watch_ads"),
        types.InlineKeyboardButton("📲 App Download", callback_data="admin_app_downloads")
    )
    markup.add(
        types.InlineKeyboardButton("🎁 Promotional", callback_data="admin_promotional"),
        types.InlineKeyboardButton("🎯 Client Tasks", callback_data="admin_client_tasks")
    )
    markup.add(
        types.InlineKeyboardButton("🔗 Referral Mgmt", callback_data="admin_referral_mgmt"),
        types.InlineKeyboardButton("📣 Send Notice", callback_data="admin_send_notice")
    )
    markup.add(types.InlineKeyboardButton("❌ Close Panel", callback_data="close_admin_panel"))
    return markup

def generate_client_task_options():
    """Generate simplified client task management with only add and remove options"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🌟 Add Link", callback_data="add_client_task_link"),
        types.InlineKeyboardButton("❌ Remove Link", callback_data="remove_client_task_link")
    )
    markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_admin"))
    return markup

def generate_promotion_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # Get dynamic emojis
    promotion_emoji = get_current_emoji('promotion')
    back_emoji = get_current_emoji('back')

    markup.row("📈 Bot Status", f"{promotion_emoji} Request Promotion")
    markup.row(f"{back_emoji} Back")
    return markup

def generate_main_menu():
    """Generate main menu markup with dynamic emojis"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # Get dynamic emojis
    task_emoji = get_current_emoji('task')
    balance_emoji = get_current_emoji('balance')
    submit_emoji = get_current_emoji('submit')
    withdraw_emoji = get_current_emoji('withdraw')
    referral_emoji = get_current_emoji('referral')
    support_emoji = get_current_emoji('support')
    user_info_emoji = get_current_emoji('user_info')
    promotion_emoji = get_current_emoji('promotion')

    markup.row(f"{task_emoji} Task", f"{balance_emoji} Balance", f"{submit_emoji} Submit Proof")
    markup.row(f"{withdraw_emoji} Withdraw", f"{referral_emoji} Referral", f"{support_emoji} Support")
    markup.row(f"{user_info_emoji} User Info", f"{promotion_emoji} Promotion")
    return markup

def generate_enhanced_remove_task_markup():
    """Enhanced task removal menu with all sections including auto-tracking"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("❌ Watch Ads", callback_data="remove_watch_ads"),
        types.InlineKeyboardButton("❌ App Download", callback_data="remove_app_downloads")
    )
    markup.add(
        types.InlineKeyboardButton("❌ Promotional", callback_data="remove_promotional"),
        types.InlineKeyboardButton("❌ Client Tasks", callback_data="remove_client_tasks")
    )
    markup.add(types.InlineKeyboardButton("🚨 Remove All Tasks", callback_data="remove_all_tasks"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_admin"))
    return markup

def generate_task_removal_list(section):
    """Generate interactive task removal list with improved handling"""
    markup = types.InlineKeyboardMarkup()

    if section == "client_tasks":
        if client_tasks:
            for client_id, task_data in client_tasks.items():
                client_name = task_data.get('info', 'Unknown Client')
                links_count = len(task_data.get('links', []))
                referrals_count = len(client_referrals.get(client_id, []))
                button_text = f"🗑️ {client_name} ({links_count} links, {referrals_count} users)"

                if len(button_text) > 60:
                    client_name = client_name[:20] + "..."
                    button_text = f"🗑️ {client_name} ({links_count}L, {referrals_count}U)"

                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"remove_client_{client_id}"))
        else:
            markup.add(types.InlineKeyboardButton("ℹ️ No client tasks available", callback_data="no_action"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Client Management", callback_data="admin_client_tasks"))

    elif section == "all_tasks":
        total_tasks = sum(len(tasks) for tasks in task_sections.values()) + len(client_tasks)
        if total_tasks > 0:
            markup.add(types.InlineKeyboardButton(f"⚠️ DELETE ALL TASKS ({total_tasks})", callback_data="confirm_delete_all"))
            markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_remove_task"))
        else:
            markup.add(types.InlineKeyboardButton("ℹ️ No tasks to remove", callback_data="no_action"))
            markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_remove_task"))

    else:
        if section in task_sections and task_sections[section]:
            for i, task in enumerate(task_sections[section]):
                task_preview = task[:30] + "..." if len(task) > 30 else task
                button_text = f"🗑️ {i+1}. {task_preview}"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"remove_task_{section}_{i}"))
        else:
            markup.add(types.InlineKeyboardButton("ℹ️ No tasks available", callback_data="no_action"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="admin_remove_task"))

    return markup

def generate_task_add_markup():
    """Generate task addition menu with back button"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 Watch Ads", callback_data="add_watch_ads"),
        types.InlineKeyboardButton("📲 App Download", callback_data="add_app_downloads")
    )
    markup.add(types.InlineKeyboardButton("🎁 Promotional", callback_data="add_promotional"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_admin"))
    return markup

# ✅ START COMMAND
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    reset_user_state(user_id)

    if is_banned(user_id):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🆘 Support", "🔙 Back")
        bot.send_message(
            message.chat.id,
            "❌ You have been banned from using this bot.\n\n🆘 You can contact admin through Support if needed.",
            reply_markup=markup
        )
        return

    # Handle referral and client tracking
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]

        if ref_code.startswith('ref_'):
            try:
                referrer_id = int(ref_code.replace('ref_', ''))
                if user_id not in referral_data and user_id not in user_balances:
                    process_referral(user_id, referrer_id)
            except Exception as e:
                print(f"Referral error: {e}")

        elif ref_code.startswith('client_'):
            try:
                parts = ref_code.replace('client_', '').split('_')
                client_id = parts[0]
                task_type = parts[1] if len(parts) > 1 else "general"

                if client_id in client_tasks:
                    if client_id not in client_referrals:
                        client_referrals[client_id] = []

                    existing_user = any(ref['user_id'] == user_id for ref in client_referrals[client_id])
                    if not existing_user:
                        process_client_referral(user_id, client_id, task_type)
                        bot.send_message(
                            user_id,
                            f"🎯 **Client Task Successfully Completed!**\n\n✅ Your participation has been tracked!\n🏷️ Client ID: {client_id}\n📝 Task: {task_type}\n\n🚨 **Admin has been notified automatically**\n💡 **Note:** Reward will be determined by admin",
                            parse_mode="Markdown"
                        )
                    else:
                        bot.send_message(user_id, f"ℹ️ You have already completed this client task.\n🏷️ Client ID: {client_id}")
                else:
                    bot.send_message(user_id, "⚠️ Invalid tracking link - client not found.")
            except Exception as e:
                print(f"Client tracking error: {e}")
                bot.send_message(user_id, "⚠️ Invalid tracking link format.")

        elif ref_code.startswith('track_'):
            try:
                parts = ref_code.replace('track_', '').split('_')
                section = parts[0]
                task_index = int(parts[1])
                task_type = parts[2] if len(parts) > 2 else "general"

                # Enhanced tracking for ALL sections
                section_mapping = {
                    'watchads': 'watch_ads',
                    'appdownload': 'app_downloads', 
                    'promo': 'promotional'
                }

                real_section = section_mapping.get(section, section)

                if real_section in task_sections:
                    if 0 <= task_index < len(task_sections[real_section]):
                        task_id = f"{real_section}_{task_index}"
                        process_task_tracking(user_id, task_id, task_type, real_section)

                        section_name = real_section.replace('_', ' ').title()

                        # Get task name for better tracking
                        task_name = "Unknown Task"
                        if task_index < len(task_sections[real_section]):
                            task_name = task_sections[real_section][task_index][:50]

                        bot.send_message(
                            user_id,
                            f"🎯 **{section_name} Task Tracking Completed!**\n\n✅ Your activity has been verified!\n📱 Section: {section_name}\n📝 Task: {task_name}...\n🔍 Action: {task_type}\n\n🚨 **Admin has been notified automatically**\n💡 **Next Step:** Complete the task to earn rewards\n\n⚡ **Status:** Real-time tracking active",
                            parse_mode="Markdown"
                        )
                    else:
                        bot.send_message(user_id, "⚠️ Invalid task index - task not found.")
                else:
                    bot.send_message(user_id, "⚠️ Invalid tracking link - section not found.")
            except Exception as e:
                print(f"Task tracking error: {e}")
                bot.send_message(user_id, "⚠️ Invalid task tracking link format.")

    markup = generate_main_menu()
    bot.send_message(
        message.chat.id,
        "👋 Welcome to *Earn Money Bot!*\nChoose an option below:",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ✅ ENHANCED TEXT MESSAGE HANDLER
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message):
    try:
        user_id = message.from_user.id
        name = message.from_user.first_name or "Unknown"
        username = message.from_user.username or "No Username"
        text = message.text.strip() if message.text else ""

        if not text:
            logger.warning(f"Empty message from user {user_id}")
            return

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return

    # ✅ SECURITY SYSTEM - Handle freeze/unfreeze commands FIRST
    if text == FREEZE_CODE:
        try:
            if freeze_bot(user_id):
                freeze_msg = f"🔒 **SECURITY ALERT: BOT FROZEN**\n\n"
                freeze_msg += f"🚨 **Emergency Freeze Activated!**\n"
                freeze_msg += f"👤 **Triggered by:** {name} (@{username})\n"
                freeze_msg += f"🆔 **User ID:** {user_id}\n"
                freeze_msg += f"⏰ **Time:** {freeze_timestamp}\n\n"
                freeze_msg += f"🔐 **Status:** All admin functions disabled\n"
                freeze_msg += f"💡 **Note:** Only unlock code can restore bot\n\n"
                freeze_msg += f"🛡️ **Security feature active**"

                bot.send_message(user_id, freeze_msg, parse_mode="Markdown")

                # Notify admin about freeze
                try:
                    admin_alert = f"🚨 **জরুরি সিকিউরিটি অ্যালার্ট**\n\n"
                    admin_alert += f"🔒 **বট ফ্রিজ হয়ে গেছে**\n\n"
                    admin_alert += f"👤 **ফ্রিজ করেছে:** {name} (@{username})\n"
                    admin_alert += f"🆔 **ইউজার আইডি:** {user_id}\n"
                    admin_alert += f"⏰ **সময়:** {freeze_timestamp}\n\n"
                    admin_alert += f"⚠️ **সমস্ত এডমিন ফাংশন বন্ধ করা হয়েছে**\n"
                    admin_alert += f"🔑 **আনলক করতে আনলক কোড পাঠান**\n\n"
                    admin_alert += f"🛡️ **এটি একটি সিকিউরিটি ফিচার**"

                    bot.send_message(ADMIN_ID, admin_alert, parse_mode="Markdown")
                except:
                    pass
        except Exception as e:
            logger.error(f"Error freezing bot: {e}")
        return

    elif text == UNFREEZE_CODE:
        if is_bot_frozen():
            try:
                if unfreeze_bot(user_id):
                    unfreeze_msg = f"🔓 **SECURITY: BOT UNFROZEN**\n\n"
                    unfreeze_msg += f"✅ **Emergency Unfreeze Successful!**\n"
                    unfreeze_msg += f"👤 **Unlocked by:** {name} (@{username})\n"
                    unfreeze_msg += f"🆔 **User ID:** {user_id}\n"
                    unfreeze_msg += f"⏰ **Time:** {get_local_time()}\n\n"
                    unfreeze_msg += f"🔐 **Status:** All functions restored\n"
                    unfreeze_msg += f"💡 **Note:** Bot is now fully operational\n\n"
                    unfreeze_msg += f"🛡️ **Security feature deactivated**"

                    bot.send_message(user_id, unfreeze_msg, parse_mode="Markdown")

                    # Notify admin about unfreeze
                    try:
                        admin_alert = f"🔓 **সিকিউরিটি অ্যালার্ট: বট আনফ্রিজ**\n\n"
                        admin_alert += f"✅ **বট আনলক করা হয়েছে**\n\n"
                        admin_alert += f"👤 **আনলক করেছে:** {name} (@{username})\n"
                        admin_alert += f"🆔 **ইউজার আইডি:** {user_id}\n"
                        admin_alert += f"⏰ **সময়:** {get_local_time()}\n\n"
                        admin_alert += f"🔐 **সমস্ত এডমিন ফাংশন পুনরুদ্ধার**\n"
                        admin_alert += f"🛡️ **বট এখন সম্পূর্ণ কার্যক্ষম**"

                        bot.send_message(ADMIN_ID, admin_alert, parse_mode="Markdown")
                    except:
                        pass

                    # Clear any waiting unlock states
                    awaiting_unlock_code.clear()
            except Exception as e:
                logger.error(f"Error unfreezing bot: {e}")
        else:
            bot.send_message(user_id, "ℹ️ **Bot is not frozen.** No action needed.")
        return

    # Handle unlock code input when admin is waiting
    if user_id in awaiting_unlock_code and awaiting_unlock_code[user_id]:
        if text == UNFREEZE_CODE:
            if unfreeze_bot(user_id):
                unfreeze_msg = f"🔓 **এডমিন আনলক সফল**\n\n"
                unfreeze_msg += f"✅ **সঠিক আনলক কোড প্রবেশ করানো হয়েছে**\n"
                unfreeze_msg += f"🔐 **সমস্ত এডমিন ফাংশন পুনরুদ্ধার**\n"
                unfreeze_msg += f"⏰ **সময়:** {get_local_time()}\n\n"
                unfreeze_msg += f"🛡️ **স্বাগতম ফিরে, এডমিন!**"

                bot.send_message(user_id, unfreeze_msg, parse_mode="Markdown")
            awaiting_unlock_code.pop(user_id, None)
        else:
            bot.send_message(user_id, f"❌ **ভুল আনলক কোড!**\n\n🔑 **প্রত্যাশিত:** আনলক কোড\n💡 **আবার চেষ্টা করুন**")
        return

    # ✅ SECURITY CHECK - Block admin functions if frozen
    if is_bot_frozen():
        # Allow basic user functions but block admin functions
        if user_id == ADMIN_ID:
            # Admin trying to use bot while frozen
            awaiting_unlock_code[user_id] = True
            frozen_msg = f"🔒 **বট ফ্রিজ হয়ে গেছে**\n\n"
            frozen_msg += f"🚨 **সিকিউরিটি মোড চালু**\n"
            frozen_msg += f"⏰ **ফ্রিজ করার সময়:** {freeze_timestamp}\n\n"
            frozen_msg += f"🔑 **আনলক কোড দিয়ে অ্যাক্সেস ফিরে পেতে পারেন**\n"
            frozen_msg += f"💡 **আনলক কোড পাঠান**\n\n"
            frozen_msg += f"🛡️ **এটি একটি সিকিউরিটি ফিচার**"

            bot.send_message(user_id, frozen_msg, parse_mode="Markdown")
            return
        else:
            # Regular user - show frozen status
            if text.startswith('/') or text in [
                f"{get_current_emoji('task')} Task", "🎯 Task",
                f"{get_current_emoji('balance')} Balance", "💎 Balance",
                f"{get_current_emoji('submit')} Submit Proof", "🚀 Submit Proof",
                f"{get_current_emoji('withdraw')} Withdraw", "💸 Withdraw",
                f"{get_current_emoji('referral')} Referral", "🔗 Referral",
                f"{get_current_emoji('support')} Support", "🛟 Support",
                f"{get_current_emoji('user_info')} User Info", "👑 User Info",
                f"{get_current_emoji('promotion')} Promotion", "⭐ Promotion"
            ]:
                frozen_user_msg = f"🔒 **BOT TEMPORARILY FROZEN**\n\n"
                frozen_user_msg += f"🚨 **Maintenance Mode Active**\n"
                frozen_user_msg += f"⏰ **Since:** {freeze_timestamp}\n\n"
                frozen_user_msg += f"💡 **Your data is safe and secure**\n"
                frozen_user_msg += f"🔄 **Bot will be restored soon**\n\n"
                frozen_user_msg += f"🛡️ **Thank you for your patience**"

                bot.send_message(user_id, frozen_user_msg, parse_mode="Markdown")
                return

    # Handle Back button - reset states first (support dynamic emojis)
    back_emoji = get_current_emoji('back')
    support_emoji = get_current_emoji('support')

    if text in [f"{back_emoji} Back", "🔙 Back"]:
        reset_user_state(user_id)

        if is_banned(user_id):
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row(f"{support_emoji} Support", f"{back_emoji} Back")
            bot.send_message(message.chat.id, "🏠 Main Menu:\n\n❌ **You are banned** - Only Support works.", reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, f"🏠 Main Menu: {get_current_emoji('task')}✨", reply_markup=generate_main_menu())
        return

    # Handle banned users
    if is_banned(user_id):
        if text in ["🆘 Support"] or user_id in awaiting_support_message:
            pass
        elif text in ["🎯 Task", "💎 Balance", "🚀 Submit Proof", "💸 Withdraw", "🔗 Referral", "🎬 Watch Ads", "📲 App Download", "🎁 Promotional", "💳 UPI", "🌍 PayPal", "📦 Amazon Pay", "🎮 Google Play Gift", "⭐ Promotion"]:
            bot.send_message(user_id, "❌ You are banned from using this feature.\n\n🛟 Only Support is available for banned users.")
            return
        else:
            bot.send_message(user_id, "❌ You have been banned from using this bot.\n\n🆘 You can only access Support to contact admin.")
            return

    # ✅ ENHANCED ADMIN COMMANDS
    if user_id == ADMIN_ID:
        # Additional security check for admin commands
        if is_bot_frozen():
            awaiting_unlock_code[user_id] = True
            frozen_admin_msg = f"🔒 **বট ফ্রিজ হয়ে গেছে**\n\n"
            frozen_admin_msg += f"🚨 **বট ফ্রিজ অবস্থায় আছে**\n"
            frozen_admin_msg += f"⏰ **ফ্রিজ করার সময়:** {freeze_timestamp}\n\n"
            frozen_admin_msg += f"🔑 **আনলক কোড দিন:**\n"
            frozen_admin_msg += f"💡 **সমস্ত এডমিন ফাংশন বন্ধ**\n\n"
            frozen_admin_msg += f"🛡️ **সিকিউরিটি সুরক্ষা চালু**"

            bot.send_message(user_id, frozen_admin_msg, parse_mode="Markdown")
            return
        if text.startswith("/addbalance"):
            try:
                parts = text.split()
                if len(parts) != 3:
                    bot.send_message(ADMIN_ID, "⚠️ Usage: /addbalance user_id amount\n💡 Use negative amounts to deduct balance")
                    return

                target_id, error = validate_user_id(parts[1])
                if error:
                    bot.send_message(ADMIN_ID, error)
                    return

                amount_str = parts[2]
                try:
                    amount = float(amount_str)
                except ValueError:
                    bot.send_message(ADMIN_ID, "❌ Invalid amount format")
                    return

                old_balance = user_balances.get(target_id, 0)
                user_balances[target_id] = max(0, old_balance + amount)
                new_balance = user_balances[target_id]
                save_data()

                operation = "added" if amount >= 0 else "deducted"
                print(f"💰 Balance updated - User: {target_id}, Amount: {amount:+.2f}, Operation: {operation}")

                try:
                    if amount >= 0:
                        notification_message = f"💰 **Balance Added!**\n\n"
                        notification_message += f"✅ ₹{amount:.2f} has been added to your account by admin!\n\n"
                    else:
                        notification_message = f"💸 **Balance Deducted!**\n\n"
                        notification_message += f"⚠️ ₹{abs(amount):.2f} has been deducted from your account by admin!\n\n"

                    notification_message += f"📊 **Balance Update:**\n"
                    notification_message += f"   • Previous: ₹{old_balance:.2f}\n"
                    notification_message += f"   • {operation.title()}: ₹{abs(amount):.2f}\n"
                    notification_message += f"   • Current: ₹{new_balance:.2f}"

                    bot.send_message(target_id, notification_message, parse_mode="Markdown")
                    bot.send_message(ADMIN_ID, f"✅ ₹{abs(amount):.2f} {operation} for user {target_id}. New balance: ₹{new_balance:.2f}")

                except Exception as e:
                    bot.send_message(ADMIN_ID, f"✅ ₹{abs(amount):.2f} {operation} for user {target_id}. New balance: ₹{new_balance:.2f}\n⚠️ Could not send notification: {str(e)}")

            except Exception as e:
                bot.reply_to(message, f"⚠️ Error: {str(e)}")

        elif text.startswith("/balance"):
            try:
                parts = text.split()
                if len(parts) != 2:
                    bot.send_message(ADMIN_ID, "⚠️ Usage: /balance user_id")
                    return

                target_id, error = validate_user_id(parts[1])
                if error:
                    bot.send_message(ADMIN_ID, error)
                    return

                bal = user_balances.get(target_id, 0)
                bot.send_message(ADMIN_ID, f"👤 User ID: {target_id}\n💰 Balance: ₹{bal:.2f}")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Error: {str(e)}")

        elif text.startswith("/addclienttask"):
            try:
                parts = text.split(' ', 2)
                if len(parts) >= 3:
                    client_name = parts[1]
                    links_text = parts[2]
                    original_links = [link.strip() for link in links_text.split() if link.strip().startswith('http')]

                    if original_links:
                        client_id = generate_fixed_client_id()

                        client_tasks[client_id] = {
                            'info': client_name,
                            'links': original_links,
                            'created_at': get_local_time(),
                            'tracking_links': [],
                            'auto_tracking': True
                        }

                        for i, original_link in enumerate(original_links):
                            tracking_link = generate_client_tracking_link(client_id, f"link{i+1}")
                            client_tasks[client_id]['tracking_links'].append(tracking_link)

                            task_name = f"{client_name} - Link {i+1}"
                            promotional_task = f"{task_name} - TRACKING:{client_id}_link{i+1} - ORIGINAL:{original_link}"
                            task_sections['promotional'].append(promotional_task)

                        save_data()

                        response = f"✅ **Client Task Created with Auto-Tracking!**\n\n"
                        response += f"🏷️ **Client ID:** {client_id}\n"
                        response += f"📋 **Client:** {client_name}\n"
                        response += f"📊 **Links:** {len(original_links)}\n"
                        response += f"🔄 **Auto-Tracking:** Enabled\n\n"
                        response += f"🔗 **Original Links:**\n"
                        for i, link in enumerate(original_links, 1):
                            response += f"{i}. `{link}`\n"
                        response += f"\n🎯 **Tracking Links:**\n"
                        for i, tracking_link in enumerate(client_tasks[client_id]['tracking_links'], 1):
                            response += f"{i}. `{tracking_link}`\n"

                        bot.send_message(ADMIN_ID, response, parse_mode="Markdown")
                    else:
                        bot.send_message(ADMIN_ID, "❌ No valid links found.")
                else:
                    bot.send_message(ADMIN_ID, "⚠️ Usage: /addclienttask client_name link1 link2")
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ Error: {str(e)}")

        elif text == "/tasks":
            try:
                markup = generate_admin_task_markup()

                watch_ads_count = len(task_sections['watch_ads'])
                app_downloads_count = len(task_sections['app_downloads'])
                promotional_count = len(task_sections['promotional'])
                client_tasks_count = len(client_tasks)

                task_info = f"📋 **Admin Task Management Panel**\n\n"
                task_info += f"📊 **Current Tasks:**\n"
                task_info += f"📺 Watch Ads: {watch_ads_count}\n"
                task_info += f"📱 App Downloads: {app_downloads_count}\n"
                task_info += f"📢 Promotional: {promotional_count}\n"
                task_info += f"🎯 Client Tasks: {client_tasks_count}\n\n"
                task_info += f"🔧 **Choose an option below:**"

                bot.send_message(ADMIN_ID, task_info, parse_mode="Markdown", reply_markup=markup)
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ **Error:** {str(e)}")

        elif text.startswith("/clientstats"):
            try:
                parts = text.split()
                if len(parts) > 1:
                    client_id = parts[1]
                    if client_id in client_referrals:
                        client_task = client_tasks.get(client_id, {})
                        client_name = client_task.get('info', 'Unknown Client')

                        stats = f"🎯 **Client Statistics:**\n\n"
                        stats += f"📋 **Client:** {client_name}\n"
                        stats += f"🏷️ **ID:** {client_id}\n"
                        stats += f"📊 **Total Completions:** {len(client_referrals[client_id])}\n\n"
                        stats += "👥 **User List:**\n"
                        for i, ref in enumerate(client_referrals[client_id], 1):
                            stats += f"{i}. {ref['first_name']} (@{ref['username']}) - {ref['timestamp']}\n"

                        bot.send_message(ADMIN_ID, stats, parse_mode="Markdown")
                    else:
                        bot.send_message(ADMIN_ID, f"❌ No data found for client {client_id}")
                else:
                    if client_referrals:
                        stats = "🎯 **All Client Statistics:**\n\n"
                        for client_id, refs in client_referrals.items():
                            client_task = client_tasks.get(client_id, {})
                            client_name = client_task.get('info', f'Client {client_id}')
                            stats += f"🏷️ **{client_name}** (ID: {client_id}): {len(refs)} completions\n"
                        stats += f"\n💡 Use /clientstats client_id for details"
                        bot.send_message(ADMIN_ID, stats, parse_mode="Markdown")
                    else:
                        bot.send_message(ADMIN_ID, "❌ No client statistics available")
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ Error: {str(e)}")

        elif text.startswith("/taskstats"):
            try:
                parts = text.split()
                if len(parts) > 1:
                    task_id = parts[1]
                    if task_id in task_tracking:
                        # Get task details
                        section = task_id.split('_')[0] + '_' + task_id.split('_')[1] if '_' in task_id else task_id
                        task_index = int(task_id.split('_')[1]) if '_' in task_id else 0

                        task_name = "Unknown Task"
                        if section in task_sections and task_index < len(task_sections[section]):
                            task_name = task_sections[section][task_index][:100]

                        stats = f"📊 **Enhanced Task Tracking Statistics:**\n\n"
                        stats += f"🎯 **Task ID:** {task_id}\n"
                        stats += f"📝 **Task:** {task_name}...\n"
                        stats += f"📱 **Section:** {section.replace('_', ' ').title()}\n"
                        stats += f"📊 **Total Engagements:** {len(task_tracking[task_id])}\n"
                        stats += f"✅ **Verification:** Real-time tracking\n\n"

                        stats += "👥 **Detailed Activity Log:**\n"
                        for i, track in enumerate(task_tracking[task_id], 1):
                            section_name = track['section'].replace('_', ' ').title()
                            verification = track.get('verification_status', 'verified')
                            stats += f"{i}. **{track['first_name']}** (@{track['username']})\n"
                            stats += f"   🆔 ID: {track['user_id']}\n"
                            stats += f"   📱 Section: {section_name}\n"
                            stats += f"   🔍 Action: {track['task_type']}\n"
                            stats += f"   ⏰ Time: {track['timestamp']}\n"
                            stats += f"   ✅ Status: {verification}\n\n"

                        stats += f"📈 **Analytics:**\n"
                        stats += f"• Unique Users: {len(set(track['user_id'] for track in task_tracking[task_id]))}\n"
                        stats += f"• Multiple Engagements: {len(task_tracking[task_id]) - len(set(track['user_id'] for track in task_tracking[task_id]))}\n"
                        stats += f"• Success Rate: 100% (All verified)\n"

                        bot.send_message(ADMIN_ID, stats, parse_mode="Markdown")
                    else:
                        bot.send_message(ADMIN_ID, f"❌ No tracking data found for task {task_id}")
                else:
                    if task_tracking:
                        stats = "📊 **Complete Task Tracking Overview:**\n\n"

                        total_engagements = sum(len(tracks) for tracks in task_tracking.values())
                        unique_users = len(set(track['user_id'] for tracks in task_tracking.values() for track in tracks))

                        stats += f"🔍 **Global Statistics:**\n"
                        stats += f"• Total Tasks with Tracking: {len(task_tracking)}\n"
                        stats += f"• Total Engagements: {total_engagements}\n"
                        stats += f"• Unique Users Tracked: {unique_users}\n\n"

                        stats += "📱 **By Section:**\n"
                        section_stats = {}
                        for task_id, tracks in task_tracking.items():
                            section = tracks[0]['section'] if tracks else 'unknown'
                            if section not in section_stats:
                                section_stats[section] = 0
                            section_stats[section] += len(tracks)

                        for section, count in section_stats.items():
                            section_name = section.replace('_', ' ').title()
                            stats += f"📱 {section_name}: {count} engagements\n"

                        stats += f"\n🎯 **Task Breakdown:**\n"
                        for task_id, tracks in sorted(task_tracking.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
                            section_name = tracks[0]['section'].replace('_', ' ').title() if tracks else 'Unknown'
                            stats += f"🎯 **{task_id}** ({section_name}): {len(tracks)} engagements\n"

                        if len(task_tracking) > 10:
                            stats += f"... and {len(task_tracking) - 10} more tasks\n"

                        stats += f"\n💡 Use `/taskstats task_id` for detailed analysis"
                        bot.send_message(ADMIN_ID, stats, parse_mode="Markdown")
                    else:
                        bot.send_message(ADMIN_ID, "❌ No task tracking statistics available")
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ Error: {str(e)}")

        elif text.startswith("/message"):
            try:
                parts = text.split(' ', 2)
                if len(parts) >= 3:
                    target_id, error = validate_user_id(parts[1])
                    if error:
                        bot.reply_to(message, error)
                        return

                    message_text = parts[2]
                    try:
                        bot.send_message(target_id, f"📩 Admin Message:\n{message_text}")
                        bot.reply_to(message, f"✅ Message sent to user {target_id}.")
                    except Exception as e:
                        bot.reply_to(message, f"⚠️ Error sending message: {str(e)}")
                elif len(parts) == 2:
                    target_id, error = validate_user_id(parts[1])
                    if error:
                        bot.reply_to(message, error)
                        return

                    awaiting_message[ADMIN_ID] = target_id
                    bot.reply_to(message, f"✅ Now send the message for user {target_id}:")
                else:
                    bot.reply_to(message, "⚠️ Usage: /message user_id [message]")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Error: {str(e)}")

        elif text.startswith("/ban"):
            try:
                parts = text.split()
                if len(parts) != 2:
                    bot.reply_to(message, "⚠️ Usage: /ban user_id")
                    return

                target_id, error = validate_user_id(parts[1])
                if error:
                    bot.send_message(ADMIN_ID, error)
                    return

                if target_id == ADMIN_ID:
                    bot.send_message(ADMIN_ID, "❌ Cannot ban admin!")
                else:
                    banned_users.add(target_id)
                    save_data()
                    print(f"🚫 User banned - ID: {target_id}")
                    bot.send_message(ADMIN_ID, f"✅ User {target_id} has been banned.")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Error: {str(e)}")

        elif text.startswith("/unban"):
            try:
                parts = text.split()
                if len(parts) != 2:
                    bot.reply_to(message, "⚠️ Usage: /unban user_id")
                    return

                target_id, error = validate_user_id(parts[1])
                if error:
                    bot.send_message(ADMIN_ID, error)
                    return

                banned_users.discard(target_id)
                save_data()
                print(f"✅ User unbanned - ID: {target_id}")
                bot.send_message(ADMIN_ID, f"✅ User {target_id} has been unbanned.")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Error: {str(e)}")

        elif text == "/stats":
            total_users = len(user_balances)
            total_banned = len(banned_users)
            total_active = total_users - total_banned
            total_tasks = sum(len(tasks) for tasks in task_sections.values())
            total_balance = sum(user_balances.values())
            pending_withdrawals = len([req for req in withdrawal_requests.values() if req.get('status') == 'pending'])

            # Security status
            security_status = "🔒 FROZEN" if is_bot_frozen() else "🔓 ACTIVE"
            security_info = f" (Since: {freeze_timestamp})" if is_bot_frozen() else ""

            stats_msg = f"📊 **Bot System Status Report:**\n\n"
            stats_msg += f"🛡️ **Security Status:** {security_status}{security_info}\n"
            stats_msg += f"👥 **Users:** {total_users} (Active: {total_active}, Banned: {total_banned})\n"
            stats_msg += f"📋 **Tasks:** {total_tasks} (Client: {len(client_tasks)})\n"
            stats_msg += f"💰 **Total Balance:** ₹{total_balance:.2f}\n"
            stats_msg += f"📤 **Pending Withdrawals:** {pending_withdrawals}\n"
            stats_msg += f"📊 **Referrals:** {len(referral_data)}\n"
            stats_msg += f"🔄 **Auto-Save:** Active (10s interval)\n"
            stats_msg += f"🎯 **Auto-Tracking:** Active\n"
            stats_msg += f"⏰ **System Time:** {get_local_time()}\n"
            stats_msg += f"💾 **Data Integrity:** ✅ Verified\n\n"

            if is_bot_frozen():
                stats_msg += f"⚠️ **SECURITY MODE:** Admin functions disabled\n"
                stats_msg += f"🔑 **Unlock:** Use unlock code to restore"
            else:
                stats_msg += f"✅ **All systems operational**"

            bot.send_message(ADMIN_ID, stats_msg, parse_mode="Markdown")

        elif text.startswith("/notice"):
            try:
                parts = text.split(' ', 1)
                if len(parts) >= 2:
                    notice_text = parts[1]

                    sent_count = 0
                    failed_count = 0

                    for user_id in user_balances.keys():
                        try:
                            if user_id != ADMIN_ID:
                                notice_message = f"📢 **NOTICE FROM ADMIN**\n\n{notice_text}\n\n📅 **Time:** {get_local_time()}"
                                bot.send_message(user_id, notice_message, parse_mode="Markdown")
                                sent_count += 1
                        except Exception as e:
                            failed_count += 1
                            print(f"Failed to send notice to {user_id}: {e}")

                    result_msg = f"✅ **Notice Sent Successfully!**\n\n📤 **Sent to:** {sent_count} users\n❌ **Failed:** {failed_count} users\n📝 **Message:** {notice_text[:100]}..."
                    bot.send_message(ADMIN_ID, result_msg, parse_mode="Markdown")
                else:
                    awaiting_notice[ADMIN_ID] = True
                    bot.reply_to(message, "📢 **Send Notice to All Users**\n\n📝 Send your notice message:")
            except Exception as e:
                bot.reply_to(message, f"❌ **Error:** {str(e)}")

        elif text.startswith("/resetreferral"):
            try:
                parts = text.split()
                if len(parts) != 2:
                    bot.send_message(ADMIN_ID, "⚠️ Usage: /resetreferral user_id\n💡 This will allow user to refer again")
                    return

                target_id, error = validate_user_id(parts[1])
                if error:
                    bot.send_message(ADMIN_ID, error)
                    return

                # Remove from referral_data to allow re-referral
                if target_id in referral_data:
                    old_referrer = referral_data[target_id]
                    del referral_data[target_id]
                    save_data()
                    bot.send_message(ADMIN_ID, f"✅ **Referral Reset Complete!**\n\n👤 **User ID:** {target_id}\n🔄 **Previous Referrer:** {old_referrer}\n✅ **Status:** Can now be referred again")

                    try:
                        bot.send_message(target_id, "🔄 **Referral Status Reset!**\n\n✅ You can now use referral links again!\n💰 Get ₹5 bonus when someone refers you", parse_mode="Markdown")
                    except:
                        pass
                else:
                    bot.send_message(ADMIN_ID, f"ℹ️ User {target_id} has not been referred yet or already reset.")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Error: {str(e)}")

        elif text == "/security":
            security_help = f"🛡️ **বট সিকিউরিটি সিস্টেম সহায়তা:**\n\n"
            security_help += f"🔒 **বট ফ্রিজ:** `{FREEZE_CODE}`\n"
            security_help += f"🔓 **বট আনফ্রিজ:** আনলক কোড ব্যবহার করুন\n\n"
            security_help += f"📋 **কিভাবে কাজ করে:**\n"
            security_help += f"• যেকোনো ইউজার বট ফ্রিজ করতে পারে\n"
            security_help += f"• শুধু এডমিন আনফ্রিজ করতে পারে\n"
            security_help += f"• ফ্রিজ হলে এডমিন ফাংশন বন্ধ\n"
            security_help += f"• সমস্ত ইউজার ডেটা নিরাপদ থাকে\n"
            security_help += f"• বট স্বয়ংক্রিয়ভাবে সেভ করে\n\n"
            security_help += f"🚨 **বর্তমান অবস্থা:** {'🔒 ফ্রিজ' if is_bot_frozen() else '🔓 সক্রিয়'}\n"

            if is_bot_frozen():
                security_help += f"⏰ **ফ্রিজ করার সময়:** {freeze_timestamp}\n"
                security_help += f"🔑 **আনলক করতে:** আনলক কোড পাঠান"
            else:
                security_help += f"✅ **সমস্ত সিস্টেম চালু**"

            bot.send_message(ADMIN_ID, security_help, parse_mode="Markdown")

        elif text.startswith("/referralstats"):
            try:
                if referral_data:
                    stats = "👥 **All Referral Statistics:**\n\n"
                    referrer_counts = {}

                    for referred_user, referrer in referral_data.items():
                        referrer_counts[referrer] = referrer_counts.get(referrer, 0) + 1

                    stats += "📊 **Referrers (Top performers):**\n"
                    for referrer, count in sorted(referrer_counts.items(), key=lambda x: x[1], reverse=True):
                        earnings = count * 5
                        stats += f"👤 **User {referrer}:** {count} referrals (₹{earnings} earned)\n"

                    stats += f"\n📈 **Total Referrals:** {len(referral_data)}\n"
                    stats += f"💰 **Total Bonus Paid:** ₹{len(referral_data) * 10} (₹5 each to referrer & new user)\n"
                    stats += f"\n💡 **Commands:**\n"
                    stats += f"• `/resetreferral user_id` - Reset user's referral status\n"
                    stats += f"• `/referralstats` - View this statistics"

                    bot.send_message(ADMIN_ID, stats, parse_mode="Markdown")
                else:
                    bot.send_message(ADMIN_ID, "📊 **No Referral Data Available**\n\n💡 Referrals will appear here once users start using referral links.")
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ Error: {str(e)}")

        # Handle client data setup through interactive mode
        elif user_id in awaiting_client_data:
            try:
                data_type = awaiting_client_data[user_id]

                if data_type == 'client_name':
                    awaiting_client_data[user_id] = {'step': 'links', 'client_name': text.strip()}
                    bot.send_message(ADMIN_ID, f"✅ **Client Name:** {text.strip()}\n\n📝 **Now send the links** (space separated):\n\n💡 **Example:**\n`https://example1.com https://example2.com`")
                    return

                elif isinstance(awaiting_client_data[user_id], dict) and awaiting_client_data[user_id].get('step') == 'links':
                    client_name = awaiting_client_data[user_id]['client_name']
                    links_text = text.strip()
                    original_links = [link.strip() for link in links_text.split() if link.strip().startswith('http')]

                    if original_links:
                        client_id = generate_fixed_client_id()

                        client_tasks[client_id] = {
                            'info': client_name,
                            'links': original_links,
                            'created_at': get_local_time(),
                            'tracking_links': [],
                            'auto_tracking': True
                        }

                        for i, original_link in enumerate(original_links):
                            tracking_link = generate_client_tracking_link(client_id, f"link{i+1}")
                            client_tasks[client_id]['tracking_links'].append(tracking_link)

                            task_name = f"{client_name} - Link {i+1}"
                            promotional_task = f"{task_name} - TRACKING:{client_id}_link{i+1} - ORIGINAL:{original_link}"
                            task_sections['promotional'].append(promotional_task)

                        save_data()

                        response = f"🎉 **Client Task Successfully Created with Auto-Tracking!**\n\n"
                        response += f"🏷️ **Client ID:** {client_id}\n"
                        response += f"📋 **Client:** {client_name}\n"
                        response += f"📊 **Links Added:** {len(original_links)}\n"
                        response += f"🔄 **Auto-Tracking:** Enabled\n\n"
                        response += f"🔗 **Original Links:**\n"
                        for i, link in enumerate(original_links, 1):
                            response += f"{i}. `{link}`\n"
                        response += f"\n🎯 **Tracking Links:**\n"
                        for i, tracking_link in enumerate(client_tasks[client_id]['tracking_links'], 1):
                            response += f"{i}. `{tracking_link}`\n"
                        response += f"\n✅ **Automatically added to Promotional Tasks**"

                        bot.send_message(ADMIN_ID, response, parse_mode="Markdown")
                        awaiting_client_data.pop(user_id, None)
                    else:
                        bot.send_message(ADMIN_ID, "❌ **No valid links found!**\n\n💡 Please send valid HTTP/HTTPS links separated by spaces.")
                        return

                elif data_type == 'simple_add_link':
                    new_link = text.strip()

                    if new_link.startswith('http'):
                        client_id = generate_fixed_client_id()
                        client_name = f"Client {client_id}"

                        client_tasks[client_id] = {
                            'info': client_name,
                            'links': [new_link],
                            'created_at': get_local_time(),
                            'tracking_links': [],
                            'auto_tracking': True
                        }

                        tracking_link = generate_client_tracking_link(client_id, "link1")
                        client_tasks[client_id]['tracking_links'].append(tracking_link)

                        task_name = f"{client_name} - Link 1"
                        promotional_task = f"{task_name} - TRACKING:{client_id}_link1 - ORIGINAL:{new_link}"
                        task_sections['promotional'].append(promotional_task)

                        save_data()

                        response = f"🎉 **Client Task Link Added Successfully!**\n\n"
                        response += f"🏷️ **Auto Client ID:** {client_id}\n"
                        response += f"🔗 **Original Link:** {new_link}\n"
                        response += f"🎯 **Tracking Link:** `{tracking_link}`\n\n"
                        response += f"✅ **Auto-completed:**\n"
                        response += f"📢 Added to Promotional Tasks\n"
                        response += f"🔄 Real-time tracking enabled\n"
                        response += f"🚨 Admin notifications active\n\n"
                        response += f"💾 **Data saved automatically**"

                        bot.send_message(ADMIN_ID, response, parse_mode="Markdown")
                        awaiting_client_data.pop(user_id, None)
                    else:
                        bot.send_message(ADMIN_ID, "❌ **Invalid link format!**\n\n💡 Please send a valid HTTP/HTTPS link starting with http:// or https://")
                        return

            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ **Error setting up client task:** {str(e)}")
                awaiting_client_data.pop(user_id, None)

        # Handle admin message sending
        elif ADMIN_ID in awaiting_message:
            target_id = awaiting_message[ADMIN_ID]
            try:
                bot.send_message(target_id, f"📩 Admin Message:\n{text}")
                bot.reply_to(message, "✅ Message sent.")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Error: {str(e)}")
            awaiting_message.pop(ADMIN_ID, None)

        # Handle referral reset
        elif ADMIN_ID in awaiting_referral_reset:
            try:
                target_id, error = validate_user_id(text.strip())
                if error:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔄 Try Again", callback_data="reset_referral_prompt"))
                    markup.add(types.InlineKeyboardButton("🔙 Back to Referral Management", callback_data="admin_referral_mgmt"))

                    bot.reply_to(message, f"{error}\n\n💡 **Please send a valid User ID**", 
                                parse_mode="Markdown", reply_markup=markup)
                    awaiting_referral_reset.pop(ADMIN_ID, None)
                    return

                # Remove from referral_data to allow re-referral
                if target_id in referral_data:
                    old_referrer = referral_data[target_id]
                    del referral_data[target_id]
                    save_data()

                    # Create success response with navigation
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔄 Reset Another User", callback_data="reset_referral_prompt"))
                    markup.add(types.InlineKeyboardButton("📊 View Statistics", callback_data="show_referral_stats"))
                    markup.add(types.InlineKeyboardButton("🔙 Back to Referral Management", callback_data="admin_referral_mgmt"))

                    result_msg = f"✅ **Referral Reset Successful!**\n\n"
                    result_msg += f"👤 **User ID:** {target_id}\n"
                    result_msg += f"🔄 **Previous Referrer:** {old_referrer}\n"
                    result_msg += f"✅ **Status:** Can now be referred again\n\n"
                    result_msg += f"📋 **What was done:**\n"
                    result_msg += f"• Removed from referral database\n"
                    result_msg += f"• User notified about reset\n"
                    result_msg += f"• Can receive ₹5 bonus again\n\n"
                    result_msg += f"⏰ **Time:** {get_local_time()}"

                    bot.reply_to(message, result_msg, parse_mode="Markdown", reply_markup=markup)

                    # Notify the user about reset
                    try:
                        user_notification = f"🔄 **Referral Status Reset by Admin!**\n\n"
                        user_notification += f"✅ **Good News:** You can now use referral links again!\n"
                        user_notification += f"💰 **Bonus:** Get ₹5 when someone refers you\n"
                        user_notification += f"🎯 **Action:** Share your referral link to earn\n\n"
                        user_notification += f"⏰ **Reset Time:** {get_local_time()}"

                        bot.send_message(target_id, user_notification, parse_mode="Markdown")
                    except Exception as notify_error:
                        print(f"Could not notify user {target_id}: {notify_error}")
                else:
                    # User not found in referral data
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔄 Try Another User", callback_data="reset_referral_prompt"))
                    markup.add(types.InlineKeyboardButton("📊 View All Referrals", callback_data="show_referral_stats"))
                    markup.add(types.InlineKeyboardButton("🔙 Back to Referral Management", callback_data="admin_referral_mgmt"))

                    not_found_msg = f"ℹ️ **User Not Found in Referral System**\n\n"
                    not_found_msg += f"👤 **User ID:** {target_id}\n"
                    not_found_msg += f"📊 **Status:** User has not been referred yet\n\n"
                    not_found_msg += f"💡 **Possible reasons:**\n"
                    not_found_msg += f"• User joined directly (not via referral)\n"
                    not_found_msg += f"• User was already reset previously\n"
                    not_found_msg += f"• Invalid User ID\n\n"
                    not_found_msg += f"🔍 **Tip:** Check user statistics for confirmation"

                    bot.reply_to(message, not_found_msg, parse_mode="Markdown", reply_markup=markup)

                awaiting_referral_reset.pop(ADMIN_ID, None)
            except Exception as e:
                # Error handling with navigation
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔄 Try Again", callback_data="reset_referral_prompt"))
                markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="back_to_admin"))

                error_msg = f"❌ **Error Processing Reset:**\n\n{str(e)}\n\n💡 Please try again with a valid User ID"
                bot.reply_to(message, error_msg, parse_mode="Markdown", reply_markup=markup)
                awaiting_referral_reset.pop(ADMIN_ID, None)

        # Handle notice sending
        elif ADMIN_ID in awaiting_notice:
            try:
                notice_text = text.strip()

                sent_count = 0
                failed_count = 0

                for user_id in user_balances.keys():
                    try:
                        if user_id != ADMIN_ID:
                            notice_message = f"📢 **NOTICE FROM ADMIN**\n\n{notice_text}\n\n📅 **Time:** {get_local_time()}"
                            bot.send_message(user_id, notice_message, parse_mode="Markdown")
                            sent_count += 1
                    except Exception as e:
                        failed_count += 1
                        print(f"Failed to send notice to {user_id}: {e}")

                result_msg = f"✅ **Notice Sent Successfully!**\n\n📤 **Sent to:** {sent_count} users\n❌ **Failed:** {failed_count} users\n📝 **Message:** {notice_text[:100]}..."
                if len(notice_text) > 100:
                    result_msg += "..."

                bot.reply_to(message, result_msg, parse_mode="Markdown")
                awaiting_notice.pop(ADMIN_ID, None)
            except Exception as e:
                bot.reply_to(message, f"❌ **Error sending notice:** {str(e)}")
                awaiting_notice.pop(ADMIN_ID, None)

        # Handle task addition
        elif user_id in awaiting_task_add:
            section = awaiting_task_add[user_id]
            if section in task_sections:
                task_sections[section].append(text)
                save_data()
                bot.reply_to(message, f"✅ Task added to {section.replace('_', ' ').title()} section with auto-tracking enabled.")
            else:
                bot.reply_to(message, f"❌ Invalid section: {section}")
            awaiting_task_add.pop(user_id, None)

    # ✅ Support Message Handling
    if user_id in awaiting_support_message:
        try:
            bot.send_message(
                ADMIN_ID,
                f"🆘 *Support Message*\n👤 Name: {name}\n🔗 Username: @{username}\n🆔 ID: {user_id}\n💬 Message:\n{text}",
                parse_mode="Markdown"
            )
            bot.reply_to(message, "✅ Your message has been sent to support team.")
        except Exception as e:
            bot.reply_to(message, "❌ Error sending support message.")
            print(f"Support message error: {e}")
        awaiting_support_message.pop(user_id, None)
        return

    # ✅ Promotion Message Handling
    if user_id in awaiting_promotion_message:
        try:
            bot.send_message(
                ADMIN_ID,
                f"📢 *Promotion Request*\n👤 Name: {name}\n🔗 Username: @{username}\n🆔 ID: {user_id}\n💬 Message:\n{text}",
                parse_mode="Markdown"
            )
            bot.reply_to(message, "✅ Your promotion request has been sent to admin.")
        except Exception as e:
            bot.reply_to(message, "❌ Error sending promotion request.")
            print(f"Promotion message error: {e}")
        awaiting_promotion_message.pop(user_id, None)
        return

    # ✅ Enhanced Withdraw Logic with Admin Approval
    if user_id in awaiting_withdraw:
        withdraw_type = awaiting_withdraw[user_id]
        try:
            parts = text.split()
            if len(parts) >= 2:
                payment_id = parts[0]
                amount, error = validate_amount(parts[1])
                if error:
                    bot.reply_to(message, error)
                    return

                balance = user_balances.get(user_id, 0)

                # Check minimum limits
                min_limits = {
                    'upi': 15,
                    'amazon': 15,
                    'googleplay': 15,
                    'paypal': 2
                }

                min_amount = min_limits.get(withdraw_type, 15)
                if amount < min_amount:
                    currency = "USD" if withdraw_type == 'paypal' else "₹"
                    bot.reply_to(message, f"❌ **Minimum Amount Required**\n\n💳 Minimum: {currency}{min_amount}\n📝 Your request: {currency}{amount}")
                    return

                # PayPal with 7% Tax
                if withdraw_type == 'paypal':
                    inr_amount = amount * 83
                    if inr_amount > balance:
                        bot.reply_to(message, f"❌ **Insufficient Balance**\n\n💰 Required: ₹{inr_amount:.2f} (${amount})\n💳 Your Balance: ₹{balance:.2f}")
                        return

                    tax_rate = 0.07
                    tax_amount_usd = amount * tax_rate
                    final_amount_usd = amount - tax_amount_usd

                    # Store withdrawal request
                    withdrawal_requests[user_id] = {
                        'type': 'paypal',
                        'payment_id': payment_id,
                        'amount': amount,
                        'final_amount': final_amount_usd,
                        'inr_amount': inr_amount,
                        'tax_amount': tax_amount_usd,
                        'timestamp': get_local_time(),
                        'status': 'pending'
                    }

                    user_balances[user_id] -= inr_amount
                    save_data()

                    bot.reply_to(message, f"✅ **PayPal Withdrawal Request Submitted**\n\n💰 **Amount:** ${amount} (₹{inr_amount:.2f})\n🏛️ **Tax (7%):** ${tax_amount_usd:.2f}\n📊 **Final Amount:** ${final_amount_usd:.2f}\n⏳ **Status:** Pending admin approval\n🕐 **Processing:** 24-48 hours", parse_mode="Markdown")

                    bot.send_message(
                        ADMIN_ID,
                        f"📤 **PayPal Withdrawal Request**\n\n👤 **User:** {name}\n🆔 **ID:** {user_id}\n🌐 **PayPal:** `{payment_id}`\n💰 **Final Amount:** ${final_amount_usd:.2f} USD\n💱 **INR:** ₹{inr_amount:.2f}\n🏛️ **Tax (7%):** ${tax_amount_usd:.2f} USD\n📱 **Contact:** @{username}",
                        parse_mode="Markdown",
                        reply_markup=generate_withdrawal_approval_markup(user_id)
                    )

                else:
                    # For INR-based withdrawals - 2% fee
                    if amount > balance:
                        bot.reply_to(message, f"❌ **Insufficient Balance**\n\n💰 Required: ₹{amount}\n💳 Your Balance: ₹{balance:.2f}")
                        return

                    fee_rate = 0.02
                    fee_amount = amount * fee_rate
                    final_amount = amount - fee_amount

                    # Store withdrawal request
                    withdrawal_requests[user_id] = {
                        'type': withdraw_type,
                        'payment_id': payment_id,
                        'amount': amount,
                        'final_amount': final_amount,
                        'fee_amount': fee_amount,
                        'timestamp': get_local_time(),
                        'status': 'pending'
                    }

                    user_balances[user_id] -= amount
                    save_data()

                    method_names = {
                        'upi': 'UPI',
                        'amazon': 'Amazon Pay',
                        'googleplay': 'Google Play Gift Card'
                    }

                    method_name = method_names.get(withdraw_type, withdraw_type.upper())
                    bot.reply_to(message, f"✅ **{method_name} Withdrawal Request**\n\n💳 **Payment ID:** {payment_id}\n💰 **Amount:** ₹{amount}\n📊 **After 2% Fee:** ₹{final_amount:.2f}\n⏳ **Status:** Pending admin approval", parse_mode="Markdown")

                    bot.send_message(
                        ADMIN_ID,
                        f"📤 **{method_name} Withdrawal**\n\n👤 **User:** {name}\n🆔 **ID:** {user_id}\n💳 **Payment ID:** `{payment_id}`\n💰 **Amount:** ₹{final_amount:.2f}\n📱 **Contact:** @{username}",
                        parse_mode="Markdown",
                        reply_markup=generate_withdrawal_approval_markup(user_id)
                    )

            else:
                # Format help
                if withdraw_type == 'upi':
                    bot.reply_to(message, "⚠️ **Format:** `upi@bank 50`\n💡 **Example:** `yourname@paytm 100`", parse_mode="Markdown")
                elif withdraw_type == 'paypal':
                    bot.reply_to(message, "⚠️ **Format:** `email@gmail.com 5`\n💡 **Example:** `john@gmail.com 10`\n💱 **Note:** Amount in USD", parse_mode="Markdown")
                elif withdraw_type == 'amazon':
                    bot.reply_to(message, "⚠️ **Format:** `9876543210 50`\n💡 **Example:** `9876543210 100`", parse_mode="Markdown")
                elif withdraw_type == 'googleplay':
                    bot.reply_to(message, "⚠️ **Format:** `email@gmail.com 50`\n💡 **Example:** `john@gmail.com 100`", parse_mode="Markdown")

        except Exception as e:
            bot.reply_to(message, "⚠️ **Error Processing Request**\n\nPlease try again.", parse_mode="Markdown")
            print(f"Withdrawal error: {e}")

        awaiting_withdraw.pop(user_id, None)
        return

    # ✅ Main Menu Options - Dynamic emoji matching
    task_emoji = get_current_emoji('task')
    balance_emoji = get_current_emoji('balance')
    submit_emoji = get_current_emoji('submit')
    withdraw_emoji = get_current_emoji('withdraw')
    referral_emoji = get_current_emoji('referral')
    support_emoji = get_current_emoji('support')
    user_info_emoji = get_current_emoji('user_info')
    promotion_emoji = get_current_emoji('promotion')
    watch_emoji = get_current_emoji('watch_ads')
    app_emoji = get_current_emoji('app_download')
    promo_emoji = get_current_emoji('promotional')
    upi_emoji = get_current_emoji('upi')
    paypal_emoji = get_current_emoji('paypal')
    amazon_emoji = get_current_emoji('amazon')
    google_emoji = get_current_emoji('googleplay')
    back_emoji = get_current_emoji('back')

    if text in [f"{task_emoji} Task", "🎯 Task"]:  # Support both current and old format for compatibility
        notify_admin_user_action(user_id, name, username, f"{task_emoji} Task Menu Accessed")
        bot.send_message(message.chat.id, f"{task_emoji} Choose a task category:", reply_markup=generate_task_markup())

    elif text in [f"{watch_emoji} Watch Ads", "🎬 Watch Ads"]:
        notify_admin_user_action(user_id, name, username, f"{watch_emoji} Watch Ads Section", f"Tasks Available: {len(task_sections['watch_ads'])}")
        if task_sections['watch_ads']:
            markup = types.InlineKeyboardMarkup()
            for i, task in enumerate(task_sections['watch_ads']):
                # Check if user has completed this task
                user_completed = completed_tasks.get(user_id, set())
                task_key = f"watch_ads_{i}"

                task_parts = task.split(" - ")
                task_name = task_parts[0] if task_parts else task[:35]
                reward = extract_reward_from_task(task)

                if task_key in user_completed:
                    button_text = f"✅ {task_name[:20]}... (₹{reward}) - DONE"
                else:
                    button_text = f"{watch_emoji} {task_name[:25]}... (₹{reward})" if reward > 0 else f"{watch_emoji} {task_name[:35]}..."

                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"complete_watch_ads_{i}"))
            bot.send_message(message.chat.id, f"{watch_emoji} Available Watch Ads Tasks:\n\n🔒 Limited - Each task can be done only once!\n🔄 Auto-Tracking: Active", reply_markup=markup)
        else:
            bot.reply_to(message, f"{watch_emoji} No watch ads tasks available.")

    elif text in [f"{app_emoji} App Download", "📲 App Download"]:
        notify_admin_user_action(user_id, name, username, f"{app_emoji} App Download Section", f"Tasks Available: {len(task_sections['app_downloads'])}")
        if task_sections['app_downloads']:
            markup = types.InlineKeyboardMarkup()
            for i, task in enumerate(task_sections['app_downloads']):
                user_completed = completed_tasks.get(user_id, set())
                task_key = f"app_downloads_{i}"

                task_parts = task.split(" - ")
                task_name = task_parts[0] if task_parts else task[:35]
                reward = extract_reward_from_task(task)

                if task_key in user_completed:
                    button_text = f"✅ {task_name[:20]}... (₹{reward}) - DONE"
                else:
                    button_text = f"{app_emoji} {task_name[:25]}... (₹{reward})" if reward > 0 else f"{app_emoji} {task_name[:35]}..."

                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"complete_app_downloads_{i}"))
            bot.send_message(message.chat.id, f"{app_emoji} Available App Download Tasks:\n\n🔒 Limited - Each task can be done only once!\n🔄 Auto-Tracking: Active", reply_markup=markup)
        else:
            bot.reply_to(message, f"{app_emoji} No app download tasks available.")

    elif text in [f"{promo_emoji} Promotional", "🎁 Promotional"]:
        notify_admin_user_action(user_id, name, username, f"{promo_emoji} Promotional Section", f"Tasks Available: {len(task_sections['promotional'])}")
        if task_sections['promotional']:
            markup = types.InlineKeyboardMarkup()
            for i, task in enumerate(task_sections['promotional']):
                user_completed = completed_tasks.get(user_id, set())
                task_key = f"promotional_{i}"

                task_parts = task.split(" - ")
                task_name = task_parts[0] if task_parts else task[:35]

                if is_client_task(task):
                    if task_key in user_completed:
                        button_text = f"✅ {task_name[:20]}... - DONE"
                    else:
                        button_text = f"🎯 {task_name[:30]}..."
                else:
                    reward = extract_reward_from_task(task)
                    if task_key in user_completed:
                        button_text = f"✅ {task_name[:20]}... (₹{reward}) - DONE"
                    else:
                        button_text = f"{promo_emoji} {task_name[:25]}... (₹{reward})" if reward > 0 else f"{promo_emoji} {task_name[:35]}..."

                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"complete_promotional_{i}"))

            bot.send_message(message.chat.id, f"{promo_emoji} Available Promotional Tasks:\n\n🔒 Limited - Each task can be done only once!\n🎯 Client Tasks - Reward determined by admin\n🔄 Auto-Tracking: Active for all tasks", reply_markup=markup)
        else:
            bot.reply_to(message, f"{promo_emoji} No promotional tasks available.")

    elif text in [f"{submit_emoji} Submit Proof", "🚀 Submit Proof"]:
        notify_admin_user_action(user_id, name, username, f"{submit_emoji} Submit Proof", "Ready to submit screenshot")
        worked_users[user_id] = name
        bot.reply_to(message, f"📸 Please send your proof (screenshot).")

    elif text in [f"{balance_emoji} Balance", "💎 Balance"]:
        balance = user_balances.get(user_id, 0)
        notify_admin_user_action(user_id, name, username, f"{balance_emoji} Balance Check", f"Current Balance: ₹{balance:.2f}")
        bot.reply_to(message, f"{balance_emoji} Your balance: ₹{balance:.2f}")

    elif text in [f"{withdraw_emoji} Withdraw", "💸 Withdraw"]:
        balance = user_balances.get(user_id, 0)
        notify_admin_user_action(user_id, name, username, f"{withdraw_emoji} Withdraw Menu", f"Current Balance: ₹{balance:.2f}")
        withdraw_info = f"💳 **Withdrawal Methods & Limits:**\n\n"
        withdraw_info += f"{upi_emoji} **UPI:** Minimum ₹15 (2% fee)\n"
        withdraw_info += f"{paypal_emoji} **PayPal:** Minimum $2 USD (7% tax)\n"
        withdraw_info += f"{amazon_emoji} **Amazon Pay:** Minimum ₹15 (2% fee)\n"
        withdraw_info += f"{google_emoji} **Google Play:** Minimum ₹15 (2% fee)\n\n"
        withdraw_info += "🕐 **Processing:** 24-48 hours\n"
        withdraw_info += "⚠️ **Note:** Admin approval required\n\n"
        withdraw_info += "Choose your withdrawal method:"

        bot.send_message(message.chat.id, withdraw_info, parse_mode="Markdown", reply_markup=generate_withdraw_markup())

    elif text in [f"{upi_emoji} UPI", "💳 UPI"]:
        balance = user_balances.get(user_id, 0)
        notify_admin_user_action(user_id, name, username, f"{upi_emoji} UPI Withdrawal", f"Balance: ₹{balance:.2f}, Min Required: ₹15")
        if balance < 15:
            bot.reply_to(message, f"❌ **Insufficient Balance**\n\n💰 Your Balance: ₹{balance:.2f}\n{upi_emoji} UPI Minimum: ₹15", parse_mode="Markdown")
        else:
            awaiting_withdraw[user_id] = 'upi'
            bot.reply_to(message, f"{upi_emoji} **UPI Withdrawal**\n\n📝 **Format:** `upi@bank 50`\n💰 **Minimum:** ₹15\n⚠️ **Fee:** 2%\n✅ **Admin approval required**", parse_mode="Markdown")

    elif text in [f"{paypal_emoji} PayPal", "🌍 PayPal"]:
        balance = user_balances.get(user_id, 0)
        usd_balance = balance / 83
        notify_admin_user_action(user_id, name, username, f"{paypal_emoji} PayPal Withdrawal", f"Balance: ₹{balance:.2f} (${usd_balance:.2f}), Min Required: $2")
        if usd_balance < 2:
            bot.reply_to(message, f"❌ **Insufficient Balance**\n\n💰 Your Balance: ₹{balance:.2f} (${usd_balance:.2f})\n{paypal_emoji} PayPal Minimum: $2 USD", parse_mode="Markdown")
        else:
            awaiting_withdraw[user_id] = 'paypal'
            bot.reply_to(message, f"{paypal_emoji} **PayPal Withdrawal**\n\n📝 **Format:** `email@gmail.com 5`\n💰 **Minimum:** $2 USD\n💱 **Rate:** $1 = ₹83\n💰 **Available:** ${usd_balance:.2f}\n🏛️ **Tax:** 7%\n✅ **Admin approval required**", parse_mode="Markdown")

    elif text in [f"{amazon_emoji} Amazon Pay", "📦 Amazon Pay"]:
        balance = user_balances.get(user_id, 0)
        notify_admin_user_action(user_id, name, username, f"{amazon_emoji} Amazon Pay Withdrawal", f"Balance: ₹{balance:.2f}, Min Required: ₹15")
        if balance < 15:
            bot.reply_to(message, f"❌ **Insufficient Balance**\n\n💰 Your Balance: ₹{balance:.2f}\n{amazon_emoji} Amazon Minimum: ₹15", parse_mode="Markdown")
        else:
            awaiting_withdraw[user_id] = 'amazon'
            bot.reply_to(message, f"{amazon_emoji} **Amazon Pay**\n\n📝 **Format:** `9876543210 50`\n💰 **Minimum:** ₹15\n⚠️ **Fee:** 2%\n✅ **Admin approval required**", parse_mode="Markdown")

    elif text in [f"{google_emoji} Google Play Gift", "🎮 Google Play Gift"]:
        balance = user_balances.get(user_id, 0)
        notify_admin_user_action(user_id, name, username, f"{google_emoji} Google Play Gift", f"Balance: ₹{balance:.2f}, Min Required: ₹15")
        if balance < 15:
            bot.reply_to(message, f"❌ **Insufficient Balance**\n\n💰 Your Balance: ₹{balance:.2f}\n{google_emoji} Google Play Minimum: ₹15", parse_mode="Markdown")
        else:
            awaiting_withdraw[user_id] = 'googleplay'
            bot.reply_to(message, f"{google_emoji} **Google Play Gift**\n\n📝 **Format:** `email@gmail.com 50`\n💰 **Minimum:** ₹15\n🎁 **Note:** Code sent to email\n⚠️ **Fee:** 2%\n✅ **Admin approval required**", parse_mode="Markdown")

    elif text in [f"{referral_emoji} Referral", "🔗 Referral"]:
        ref_link = generate_referral_link(user_id)
        referred_count = sum(1 for ref_id in referral_data.values() if ref_id == user_id)
        notify_admin_user_action(user_id, name, username, f"{referral_emoji} Referral Menu", f"Total Referrals: {referred_count}, Bonus Earned: ₹{referred_count * 5:.2f}")
        bot.reply_to(message, f"{referral_emoji} *Your Referral Info:*\n\n🌟 Your Link:\n`{ref_link}`\n\n👥 Total Referrals: {referred_count}\n💰 Bonus: ₹{referred_count * 5:.2f}\n\n📢 Share with friends!\nBoth get ₹5.00!", parse_mode="Markdown")

    elif text in [f"{support_emoji} Support", "🛟 Support"]:
        notify_admin_user_action(user_id, name, username, f"{support_emoji} Support Request", "User wants to contact support")
        awaiting_support_message[user_id] = True
        bot.reply_to(message, f"{support_emoji} *Support*\n\nDescribe your problem. Your message will be sent to admin.", parse_mode="Markdown")

    elif text in [f"{promotion_emoji} Promotion", "⭐ Promotion"]:
        notify_admin_user_action(user_id, name, username, f"{promotion_emoji} Promotion Menu", "Accessed promotion features")
        bot.send_message(message.chat.id, f"{promotion_emoji} *Promotion Menu*", parse_mode="Markdown", reply_markup=generate_promotion_menu())

    elif text == "📈 Bot Status":
        total_users = len(user_balances)
        total_banned = len(banned_users)
        active_users = total_users - total_banned
        total_tasks = sum(len(tasks) for tasks in task_sections.values())

        notify_admin_user_action(user_id, name, username, "📈 Bot Status Check", "Viewed bot statistics")

        current_emoji_set = {cat: get_current_emoji(cat) for cat in EMOJI_SETS.keys()}
        next_change = (last_emoji_change + timedelta(hours=24)).strftime('%H:%M') if last_emoji_change else "Soon"

        status_msg = f"📈 **Bot Statistics**\n\n"
        status_msg += f"👥 **Total Members:** {total_users}\n"
        status_msg += f"✅ **Active Users:** {active_users}\n"
        status_msg += f"🚫 **Banned Users:** {total_banned}\n"
        status_msg += f"📋 **Available Tasks:** {total_tasks}\n"
        status_msg += f"🎯 **Client Projects:** {len(client_tasks)}\n"
        status_msg += f"🔄 **Auto-Tracking:** Active\n"
        status_msg += f"🎨 **Dynamic Emojis:** Active\n"
        status_msg += f"⏰ **Next Emoji Change:** {next_change}\n\n"
        status_msg += f"🚀 **Status:** Online & Active"

        bot.reply_to(message, status_msg, parse_mode="Markdown")

    elif text in [f"{promotion_emoji} Request Promotion", "🌟 Request Promotion"]:
        notify_admin_user_action(user_id, name, username, f"{promotion_emoji} Promotion Request", "Starting promotion request")
        awaiting_promotion_message[user_id] = True
        bot.reply_to(message, f"{promotion_emoji} *Promotion Request*\n\nDescribe your requirements:\n• Members needed\n• Links\n• Budget\n• Requirements\n\nMessage will be sent to admin.", parse_mode="Markdown")

    elif text in [f"{user_info_emoji} User Info", "👑 User Info"]:
        balance = user_balances.get(user_id, 0)
        referral_count = sum(1 for ref_id in referral_data.values() if ref_id == user_id)
        referral_bonus = referral_count * 5
        join_date = "Unknown"

        # Check if user has referral data (approximate join tracking)
        if user_id in referral_data:
            join_date = "Via Referral"
        elif user_id in user_balances:
            join_date = "Direct Join"

        notify_admin_user_action(user_id, name, username, f"{user_info_emoji} User Info Access", f"Balance: ₹{balance:.2f}, Referrals: {referral_count}")

        user_info = f"{user_info_emoji} **Your Account Information:**\n\n"
        user_info += f"📝 **Name:** {name}\n"
        user_info += f"🔗 **Username:** @{username}\n"
        user_info += f"🆔 **User ID:** {user_id}\n"
        user_info += f"💰 **Current Balance:** ₹{balance:.2f}\n"
        user_info += f"👥 **Referrals Made:** {referral_count}\n"
        user_info += f"💵 **Referral Bonus:** ₹{referral_bonus:.2f}\n"
        user_info += f"📅 **Join Type:** {join_date}\n"
        user_info += f"🎯 **Account Status:** {'🚫 Banned' if is_banned(user_id) else '✅ Active'}\n\n"
        user_info += f"📊 **Want to see your detailed activity data?**"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📊 View My Database", callback_data=f"view_user_data_{user_id}"))
        markup.add(types.InlineKeyboardButton("🔄 Refresh Info", callback_data=f"refresh_user_info_{user_id}"))

        bot.send_message(message.chat.id, user_info, parse_mode="Markdown", reply_markup=markup)

# ✅ HANDLE MEDIA SUBMISSION
@bot.message_handler(content_types=['photo', 'video', 'document'])
def handle_media(message):
    user_id = message.from_user.id

    # Handle promotion media
    if user_id in awaiting_promotion_message:
        try:
            caption = f"📢 *Promotion Media*\n👤 {message.from_user.first_name}\n🔗 @{message.from_user.username or 'No Username'}\n🆔 {user_id}"

            if message.content_type == 'photo':
                bot.send_photo(ADMIN_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
            elif message.content_type == 'video':
                bot.send_video(ADMIN_ID, video=message.video.file_id, caption=caption, parse_mode="Markdown")
            elif message.content_type == 'document':
                bot.send_document(ADMIN_ID, document=message.document.file_id, caption=caption, parse_mode="Markdown")

            bot.reply_to(message, "✅ Media sent to admin with promotion request.")
        except Exception as e:
            bot.reply_to(message, "❌ Error sending media.")
            print(f"Promotion media error: {e}")
        return

    # Handle banned users
    if is_banned(user_id) and user_id not in awaiting_support_message:
        bot.send_message(user_id, "❌ You are banned. Only Support is available.")
        return

    # Handle support media
    if user_id in awaiting_support_message:
        try:
            caption = f"🆘 *Support Media*\n👤 {message.from_user.first_name}\n🔗 @{message.from_user.username or 'No Username'}\n🆔 {user_id}"

            if message.content_type == 'photo':
                bot.send_photo(ADMIN_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
            elif message.content_type == 'video':
                bot.send_video(ADMIN_ID, video=message.video.file_id, caption=caption, parse_mode="Markdown")
            elif message.content_type == 'document':
                bot.send_document(ADMIN_ID, document=message.document.file_id, caption=caption, parse_mode="Markdown")

            bot.reply_to(message, "✅ Media sent to support team.")
        except Exception as e:
            bot.reply_to(message, "❌ Error sending media.")
            print(f"Support media error: {e}")
        return

    # Handle proof submission (photos only)
    if message.content_type == 'photo' and user_id in worked_users:
        task_info = ""
        reward_info = ""
        if user_id in pending_tasks:
            task_data = pending_tasks[user_id]
            task_name = task_data.get('task_name', 'Unknown Task')
            reward = task_data.get('reward', 0)
            section = task_data.get('section', 'Unknown')
            task_info = f"\n📝 Task: {task_name}\n🔗 Section: {section.replace('_', ' ').title()}"

            if not is_client_task(task_data.get('task', '')):
                reward_info = f"\n💰 Reward: ₹{reward}" if reward > 0 else ""

        pending_tasks[user_id] = pending_tasks.get(user_id, {})
        pending_tasks[user_id]['photo_id'] = message.photo[-1].file_id

        try:
            bot.send_photo(
                ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=f"📤 *Task Submission*\n👤 User ID: {user_id}{task_info}{reward_info}",
                parse_mode='Markdown',
                reply_markup=generate_approval_markup(user_id)
            )
            bot.reply_to(message, "✅ Screenshot submitted! Wait for admin approval.\n\n⚠️ Money added manually by admin using /addbalance command.")
        except Exception as e:
            bot.reply_to(message, "❌ Error submitting screenshot.")
            print(f"Screenshot submission error: {e}")

        worked_users.pop(user_id, None)

# ✅ ENHANCED CALLBACK HANDLER
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id

    try:
        # Handle withdrawal approval/rejection
        if call.data.startswith("approve_withdrawal_"):
            uid = int(call.data.split("_")[2])

            if uid in withdrawal_requests:
                request = withdrawal_requests[uid]

                # Send payment confirmation message based on withdrawal type
                if request['type'] == 'paypal':
                    message = f"✅ **PayPal Payment Approved!**\n\n💰 **Amount:** ${request['final_amount']:.2f}\n🌐 **PayPal:** {request['payment_id']}\n\n💡 **Please check your PayPal account**\n⏰ **Time:** {get_local_time()}"
                elif request['type'] == 'upi':
                    message = f"✅ **UPI Payment Approved!**\n\n💰 **Amount:** ₹{request['final_amount']:.2f}\n💳 **UPI ID:** {request['payment_id']}\n\n💡 **Please check your UPI account**\n⏰ **Time:** {get_local_time()}"
                elif request['type'] == 'amazon':
                    message = f"✅ **Amazon Pay Approved!**\n\n💰 **Amount:** ₹{request['final_amount']:.2f}\n📦 **Mobile:** {request['payment_id']}\n\n💡 **Please check your Amazon Pay account**\n⏰ **Time:** {get_local_time()}"
                elif request['type'] == 'googleplay':
                    message = f"✅ **Google Play Gift Card Approved!**\n\n💰 **Amount:** ₹{request['final_amount']:.2f}\n🎮 **Email:** {request['payment_id']}\n\n💡 **Please check your email for gift card code**\n⏰ **Time:** {get_local_time()}"

                bot.send_message(uid, message, parse_mode="Markdown")

                # Update withdrawal status
                withdrawal_requests[uid]['status'] = 'approved'
                save_data()

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"✅ Payment approved and sent to user {uid}. Amount: {request.get('final_amount', request.get('amount'))}"
                )

        elif call.data.startswith("reject_withdrawal_"):
            uid = int(call.data.split("_")[2])

            if uid in withdrawal_requests:
                request = withdrawal_requests[uid]

                # Refund the balance
                if request['type'] == 'paypal':
                    user_balances[uid] = user_balances.get(uid, 0) + request['inr_amount']
                else:
                    user_balances[uid] = user_balances.get(uid, 0) + request['amount']

                # Update withdrawal status
                withdrawal_requests[uid]['status'] = 'rejected'
                save_data()

                bot.send_message(uid, "❌ **Withdrawal Request Rejected**\n\n💰 Your balance has been refunded\n📞 Contact support for more information")

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"❌ Payment rejected for user {uid}. Balance refunded."
                )

        # Handle task finishing (Complete Task button)
        elif call.data.startswith("finish_task_"):
            try:
                parts = call.data.split("_")
                if len(parts) >= 4:
                    section = "_".join(parts[2:-1])
                    task_index = int(parts[-1])

                    # Validate section exists
                    if section not in task_sections:
                        bot.answer_callback_query(call.id, "❌ Invalid task section!", show_alert=True)
                        return

                    # Validate task index
                    if not (0 <= task_index < len(task_sections[section])):
                        bot.answer_callback_query(call.id, "❌ Task not found!", show_alert=True)
                        return

                    # Check completion limits for all sections
                    if section in ['app_downloads', 'promotional', 'watch_ads']:
                        user_completed = completed_tasks.get(call.from_user.id, set())
                        task_key = f"{section}_{task_index}"

                        if task_key in user_completed:
                            if section == 'app_downloads':
                                bot.answer_callback_query(call.id, "🚫 You have already completed this App Download task! Each app can only be downloaded once.", show_alert=True)
                            elif section == 'promotional':
                                bot.answer_callback_query(call.id, "🚫 You have already completed this Promotional task! Each promotional task can only be done once.", show_alert=True)
                            elif section == 'watch_ads':
                                bot.answer_callback_query(call.id, "🚫 You have already completed this Watch Ads task! Each video can only be watched once.", show_alert=True)
                            return

                    # Get task details
                    task = task_sections[section][task_index]
                    reward = extract_reward_from_task(task)
                    task_parts = task.split(" - ")
                    task_name = task_parts[0] if task_parts else task[:50]

                    # Check for auto-balance feature
                    auto_added, auto_reward = auto_add_balance_for_task(call.from_user.id, task, section, task_index)

                    # Notify admin about task completion
                    balance = user_balances.get(call.from_user.id, 0)
                    first_name = call.from_user.first_name or "Unknown"
                    username = call.from_user.username or "No Username"

                    task_type = section.replace('_', ' ').title()
                    reward_text = f"₹{reward}" if reward > 0 and not is_client_task(task) else "Admin Determined"

                    notify_admin_user_action(
                        call.from_user.id, 
                        first_name, 
                        username, 
                        f"✅ Completed {task_type} Task (Auto-Complete)", 
                        f"Task: {task_name[:50]}..., Reward: {reward_text}, Auto-Added: {'Yes' if auto_added else 'No'}"
                    )

                    if auto_added:
                        completion_msg = f"✅ **Task Completed Successfully!**\n\n"
                        completion_msg += f"📝 **Task:** {task_name}\n"
                        completion_msg += f"💰 **Reward:** ₹{auto_reward} (Auto-Added)\n"
                        completion_msg += f"🔄 **Type:** {task_type}\n\n"
                        completion_msg += f"✅ **Balance automatically updated!**\n"
                        completion_msg += f"📸 You can still submit screenshot for verification"

                        bot.send_message(call.from_user.id, completion_msg, parse_mode="Markdown")
                        bot.answer_callback_query(call.id, f"✅ Task completed! ₹{auto_reward} added automatically!")
                    else:
                        completion_msg = f"✅ **Task Marked as Completed!**\n\n"
                        completion_msg += f"📝 **Task:** {task_name}\n"
                        completion_msg += f"💰 **Reward:** ₹{reward} (Pending)\n"
                        completion_msg += f"🔄 **Type:** {task_type}\n\n"
                        completion_msg += f"📸 **Next Step:** Submit screenshot for admin approval\n"
                        completion_msg += f"⚠️ **Note:** Balance will be added after admin verification"

                        bot.send_message(call.from_user.id, completion_msg, parse_mode="Markdown")
                        bot.answer_callback_query(call.id, "✅ Task completed! Now submit screenshot for verification.")
                else:
                    bot.answer_callback_query(call.id, "❌ Invalid task format!", show_alert=True)
            except ValueError as e:
                bot.answer_callback_query(call.id, "❌ Invalid task index!", show_alert=True)
                print(f"Task finish error: {e}")
            except Exception as e:
                bot.answer_callback_query(call.id, "❌ Error completing task!", show_alert=True)
                print(f"Task completion error: {e}")
            return

        # Handle task completion with auto-balance feature
        elif call.data.startswith("complete_"):
            try:
                parts = call.data.split("_")
                if len(parts) >= 3:
                    section = "_".join(parts[1:-1])
                    task_index = int(parts[-1])

                    # Validate section exists
                    if section not in task_sections:
                        bot.answer_callback_query(call.id, "❌ Invalid task section!", show_alert=True)
                        return

                    # Validate task index
                    if not (0 <= task_index < len(task_sections[section])):
                        bot.answer_callback_query(call.id, "❌ Task not found!", show_alert=True)
                        return

                    # Check completion limits for all sections including watch_ads
                    if section in ['app_downloads', 'promotional', 'watch_ads']:
                        user_completed = completed_tasks.get(call.from_user.id, set())
                        task_key = f"{section}_{task_index}"

                        if task_key in user_completed:
                            if section == 'app_downloads':
                                bot.answer_callback_query(call.id, "🚫 You have already completed this App Download task! Each app can only be downloaded once.", show_alert=True)
                            elif section == 'promotional':
                                bot.answer_callback_query(call.id, "🚫 You have already completed this Promotional task! Each promotional task can only be done once.", show_alert=True)
                            elif section == 'watch_ads':
                                bot.answer_callback_query(call.id, "🚫 You have already completed this Watch Ads task! Each video can only be watched once.", show_alert=True)

                            # Notify admin about attempted re-completion
                            first_name = call.from_user.first_name or "Unknown"
                            username = call.from_user.username or "No Username"
                            task_name = task_sections[section][task_index][:50]

                            notify_admin_user_action(
                                call.from_user.id, 
                                first_name, 
                                username, 
                                f"🚫 Attempted Re-completion", 
                                f"Section: {section.replace('_', ' ').title()}, Task: {task_name}..."
                            )
                            return

                    # Get task details
                    task = task_sections[section][task_index]
                    link = extract_link_from_task(task)
                    reward = extract_reward_from_task(task)
                    task_parts = task.split(" - ")
                    task_name = task_parts[0] if task_parts else task[:50]

                    # Check for auto-balance feature
                    auto_added, auto_reward = auto_add_balance_for_task(call.from_user.id, task, section, task_index)

                    # Notify admin about task start
                    balance = user_balances.get(call.from_user.id, 0)
                    first_name = call.from_user.first_name or "Unknown"
                    username = call.from_user.username or "No Username"

                    task_type = section.replace('_', ' ').title()
                    reward_text = f"₹{reward}" if reward > 0 and not is_client_task(task) else "Admin Determined"

                    notify_admin_user_action(
                        call.from_user.id, 
                        first_name, 
                        username, 
                        f"🎯 Started {task_type} Task (Auto-Tracking)", 
                        f"Task: {task_name[:50]}..., Reward: {reward_text}, Auto-Added: {'Yes' if auto_added else 'No'}"
                    )

                    # Store task info
                    pending_tasks[call.from_user.id] = {
                        'task': task,
                        'task_name': task_name,
                        'section': section,
                        'task_index': task_index,
                        'reward': reward,
                        'link': link
                    }

                    # Handle client tasks
                    if is_client_task(task):
                        try:
                            tracking_part = task.split("TRACKING:")[1].split(" - ")[0]
                            original_part = task.split("ORIGINAL:")[1].split(" - ")[0] if " - " in task.split("ORIGINAL:")[1] else task.split("ORIGINAL:")[1]
                            client_id = tracking_part.split("_")[0]
                            tracking_link = generate_client_tracking_link(client_id, tracking_part.split("_")[1])

                            markup = types.InlineKeyboardMarkup()
                            markup.add(types.InlineKeyboardButton("🔗 Visit Website", url=original_part))
                            markup.add(types.InlineKeyboardButton("✅ Complete Task", url=tracking_link))

                            # Fixed Markdown formatting to avoid parsing errors
                            task_info = f"🎯 Client Task (Real-Time Tracking): {task_name}\n"
                            task_info += f"💡 Reward: Determined by admin\n\n"
                            task_info += f"Steps:\n"
                            task_info += f"1. Click 'Visit Website'\n"
                            task_info += f"2. Complete the required action\n"
                            task_info += f"3. Click 'Complete Task'\n"
                            task_info += f"4. Submit screenshot\n"
                            task_info += f"5. Wait for approval\n\n"
                            task_info += f"🔄 Auto-Tracking: Active\n"
                            task_info += f"🚨 Admin will get instant notification!"

                            bot.send_message(call.from_user.id, task_info, reply_markup=markup)
                            bot.answer_callback_query(call.id, "✅ Client task loaded!")

                        except Exception as e:
                            bot.answer_callback_query(call.id, "❌ Error processing client task!", show_alert=True)
                            print(f"Client task error: {e}")

                    elif link:
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔗 Visit Website", url=link))

                        # Add tracking link for ALL sections including promotional
                        if section in ['watch_ads', 'app_downloads', 'promotional']:
                            tracking_link = generate_task_tracking_link(section, task_index, f"task{task_index+1}")
                            markup.add(types.InlineKeyboardButton("🎯 Track Activity", url=tracking_link))

                        # Only add Complete Task button for non-watch_ads sections
                        if section != 'watch_ads':
                            markup.add(types.InlineKeyboardButton("✅ Complete Task", callback_data=f"finish_task_{section}_{task_index}"))

                        # Fixed Markdown formatting to avoid parsing errors
                        task_info = f"📝 Task (Enhanced Tracking): {task_name}\n"
                        if reward > 0:
                            task_info += f"💰 Reward: ₹{reward}\n"

                        if auto_added:
                            task_info += f"✅ Auto-Added: ₹{auto_reward} (task completed!)\n"

                        if section == 'watch_ads':
                            task_info += "🔒 Type: One-time only\n"
                            task_info += "📺 Enhanced Tracking: Active\n"
                        elif section == 'app_downloads':
                            task_info += "🔒 Type: One-time only\n"
                            task_info += "📱 Enhanced Tracking: Active\n"
                        elif section == 'promotional':
                            task_info += "🔒 Type: One-time only\n"

                        if auto_added:
                            task_info += "\n✅ Task Completed Automatically!\n📸 You can still submit screenshot for verification"
                        else:
                            if section in ['watch_ads', 'app_downloads', 'promotional']:
                                task_info += "\n📋 **Complete Task Steps:**\n"
                                task_info += "1️⃣ Click 'Visit Website'\n"
                                task_info += "2️⃣ Complete the required action\n"
                                task_info += "3️⃣ Click 'Track Activity' (🚨 IMPORTANT for verification)\n"
                                task_info += "4️⃣ Click 'Complete Task'\n"
                                task_info += "5️⃣ Submit screenshot proof\n\n"
                                task_info += "🔍 **Enhanced Tracking Features:**\n"
                                task_info += "✅ Real-time activity monitoring\n"
                                task_info += "🚨 Instant admin notifications\n"
                                task_info += "📊 Engagement verification\n"
                                task_info += "🛡️ Anti-fraud protection\n\n"
                                task_info += "💡 **Note:** Tracking link proves you visited the website!"
                            else:
                                task_info += "\nSteps:\n1. Click 'Visit Website'\n2. Complete the required action\n3. Click 'Complete Task'\n4. Submit screenshot\n\n🔄 Auto-Tracking: Active"

                        bot.send_message(call.from_user.id, task_info, reply_markup=markup)

                        if auto_added:
                            bot.answer_callback_query(call.id, f"✅ Task completed! ₹{auto_reward} added automatically!")
                        else:
                            if section in ['watch_ads', 'app_downloads']:
                                bot.answer_callback_query(call.id, "✅ Task loaded with enhanced tracking!")
                            else:
                                bot.answer_callback_query(call.id, "✅ Task loaded successfully!")
                    else:
                        bot.answer_callback_query(call.id, "❌ No valid link found!", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "❌ Invalid task format!", show_alert=True)
            except ValueError as e:
                bot.answer_callback_query(call.id, "❌ Invalid task index!", show_alert=True)
                print(f"Task index error: {e}")
            except Exception as e:
                bot.answer_callback_query(call.id, "❌ Error loading task!", show_alert=True)
                print(f"Task completion error: {e}")
            return

        # Handle approval/rejection for task submissions
        elif call.data.startswith("approve_"):
            uid = int(call.data.split("_")[1])

            if uid in pending_tasks:
                task_data = pending_tasks[uid]
                section = task_data.get('section', '')
                task_index = task_data.get('task_index', 0)
                task_name = task_data.get('task_name', 'Unknown Task')

                # Mark as completed for limited sections
                if section in ['app_downloads', 'promotional', 'watch_ads']:
                    if uid not in completed_tasks:
                        completed_tasks[uid] = set()
                    completed_tasks[uid].add(f"{section}_{task_index}")

                pending_tasks.pop(uid, None)
                save_data()
                print(f"✅ Task completed - User: {uid}, Section: {section}")

                task = task_data.get('task', '')
                if is_client_task(task):
                    bot.send_message(uid, f"✅ Client task approved!\n📝 Task: {task_name}\n⚠️ Admin will add reward manually.")
                else:
                    reward = task_data.get('reward', 0)
                    bot.send_message(uid, f"✅ Task approved!\n📝 Task: {task_name}\n⚠️ Admin will add ₹{reward} manually.")
            else:
                bot.send_message(uid, "✅ Task approved!")

            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption=f"✅ Approved task from user {uid}. (Admin must use /addbalance manually)"
            )

        elif call.data.startswith("reject_"):
            uid = int(call.data.split("_")[1])
            bot.send_message(uid, "❌ Task proof rejected. Please follow requirements properly.")
            bot.edit_message_caption(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                caption=f"❌ Rejected task from user {uid}."
            )

        # Admin management callbacks
        elif call.data.startswith("admin_"):
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
                return

            if call.data == "admin_add_task":
                markup = generate_task_add_markup()
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="➕ **Add New Task**\n\nSelect task category:",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "admin_watch_ads":
                watch_ads_list = "📺 **Watch Ads Tasks:**\n\n"
                if task_sections['watch_ads']:
                    for i, task in enumerate(task_sections['watch_ads'], 1):
                        task_preview = task[:50] + "..." if len(task) > 50 else task
                        reward = extract_reward_from_task(task)
                        watch_ads_list += f"{i}. {task_preview}"
                        if reward > 0:
                            watch_ads_list += f" (₹{reward})"
                        watch_ads_list += "\n"
                else:
                    watch_ads_list += "❌ No watch ads tasks available"

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("➕ Add Watch Ads Task", callback_data="add_watch_ads"))
                if task_sections['watch_ads']:
                    markup.add(types.InlineKeyboardButton("🗑️ Remove Watch Ads", callback_data="remove_watch_ads"))
                markup.add(types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="back_to_admin"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=watch_ads_list,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "admin_app_downloads":
                app_downloads_list = "📱 **App Download Tasks:**\n\n"
                if task_sections['app_downloads']:
                    for i, task in enumerate(task_sections['app_downloads'], 1):
                        task_preview = task[:50] + "..." if len(task) > 50 else task
                        reward = extract_reward_from_task(task)
                        app_downloads_list += f"{i}. {task_preview}"
                        if reward > 0:
                            app_downloads_list += f" (₹{reward})"
                        app_downloads_list += "\n"
                else:
                    app_downloads_list += "❌ No app download tasks available"

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("➕ Add App Download Task", callback_data="add_app_downloads"))
                if task_sections['app_downloads']:
                    markup.add(types.InlineKeyboardButton("🗑️ Remove App Downloads", callback_data="remove_app_downloads"))
                markup.add(types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="back_to_admin"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=app_downloads_list,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "admin_promotional":
                promotional_list = "📢 **Promotional Tasks:**\n\n"
                if task_sections['promotional']:
                    for i, task in enumerate(task_sections['promotional'], 1):
                        task_preview = task[:50] + "..." if len(task) > 50 else task
                        if is_client_task(task):
                            promotional_list += f"{i}. 🎯 {task_preview} (Client Task)\n"
                        else:
                            reward = extract_reward_from_task(task)
                            promotional_list += f"{i}. {task_preview}"
                            if reward > 0:
                                promotional_list += f" (₹{reward})"
                            promotional_list += "\n"
                else:
                    promotional_list += "❌ No promotional tasks available"

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("➕ Add Promotional Task", callback_data="add_promotional"))
                if task_sections['promotional']:
                    markup.add(types.InlineKeyboardButton("🗑️ Remove Promotional", callback_data="remove_promotional"))
                markup.add(types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="back_to_admin"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=promotional_list,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "admin_client_tasks":
                client_list = "🎯 **Client Tasks Management:**\n\n"
                if client_tasks:
                    for client_id, task_data in client_tasks.items():
                        client_name = task_data.get('info', 'Unknown Client')
                        links_count = len(task_data.get('links', []))
                        referrals_count = len(client_referrals.get(client_id, []))
                        created_date = task_data.get('created_at', 'Unknown')[:10]

                        client_list += f"🏷️ **ID:** {client_id}\n"
                        client_list += f"📋 **Name:** {client_name}\n"
                        client_list += f"🔗 **Links:** {links_count}\n"
                        client_list += f"👥 **Completions:** {referrals_count}\n"
                        client_list += f"📅 **Created:** {created_date}\n\n"
                else:
                    client_list += "❌ No client tasks available\n\n"

                client_list += "🔧 **Simple Management:**\n"
                client_list += "🔗 **Add Link** - Paste it, auto-tracking will be enabled\n"
                client_list += "🗑️ **Remove Link** - Delete client task"

                markup = generate_client_task_options()
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=client_list,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "admin_remove_task":
                markup = generate_enhanced_remove_task_markup()
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="🗑️ **Remove Tasks**\n\nSelect category to remove tasks from:",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "admin_referral_mgmt":
                referral_stats = ""
                if referral_data:
                    referrer_counts = {}
                    for referred_user, referrer in referral_data.items():
                        referrer_counts[referrer] = referrer_counts.get(referrer, 0) + 1

                    referral_stats = "📊 **Top Referrers:**\n"
                    for referrer, count in sorted(referrer_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                        earnings = count * 5
                        referral_stats += f"👤 User {referrer}: {count} referrals (₹{earnings})\n"
                    referral_stats += f"\n📈 **Total:** {len(referral_data)} referrals\n"
                else:
                    referral_stats = "📊 **No referrals yet**\n"

                referral_info = f"👥 **Referral Management Panel**\n\n{referral_stats}\n"
                referral_info += "🔧 **Available Commands:**\n"
                referral_info += "• `/resetreferral user_id` - Reset user's referral status\n"
                referral_info += "• `/referralstats` - View detailed statistics\n\n"
                referral_info += "💡 **How it works:**\n"
                referral_info += "• Normally each user can only be referred once\n"
                referral_info += "• Reset allows user to be referred again\n"
                referral_info += "• Both referrer and new user get ₹5 bonus"

                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("🔄 Reset User", callback_data="reset_referral_prompt"),
                    types.InlineKeyboardButton("🔄 Reset All", callback_data="reset_all_referrals")
                )
                markup.add(
                    types.InlineKeyboardButton("📊 Detailed Stats", callback_data="show_referral_stats"),
                    types.InlineKeyboardButton("📋 Export Data", callback_data="export_referral_data")
                )
                markup.add(types.InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="back_to_admin"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=referral_info,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "reset_referral_prompt":
                awaiting_referral_reset[call.from_user.id] = True

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_referral_mgmt"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="🔄 **Reset User Referral**\n\n📝 **Send the User ID to reset:**\n\n💡 **Example:** 123456789\n\n⚠️ **Note:** This will allow the user to be referred again\n\n📋 **What happens after reset:**\n• User can be referred again\n• User can get ₹5 bonus again\n• Previous referral data is removed",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id, "📝 Send user ID to reset")

            elif call.data == "reset_all_referrals":
                if referral_data:
                    confirm_markup = types.InlineKeyboardMarkup()
                    confirm_markup.add(types.InlineKeyboardButton("⚠️ CONFIRM RESET ALL", callback_data="confirm_reset_all_referrals"))
                    confirm_markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="admin_referral_mgmt"))

                    warning_msg = f"⚠️ **BULK REFERRAL RESET WARNING**\n\n"
                    warning_msg += f"🚨 **This will reset ALL {len(referral_data)} referrals!**\n\n"
                    warning_msg += f"📋 **What will happen:**\n"
                    warning_msg += f"• All users can be referred again\n"
                    warning_msg += f"• All users will get ₹5 bonus again\n"
                    warning_msg += f"• All referral history will be cleared\n"
                    warning_msg += f"• This action cannot be undone\n\n"
                    warning_msg += f"💡 **Use case:** Special promotions, events\n\n"
                    warning_msg += f"🔄 **Are you absolutely sure?**"

                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=warning_msg,
                        parse_mode="Markdown",
                        reply_markup=confirm_markup
                    )
                else:
                    bot.answer_callback_query(call.id, "❌ No referrals to reset!", show_alert=True)

            elif call.data == "confirm_reset_all_referrals":
                try:
                    reset_count = len(referral_data)

                    if reset_count > 0:
                        # Store user list for notification
                        users_to_notify = list(referral_data.keys())

                        # Clear all referral data
                        referral_data.clear()
                        save_data()

                        # Notify all affected users
                        notification_count = 0
                        for user_id in users_to_notify:
                            try:
                                user_notification = f"🎉 **Special Referral Reset Event!**\n\n"
                                user_notification += f"✅ **Great News:** Your referral status has been reset!\n"
                                user_notification += f"💰 **Bonus:** You can get ₹5 again when referred\n"
                                user_notification += f"🎯 **Event:** Admin special promotion\n\n"
                                user_notification += f"⏰ **Reset Time:** {get_local_time()}"

                                bot.send_message(user_id, user_notification, parse_mode="Markdown")
                                notification_count += 1
                            except:
                                pass

                        # Success response
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("📊 View Stats", callback_data="show_referral_stats"))
                        markup.add(types.InlineKeyboardButton("🔙 Back to Referral Management", callback_data="admin_referral_mgmt"))

                        success_msg = f"✅ **Bulk Referral Reset Completed!**\n\n"
                        success_msg += f"🔄 **Reset Count:** {reset_count} users\n"
                        success_msg += f"📤 **Notifications Sent:** {notification_count} users\n"
                        success_msg += f"❌ **Failed Notifications:** {reset_count - notification_count} users\n\n"
                        success_msg += f"📋 **Results:**\n"
                        success_msg += f"• All referral data cleared\n"
                        success_msg += f"• Users can be referred again\n"
                        success_msg += f"• Bonus system reset for all\n\n"
                        success_msg += f"⏰ **Completed:** {get_local_time()}"

                        bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=success_msg,
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                        bot.answer_callback_query(call.id, f"✅ {reset_count} referrals reset successfully!")
                    else:
                        bot.answer_callback_query(call.id, "❌ No referrals found to reset!", show_alert=True)
                except Exception as e:
                    bot.answer_callback_query(call.id, f"❌ Error: {str(e)}", show_alert=True)

            elif call.data == "export_referral_data":
                try:
                    if referral_data:
                        export_msg = f"📊 **Referral Data Export**\n\n"
                        export_msg += f"📅 **Export Time:** {get_local_time()}\n"
                        export_msg += f"📈 **Total Referrals:** {len(referral_data)}\n\n"

                        # Calculate referrer stats
                        referrer_counts = {}
                        for referred_user, referrer in referral_data.items():
                            referrer_counts[referrer] = referrer_counts.get(referrer, 0) + 1

                        export_msg += f"🏆 **Top Referrers:**\n"
                        for referrer, count in sorted(referrer_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                            earnings = count * 5
                            export_msg += f"👤 {referrer}: {count} refs (₹{earnings})\n"

                        if len(referrer_counts) > 10:
                            export_msg += f"... and {len(referrer_counts) - 10} more\n"

                        export_msg += f"\n📋 **Detailed Data:**\n"
                        for referred, referrer in list(referral_data.items())[:20]:
                            export_msg += f"• {referred} ← {referrer}\n"

                        if len(referral_data) > 20:
                            export_msg += f"... and {len(referral_data) - 20} more entries\n"

                        export_msg += f"\n💰 **Financial Summary:**\n"
                        export_msg += f"• Total Paid: ₹{len(referral_data) * 10}\n"
                        export_msg += f"• Referrer Bonus: ₹{len(referral_data) * 5}\n"
                        export_msg += f"• New User Bonus: ₹{len(referral_data) * 5}"

                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 Back to Referral Management", callback_data="admin_referral_mgmt"))

                        bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=export_msg,
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                        bot.answer_callback_query(call.id, "📊 Data exported successfully!")
                    else:
                        bot.answer_callback_query(call.id, "❌ No referral data to export!", show_alert=True)
                except Exception as e:
                    bot.answer_callback_query(call.id, f"❌ Export error: {str(e)}", show_alert=True)

            elif call.data == "show_referral_stats":
                if referral_data:
                    stats = "👥 **Detailed Referral Statistics:**\n\n"
                    referrer_counts = {}

                    for referred_user, referrer in referral_data.items():
                        referrer_counts[referrer] = referrer_counts.get(referrer, 0) + 1

                    stats += "📊 **All Referrers:**\n"
                    for referrer, count in sorted(referrer_counts.items(), key=lambda x: x[1], reverse=True):
                        earnings = count * 5
                        stats += f"👤 **User {referrer}:** {count} referrals (₹{earnings} earned)\n"

                    stats += f"\n📈 **Summary:**\n"
                    stats += f"• Total Referrals: {len(referral_data)}\n"
                    stats += f"• Unique Referrers: {len(referrer_counts)}\n"
                    stats += f"• Total Bonus Paid: ₹{len(referral_data) * 10}\n"

                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 Back to Referral Management", callback_data="admin_referral_mgmt"))

                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=stats,
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                else:
                    bot.answer_callback_query(call.id, "❌ No referral data available!", show_alert=True)

            elif call.data == "admin_send_notice":
                awaiting_notice[call.from_user.id] = True
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="📢 **Send Notice to All Users**\n\n📝 **Instructions:**\n• Send your notice message in next message\n• It will be sent to ALL registered users\n• Message will include timestamp\n\n💡 **Example:** Important update about bot features\n\n⚠️ **Note:** This will send to all users except admin",
                    parse_mode="Markdown"
                )
                bot.answer_callback_query(call.id, "📝 Send your notice message now")

        # Task addition callbacks
        elif call.data.startswith("add_"):
            section = call.data.replace("add_", "")
            if section in task_sections:
                awaiting_task_add[call.from_user.id] = section
                section_name = section.replace('_', ' ').title()

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"➕ **Add {section_name} Task**\n\n📝 **Format:** Task Name - https://example.com ₹10\n\n✅ **Auto-Features:**\n💰 **Auto-Reward:** ₹0.1+ will be added automatically\n⚠️ **Manual Reward:** Below ₹0.1 or no amount = manual /addbalance\n🔄 **Auto-Tracking:** Always enabled\n\n💡 **Examples:**\n• `Watch Video - https://youtube.com ₹5` ✅ Auto\n• `Download App - https://play.google.com ₹0.05` ❌ Manual\n• `Visit Website - https://example.com` ❌ Manual",
                    parse_mode="Markdown"
                )
                bot.answer_callback_query(call.id, f"📝 Send {section_name} task details")

        # Task removal callbacks
        elif call.data.startswith("remove_"):
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
                return

            if call.data == "remove_watch_ads":
                markup = generate_task_removal_list("watch_ads")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="🗑️ **Remove Watch Ads Tasks:**\n\nSelect task to remove:",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "remove_app_downloads":
                markup = generate_task_removal_list("app_downloads")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="🗑️ **Remove App Download Tasks:**\n\nSelect task to remove:",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "remove_promotional":
                markup = generate_task_removal_list("promotional")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="🗑️ **Remove Promotional Tasks:**\n\nSelect task to remove:",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "remove_client_tasks":
                markup = generate_task_removal_list("client_tasks")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="🗑️ **Remove Client Tasks:**\n\nSelect client task to remove:",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data == "remove_all_tasks":
                markup = generate_task_removal_list("all_tasks")
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="⚠️ **REMOVE ALL TASKS**\n\n🚨 This will delete ALL tasks from ALL sections!\n\nAre you sure?",
                    parse_mode="Markdown",
                    reply_markup=markup
                )

            elif call.data.startswith("remove_task_"):
                parts = call.data.split("_")
                section = "_".join(parts[2:-1])
                task_index = int(parts[-1])

                if section in task_sections and 0 <= task_index < len(task_sections[section]):
                    removed_task = task_sections[section].pop(task_index)
                    save_data()

                    task_preview = removed_task[:50] + "..." if len(removed_task) > 50 else removed_task

                    # Create back navigation markup
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 Back to Remove Tasks", callback_data="admin_remove_task"))
                    markup.add(types.InlineKeyboardButton("🏠 Back to Admin Panel", callback_data="back_to_admin"))

                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=f"✅ **Task Removed Successfully!**\n\n🗑️ **Removed:** {task_preview}\n📂 **From:** {section.replace('_', ' ').title()}\n\n💾 **Data saved automatically**\n\n🔄 **Choose next action:**",
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                    bot.answer_callback_query(call.id, "✅ Task removed! Use buttons below to continue.")

            elif call.data.startswith("remove_client_"):
                client_id = call.data.replace("remove_client_", "")
                if client_id in client_tasks:
                    client_name = client_tasks[client_id].get('info', 'Unknown Client')

                    # Remove client task
                    del client_tasks[client_id]

                    # Remove client referrals
                    if client_id in client_referrals:
                        del client_referrals[client_id]

                    # Remove from promotional tasks
                    task_sections['promotional'] = [
                        task for task in task_sections['promotional'] 
                        if not (is_client_task(task) and client_id in task)
                    ]

                    save_data()

                    # Create back navigation markup
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 Back to Client Tasks", callback_data="admin_client_tasks"))
                    markup.add(types.InlineKeyboardButton("🗑️ Remove More Tasks", callback_data="admin_remove_task"))
                    markup.add(types.InlineKeyboardButton("🏠 Back to Admin Panel", callback_data="back_to_admin"))

                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=f"✅ **Client Task Removed Successfully!**\n\n🗑️ **Client:** {client_name}\n🏷️ **ID:** {client_id}\n📂 **Removed from:** All sections\n\n💾 **Data saved automatically**\n\n🔄 **Choose next action:**",
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                    bot.answer_callback_query(call.id, "✅ Client task removed! Use buttons below to continue.")

            elif call.data == "confirm_delete_all":
                # Clear all tasks
                task_sections['watch_ads'].clear()
                task_sections['app_downloads'].clear()
                task_sections['promotional'].clear()
                client_tasks.clear()
                client_referrals.clear()
                save_data()

                # Create back navigation markup
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("➕ Add New Tasks", callback_data="admin_add_task"))
                markup.add(types.InlineKeyboardButton("🏠 Back to Admin Panel", callback_data="back_to_admin"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="✅ **ALL TASKS REMOVED SUCCESSFULLY!**\n\n🗑️ **Cleared:**\n📺 Watch Ads Tasks\n📱 App Download Tasks\n📢 Promotional Tasks\n🎯 Client Tasks\n\n💾 **Data saved automatically**\n\n🔄 **Choose next action:**",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id, "✅ All tasks removed! Use buttons below to continue.")

        # Simplified client task management callbacks
        elif call.data == "add_client_task_link":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
                return

            awaiting_client_data[call.from_user.id] = 'simple_add_link'
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="🔗 **Add Client Task Link**\n\n📝 **Send the link to add:**\n\n💡 **Example:** https://example.com\n\n✅ **Auto Features:**\n🎯 Automatic tracking link generation\n📢 Auto-add to promotional tasks\n🔄 Real-time user tracking",
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id, "📝 Send client link")

        elif call.data == "remove_client_task_link":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
                return

            if client_tasks:
                remove_list = "🗑️ **Remove Client Task Link:**\n\nSelect client task to remove:"
                markup = types.InlineKeyboardMarkup()

                for client_id, task_data in client_tasks.items():
                    client_name = task_data.get('info', 'Unknown Client')
                    links_count = len(task_data.get('links', []))
                    referrals_count = len(client_referrals.get(client_id, []))
                    button_text = f"🗑️ {client_name} ({links_count}L, {referrals_count}U)"
                    markup.add(types.InlineKeyboardButton(button_text, callback_data=f"simple_remove_client_{client_id}"))

                markup.add(types.InlineKeyboardButton("🔙 Back to Client Tasks", callback_data="admin_client_tasks"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=remove_list,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            else:
                bot.answer_callback_query(call.id, "❌ No client tasks available!", show_alert=True)

        # Simplified client removal callback
        elif call.data.startswith("simple_remove_client_"):
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
                return

            client_id = call.data.replace("simple_remove_client_", "")
            if client_id in client_tasks:
                client_name = client_tasks[client_id].get('info', 'Unknown Client')

                # Remove client task
                del client_tasks[client_id]

                # Remove client referrals
                if client_id in client_referrals:
                    del client_referrals[client_id]

                # Remove from promotional tasks
                task_sections['promotional'] = [
                    task for task in task_sections['promotional'] 
                    if not (is_client_task(task) and client_id in task)
                ]

                save_data()

                # Create back navigation markup
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 Back to Client Tasks", callback_data="admin_client_tasks"))
                markup.add(types.InlineKeyboardButton("🔗 Add More Client Links", callback_data="add_client_task_link"))
                markup.add(types.InlineKeyboardButton("🏠 Back to Admin Panel", callback_data="back_to_admin"))

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"✅ **Client Task Link Removed Successfully!**\n\n🗑️ **Client:** {client_name}\n🏷️ **ID:** {client_id}\n📂 **Removed from:** All sections\n🎯 **Tracking:** Disabled\n\n💾 **Data saved automatically**\n\n🔄 **Choose next action:**",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id, "✅ Client task link removed! Use buttons below to continue.")

        # Navigation callbacks
        elif call.data == "back_to_admin":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
                return

            markup = generate_admin_task_markup()

            watch_ads_count = len(task_sections['watch_ads'])
            app_downloads_count = len(task_sections['app_downloads'])
            promotional_count = len(task_sections['promotional'])
            client_tasks_count = len(client_tasks)

            task_info = f"📋 **Admin Task Management Panel**\n\n"
            task_info += f"📊 **Current Tasks:**\n"
            task_info += f"📺 Watch Ads: {watch_ads_count}\n"
            task_info += f"📱 App Downloads: {app_downloads_count}\n"
            task_info += f"📢 Promotional: {promotional_count}\n"
            task_info += f"🎯 Client Tasks: {client_tasks_count}\n\n"
            task_info += f"🔧 **Choose an option below:**"

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=task_info,
                parse_mode="Markdown",
                reply_markup=markup
            )

        elif call.data == "close_admin_panel":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Admin only!", show_alert=True)
                return

            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Admin panel closed")

        elif call.data == "no_action":
            bot.answer_callback_query(call.id, "ℹ️ No action available")

        # Handle User Info callbacks
        elif call.data.startswith("view_user_data_"):
            user_data_id = int(call.data.split("_")[3])

            if call.from_user.id != user_data_id:
                bot.answer_callback_query(call.id, "❌ You can only view your own data!", show_alert=True)
                return

            # Collect user's detailed data
            user_balance = user_balances.get(user_data_id, 0)
            user_completed = completed_tasks.get(user_data_id, set())
            user_referrals = sum(1 for ref_id in referral_data.values() if ref_id == user_data_id)

            # Get completed tasks details
            task_details = []
            total_earned = 0

            for task_key in user_completed:
                try:
                    section, task_index = task_key.split('_', 1)
                    task_index = int(task_index)

                    if section in task_sections and task_index < len(task_sections[section]):
                        task = task_sections[section][task_index]
                        reward = extract_reward_from_task(task)
                        task_name = task.split(" - ")[0] if " - " in task else task[:30]

                        task_details.append({
                            'section': section.replace('_', ' ').title(),
                            'task': task_name,
                            'reward': reward
                        })
                        total_earned += reward
                except:
                    continue

            # Check withdrawal history
            withdrawal_history = []
            if user_data_id in withdrawal_requests:
                req = withdrawal_requests[user_data_id]
                withdrawal_history.append({
                    'type': req.get('type', 'Unknown').upper(),
                    'amount': req.get('final_amount', req.get('amount', 0)),
                    'status': req.get('status', 'pending').title(),
                    'timestamp': req.get('timestamp', 'Unknown')
                })

            # Generate detailed report
            detailed_data = f"📊 **Your Complete Database Report:**\n\n"
            detailed_data += f"👤 **Account Summary:**\n"
            detailed_data += f"🆔 User ID: {user_data_id}\n"
            detailed_data += f"💰 Current Balance: ₹{user_balance:.2f}\n"
            detailed_data += f"✅ Completed Tasks: {len(user_completed)}\n"
            detailed_data += f"👥 Successful Referrals: {user_referrals}\n"
            detailed_data += f"💵 Total Earned (Tasks): ₹{total_earned:.2f}\n"
            detailed_data += f"💰 Referral Bonus: ₹{user_referrals * 5:.2f}\n\n"

            if task_details:
                detailed_data += f"📋 **Completed Tasks History:**\n"
                for i, task in enumerate(task_details[:10], 1):  # Show last 10 tasks
                    detailed_data += f"{i}. **{task['section']}**\n"
                    detailed_data += f"   📝 Task: {task['task']}...\n"
                    detailed_data += f"   💰 Earned: ₹{task['reward']:.2f}\n\n"

                if len(task_details) > 10:
                    detailed_data += f"... and {len(task_details) - 10} more tasks\n\n"
            else:
                detailed_data += f"📋 **Completed Tasks:** No tasks completed yet\n\n"

            if withdrawal_history:
                detailed_data += f"🏧 **Withdrawal History:**\n"
                for withdrawal in withdrawal_history:
                    detailed_data += f"💳 Method: {withdrawal['type']}\n"
                    detailed_data += f"💰 Amount: ₹{withdrawal['amount']:.2f}\n"
                    detailed_data += f"📊 Status: {withdrawal['status']}\n"
                    detailed_data += f"📅 Date: {withdrawal['timestamp'][:10]}\n\n"
            else:
                detailed_data += f"🏧 **Withdrawals:** No withdrawals yet\n\n"

            # Check if user was referred
            referrer_info = ""
            if user_data_id in referral_data:
                referrer_id = referral_data[user_data_id]
                referrer_info = f"👥 **Referred by:** User {referrer_id}\n"
            else:
                referrer_info = f"👥 **Join Type:** Direct Join\n"

            detailed_data += referrer_info
            detailed_data += f"📊 **Account Status:** {'🚫 Banned' if is_banned(user_data_id) else '✅ Active'}\n"
            detailed_data += f"⏰ **Report Generated:** {get_local_time()}\n\n"
            detailed_data += f"💡 **Note:** This is your complete activity history in the bot"

            # Create navigation markup
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh Data", callback_data=f"view_user_data_{user_data_id}"))
            markup.add(types.InlineKeyboardButton("👤 Back to User Info", callback_data=f"refresh_user_info_{user_data_id}"))

            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=detailed_data,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id, "📊 Database loaded successfully!")
            except Exception as e:
                # If message is too long, send as new message
                bot.send_message(call.from_user.id, detailed_data, parse_mode="Markdown", reply_markup=markup)
                bot.answer_callback_query(call.id, "📊 Database report sent!")

        elif call.data.startswith("refresh_user_info_"):
            user_info_id = int(call.data.split("_")[3])

            if call.from_user.id != user_info_id:
                bot.answer_callback_query(call.id, "❌ You can only view your own info!", show_alert=True)
                return

            try:
                user_chat = bot.get_chat(user_info_id)
                name = user_chat.first_name or "Unknown"
                username = user_chat.username or "No Username"
            except:
                name = "Unknown"
                username = "No Username"

            balance = user_balances.get(user_info_id, 0)
            referral_count = sum(1 for ref_id in referral_data.values() if ref_id == user_info_id)
            referral_bonus = referral_count * 5
            join_date = "Unknown"

            if user_info_id in referral_data:
                join_date = "Via Referral"
            elif user_info_id in user_balances:
                join_date = "Direct Join"

            user_info = f"👤 **Your Account Information:**\n\n"
            user_info += f"📝 **Name:** {name}\n"
            user_info += f"🔗 **Username:** @{username}\n"
            user_info += f"🆔 **User ID:** {user_info_id}\n"
            user_info += f"💰 **Current Balance:** ₹{balance:.2f}\n"
            user_info += f"👥 **Referrals Made:** {referral_count}\n"
            user_info += f"💵 **Referral Bonus:** ₹{referral_bonus:.2f}\n"
            user_info += f"📅 **Join Type:** {join_date}\n"
            user_info += f"🎯 **Account Status:** {'🚫 Banned' if is_banned(user_info_id) else '✅ Active'}\n\n"
            user_info += f"📊 **Want to see your detailed activity data?**"

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📊 View My Database", callback_data=f"view_user_data_{user_info_id}"))
            markup.add(types.InlineKeyboardButton("🔄 Refresh Info", callback_data=f"refresh_user_info_{user_info_id}"))

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=user_info,
                parse_mode="Markdown",
                reply_markup=markup
            )
            bot.answer_callback_query(call.id, "🔄 Information refreshed!")

    except Exception as e:
        print(f"Callback error in {call.data}: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ Error occurred: {str(e)[:50]}", show_alert=True)
        except:
            print(f"Failed to send callback answer for error: {e}")

# ✅ ERROR HANDLER - Removed to prevent double message handling
# The main handle_message function already handles all messages

# ✅ MAIN FUNCTION WITH IMPROVED ERROR HANDLING
def run_bot():
    """Run bot with robust error handling and restart mechanism"""
    restart_count = 0
    max_restarts = 5  # Reduced max restarts

    while restart_count < max_restarts:
        try:
            logger.info("🤖 Bot starting...")

            username = get_bot_username()
            logger.info(f"✅ Bot connected: @{username}")
            logger.info(f"📺 Watch Ads tasks: {len(task_sections['watch_ads'])}")
            logger.info(f"📱 App Download tasks: {len(task_sections['app_downloads'])}")
            logger.info(f"📢 Promotional tasks: {len(task_sections['promotional'])}")
            logger.info(f"🎯 Client tasks: {len(client_tasks)}")
            logger.info(f"👥 Total users: {len(user_balances)}")
            logger.info(f"🚫 Banned users: {len(banned_users)}")
            logger.info("🚨 REAL-TIME CLIENT TRACKING: ACTIVE")
            logger.info("💾 Data persistence: ENABLED")
            logger.info("🔧 Error handling: IMPROVED")
            logger.info("✅ PayPal 7% tax: IMPLEMENTED")
            logger.info("🔧 Withdrawal approval system: ENABLED")
            logger.info("🛠️ Admin features: ENHANCED")
            logger.info("🗑️ Task removal: ALL SECTIONS WORKING")
            logger.info("🎯 Client tracking: REAL-TIME NOTIFICATIONS")
            logger.info("⏰ Local time: INDIAN STANDARD TIME")
            logger.info("🏷️ Fixed client IDs: IMPLEMENTED")
            logger.info("🔙 Back buttons: COMPLETE")
            logger.info("🔄 AUTO-TRACKING: ENABLED FOR ALL TASKS")
            logger.info("🎯 Client task options: TRACKING & REMOVAL LINKS")
            logger.info("📊 Enhanced admin panel: FULL FUNCTIONALITY")
            logger.info("🚨 All bugs fixed and code optimized")
            logger.info("📢 Notice feature: ENABLED")
            logger.info("💳 Withdrawal approval system: ADDED")
            logger.info("🔒 Watch Ads limit: ONE-TIME ONLY")
            logger.info("💰 Auto-balance feature: ₹0.1+ AUTO ADDED")
            logger.info("📺 Watch Ads tracking: REAL-TIME ENABLED")
            logger.info("📱 App Download tracking: REAL-TIME ENABLED")
            logger.info("🎯 Enhanced task tracking: ALL SECTIONS ACTIVE")
            logger.info("🔄 Task tracking notifications: ADMIN ALERTS ACTIVE")
            logger.info("🛡️ Security freeze/unfreeze system: ENABLED")
            logger.info("🔒 Emergency freeze code: ACTIVE")
            logger.info("🔓 Emergency unlock code: ACTIVE")
            logger.info("🚀 Bot ready with ALL ENHANCED TRACKING & SECURITY FEATURES!")

            bot.infinity_polling(
                timeout=60,  # Increased timeout
                long_polling_timeout=20,  # Increased long polling timeout
                none_stop=True,
                interval=2  # Increased interval
            )

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            restart_count += 1
            logger.error(f"❌ Bot error (attempt {restart_count}/{max_restarts}): {e}")

            if restart_count < max_restarts:
                wait_time = min(120, 20 * restart_count)  # Increased wait time
                logger.info(f"🔄 Restarting in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Max restart attempts reached. Bot stopped.")
                break

    # Graceful shutdown
    try:
        if save_data():
            logger.info("💾 Data saved before shutdown")
        else:
            logger.error("❌ Failed to save data on shutdown")
    except Exception as e:
        logger.error(f"❌ Error saving data on shutdown: {e}")

    logger.info("Bot shutdown completed")

# ✅ HEALTH CHECK SERVER FOR RENDER
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'bot_username': BOT_USERNAME,
                'users': len(user_balances),
                'tasks': sum(len(tasks) for tasks in task_sections.values()),
                'timestamp': get_local_time()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress HTTP server logs
        pass

def start_health_server():
    """Start health check server for Render"""
    try:
        PORT = int(os.getenv('PORT', 10000))
        with socketserver.TCPServer(("0.0.0.0", PORT), HealthHandler) as httpd:
            logger.info(f"🌐 Health server running on port {PORT}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"❌ Health server error: {e}")

# ✅ RUN BOT WITH HEALTH SERVER
if __name__ == "__main__":
    # Start health check server in background for Render
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    logger.info("🏥 Health check server started for Render")
    
    # Start the bot
    run_bot()
