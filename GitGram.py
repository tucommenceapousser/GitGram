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
import tempfile


# telegram v20+
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# --- Logging
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # ~50 MB
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Config (ENV or config.py fallback)
ENV = bool(os.environ.get("ENV", False))
if ENV:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    PROJECT_NAME = os.environ.get("PROJECT_NAME", "TrknGitGram")
    ip_addr = os.environ.get("APP_URL", None)
    GIT_REPO_URL = os.environ.get(
        "GIT_REPO_URL", "https://github.com/tucommenceapousser/GitGram"
    )
else:
    try:
        import config  # type: ignore
        BOT_TOKEN = getattr(config, "BOT_TOKEN", None)
        PROJECT_NAME = getattr(config, "PROJECT_NAME", "TrknGitGram")
        ip_addr = None
        GIT_REPO_URL = getattr(
            config, "GIT_REPO_URL", "https://github.com/tucommenceapousser/GitGram"
        )
    except Exception:
        BOT_TOKEN = None
        PROJECT_NAME = "TrknGitGram"
        ip_addr = None
        GIT_REPO_URL = "https://github.com/tucommenceapousser/GitGram"

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
        f"This is the Updates watcher for {PROJECT_NAME}. I notify users about Git repository updates via webhooks.\n\n"
        "Use /help to see available commands.",
        parse_mode="Markdown",
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return

    video_url = "https://c.top4top.io/m_3566qycjx1.mp4"
    help_text = (
        "😈 *TrknGitGram Bot - Help Menu*\n"
        "🙈🙉🙊 Maintained by *trhacknon*\n\n"
        "💡 *Available Commands:*\n"
        "🔗 `/connect` - Setup this chat to receive Git repository notifications.\n"
        "🛠️ `/support` - Get support links if you get stuck.\n"
        "📂 `/source` - Get the Git repository URL.\n\n"
        "⚡ _Tip: Self-host the bot to receive notifications in your groups._\n\n"
        "🚀 Enjoy tracking your Git updates like a hacker!"
    )

    await msg.reply_text(help_text, parse_mode="Markdown")


