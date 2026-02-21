"""
╔══════════════════════════════════════════════╗
║        تيلثون تـلـاشـاني - بوت الموسيقى      ║
║         Telethon TALASHNY Music Bot v3       ║
╚══════════════════════════════════════════════╝
البوت يستقبل الأوامر — الحساب المساعد للصوت فقط
pytgcalls >= 2.2.x API
"""

import os, asyncio, logging, glob, re

from pyrogram import Client as PyroClient
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types.stream import AudioQuality

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    ContextTypes, CallbackQueryHandler
)

import yt_dlp
import googleapiclient.discovery

from config import (
    BOT_TOKEN, ASSISTANT_API_ID, ASSISTANT_API_HASH,
    SESSION_STRING, YOUTUBE_API_KEY
)

# ══════════════════════════════════════════════════
# إعداد
# ══════════════════════════════════════════════════
os.makedirs("logs", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════
# YouTube
# ══════════════════════════════════════════════════
youtube = googleapiclient.discovery.build(
    "youtube", "v3", developerKey=YOUTUBE_API_KEY
)

def _parse_duration(iso: str) -> str:
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso)
    if not m: return "?"
    h, mn, s = (int(x) if x else 0 for x in m.groups())
    return f"{h}:{mn:02d}:{s:02d}" if h else f"{mn}:{s:02d}"

async def search_youtube(query: str):
    req = youtube.search().list(part="snippet", q=query, type="video",
                                maxResults=1, videoCategoryId="10")
    res = req.execute()
    if not res.get("items"):
        raise Exception("مفيش نتايج!")
    item   = res["items"][0]
    vid_id = item["id"]["videoId"]
    title  = item["snippet"]["title"]
    det    = youtube.videos().list(part="contentDetails", id=vid_id).execute()
    dur    = _parse_duration(det["items"][0]["contentDetails"]["duration"]) if det.get("items") else "؟"
    return f"https://www.youtube.com/watch?v={vid_id}", title, dur

async def get_video_info(url: str):
    try:
        vid_id = url.split("v=")[1].split("&")[0] if "v=" in url else url.split("/")[-1]
        res    = youtube.videos().list(part="snippet,contentDetails", id=vid_id).execute()
        if res.get("items"):
            item = res["items"][0]
            return item["snippet"]["title"], _parse_duration(item["contentDetails"]["duration"])
    except Exception as e:
        logger.error(f"get_video_info: {e}")
    return "غير معروف", "؟"

async def download_audio(url: str, chat_id: int) -> str:
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": f"downloads/{chat_id}_%(id)s.%(ext)s",
        "quiet": True, "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3", "preferredquality": "192"}],
    }
    def _dl():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info   = ydl.extract_info(url, download=True)
            vid_id = info.get("id", "")
            p      = f"downloads/{chat_id}_{vid_id}.mp3"
            if os.path.exists(p): return p
            files  = glob.glob(f"downloads/{chat_id}_{vid_id}*")
            if files: return files[0]
            raise FileNotFoundError("الملف مش موجود")
    return await asyncio.get_event_loop().run_in_executor(None, _dl)

def cleanup_downloads(chat_id: int):
    for f in glob.glob(f"downloads/{chat_id}_*"):
        try: os.remove(f)
        except: pass

# ══════════════════════════════════════════════════
# مشغّل الموسيقى
# ══════════════════════════════════════════════════
music_players: dict = {}

def get_player(chat_id: int) -> dict:
    if chat_id not in music_players:
        music_players[chat_id] = {"queue": [], "current": None,
                                  "loop": False, "history": []}
    return music_players[chat_id]

# ══════════════════════════════════════════════════
# الحساب المساعد — pytgcalls 2.2.x
# ══════════════════════════════════════════════════
pyro_client: PyroClient = None
pytgcalls:   PyTgCalls  = None
bot_app = None

