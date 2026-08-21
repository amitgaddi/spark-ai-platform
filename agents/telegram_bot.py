import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://agent-api:8000")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    await update.message.reply_text("Spark Agent is online. Send a message!\n\nUse `!q2` for background tasks.\nUse `/queue` to view tasks.", parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
        
    # Check if we are awaiting an edited prompt from the user
    if context.user_data.get("awaiting_edit"):
        task_id = context.user_data["awaiting_edit"]
        edited_prompt = update.message.text
        
        res = requests.post(f"{AGENT_API_URL}/v1/approve", json={
            "task_id": task_id,
            "approved_prompt": edited_prompt
        })
        
        context.user_data["awaiting_edit"] = None
        if res.status_code == 200:
            await update.message.reply_text("✅ Edited prompt accepted and queued for processing!")
        else:
            await update.message.reply_text("❌ Error approving edited prompt. It may have expired.")
        return

    user_msg = update.message.text
    chat_id = update.message.chat_id
    
    # Check for /raw command to bypass enhancer
    bypass = False
    if user_msg.startswith("/raw "):
        bypass = True
        user_msg = user_msg[5:] # Remove "/raw " from the message
        
    # Call Agent API
    res = requests.post(f"{AGENT_API_URL}/v1/chat", json={
        "message": user_msg,
        "chat_id": str(chat_id),
        "bypass_enhancer": bypass
    })
    data = res.json()
    
    if data.get("status") == "needs_approval":
        task_id = data["task_id"]
        suggested = data["suggested_prompt"]
        priority = data["priority"]
        
        keyboard = [
            [InlineKeyboardButton("✅ Accept", callback_data=f"accept:{task_id}"),
             InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{task_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject:{task_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"*Suggested Prompt ({priority}):*\n\n`{suggested}`\n\nApprove this?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    elif data.get("status") == "queued":
        await update.message.reply_text(f"✅ Task queued directly ({data['priority']}). Worker is processing...")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ALLOWED_USER_ID:
        return
        
    data = query.data.split(":")
    action = data[0]
    task_id = data[1]
    
    if action == "accept":
        # Need to fetch the suggested prompt to approve it
        # In a real app, we'd fetch from API, but we can just approve via API
        res = requests.post(f"{AGENT_API_URL}/v1/approve", json={
            "task_id": task_id,
            "approved_prompt": "ACCEPTED_DEFAULT" # Worker will fetch original
        })
        # Actually, we need the text. Let's just tell the user to send it if edit.
        # For accept, we need the API to know what to approve. Let's update API to fetch original if "ACCEPTED_DEFAULT"
        await query.edit_message_text("✅ Accepted and queued for processing!")
        
    elif action == "edit":
        # Store the task_id in the user's context so the next message overwrites it
        context.user_data["awaiting_edit"] = task_id
        await query.edit_message_text("Please reply with your edited prompt directly in the chat.")
        
    elif action == "reject":
        await query.edit_message_text("❌ Task rejected.")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
        
    res = requests.get(f"{AGENT_API_URL}/v1/queue")
    data = res.json()
    
    q1 = data.get("q1_urgent", [])
    q2 = data.get("q2_background", [])
    
    msg = "* Eisenhower Matrix Queue *\n\n"
    msg += f"*Q1 Urgent ({len(q1)}):*\n"
    for t in q1:
        msg += f"- {t['final_prompt'][:50]}...\n"
        
    msg += f"\n*Q2 Background ({len(q2)}):*\n"
    for t in q2:
        msg += f"- {t['final_prompt'][:50]}...\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Telegram Bot started. Polling for messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
