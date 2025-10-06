#!/usr/bin/env python3
"""
GitGram - webhook -> Telegram notifier
Compatible with python-telegram-bot v20+ (async) and Flask.
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
    # try to import local config.py if present
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

# --- Utility: if ip_addr not set and we are not using ENV, fetch public IP
if not ENV and not ip_addr:
    try:
        ip_addr = requests.get("https://api.ipify.org").text
    except Exception:
        ip_addr = "http://<your-server>"

# --- Telegram low-level API helpers (useful from webhooks)
TG_BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}/"


def post_tg(chat: str, message: str, parse_mode: Optional[str] = None) -> dict:
    """Send message to desired chat via Telegram HTTP API (fallback)."""
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
    """Reply to a message id via Telegram HTTP API."""
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


# --- Telegram bot handlers (async for v20+)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start command"""
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(
        (
            f"This is the Updates watcher for {PROJECT_NAME}. "
            "I notify users about what's happening on their Git repositories via webhooks.\n\n"
            "You need to self-host or see /help to use this bot in your groups."
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
            "`/connect` - Setup how to connect this chat to receive Git activity notifications.\n"
            "`/support` - Get links to get support if you're stuck.\n"
            "`/source` - Get the Git repository URL."
        ),
        parse_mode="Markdown",
    )


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(
        "To get support in using the bot, join the GitGram support: https://t.me/GitGramChat",
        parse_mode="Markdown",
    )


async def source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(f"Source: {GIT_REPO_URL}", parse_mode="Markdown")


# --- Flask endpoints

