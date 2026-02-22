"""
🎵 تلاشاني ميوزك - Tlashani Music Bot
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
from pyrogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
USER_SESSION = os.getenv("USER_SESSION", "")
OWNER_ID     = int(os.getenv("OWNER_ID", "0"))

bot     = Client("tlashani_bot",     api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("tlashani_userbot", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION)
call_py = PyTgCalls(userbot)

queues:    dict[int, list] = {}
playing:   dict[int, dict] = {}
temp_dirs: dict[int, str]  = {}

BOT_NAME = "تلاشاني ميوزك 🎵"

# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════
def get_queue(chat_id):
    queues.setdefault(chat_id, [])
    return queues[chat_id]

def fmt_dur(sec):
    if not sec: return "?"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

def cleanup(chat_id):
    tmp = temp_dirs.pop(chat_id, None)
    if tmp and os.path.exists(tmp):
        shutil.rmtree(tmp, ignore_errors=True)

async def is_admin(client, chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status.name in ("OWNER", "ADMINISTRATOR")
    except:
        return False

def download_track(query):
    tmp = tempfile.mkdtemp()
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
        "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    }
    is_url = bool(re.match(r"https?://", query))
    targets = [query] if is_url else [f"scsearch1:{query}", f"ytsearch1:{query}"]
    for target in targets:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if not info: continue
                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries: continue
                    info = entries[0]
                files = os.listdir(tmp)
                if not files: continue
                path = os.path.join(tmp, files[0])
                if os.path.getsize(path) < 1000: continue
                return {
                    "title":    info.get("title", "Unknown"),
                    "file":     path,
                    "tmp":      tmp,
                    "duration": info.get("duration", 0),
                    "url":      info.get("webpage_url", ""),
                    "thumb":    info.get("thumbnail", ""),
                }
        except Exception as e:
            logger.warning(f"Failed '{target}': {e}")
    shutil.rmtree(tmp, ignore_errors=True)
    return None

async def play_track(chat_id, track):
    cleanup(chat_id)
    playing[chat_id]   = track
    temp_dirs[chat_id] = track["tmp"]
    await call_py.play(chat_id, MediaStream(track["file"], video_flags=MediaStream.Flags.IGNORE))
    logger.info(f"▶ Playing: {track['title']}")

async def next_track(chat_id):
    q = get_queue(chat_id)
    if q:
        await play_track(chat_id, q.pop(0))
    else:
        playing.pop(chat_id, None)
        cleanup(chat_id)
        try: await call_py.leave_call(chat_id)
        except: pass

# ══════════════════════════════════════════
# STREAM END
# ══════════════════════════════════════════
try:
    from pytgcalls import filters as tgf
    @call_py.on_update(tgf.stream_end)
    async def on_end(_, update):
        await next_track(update.chat_id)
except Exception as e:
    logger.warning(f"stream_end not registered: {e}")

# ══════════════════════════════════════════
# /start
# ══════════════════════════════════════════
@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    name = msg.from_user.first_name if msg.from_user else "صديقي"
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 الأوامر", callback_data="help"),
         InlineKeyboardButton("🎵 شغّل أغنية", switch_inline_query_current_chat="/play ")],
    ])
    await msg.reply_text(
        f"👋 أهلاً {name}!\n\n"
        f"🎵 **{BOT_NAME}**\n\n"
        "أنا بوت موسيقى احترافي — بشغّل في الـ Voice Chat.\n\n"
        "▶️ `/play <اسم>` — شغّل أغنية\n"
        "⏭️ `/skip` — تخطي\n"
        "⏹️ `/stop` — وقّف\n"
        "📋 `/queue` — القائمة\n"
        "🎵 `/now` — الشغّال دلوقتي\n"
        "🔇 `/mute @user` — ميوت\n"
        "🔊 `/unmute @user` — رفع ميوت\n"
        "👢 `/kick @user` — طرد\n"
        "🚫 `/ban @user` — حظر\n\n"
        "💡 مثال: `/play fairuz`",
        reply_markup=buttons
    )

@bot.on_callback_query(filters.regex("help"))
async def cb_help(_, query):
    await query.answer()
    await query.message.edit_text(
        f"📋 **أوامر {BOT_NAME}**\n\n"
        "🎵 **الموسيقى:**\n"
        "▶️ `/play <اسم أو رابط>` — شغّل\n"
        "⏭️ `/skip` — تخطي\n"
        "⏹️ `/stop` — وقّف وامسح القائمة\n"
        "📋 `/queue` — اعرض القائمة\n"
        "🎵 `/now` — الأغنية الحالية\n\n"
        "👮 **الإدارة (للأدمنز):**\n"
        "🔇 `/mute @user` — ميوت\n"
        "🔊 `/unmute @user` — رفع ميوت\n"
        "👢 `/kick @user` — طرد\n"
        "🚫 `/ban @user` — حظر\n"
        "✅ `/unban @user` — رفع حظر\n",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back")]])
    )

@bot.on_callback_query(filters.regex("back"))
async def cb_back(_, query):
    await query.answer()
    name = query.from_user.first_name if query.from_user else "صديقي"
    await query.message.edit_text(
        f"👋 أهلاً {name}!\n\n"
        f"🎵 **{BOT_NAME}**\n\n"
        "أنا بوت موسيقى — بشغّل في الـ Voice Chat.\n\n"
        "▶️ `/play <اسم>` — شغّل أغنية\n"
        "⏭️ `/skip` — تخطي\n"
        "⏹️ `/stop` — وقّف\n"
        "📋 `/queue` — القائمة\n"
        "🎵 `/now` — الشغّال دلوقتي\n\n"
        "💡 مثال: `/play fairuz`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 الأوامر", callback_data="help"),
             InlineKeyboardButton("🎵 شغّل أغنية", switch_inline_query_current_chat="/play ")],
        ])
    )

# ══════════════════════════════════════════
# /play
# ══════════════════════════════════════════
@bot.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("❌ اكتب اسم الأغنية!\n💡 مثال: `/play fairuz`")
        return
    query   = " ".join(msg.command[1:])
    chat_id = msg.chat.id
    status  = await msg.reply_text(f"🔍 بدور على: **{query}**...")
    try:
        track = await asyncio.get_running_loop().run_in_executor(None, download_track, query)
    except Exception as e:
        await status.edit_text(f"❌ خطأ: {e}")
        return
    if not track:
        await status.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return
    dur = fmt_dur(track["duration"])
    if playing.get(chat_id):
        get_queue(chat_id).append(track)
        pos = len(get_queue(chat_id))
        await status.edit_text(
            f"✅ **اتضافت للقائمة #{pos}**\n"
            f"🎵 {track['title']}\n⏱ {dur}"
        )
        return
    await status.edit_text(f"⬇️ جاري التحميل...\n🎵 **{track['title']}**")
    try:
        await play_track(chat_id, track)
        await status.edit_text(
            f"▶️ **شغّال دلوقتي!**\n"
            f"🎵 {track['title']}\n"
            f"⏱ {dur}\n"
            f"🔗 [المصدر]({track['url']})"
        )
    except Exception as e:
        err = str(e)
        tip = ""
        if "not participant" in err.lower():
            tip = "\n\n💡 أضف الحساب المساعد للجروب يدوياً"
        elif "forbidden" in err.lower():
            tip = "\n\n💡 سمح للأعضاء بالبث في الـ VC من إعدادات الجروب"
        elif "no active" in err.lower() or "not found" in err.lower():
            tip = "\n\n💡 افتح الـ Voice Chat في الجروب الأول"
        await status.edit_text(f"⚠️ مش قادر يشغل!\n\n`{err[:200]}`{tip}")
        cleanup(chat_id)
        playing.pop(chat_id, None)

# ══════════════════════════════════════════
# /skip /stop /queue /now
# ══════════════════════════════════════════
@bot.on_message(filters.command("skip"))
async def cmd_skip(_, msg: Message):
    if not playing.get(msg.chat.id):
        await msg.reply_text("❌ مفيش أغنية شغّالة!")
        return
    await msg.reply_text("⏭️ تخطي...")
    await next_track(msg.chat.id)

@bot.on_message(filters.command("stop"))
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)
    cleanup(chat_id)
    try: await call_py.leave_call(chat_id)
    except: pass
    await msg.reply_text("⏹️ تم الإيقاف!")

@bot.on_message(filters.command("queue"))
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    cur = playing.get(chat_id)
    q   = get_queue(chat_id)
    if not cur and not q:
        await msg.reply_text("📋 القائمة فاضية!")
        return
    lines = [f"📋 **قائمة تلاشاني ميوزك:**\n"]
    if cur:
        lines.append(f"▶️ **{cur['title']}** ← شغّال الآن")
    for i, t in enumerate(q, 1):
        lines.append(f"{i}. {t['title']} — {fmt_dur(t['duration'])}")
    await msg.reply_text("\n".join(lines))

@bot.on_message(filters.command("now"))
async def cmd_now(_, msg: Message):
    t = playing.get(msg.chat.id)
    if not t:
        await msg.reply_text("😶 مفيش أغنية شغّالة.")
        return
    await msg.reply_text(
        f"▶️ **شغّال دلوقتي:**\n"
        f"🎵 {t['title']}\n"
        f"⏱ {fmt_dur(t['duration'])}\n"
        f"🔗 [المصدر]({t['url']})"
    )

# ══════════════════════════════════════════
# إدارة الجروب
# ══════════════════════════════════════════
async def get_target(msg: Message):
    if msg.reply_to_message:
        return msg.reply_to_message.from_user
    if len(msg.command) > 1:
        try:
            return await msg.chat.get_member(msg.command[1])
        except:
            try:
                return await bot.get_users(msg.command[1].lstrip("@"))
            except:
                return None
    return None

@bot.on_message(filters.command("mute"))
async def cmd_mute(_, msg: Message):
    if not await is_admin(bot, msg.chat.id, msg.from_user.id):
        await msg.reply_text("❌ الأمر ده للأدمنز بس!")
        return
    target = await get_target(msg)
    if not target:
        await msg.reply_text("❌ مين اللي هتميوته؟")
        return
    try:
        await bot.restrict_chat_member(msg.chat.id, target.id, ChatPermissions())
        await msg.reply_text(f"🔇 تم ميوت **{target.first_name}**")
    except Exception as e:
        await msg.reply_text(f"❌ مش قادر: {e}")

@bot.on_message(filters.command("unmute"))
async def cmd_unmute(_, msg: Message):
    if not await is_admin(bot, msg.chat.id, msg.from_user.id):
        await msg.reply_text("❌ الأمر ده للأدمنز بس!")
        return
    target = await get_target(msg)
    if not target:
        await msg.reply_text("❌ مين؟")
        return
    try:
        await bot.restrict_chat_member(msg.chat.id, target.id, ChatPermissions(
            can_send_messages=True, can_send_media_messages=True,
            can_send_other_messages=True, can_add_web_page_previews=True
        ))
        await msg.reply_text(f"🔊 تم رفع ميوت **{target.first_name}**")
    except Exception as e:
        await msg.reply_text(f"❌ مش قادر: {e}")

@bot.on_message(filters.command("kick"))
async def cmd_kick(_, msg: Message):
    if not await is_admin(bot, msg.chat.id, msg.from_user.id):
        await msg.reply_text("❌ الأمر ده للأدمنز بس!")
        return
    target = await get_target(msg)
    if not target:
        await msg.reply_text("❌ مين؟")
        return
    try:
        await bot.ban_chat_member(msg.chat.id, target.id)
        await bot.unban_chat_member(msg.chat.id, target.id)
        await msg.reply_text(f"👢 تم طرد **{target.first_name}**")
    except Exception as e:
        await msg.reply_text(f"❌ مش قادر: {e}")

@bot.on_message(filters.command("ban"))
async def cmd_ban(_, msg: Message):
    if not await is_admin(bot, msg.chat.id, msg.from_user.id):
        await msg.reply_text("❌ الأمر ده للأدمنز بس!")
        return
    target = await get_target(msg)
    if not target:
        await msg.reply_text("❌ مين؟")
        return
    try:
        await bot.ban_chat_member(msg.chat.id, target.id)
        await msg.reply_text(f"🚫 تم حظر **{target.first_name}**")
    except Exception as e:
        await msg.reply_text(f"❌ مش قادر: {e}")

@bot.on_message(filters.command("unban"))
async def cmd_unban(_, msg: Message):
    if not await is_admin(bot, msg.chat.id, msg.from_user.id):
        await msg.reply_text("❌ الأمر ده للأدمنز بس!")
        return
    target = await get_target(msg)
    if not target:
        await msg.reply_text("❌ مين؟")
        return
    try:
        await bot.unban_chat_member(msg.chat.id, target.id)
        await msg.reply_text(f"✅ تم رفع حظر **{target.first_name}**")
    except Exception as e:
        await msg.reply_text(f"❌ مش قادر: {e}")

# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════
async def main():
    if not shutil.which("ffmpeg"):
        logger.info("Installing ffmpeg...")
        try:
            subprocess.run(["apt-get", "update", "-qq"], check=True, capture_output=True)
            subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], check=True, capture_output=True)
            logger.info("ffmpeg installed!")
        except Exception as e:
            logger.error(f"ffmpeg failed: {e}")
    else:
        logger.info("ffmpeg OK")

    await bot.start()
    logger.info("✅ Bot started")
    await userbot.start()
    logger.info("✅ Userbot started")
    await call_py.start()
    logger.info("✅ PyTgCalls started")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, stop.set)
        except: pass

    logger.info("🎵 تلاشاني ميوزك - Bot is running!")
    await stop.wait()

    await call_py.stop()
    await userbot.stop()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
