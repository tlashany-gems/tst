"""
🎵 Telegram Music Bot
"""

import asyncio
import os
import re
import logging
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


def search_song(query):
    # جرب YouTube أول، لو فشل جرب SoundCloud
    is_url = re.match(r"https?://", query)
    
    searches = []
    if is_url:
        searches = [query]
    else:
        searches = [
            f"scsearch1:{query}",   # SoundCloud أول
            f"ytsearch1:{query}",   # YouTube تاني
        ]

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 15,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        },
    }

    for search in searches:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search, download=False)
                if not info:
                    continue
                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        continue
                    info = entries[0]
                stream_url = None
                for fmt in reversed(info.get("formats", [])):
                    if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none":
                        stream_url = fmt.get("url")
                        break
                if not stream_url:
                    stream_url = info.get("url")
                if not stream_url:
                    continue
                return {
                    "title": info.get("title", "Unknown"),
                    "url": stream_url,
                    "duration": info.get("duration", 0),
                    "webpage": info.get("webpage_url", ""),
                    "source": info.get("extractor", ""),
                }
        except Exception as e:
            logger.warning(f"search failed for '{search}': {e}")
            continue
    return None


def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "صديقي"
    await update.message.reply_text(
        f"👋 أهلاً {name}!\n\n"
        "🎵 بوت الموسيقى جاهز!\n\n"
        "▶️ /play <اسم أو رابط> — شغّل\n"
        "⏹️ /stop — وقف\n"
        "📋 /queue — القائمة\n"
        "⏭️ /skip — تخطي\n"
        "🎵 /now — الشغال دلوقتي\n\n"
        "💡 مثال: /play Fairuz\n"
        "💡 أو: /play https://soundcloud.com/..."
    )


async def play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ اكتب اسم الأغنية!\nمثال: /play Fairuz")
        return
    query = " ".join(ctx.args)
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(f"🔍 بدور على: {query}...")

    try:
        track = await asyncio.get_running_loop().run_in_executor(None, search_song, query)
    except Exception as e:
        logger.error(f"play error: {e}")
        await msg.edit_text("❌ حصل error، جرب تاني!")
        return

    if not track:
        await msg.edit_text(
            "❌ مش قادر يجيب الأغنية دي!\n\n"
            "جرب:\n"
            "• اسم الأغنية بالعربي أو الإنجليزي\n"
            "• رابط SoundCloud مباشر"
        )
        return

    dur = fmt_duration(track["duration"])
    source_emoji = "🎵" if "soundcloud" in track.get("source","").lower() else "▶️"

    if playing.get(chat_id):
        queues.setdefault(chat_id, []).append(track)
        pos = len(queues[chat_id])
        await msg.edit_text(f"✅ اتضافت للقائمة #{pos}:\n🎵 {track['title']}\n⏱️ {dur}")
    else:
        playing[chat_id] = track
        await msg.edit_text(
            f"{source_emoji} بيشغل:\n"
            f"🎵 {track['title']}\n"
            f"⏱️ {dur}\n\n"
            f"🔗 {track['webpage']}",
        )
        logger.info(f"Now playing: {track['title']} ({track['source']})")


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


async def now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    track = playing.get(update.effective_chat.id)
    if not track:
        await update.message.reply_text("😶 مفيش أغنية شغالة.")
        return
    await update.message.reply_text(
        f"▶️ شغال دلوقتي:\n🎵 {track['title']}\n"
        f"⏱️ {fmt_duration(track['duration'])}\n"
        f"🔗 {track['webpage']}"
    )


def main():
    logger.info(f"🚀 Starting with token: {BOT_TOKEN[:10]}...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("now", now))
    logger.info("✅ Bot polling started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