async def setup_assistant():
    global pyro_client, pytgcalls

    pyro_client = PyroClient(
        name="assistant",
        api_id=ASSISTANT_API_ID,
        api_hash=ASSISTANT_API_HASH,
        session_string=SESSION_STRING,
        no_updates=True
    )
    pytgcalls = PyTgCalls(pyro_client)

    @pytgcalls.on_stream_end()
    async def on_stream_end(client, update):
        cid    = update.chat_id
        player = get_player(cid)

        if player["loop"] and player["current"]:
            try:
                await pytgcalls.change_stream(
                    cid,
                    MediaStream(player["current"]["file"],
                                audio_quality=AudioQuality.HIGH)
                )
            except Exception as e: logger.error(f"loop: {e}")
            return

        if player["current"]:
            player["history"].append(player["current"])
        if player["queue"]:
            player["queue"].pop(0)

        if player["queue"]:
            nxt = player["queue"][0]
            player["current"] = nxt
            try:
                await pytgcalls.change_stream(
                    cid,
                    MediaStream(nxt["file"], audio_quality=AudioQuality.HIGH)
                )
                if bot_app:
                    await bot_app.bot.send_message(
                        cid,
                        f"🎵 *بيشتغل دلوقتي:*\n━━━━━━━━━━━━━━━\n"
                        f"🎧 {nxt['title']}\n⏱ {nxt['duration']}\n"
                        f"📋 باقي: {len(player['queue'])-1} أغنية",
                        parse_mode="Markdown", reply_markup=_now_kb()
                    )
            except Exception as e: logger.error(f"auto-play: {e}")
        else:
            player["current"] = None
            try:
                await pytgcalls.leave_group_call(cid)
                cleanup_downloads(cid)
                if bot_app: await bot_app.bot.send_message(cid, "⏹ خلصت القايمة!")
            except: pass

    await pyro_client.start()
    await pytgcalls.start()
    me = await pyro_client.get_me()
    logger.info(f"✅ الحساب المساعد: {me.first_name} (@{me.username})")
    print(f"✅ الحساب المساعد: {me.first_name} (@{me.username})")

# ══════════════════════════════════════════════════
# أزرار التحكم
# ══════════════════════════════════════════════════
def _now_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏮ السابقة", callback_data="prev"),
         InlineKeyboardButton("⏸ وقّف",    callback_data="pause"),
         InlineKeyboardButton("⏭ التالية", callback_data="skip")],
        [InlineKeyboardButton("🔁 تكرار",      callback_data="loop"),
         InlineKeyboardButton("⏹ إيقاف كلي", callback_data="stop")],
        [InlineKeyboardButton("📋 القايمة", callback_data="queue"),
         InlineKeyboardButton("🎵 الحالية", callback_data="now")]
    ])

def _paused_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏮ السابقة",  callback_data="prev"),
         InlineKeyboardButton("▶️ كمّل",    callback_data="resume"),
         InlineKeyboardButton("⏭ التالية", callback_data="skip")],
        [InlineKeyboardButton("🔁 تكرار",      callback_data="loop"),
         InlineKeyboardButton("⏹ إيقاف كلي", callback_data="stop")],
        [InlineKeyboardButton("📋 القايمة", callback_data="queue"),
         InlineKeyboardButton("🎵 الحالية", callback_data="now")]
    ])

# ══════════════════════════════════════════════════
# أوامر البوت
# ══════════════════════════════════════════════════
async def cmd_start(u: Update, _):
    await u.message.reply_text(
        "🎵 *أهلاً بك في تيلثون تـلـاشـاني!* 🎧\n\n"
        "📌 *الأوامر الأساسية:*\n"
        "  `/play <اسم أو رابط>` — شغّل أغنية\n"
        "  `/pause` — وقّف مؤقتاً ⏸\n"
        "  `/resume` — كمّل ▶️\n"
        "  `/skip` — التالية ⏭\n"
        "  `/prev` — السابقة ⏮\n"
        "  `/stop` — وقّف كل شيء ⏹\n"
        "  `/queue` — القايمة 📋\n"
        "  `/now` — الأغنية الحالية 🎵\n"
        "  `/loop` — تكرار 🔁\n"
        "  `/vcstart` — افتح الدردشة الصوتية 🎙\n"
        "  `/vcend` — اقفل الدردشة الصوتية 📴\n"
        "  `/help` — كل الأوامر\n",
        parse_mode="Markdown"
    )

