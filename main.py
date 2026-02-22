"""
🎵 Telegram Music Bot - python-telegram-bot
"""

import asyncio
import os
import re
import logging
import subprocess
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

queues:  dict[int, list] = {}
playing: dict[int, dict] = {}
procs:   dict[int, subprocess.Popen] = {}


def search_song(query):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": "/tmp/%(id)s.%(ext)s",
    }
    if not re.match(r"https?://", query):
        query = f"ytsearch1:{query}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if "entries" in info:
                info = info["entries"][0]
            filename = ydl.prepare_filename(info)
            return {
                "title": info.get("title", "Unknown"),
                "file": filename,
                "duration": info.get("duration", 0),
                "webpage": info.get("webpage_url", ""),
            }
    except Exception as e:
        logger.error(f"search error: {e}")
        return None


def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logger.info(f"✅ /start from {update.effective_user.id}")
    name = update.effective_user.first_name or "صديقي"
    await update.message.reply_text(
        f"👋 أهلاً {name}!\n\n"
        "🎵 بوت الموسيقى جاهز!\n\n"
        "▶️ /play <اسم> — شغّل\n"
        "⏹️ /stop — وقف\n"
        "📋 /queue — القائمة\n"
        "⏭️ /skip — تخطي\n\n"
        "💡 مثال: /play Fairuz"
    )


async def play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logger.info(f"✅ /play from {update.effective_chat.id}")
    if not ctx.args:
        await update.message.reply_text("❌ اكتب اسم الأغنية!\nمثال: /play Fairuz")
        return
    query = " ".join(ctx.args)
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(f"🔍 بدور على: {query}...")

    track = await asyncio.get_running_loop().run_in_executor(None, search_song, query)
    if not track:
        await msg.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return

    dur = fmt_duration(track["duration"])

    if playing.get(chat_id):
        queues.setdefault(chat_id, []).append(track)
        await msg.edit_text(f"✅ اتضافت للقائمة:\n🎵 {track['title']}\n⏱️ {dur}")
    else:
        playing[chat_id] = track
        await msg.edit_text(f"▶️ بيشغل:\n🎵 {track['title']}\n⏱️ {dur}")
        logger.info(f"Playing: {track['title']} | file: {track['file']}")


async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    playing.pop(chat_id, None)
    queues.pop(chat_id, None)
    await update.message.reply_text("⏹️ تم الإيقاف!")


async def skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not playing.get(chat_id):
        await update.message.reply_text("❌ مفيش أغنية!")
        return
    queue = queues.get(chat_id, [])
    if queue:
        next_track = queue.pop(0)
        playing[chat_id] = next_track
        dur = fmt_duration(next_track["duration"])
        await update.message.reply_text(f"⏭️ تخطي\n▶️ {next_track['title']}\n⏱️ {dur}")
    else:
        playing.pop(chat_id, None)
        await update.message.reply_text("⏭️ خلصت القائمة!")


async def queue_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current = playing.get(chat_id)
    queue = queues.get(chat_id, [])
    if not current and not queue:
        await update.message.reply_text("📋 القائمة فاضية!")
        return
    lines = ["📋 قائمة الانتظار:\n"]
    if current:
        lines.append(f"▶️ {current['title']} ← شغال")
    for i, t in enumerate(queue, 1):
        lines.append(f"{i}. {t['title']} — {fmt_duration(t['duration'])}")
    await update.message.reply_text("\n".join(lines))


def main():
    logger.info(f"🚀 Starting bot with token: {BOT_TOKEN[:10]}...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("queue", queue_cmd))
    logger.info("✅ Bot is running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