async def vid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return

    video_url = "https://c.top4top.io/m_3566qycjx1.mp4"
    caption = "🎬 Tutoriel GitGram - by trhacknon"

    # 1) Essayer d'envoyer directement l'URL (Telegram se charge de récupérer le fichier)
    try:
        await msg.reply_video(video_url, caption=caption, timeout=120)
        return
    except Exception as e:
        log.warning("reply_video(video_url) a échoué, fallback. Erreur: %s", e)

    # 2) Envoyer d'abord un message avec le lien (fallback simple, toujours utile)
    try:
        await msg.reply_text(f"Impossible d'envoyer la vidéo directement. Voici le lien :\n{video_url}")
    except Exception:
        # ignore
        pass

    # 3) Tenter de télécharger la vidéo côté bot si elle n'est pas trop grosse, puis l'envoyer
    try:
        # HEAD pour obtenir content-length si disponible
        head = requests.head(video_url, allow_redirects=True, timeout=10)
        content_length = int(head.headers.get("content-length", 0))
    except Exception:
        content_length = 0

    if content_length and content_length > MAX_UPLOAD_BYTES:
        await msg.reply_text("La vidéo dépasse la taille maximale autorisée pour l'upload via le bot. Utilisez un hébergement (YouTube/CDN) et envoyez le lien.")
        return

    # Si la taille est inconnue, on peut tenter le téléchargement mais avec précaution
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp_path = tmp.name
        tmp.close()

        with requests.get(video_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = 0
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise RuntimeError("Fichier trop volumineux pendant le téléchargement")

        # envoyer le fichier téléchargé
        try:
            await msg.reply_video(InputFile(tmp_path), caption=caption, timeout=120)
            return
        finally:
            # cleanup
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    except Exception as e:
        log.exception("Échec du téléchargement/envoi local de la vidéo: %s", e)
        try:
            await msg.reply_text(f"Impossible d'envoyer la vidéo (erreur: {e}). Voici le lien direct :\n{video_url}")
        except Exception:
            pass
            
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(
        f"*Getting Support*\n\nTo get support in using the bot, join [the {PROJECT_NAME} support](https://t.me/trhacknonsBot).",
        parse_mode="markdown",
    )

async def source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message or update.message
    if not msg:
        return
    await msg.reply_text(f"*Source*:\n[Trhacknon GitGram Repo]({GIT_REPO_URL}). ", parse_mode="Markdown")

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

    # Assets fournis
    logo_url = "https://f.top4top.io/p_3566y9txm0.jpg"
    video_url = "https://c.top4top.io/m_3566qycjx1.mp4"

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width,initial-scale=1" />
      <title>GitGram — {escape(bot_username)}</title>
      <style>
        :root{{
          --bg:#050507;
          --panel:#0b0b0d;
          --neon-green:#00ff99;
          --neon-pink:#ff00dd;
          --cyan:#00ffff;
          --muted:#9aa3a1;
        }}
        html,body{{height:100%;margin:0;background:linear-gradient(180deg,#020203 0%, #071018 100%);font-family:Inter, "Courier New", monospace;color:var(--neon-green);}}
        .wrap{{max-width:1100px;margin:40px auto;padding:28px;border-radius:12px;background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));box-shadow: 0 8px 40px rgba(0,0,0,0.7);border:1px solid rgba(0,255,153,0.06);display:grid;grid-template-columns:320px 1fr;gap:24px;align-items:start}}
        .left{{padding:18px;border-radius:10px;background:linear-gradient(90deg, rgba(0,0,0,0.25), rgba(255,255,255,0.02));backdrop-filter: blur(4px);}}
        .logo{{width:100%;border-radius:8px;border:2px solid rgba(255,0,153,0.06);box-shadow:0 6px 20px rgba(0,255,153,0.06) inset;}}
        h1{{
          font-size:28px;margin:12px 0 4px;color:var(--neon-green);text-shadow:0 0 10px rgba(0,255,153,0.12), 0 0 24px rgba(0,255,153,0.06);
          display:flex;gap:10px;align-items:center;justify-content:flex-start;
        }}
        .tag{{font-size:14px;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,0.02);color:var(--muted);border:1px solid rgba(255,255,255,0.02)}}
        p.lead{{color:var(--cyan);margin:8px 0 14px;line-height:1.4}}
        .btn{{display:inline-block;padding:10px 14px;border-radius:8px;background:transparent;border:1px solid rgba(255,255,255,0.06);color:var(--neon-pink);text-decoration:none;font-weight:600;cursor:pointer;box-shadow:0 6px 30px rgba(255,0,153,0.02)}}
        .copy-btn{{margin-left:8px;padding:6px 10px;font-size:13px}}
        .meta{{font-size:13px;color:var(--muted);margin-top:8px}}
        .right{{padding:18px;border-radius:10px; background:linear-gradient(90deg, rgba(255,255,255,0.01), rgba(0,0,0,0.2));}}
        section.card{{
          background:linear-gradient(180deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00));
          border-radius:10px;padding:14px;margin-bottom:14px;border:1px solid rgba(0,255,153,0.03)
        }}
        h3{{margin:0 0 8px;color:var(--neon-pink);text-shadow:0 0 6px rgba(255,0,221,0.04)}}
        ul{{padding-left:18px;margin:6px 0;color:var(--muted)}}
        code{{background:rgba(0,0,0,0.25);padding:4px 6px;border-radius:6px;color:var(--cyan)}}

        /* video */
        .video-wrap{{display:flex;flex-direction:column;gap:8px;align-items:center}}
        video{{width:100%;max-width:640px;border-radius:10px;box-shadow:0 12px 48px rgba(0,0,0,0.6);border:1px solid rgba(255,255,255,0.02)}}

        /* footer */
        footer{{text-align:center;margin-top:18px;color:var(--muted);font-size:13px}}

        /* subtle animated scanline */
        .scanline::after{content:"";position:absolute;left:0;right:0;top:0;height:100%;background:linear-gradient(0deg, transparent, rgba(0,255,153,0.02), transparent);pointer-events:none;mix-blend-mode:overlay;animation:scan 6s linear infinite}
        @keyframes scan{{0%{{transform:translateY(-100%)}}100%{{transform:translateY(100%)}}}}

        /* responsive */
        @media (max-width:880px){{.wrap{{grid-template-columns:1fr; padding:18px}} .left{order:2}}}
      </style>
    </head>
    <body>
      <div style="position:relative" class="scanline">
        <div class="wrap">
          <div class="left">
            <img src="{logo_url}" alt="logo" class="logo" />
            <h1>
              <span style="font-family:system-ui,Segoe UI,Roboto,monospace">{escape(bot_username)}</span>
              <span class="tag">GitGram</span>
            </h1>
            <div class="meta">By <strong style="color:var(--neon-pink)">trhacknon</strong> — esprit hacking / anonymous</div>
            <p class="lead">Un outil léger pour notifier vos groupes Telegram des événements Git (commits, issues, PR, releases) via webhooks. Self‑host, configure, et surveille.</p>

            <div style="margin-top:10px">
              <button class="btn copy-btn" onclick="copyBot()">📋 Copier le nom du bot</button>
              <a class="btn" href="{GIT_REPO_URL}" target="_blank">🔗 Source</a>
              <a class="btn" href="https://t.me/GitGramChat" target="_blank">💬 Support</a>
            </div>

            <div style="margin-top:14px;font-size:13px;color:var(--muted)">
              <div>Token: <code>env:BOT_TOKEN</code></div>
              <div style="margin-top:6px">Example webhook URL:</div>
              <div style="font-size:13px;color:var(--cyan)"> <code>{escape(ip_addr or 'https://your.domain')}/&lt;chat_id&gt;</code> </div>
            </div>
          </div>

          <div class="right">
            <section class="card">
              <h3>À propos</h3>
              <p style="color:var(--muted);margin:6px 0 0">
                GitGram relaie automatiquement les activités GitHub/GitLab vers Telegram. Idéal pour les équipes, channels et pour garder un œil sur les dépôts. Conçu par <strong>trhacknon</strong>.
              </p>
            </section>

            <section class="card">
              <h3>Fonctionnalités</h3>
              <ul>
                <li>🔔 Notifications pour commits, issues, PR, releases</li>
                <li>🛡️ Self‑host & privacy friendly</li>
                <li>⚡ Simple à configurer (webhook → /&lt;chat_id&gt;)</li>
                <li>🎛️ Compatible avec Telegram bots modernes (async)</li>
              </ul>
            </section>

            <section class="card video-wrap">
              <h3>Vidéo d'installation</h3>
              <video controls poster="{logo_url}">
                <source src="{video_url}" type="video/mp4">
                Ton navigateur ne supporte pas la balise vidéo. Voici le lien direct : <a href="{video_url}" target="_blank">Voir la vidéo</a>
              </video>
              <div style="color:var(--muted);font-size:13px;margin-top:8px">Tutoriel rapide pour déployer et configurer (par trhacknon)</div>
            </section>

            <section class="card">
              <h3>Commandes utiles</h3>
              <ul>
                <li><code>/start</code> — Démarrer le bot</li>
                <li><code>/help</code> — Menu d'aide (incl. tutoriel vidéo)</li>
                <li><code>/support</code> — Lien support & tutoriel</li>
                <li><code>/source</code> — Lien vers le repo</li>
              </ul>
            </section>

            <footer>
              <div>© {escape(PROJECT_NAME)} — Maintenu par <strong style="color:var(--neon-pink)">trhacknon</strong></div>
              <div style="margin-top:6px;color:var(--muted)">Ne partagez jamais votre <code>BOT_TOKEN</code> publiquement.</div>
            </footer>
          </div>
        </div>
      </div>

      <script>
        function copyBot(){ 
          const text = "{escape(bot_username)}";
          navigator.clipboard?.writeText(text).then(()=>{ alert("Nom du bot copié: " + text); }, ()=>{ prompt("Copier manuellement:", text); });
        }
      </script>
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

    # --- Webhook event handling
    # Commits
    if data.get("commits"):
        commits_text = ""
        rng = min(len(data["commits"]), 10)
        for x in range(rng):
            commit = data["commits"][x]
            msg_raw = commit.get("message", "")
            commit_msg = _escape_text(msg_raw.split("\n")[0] if len(msg_raw) > 300 else msg_raw)
            commits_text += f"{commit_msg}\n<a href='{commit['url']}'>{commit['id'][:7]}</a> - {_escape_text(commit['author']['name'])}\n\n"
        text = f"✨ <b>{_escape_text(data['repository']['name'])}</b> - New {len(data['commits'])} commits\n{commits_text}"
        if len(data["commits"]) > 10:
            text += f"\n<i>And {len(data['commits']) - 10} other commits</i>"
        return jsonify(post_tg(groupid, text, "HTML"))

    # Issues and comments
    if data.get("issue"):
        if data.get("comment"):
            text = f"💬 New comment: <b>{_escape_text(data['repository']['name'])}</b>\n{_escape_text(data['comment']['body'])}\n<a href='{data['comment']['html_url']}'>Issue #{data['issue']['number']}</a>"
        else:
            text = f"🚨 New {data.get('action', '')} issue for <b>{_escape_text(data['repository']['name'])}</b>\n<b>{_escape_text(data['issue']['title'])}</b>\n{_escape_text(data['issue']['body'])}\n<a href='{data['issue']['html_url']}'>Issue #{data['issue']['number']}</a>"
        return jsonify(post_tg(groupid, text, "HTML"))

    # Pull Requests
    if data.get("pull_request"):
        if data.get("comment"):
            text = f"❗ New comment on PR: {_escape_text(data['comment']['body'])}\n<a href='{data['comment']['html_url']}'>Pull Request</a>"
        else:
            pr = data["pull_request"]
            text = f"❗ New {data.get('action', '')} pull request for <b>{_escape_text(data['repository']['name'])}</b>\n<b>{_escape_text(pr.get('title',''))}</b> ({pr.get('state','')})\n{_escape_text(pr.get('body',''))}\n<a href='{pr['html_url']}'>Pull Request #{pr.get('number','')}</a>"
        return jsonify(post_tg(groupid, text, "HTML"))

    # Forks
    if data.get("forkee"):
        text = f"🍴 <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> forked <a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a>! Total forks: {data['repository'].get('forks_count', 0)}"
        return jsonify(post_tg(groupid, text, "HTML"))

    # Releases and stars
    if data.get("action") and data.get("release") or data.get("action") in ["published","started","edited"]:
        action = data.get("action")
        if action == "published":
            text = f"<a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> published release <b>{_escape_text(data['release'].get('name',''))}</b> ({_escape_text(data['release'].get('tag_name',''))})\n<a href='{data['release'].get('tarball_url','')}'>Tar</a> | <a href='{data['release'].get('zipball_url','')}'>Zip</a>"
        elif action == "started":
            text = f"🌟 <a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> starred <a href='{data['repository']['html_url']}'>{_escape_text(data['repository']['name'])}</a>! Total stars: {data['repository'].get('stargazers_count',0)}"
        else:
            text = f"<a href='{data['sender']['html_url']}'>{_escape_text(data['sender']['login'])}</a> {action} release <b>{_escape_text(data['release'].get('name',''))}</b>"
        return jsonify(post_tg(groupid, text, "HTML"))

    # Fallback: unknown event
    url = deldog(data)
    fallback_text = f"🚫 Unknown webhook event received.\nDebug: {url}"
    return jsonify(post_tg(groupid, fallback_text, "Markdown"))

# --- del.dog helper
def deldog(data) -> str:
    BASE_URL = "https://del.dog"
    try:
        r = requests.post(f"{BASE_URL}/documents", data=str(data).encode("utf-8"), timeout=15)
        r.raise_for_status()
        res = r.json()
    except Exception as e:
        log.exception("Failed to upload to del.dog")
        return f"Failed to upload to del.dog: {e}"
    key = res.get("key","")
    return f"{BASE_URL}/{key}" if key else f"{BASE_URL}/"

# --- Bot thread
def start_bot_in_thread():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN is not set. Exiting bot start.")
        return

    try:
        r = requests.get(TG_BOT_API + "getMe", timeout=10).json()
        if not r.get("ok"):
            log.error("[ERROR] Invalid Token!")
            return
        username = r["result"]["username"]
        log.info(f"[INFO] Logged in as @{username}, starting bot...")
    except Exception:
        log.exception("Failed to contact Telegram API")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("vid", vid_cmd))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("source", source))
    app.run_polling(stop_signals=None)

if __name__ == "__main__":
    t = threading.Thread(target=start_bot_in_thread, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)