async def cmd_play(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = u.effective_chat.id
    query   = " ".join(ctx.args).strip() if ctx.args else ""
    if not query and u.message.reply_to_message:
        query = (u.message.reply_to_message.text or "").strip()
    if not query:
        await u.message.reply_text("⚠️ استخدم: `/play <اسم أو رابط>`", parse_mode="Markdown")
        return

    msg = await u.message.reply_text("🔍 جاري البحث...")
    try:
        is_url = "youtube.com" in query or "youtu.be" in query
        if is_url:
            title, dur = await get_video_info(query)
            url = query
        else:
            url, title, dur = await search_youtube(query)

        await msg.edit_text(f"⬇️ جاري التحميل:\n🎧 *{title}*...", parse_mode="Markdown")
        file_path = await download_audio(url, chat_id)
        player    = get_player(chat_id)
        requester = u.effective_user.first_name
        track     = {"title": title, "duration": dur, "url": url,
                     "file": file_path, "requested_by": requester}

        if player["current"] is None:
            player["queue"].append(track)
            player["current"] = track
            stream = MediaStream(file_path, audio_quality=AudioQuality.HIGH)
            try:
                await pytgcalls.join_group_call(chat_id, stream)
            except Exception:
                try: await pytgcalls.change_stream(chat_id, stream)
                except Exception as e2:
                    await msg.edit_text(
                        f"❌ فشل التشغيل: {e2}\n"
                        "افتح الدردشة الصوتية أو استخدم /vcstart"
                    )
                    return
            await msg.edit_text(
                f"🎵 *بيشتغل دلوقتي:*\n━━━━━━━━━━━━━━━\n"
                f"🎧 {title}\n⏱ المدة: {dur}\n"
                f"👤 طلب: {requester}\n📋 القايمة: {len(player['queue'])} أغنية",
                parse_mode="Markdown", reply_markup=_now_kb()
            )
        else:
            player["queue"].append(track)
            await msg.edit_text(
                f"✅ *تمت الإضافة للقايمة!*\n━━━━━━━━━━━━━━━\n"
                f"🎧 {title}\n⏱ {dur}\n"
                f"📍 الترتيب: #{len(player['queue'])}\n👤 طلب: {requester}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"cmd_play: {e}")
        await msg.edit_text(f"❌ حصل خطأ: {e}")

async def cmd_pause(u: Update, _):
    try:
        await pytgcalls.pause_stream(u.effective_chat.id)
        await u.message.reply_text("⏸ تم الإيقاف المؤقت", reply_markup=_paused_kb())
    except Exception as e: await u.message.reply_text(f"❌ {e}")

async def cmd_resume(u: Update, _):
    try:
        await pytgcalls.resume_stream(u.effective_chat.id)
        await u.message.reply_text("▶️ تم الاستئناف", reply_markup=_now_kb())
    except Exception as e: await u.message.reply_text(f"❌ {e}")

async def cmd_skip(u: Update, _):
    chat_id = u.effective_chat.id
    player  = get_player(chat_id)
    try:
        if player["current"]: player["history"].append(player["current"])
        if player["queue"]:   player["queue"].pop(0)
        if player["queue"]:
            nxt = player["queue"][0]; player["current"] = nxt
            await pytgcalls.change_stream(
                chat_id, MediaStream(nxt["file"], audio_quality=AudioQuality.HIGH)
            )
            await u.message.reply_text(
                f"⏭ *تم التخطي!*\n🎧 {nxt['title']}\n⏱ {nxt['duration']}\n"
                f"📋 باقي: {len(player['queue'])} أغنية",
                parse_mode="Markdown", reply_markup=_now_kb()
            )
        else:
            player["current"] = None
            await pytgcalls.leave_group_call(chat_id)
            cleanup_downloads(chat_id)
            await u.message.reply_text("⏹ خلصت القايمة!")
    except Exception as e: await u.message.reply_text(f"❌ {e}")

async def cmd_prev(u: Update, _):
    chat_id = u.effective_chat.id
    player  = get_player(chat_id)
    if not player["history"]:
        await u.message.reply_text("⚠️ مفيش أغنية سابقة!"); return
    prev = player["history"].pop()
    if player["current"]: player["queue"].insert(0, player["current"])
    player["queue"].insert(0, prev); player["current"] = prev
    try:
        await pytgcalls.change_stream(
            chat_id, MediaStream(prev["file"], audio_quality=AudioQuality.HIGH)
        )
        await u.message.reply_text(
            f"⏮ *رجعنا للسابقة!*\n🎧 {prev['title']}\n⏱ {prev['duration']}",
            parse_mode="Markdown", reply_markup=_now_kb()
        )
    except Exception as e: await u.message.reply_text(f"❌ {e}")

async def cmd_stop(u: Update, _):
    chat_id = u.effective_chat.id
    player  = get_player(chat_id)
    try:
        await pytgcalls.leave_group_call(chat_id)
        player["queue"].clear(); player["current"] = None; player["history"].clear()
        cleanup_downloads(chat_id)
        await u.message.reply_text("⏹ تم إيقاف الموسيقى وتفريغ القايمة!")
    except Exception as e: await u.message.reply_text(f"❌ {e}")

async def cmd_queue(u: Update, _):
    player = get_player(u.effective_chat.id)
    if not player["queue"]:
        await u.message.reply_text("📋 القايمة فاضية!\nاستخدم `/play`.", parse_mode="Markdown"); return
    lines = ["🎵 *قايمة الأغاني:*\n━━━━━━━━━━━━━━━"]
    for i, t in enumerate(player["queue"]):
        lines.append(f"{'▶️' if i==0 else str(i)+'.'} {t['title']} | ⏱ {t['duration']}")
    lines.append(f"━━━━━━━━━━━━━━━\nالإجمالي: {len(player['queue'])} أغنية")
    await u.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_now(u: Update, _):
    player = get_player(u.effective_chat.id)
    if not player["current"]:
        await u.message.reply_text("📭 مفيش أغنية شغّالة!\nاستخدم `/play`.", parse_mode="Markdown"); return
    t = player["current"]
    await u.message.reply_text(
        f"🎧 *الأغنية الحالية:*\n━━━━━━━━━━━━━━━\n"
        f"🎵 {t['title']}\n⏱ المدة: {t['duration']}\n"
        f"👤 طلب: {t.get('requested_by','؟')}\n"
        f"🔁 التكرار: {'شغّال' if player['loop'] else 'مطفي'}\n"
        f"📋 باقي: {len(player['queue'])}",
        parse_mode="Markdown", reply_markup=_now_kb()
    )

async def cmd_loop(u: Update, _):
    player = get_player(u.effective_chat.id)
    player["loop"] = not player["loop"]
    await u.message.reply_text(f"التكرار: {'🔁 شغّال' if player['loop'] else '➡️ مطفي'}")

async def cmd_vcstart(u: Update, _):
    chat_id = u.effective_chat.id
    silent  = "silent.mp3"
    if not os.path.exists(silent):
        os.system("ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo "
                  "-t 3 -q:a 9 -acodec libmp3lame silent.mp3 -y -loglevel quiet")
    try:
        await pytgcalls.join_group_call(
            chat_id,
            MediaStream(silent, audio_quality=AudioQuality.HIGH)
        )
        await u.message.reply_text(
            "🎙 *تم فتح الدردشة الصوتية!*\n"
            "استخدم `/play` لتشغيل أغنية\n"
            "استخدم `/vcend` لإغلاق الدردشة",
            parse_mode="Markdown"
        )
    except Exception as e:
        await u.message.reply_text(f"❌ فشل: {e}")

async def cmd_vcend(u: Update, _):
    chat_id = u.effective_chat.id
    player  = get_player(chat_id)
    try:
        await pytgcalls.leave_group_call(chat_id)
        player["queue"].clear(); player["current"] = None
        cleanup_downloads(chat_id)
        await u.message.reply_text("📴 تم إغلاق الدردشة الصوتية!")
    except Exception as e: await u.message.reply_text(f"❌ {e}")

async def cmd_help(u: Update, _):
    await u.message.reply_text(
        "📌 *كل أوامر تيلثون تـلـاشـاني* 📌\n"
        "═══════════════════\n"
        "🎵 *الموسيقى:*\n"
        "  `/play <اسم/رابط>` — شغّل أو أضف للقايمة\n"
        "  `/pause` — وقّف مؤقتاً ⏸\n"
        "  `/resume` — كمّل ▶️\n"
        "  `/skip` أو `/next` — التالية ⏭\n"
        "  `/prev` — السابقة ⏮\n"
        "  `/stop` — وقّف كل شيء ⏹\n"
        "  `/queue` أو `/q` — القايمة 📋\n"
        "  `/now` أو `/np` — الأغنية الحالية 🎵\n"
        "  `/loop` — تشغيل/إيقاف التكرار 🔁\n"
        "═══════════════════\n"
        "🎙 *الدردشة الصوتية:*\n"
        "  `/vcstart` — افتح الدردشة الصوتية\n"
        "  `/vcend` — اقفل الدردشة الصوتية\n"
        "═══════════════════\n"
        "💡 الأزرار تحت رسالة الأغنية للتحكم السريع!",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════════
# Callback Buttons
# ══════════════════════════════════════════════════
async def button_handler(u: Update, _):
    q       = u.callback_query
    chat_id = q.message.chat_id
    data    = q.data
    player  = get_player(chat_id)
    await q.answer()

    if data == "pause":
        try:
            await pytgcalls.pause_stream(chat_id)
            await q.edit_message_reply_markup(_paused_kb())
        except Exception as e: await q.answer(f"❌ {e}", show_alert=True)

    elif data == "resume":
        try:
            await pytgcalls.resume_stream(chat_id)
            await q.edit_message_reply_markup(_now_kb())
        except Exception as e: await q.answer(f"❌ {e}", show_alert=True)

    elif data == "skip":
        if player["current"]: player["history"].append(player["current"])
        if player["queue"]:   player["queue"].pop(0)
        if player["queue"]:
            nxt = player["queue"][0]; player["current"] = nxt
            try:
                await pytgcalls.change_stream(
                    chat_id, MediaStream(nxt["file"], audio_quality=AudioQuality.HIGH)
                )
                await q.edit_message_text(
                    f"🎵 *بيشتغل دلوقتي:*\n━━━━━━━━━━━━━━━\n"
                    f"🎧 {nxt['title']}\n⏱ {nxt['duration']}\n"
                    f"📋 باقي: {len(player['queue'])} أغنية",
                    parse_mode="Markdown", reply_markup=_now_kb()
                )
            except Exception as e: await q.answer(f"❌ {e}", show_alert=True)
        else:
            player["current"] = None
            try:
                await pytgcalls.leave_group_call(chat_id)
                cleanup_downloads(chat_id)
                await q.edit_message_text("⏹ خلصت القايمة!")
            except: pass

    elif data == "prev":
        if not player["history"]:
            await q.answer("⚠️ مفيش أغنية سابقة!", show_alert=True); return
        prev = player["history"].pop()
        if player["current"]: player["queue"].insert(0, player["current"])
        player["queue"].insert(0, prev); player["current"] = prev
        try:
            await pytgcalls.change_stream(
                chat_id, MediaStream(prev["file"], audio_quality=AudioQuality.HIGH)
            )
            await q.edit_message_text(
                f"⏮ *رجعنا للسابقة!*\n🎧 {prev['title']}\n⏱ {prev['duration']}",
                parse_mode="Markdown", reply_markup=_now_kb()
            )
        except Exception as e: await q.answer(f"❌ {e}", show_alert=True)

    elif data == "stop":
        try:
            await pytgcalls.leave_group_call(chat_id)
            player["queue"].clear(); player["current"] = None; player["history"].clear()
            cleanup_downloads(chat_id)
            await q.edit_message_text("⏹ تم إيقاف الموسيقى!")
        except Exception as e: await q.answer(f"❌ {e}", show_alert=True)

    elif data == "loop":
        player["loop"] = not player["loop"]
        await q.answer(f"التكرار: {'🔁 شغّال' if player['loop'] else '➡️ مطفي'}")

    elif data == "queue":
        if not player["queue"]:
            await q.answer("📋 القايمة فاضية!", show_alert=True); return
        lines = [f"{'▶️' if i==0 else str(i)+'.'} {t['title'][:30]} | {t['duration']}"
                 for i, t in enumerate(player["queue"][:8])]
        if len(player["queue"]) > 8:
            lines.append(f"... و{len(player['queue'])-8} أغاني أخرى")
        await q.answer("\n".join(lines), show_alert=True)

    elif data == "now":
        if player["current"]:
            t = player["current"]
            await q.answer(f"🎵 {t['title'][:40]}\n⏱ {t['duration']}", show_alert=True)
        else:
            await q.answer("مفيش أغنية شغّالة!", show_alert=True)

# ══════════════════════════════════════════════════
# تشغيل
# ══════════════════════════════════════════════════
async def post_init(app):
    global bot_app
    bot_app = app
    await setup_assistant()

def main():
    print("╔══════════════════════════════════════╗")
    print("║   تيلثون تـلـاشـاني - Music Bot      ║")
    print("╚══════════════════════════════════════╝\n")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    for cmd, func in [
        ("start",   cmd_start),  ("play",    cmd_play),
        ("pause",   cmd_pause),  ("resume",  cmd_resume),
        ("skip",    cmd_skip),   ("next",    cmd_skip),
        ("prev",    cmd_prev),   ("stop",    cmd_stop),
        ("queue",   cmd_queue),  ("q",       cmd_queue),
        ("now",     cmd_now),    ("np",      cmd_now),
        ("loop",    cmd_loop),   ("vcstart", cmd_vcstart),
        ("vcend",   cmd_vcend),  ("help",    cmd_help),
    ]:
        app.add_handler(CommandHandler(cmd, func))

    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 البوت شغال! ابعت /start في التليجرام\n")
    app.run_polling()

if __name__ == "__main__":
    main()