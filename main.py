"""
Telegram Music Bot - Stable version with download-before-play
"""
import asyncio
import os
import re
import logging
import subprocess
import shutil
import tempfile
import signal
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import yt_dlp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
USER_SESSION = os.getenv("USER_SESSION", "")

bot     = Client("bot",     api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION)
call_py = PyTgCalls(userbot)

queues:     dict[int, list] = {}
playing:    dict[int, dict] = {}
temp_dirs:  dict[int, str]  = {}


def get_queue(chat_id: int) -> list:
    queues.setdefault(chat_id, [])
    return queues[chat_id]


def fmt_duration(seconds) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def cleanup_temp(chat_id: int):
    tmp = temp_dirs.pop(chat_id, None)
    if tmp and os.path.exists(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
        logger.info(f"Cleaned temp: {tmp}")


def download_audio(query: str) -> dict | None:
    tmp_dir = tempfile.mkdtemp()
    out_tpl  = os.path.join(tmp_dir, "audio.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_tpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    }

    is_url  = bool(re.match(r"https?://", query))
    targets = [query] if is_url else [f"scsearch1:{query}", f"ytsearch1:{query}"]

    for target in targets:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if not info:
                    continue
                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        continue
                    info = entries[0]

                # ابحث عن الملف بأي امتداد
                audio_path = None
                for f in os.listdir(tmp_dir):
                    audio_path = os.path.join(tmp_dir, f)
                    break

                if not audio_path or not os.path.exists(audio_path):
                    logger.warning(f"No file found in {tmp_dir}")
                    continue

                size = os.path.getsize(audio_path)
                logger.info(f"Downloaded OK: {audio_path} ({size} bytes)")

                if size < 1000:
                    logger.warning("File too small, skipping")
                    continue

                return {
                    "title":     info.get("title", "Unknown"),
                    "file_path": audio_path,
                    "tmp_dir":   tmp_dir,
                    "duration":  info.get("duration", 0),
                    "webpage":   info.get("webpage_url", ""),
                }
        except Exception as e:
            logger.warning(f"Failed '{target}': {e}")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    return None


async def play_in_vc(chat_id: int, track: dict):
    cleanup_temp(chat_id)
    playing[chat_id]   = track
    temp_dirs[chat_id] = track["tmp_dir"]
    stream = MediaStream(track["file_path"], video_flags=MediaStream.Flags.IGNORE)
    await call_py.play(chat_id, stream)
    logger.info(f"Playing: {track['title']}")


async def play_next(chat_id: int):
    queue = get_queue(chat_id)
    if queue:
        await play_in_vc(chat_id, queue.pop(0))
    else:
        playing.pop(chat_id, None)
        cleanup_temp(chat_id)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass


# ══════════════════════════════════════════
# STREAM END HANDLER
# ══════════════════════════════════════════
try:
    from pytgcalls import filters as tgf

    @call_py.on_update(tgf.stream_end)
    async def on_stream_end(_, update):
        await play_next(update.chat_id)

except Exception as e:
    logger.warning(f"stream_end handler not registered: {e}")


# ══════════════════════════════════════════
# BOT COMMANDS
# ══════════════════════════════════════════
@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    name = msg.from_user.first_name if msg.from_user else "صديقي"
    await msg.reply_text(
        f"👋 أهلاً {name}!\n\n"
        "🎵 بوت الموسيقى جاهز!\n\n"
        "▶️ /play <اسم أو رابط>\n"
        "⏭️ /skip\n"
        "⏹️ /stop\n"
        "📋 /queue\n"
        "🎵 /now"
    )


@bot.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("❌ اكتب اسم الأغنية!\nمثال: /play fairuz")
        return

    query   = " ".join(msg.command[1:])
    chat_id = msg.chat.id
    status  = await msg.reply_text(f"🔍 بدور على: {query}...")

    try:
        track = await asyncio.get_running_loop().run_in_executor(
            None, download_audio, query
        )
    except Exception as e:
        logger.error(f"Executor error: {e}")
        await status.edit_text(f"❌ خطأ أثناء البحث:\n{e}")
        return

    if not track:
        await status.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return

    dur = fmt_duration(track["duration"])

    if playing.get(chat_id):
        get_queue(chat_id).append(track)
        pos = len(get_queue(chat_id))
        await status.edit_text(
            f"✅ اتضافت للقائمة #{pos}\n🎵 {track['title']}\n⏱ {dur}"
        )
        return

    await status.edit_text(f"⬇️ جاري التحميل...\n🎵 {track['title']}")

    try:
        await play_in_vc(chat_id, track)
        await status.edit_text(
            f"▶️ شغال دلوقتي!\n🎵 {track['title']}\n⏱ {dur}"
        )
    except Exception as e:
        logger.error(f"VC error: {e}")
        err = str(e)
        tip = ""
        if "not participant" in err.lower():
            tip = "\n\n💡 الحساب المساعد مش في الجروب — أضفه يدوياً"
        elif "forbidden" in err.lower():
            tip = "\n\n💡 غيّر إعدادات الجروب: سمح لكل الأعضاء بالبث في الـ VC"
        elif "no active" in err.lower() or "not found" in err.lower():
            tip = "\n\n💡 افتح الـ Voice Chat في الجروب الأول"
        await status.edit_text(
            f"⚠️ مش قادر يشغل في الـ VC\n🎵 {track['title']}\n\n"
            f"Error: {err[:200]}{tip}"
        )
        cleanup_temp(chat_id)
        playing.pop(chat_id, None)


@bot.on_message(filters.command("skip"))
async def cmd_skip(_, msg: Message):
    if not playing.get(msg.chat.id):
        await msg.reply_text("❌ مفيش أغنية شغالة!")
        return
    await msg.reply_text("⏭️ تخطي...")
    await play_next(msg.chat.id)


@bot.on_message(filters.command("stop"))
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)
    cleanup_temp(chat_id)
    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass
    await msg.reply_text("⏹️ تم الإيقاف!")


@bot.on_message(filters.command("queue"))
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    current = playing.get(chat_id)
    queue   = get_queue(chat_id)
    if not current and not queue:
        await msg.reply_text("📋 القائمة فاضية!")
        return
    lines = ["📋 قائمة الانتظار:\n"]
    if current:
        lines.append(f"▶️ {current['title']} ← شغال")
    for i, t in enumerate(queue, 1):
        lines.append(f"{i}. {t['title']} — {fmt_duration(t['duration'])}")
    await msg.reply_text("\n".join(lines))


@bot.on_message(filters.command("now"))
async def cmd_now(_, msg: Message):
    track = playing.get(msg.chat.id)
    if not track:
        await msg.reply_text("😶 مفيش أغنية شغالة.")
        return
    await msg.reply_text(
        f"▶️ شغال دلوقتي:\n🎵 {track['title']}\n"
        f"⏱ {fmt_duration(track['duration'])}\n🔗 {track['webpage']}"
    )


# ══════════════════════════════════════════
# MAIN — keep-alive loop بدل idle()
# ══════════════════════════════════════════
async def main():
    # تثبيت ffmpeg لو مش موجود
    if not shutil.which("ffmpeg"):
        logger.info("Installing ffmpeg...")
        try:
            subprocess.run(["apt-get", "update",  "-qq"], check=True, capture_output=True)
            subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"],
                           check=True, capture_output=True)
            logger.info("ffmpeg installed!")
        except Exception as e:
            logger.error(f"ffmpeg install failed: {e}")
    else:
        logger.info("ffmpeg OK")

    await bot.start()
    logger.info("Bot started")

    await userbot.start()
    logger.info("Userbot started")

    await call_py.start()
    logger.info("PyTgCalls started - ready!")

    # ✅ keep-alive loop — بيخلي البوت يفضل شغال للأبد
    stop_event = asyncio.Event()

    def _stop(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except Exception:
            pass

    logger.info("Bot is running... press Ctrl+C to stop")
    await stop_event.wait()

    logger.info("Shutting down...")
    await call_py.stop()
    await userbot.stop()
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