@server.route("/", methods=["GET"])
def hello_world():
    # Try to get bot username
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
                font-family: 'Courier New', Courier, monospace;
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
                margin-bottom: 0.2em;
                text-shadow: 0 0 5px #00ff99, 0 0 10px #00ff99;
                animation: glow 1.5s infinite alternate;
            }}
            h2 {{
                font-size: 1.5em;
                color: #ff00ff;
                text-shadow: 0 0 5px #ff00ff, 0 0 10px #ff00ff;
                margin-top: 0;
            }}
            p {{
                font-size: 1.1em;
                color: #00ffff;
                max-width: 600px;
            }}
            @keyframes glow {{
                from {{ text-shadow: 0 0 5px #00ff99, 0 0 10px #00ff99; }}
                to {{ text-shadow: 0 0 20px #00ff99, 0 0 40px #00ff99; }}
            }}
            a {{
                color: #ff0099;
                text-decoration: none;
            }}
            a:hover {{
                text-shadow: 0 0 10px #ff0099;
            }}
        </style>
    </head>
    <body>
        <h1>{bot_username}</h1>
        <h2>By trhacknon</h2>
        <p>Welcome to GitGram! This bot notifies you about updates on your Git repositories via webhooks.</p>
        <p>Check out the source code here: <a href="{GIT_REPO_URL}" target="_blank">{GIT_REPO_URL}</a></p>
    </body>
    </html>
    """
    return Markup(html)


def _escape_text(s: str) -> str:
    # small wrapper to ensure we always escape HTML special chars
    return escape(s) if s is not None else ""


@server.route("/<groupid>", methods=["GET", "POST"])
def git_api(groupid):
    """Main webhook endpoint that GitHub will post to."""
    data = request.json
    if not data:
        return f"<b>Add this url:</b> {ip_addr}/{groupid} to webhooks of the project"

    # New webhook set
    if data.get("hook"):
        repo_url = data["repository"]["html_url"]
        repo_name = _escape_text(data["repository"]["name"])
        sender_url = data["sender"]["html_url"]
        sender_name = _escape_text(data["sender"]["login"])
        response = post_tg(
            groupid,
            f"🙌 Successfully set webhook for <a href='{repo_url}'>{repo_name}</a> by <a href='{sender_url}'>{sender_name}</a>!",
            "HTML",
        )
        return jsonify(response)

    # Commits
    if data.get("commits"):
        commits_text = ""
        rng = len(data["commits"])
        if rng > 10:
            rng = 10
        for x in range(rng):
            commit = data["commits"][x]
            msg_raw = commit.get("message", "")
            if len(msg_raw) > 300:
                commit_msg = _escape_text(msg_raw).split("\n")[0]
            else:
                commit_msg = _escape_text(msg_raw)
            commits_text += (
                f"{commit_msg}\n"
                f"<a href='{commit['url']}'>{commit['id'][:7]}</a> - "
                f"{_escape_text(commit['author']['name'])} "
                f"{_escape_text('<')}{_escape_text(commit['author']['email'])}{_escape_text('>')}\n\n"
            )
            if len(commits_text) > 1000:
                text = (
                    f"✨ <b>{_escape_text(data['repository']['name'])}</b> - New {len(data['commits'])} commits "
                    f"({_escape_text(data['ref'].split('/')[-1])})\n{commits_text}"
                )
                post_tg(groupid, text, "HTML")
                commits_text = ""
        if not commits_text:
            return jsonify({"ok": True, "text": "Commits text is none"})
        text = (
            f"✨ <b>{_escape_text(data['repository']['name'])}</b> - New {len(data['commits'])} commits "
            f"({_escape_text(data['ref'].split('/')[-1])})\n{commits_text}"
        )
        if len(data["commits"]) > 10:
            text += f"\n\n<i>And {len(data['commits']) - 10} other commits</i>"
        response = post_tg(groupid, text, "HTML")
        return jsonify(response)

    # Issue (and comment)
    if data.get("issue"):
        if data.get("comment"):
            text = (
                f"💬 New comment: <b>{_escape_text(data['repository']['name'])}</b>\n"
                f"{_escape_text(data['comment']['body'])}\n\n"
                f"<a href='{data['comment']['html_url']}'>Issue #{data['issue']['number']}</a>\n"
            )
            response = post_tg(groupid, text, "HTML")
            return jsonify(response)
        text = (
            f"🚨 New {data.get('action', '')} issue for <b>{_escape_text(data['repository']['name'])}</b>\n"
            f"<b>{_escape_text(data['issue']['title'])}</b>\n{_escape_text(data['issue']['body'])}\n\n"
            f"<a href='{data['issue']['html_url']}'>issue #{data['issue']['number']}</a>\n"
        )
        response = post_tg(groupid, text, "HTML")
        return jsonify(response)

    # Pull request (and comment)
    if data.get("pull_request"):
        if data.get("comment"):
            text = (
                f"❗ There is a new pull request for <b>{_escape_text(data['repository']['name'])}</b> "
                f"({data['pull_request'].get('state', '')})\n{_escape_text(data['comment']['body'])}\n\n"
                f"<a href='{data['comment']['html_url']}'>Pull request</a>\n"
            )
            response = post_tg(groupid, text, "HTML")
            return jsonify(response)
        text = (
            f"❗  New {data.get('action', '')} pull request for <b>{_escape_text(data['repository']['name'])}</b>\n"
            f"<b>{_escape_text(data['pull_request'].get('title',''))}</b> "
            f"({data['pull_request'].get('state','')})\n{_escape_text(data['pull_request'].get('body',''))}\n\n"
            f"<a href='{data['pull_request']['html_url']}'>Pull request #{data['pull_request'].get('number','')}</a>\n"
        )
        response = post_tg(groupid, text, "HTML")
        return jsonify(response)

    # Fork
    if data.get("forkee"):
        response = post_tg(
            groupid,
            f"🍴 <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> forked "
            f"<a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a>!\n"
            f"Total forks now are {data['repository'].get('forks_count', 0)}",
            "HTML",
        )
        return jsonify(response)

    # Releases, stars, actions...
    if data.get("action"):
        action = data.get("action")
        if action == "published" and data.get("release"):
            text = (
                f"<a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> "
                f"{action} <a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a>!\n\n"
                f"<b>{_escape_text(data['release'].get('name',''))}</b> ({_escape_text(data['release'].get('tag_name',''))})\n"
                f"{_escape_text(data['release'].get('body',''))}\n\n"
                f"<a href='{data['release'].get('tarball_url','')}'>Download tar</a> | "
                f"<a href='{data['release'].get('zipball_url','')}'>Download zip</a>"
            )
            response = post_tg(groupid, text, "HTML")
            return jsonify(response)

        if action == "started":
            text = (
                f"🌟 <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> "
                f"gave a star to <a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a>!\n"
                f"Total stars are now {data['repository'].get('stargazers_count', 0)}"
            )
            response = post_tg(groupid, text, "HTML")
            return jsonify(response)

        if action == "edited" and data.get("release"):
            text = (
                f"<a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> "
                f"{action} <a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a>!\n\n"
                f"<b>{_escape_text(data['release'].get('name',''))}</b> ({_escape_text(data['release'].get('tag_name',''))})\n"
                f"{_escape_text(data['release'].get('body',''))}\n\n"
                f"<a href='{data['release'].get('tarball_url','')}'>Download tar</a> | "
                f"<a href='{data['release'].get('zipball_url','')}'>Download zip</a>"
            )
            response = post_tg(groupid, text, "HTML")
            return jsonify(response)

        if action == "created":
            return jsonify({"ok": True, "text": "Pass trigger for created"})

        response = post_tg(
            groupid,
            f"<a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> {action} "
            f"<a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a>!",
            "HTML",
        )
        return jsonify(response)

    # ref_type
    if data.get("ref_type"):
        response = post_tg(
            groupid,
            f"A new {data['ref_type']} on <a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a> "
            f"was created by <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a>!",
            "HTML",
        )
        return jsonify(response)

    # created/deleted/forced pages/context...
    if data.get("created"):
        response = post_tg(
            groupid,
            f"Branch {data['ref'].split('/')[-1]} <b>{data['ref'].split('/')[-2]}</b> on "
            f"<a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a> "
            f"was created by <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a>!",
            "HTML",
        )
        return jsonify(response)

    if data.get("deleted"):
        response = post_tg(
            groupid,
            f"Branch {data['ref'].split('/')[-1]} <b>{data['ref'].split('/')[-2]}</b> on "
            f"<a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a> "
            f"was deleted by <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a>!",
            "HTML",
        )
        return jsonify(response)

    if data.get("forced"):
        response = post_tg(
            groupid,
            f"Branch {data['ref'].split('/')[-1]} <b>{data['ref'].split('/')[-2]}</b> on "
            f"<a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a> was "
            f"forced by <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a>!",
            "HTML",
        )
        return jsonify(response)

    if data.get("pages"):
        text = f"<a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a> wiki pages were updated by <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a>!\n\n"
        for x in data["pages"]:
            summary = _escape_text(x.get("summary", "")) + "\n" if x.get("summary") else ""
            text += f"📝 <b>{_escape_text(x['title'])}</b> ({x['action']})\n{summary}<a href='{x['html_url']}'>{_escape_text(x['page_name'])}</a> - {x['sha'][:7]}"
            if len(data["pages"]) >= 2:
                text += "\n=====================\n"
            post_tg(groupid, text, "HTML")
        return jsonify({"ok": True})

    if data.get("context"):
        state = data.get("state", "")
        emo = "⏳" if state == "pending" else "✔️" if state == "success" else "❌" if state == "failure" else "🌀"
        response = post_tg(
            groupid,
            f"{emo} <a href='{data['target_url']}'>{_escape_text(data['description'])}</a> on "
            f"<a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a> by "
            f"<a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a>!\n"
            f"Latest commit:\n<a href='{data['commit']['commit']['url']}'>{_escape_text(data['commit']['commit']['message'])}</a>",
            "HTML",
        )
        return jsonify(response)

    # fallback: dump to del.dog and notify
    url = deldog(data)
    response = post_tg(
        groupid,
        "🚫 Webhook endpoint for this chat has received something that isn't understood yet. "
        f"\n\nLink to logs for debugging: {url}",
        "Markdown",
    )
    return jsonify(response)


def deldog(data) -> str:
    """Posting the raw payload to del.dog for debugging and returning the link."""
    BASE_URL = "https://del.dog"
    try:
        r = requests.post(f"{BASE_URL}/documents", data=str(data).encode("utf-8"), timeout=15)
        r.raise_for_status()
        res = r.json()
    except Exception as e:
        log.exception("Failed to upload to del.dog")
        return f"Failed to upload to del.dog: {e}"
    key = res.get("key")
    if not key:
        return f"{BASE_URL}/ (no key returned)"
    if res.get("isUrl"):
        return f"{BASE_URL}/{key}"
    return f"{BASE_URL}/{key}"


# --- Bot bootstrap + Flask run
def start_bot_in_thread():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN is not set. Exiting bot start.")
        return

    # Check token quickly (optional)
    try:
        r = requests.get(TG_BOT_API + "getMe", timeout=10).json()
        if not r.get("ok"):
            log.error("[ERROR] Invalid Token!")
            return
        username = r["result"]["username"]
        log.info(f"[INFO] Logged in as @{username}, starting bot...")
    except Exception:
        log.exception("Failed to contact Telegram API (getMe). Continuing to start bot...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("source", source))

    # Run polling in this (thread) context
    app.run_polling(stop_signals=None)


if __name__ == "__main__":
    # Start bot in background thread, then run Flask (main thread)
    t = threading.Thread(target=start_bot_in_thread, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)
