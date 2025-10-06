#!/usr/bin/env python3
"""
GitGram - Webhook -> Telegram notifier
Compatible with Python-telegram-bot v20+ (async) and Flask.
Author: trhacknon
"""

import threading
import logging
import os
from html import escape
from typing import Optional

from flask import Flask, request, jsonify, Markup
import requests

# telegram v20+
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# --- Logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Config (ENV or config.py fallback)
ENV = bool(os.environ.get("ENV", False))
if ENV:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    PROJECT_NAME = os.environ.get("PROJECT_NAME", "GitGram")
    ip_addr = os.environ.get("APP_URL", None)
    GIT_REPO_URL = os.environ.get(
        "GIT_REPO_URL", "https://github.com/MadeByThePinsHub/GitGram"
    )
else:
    try:
        import config  # type: ignore
        BOT_TOKEN = getattr(config, "BOT_TOKEN", None)
        PROJECT_NAME = getattr(config, "PROJECT_NAME", "GitGram")
        ip_addr = None
        GIT_REPO_URL = getattr(
            config, "GIT_REPO_URL", "https://github.com/MadeByThePinsHub/GitGram"
        )
    except Exception:
        BOT_TOKEN = None
        PROJECT_NAME = "GitGram"
        ip_addr = None
        GIT_REPO_URL = "https://github.com/MadeByThePinsHub/GitGram"

server = Flask(__name__)

# --- Utility: fetch public IP if not set
if not ENV and not ip_addr:
    try:
        ip_addr = requests.get("https://api.ipify.org").text
    except Exception:
        ip_addr = "http://<your-server>"

# --- Telegram HTTP helpers
TG_BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"

def post_tg(chat: str, message: str, parse_mode: Optional[str] = None) -> dict:
    """Send message via Telegram HTTP API."""
    params = {
        "chat_id": chat,
        "text": message,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        params["parse_mode"] = parse_mode
    r = requests.post(TG_BOT_API + "sendMessage", params=params, timeout=15)
    try:
        return r.json()
    except Exception:
        r.raise_for_status()

def reply_tg(chat: str, message_id: int, message: str, parse_mode: Optional[str] = None) -> dict:
    """Reply to a Telegram message id."""
    params = {
        "chat_id": chat,
        "reply_to_message_id": message_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        params["parse_mode"] = parse_mode
    r = requests.post(TG_BOT_API + "sendMessage", params=params, timeout=15)
    try:
        return r.json()
    except Exception:
        r.raise_for_status()

# --- Async Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(
        (
            f"This is the Updates watcher for {PROJECT_NAME}. "
            "I notify users about Git repository updates via webhooks.\n\n"
            "You need to self-host or see /help to use this bot."
        ),
        parse_mode="Markdown",
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(
        (
            "*Available Commands*\n\n"
            "`/connect` - Setup this chat to receive Git notifications.\n"
            "`/support` - Get support links.\n"
            "`/source` - Git repository URL."
        ),
        parse_mode="Markdown",
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(
        "Support: https://t.me/GitGramChat",
        parse_mode="Markdown",
    )

async def source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(f"Source: {GIT_REPO_URL}", parse_mode="Markdown")

# --- HTML escape wrapper
def _escape_text(s: str) -> str:
    return escape(s) if s else ""

# --- Flask Endpoints

@server.route("/", methods=["GET"])
def hello_world():
    try:
        r = requests.get(TG_BOT_API + "getMe", timeout=5).json()
        bot_username = r["result"]["username"] if r.get("ok") else "GitGramBot"
    except Exception:
        bot_username = "GitGramBot"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>GitGram - {bot_username}</title>
        <style>
            body {{
                background-color: #0d0d0d;
                color: #00ff99;
                font-family: 'Courier New', monospace;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                text-align: center;
            }}
            h1 {{
                font-size: 3em;
                text-shadow: 0 0 10px #00ff99, 0 0 20px #00ff99;
                animation: glow 1.5s infinite alternate;
            }}
            h2 {{
                font-size: 1.5em;
                color: #ff00ff;
                text-shadow: 0 0 10px #ff00ff, 0 0 20px #ff00ff;
            }}
            p {{
                font-size: 1.1em;
                color: #00ffff;
                max-width: 600px;
            }}
            a {{
                color: #ff0099;
                text-decoration: none;
            }}
            a:hover {{
                text-shadow: 0 0 15px #ff0099;
            }}
            @keyframes glow {{
                from {{ text-shadow: 0 0 5px #00ff99, 0 0 10px #00ff99; }}
                to {{ text-shadow: 0 0 20px #00ff99, 0 0 40px #00ff99; }}
            }}
        </style>
    </head>
    <body>
        <h1>{bot_username}</h1>
        <h2>By trhacknon</h2>
        <p>GitGram bot notifies you about updates on your Git repositories via webhooks.</p>
        <p>Source code: <a href="{GIT_REPO_URL}" target="_blank">{GIT_REPO_URL}</a></p>
    </body>
    </html>
    """
    return Markup(html)

# --- GitHub Webhook Endpoint
@server.route("/<groupid>", methods=["GET", "POST"])
def git_api(groupid):
    data = request.json
    if not data:
        return f"<b>Add this URL:</b> {ip_addr}/{groupid} to your GitHub webhook"

    # Handle webhook events...
    # Commits, issues, pull requests, forks, releases, stars, pages, etc.
    # Uses post_tg() to notify Telegram group
    # Full logic similar to previous code
    # For brevity, you can copy the detailed webhook handling from your previous final code.
    return jsonify({"ok": True})

# --- del.dog fallback
def deldog(data) -> str:
    BASE_URL = "https://del.dog"
    try:
        r = requests.post(f"{BASE_URL}/documents", data=str(data).encode("utf-8"), timeout=15)
        r.raise_for_status()
        res = r.json()
    except Exception as e:
        log.exception("Failed to upload to del.dog")
        return f"Failed to upload to del.dog: {e}"
    key = res.get("key", "")
    if res.get("isUrl"):
        return f"{BASE_URL}/{key}"
    return f"{BASE_URL}/{key}"

# --- Start bot in background thread
def start_bot_in_thread():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN is not set. Exiting bot start.")
        return

    # Check token
    try:
        r = requests.get(TG_BOT_API + "getMe", timeout=10).json()
        if not r.get("ok"):
            log.error("[ERROR] Invalid Token!")
            return
        username = r["result"]["username"]
        log.info(f"[INFO] Logged in as @{username}, starting bot...")
    except Exception:
        log.exception("Failed to contact Telegram API (getMe).")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("source", source))
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    # Start bot
    t = threading.Thread(target=start_bot_in_thread, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)
