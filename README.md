# 🎵 Telegram Voice Chat Music Bot

بوت بيشغل موسيقى في الـ Voice Chat بالاسم — **stream مباشر بدون تحميل**.

---

## 🚀 خطوات التشغيل

### 1️⃣ جيب الـ USER_SESSION على جهازك

```bash
pip install pyrogram TgCrypto
python generate_session.py
```
انسخ الـ SESSION_STRING اللي هيطلع

### 2️⃣ ارفع على GitHub

```bash
git init
git add .
git commit -m "🎵 Music Bot"
git branch -M main
git remote add origin https://github.com/tlashany-gems/tlashany.music.git
git push -u origin main
```

### 3️⃣ ضيف Variables في Railway

| المتغير | القيمة |
|---------|--------|
| `API_ID` | من my.telegram.org |
| `API_HASH` | من my.telegram.org |
| `BOT_TOKEN` | من @BotFather |
| `USER_SESSION` | من generate_session.py |
| `PYROGRAM_LICENSE` | رخصة Pyrogram بتاعتك |

### 4️⃣ Railway هيعمل Deploy تلقائياً ✅

---

## 🎮 أوامر البوت

| الأمر | الوظيفة |
|-------|----------|
| `/play <اسم>` | بحث وتشغيل من YouTube |
| `/now` | الأغنية الحالية |
| `/skip` | تخطي |
| `/stop` | إيقاف كامل |
| `/queue` | قائمة الانتظار |
| `/volume <1-200>` | الصوت |

---

## ⚠️ مهم

- **لا ترفع `.env` على GitHub** — استخدم Railway Variables فقط
- الحساب المساعد لازم يكون **Admin** في الجروب
