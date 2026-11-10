import os
import asyncio
import random
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
import uvicorn

app = FastAPI()

# --- TELEGRAM API BİLGİLERİ ---
API_ID = int(os.environ.get("API_ID", 16896485))
API_HASH = os.environ.get("API_HASH", "29b5bb9351b4cb3738d73abaf5eb28ca")
SESSION_STR = os.environ.get("SESSION_STRING", "")

# StringSession öncelikli, yoksa /tmp kullanır
client = TelegramClient(StringSession(SESSION_STR) if SESSION_STR else os.path.join("/tmp", "bot_session"), API_ID, API_HASH)

# Giriş adımı hafızası
auth_state = {
    "phone": None,
    "phone_code_hash": None
}

config = {
    "channel_link": "https://t.me/+vbR5re1Xa-VkOWE0",
    "storage_channel": "@ratlogscloud",
    "promo_message": "Ads to ads @tgciyim https://t.me/+vbR5re1Xa-VkOWE0",
    "is_auto_pilot_on": False,
    "logs": []
}

broadcast_task: asyncio.Task | None = None

def add_log(msg: str):
    time_str = datetime.now().strftime("%H:%M:%S")
    entry = f"[{time_str}] {msg}"
    config["logs"].append(entry)
    if len(config["logs"]) > 100:
        config["logs"].pop(0)
    print(entry)

def get_targets():
    targets = []
    try:
        if os.path.exists("ids.txt"):
            with open("ids.txt", "r", encoding="utf-8") as f:
                for line in f:
                    val = line.strip().replace("https://t.me/", "").replace("@", "")
                    if val:
                        targets.append(int(val) if val.isdigit() else val)
    except Exception as e:
        add_log(f"❌ ids.txt okuma hatası: {e}")
    return targets

# --- 1 SAATTE BİR LİSTEYE MESAJ ATMA ---
async def hourly_broadcast_task():
    try:
        while config["is_auto_pilot_on"]:
            targets = get_targets()
            if not targets:
                add_log("⚠️ Liste boş, 15 dk sonra tekrar denenecek.")
                await asyncio.sleep(900)
                continue

            add_log(f"📢 Döngü başladı: {len(targets)} kullanıcı hedefleniyor.")
            for user in targets:
                if not config["is_auto_pilot_on"]:
                    break
                try:
                    await client.send_message(user, config["promo_message"])
                    add_log(f"✉️ İletildi: {user}")
                    await asyncio.sleep(random.uniform(6, 12))
                except errors.FloodWaitError as e:
                    add_log(f"🕒 Spam engeli: {e.seconds} sn bekleniyor...")
                    await asyncio.sleep(e.seconds + 5)
                except errors.UserDeactivatedBanError:
                    add_log("❌ Hesap sınırlandırıldı!")
                    config["is_auto_pilot_on"] = False
                    break
                except Exception as e:
                    add_log(f"⚠️ Hata ({user}): {e}")
                    continue

            if config["is_auto_pilot_on"]:
                add_log("💤 Tur bitti. 1 saat (3600 sn) uyku modu.")
                await asyncio.sleep(3600)
    except asyncio.CancelledError:
        add_log("🛑 Broadcast durduruldu.")
    except Exception as e:
        add_log(f"❌ Kritik hata: {e}")

# --- TETİKLENME (GELEN LİNK) ---
@client.on(events.NewMessage(incoming=True))
async def handle_response(event):
    if not event.is_private:
        return
    text = (event.raw_text or "").lower()
    if "t.me/" in text or "telegram.me/" in text:
        try:
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            chan_name = config["storage_channel"].replace("@", "").strip()
            done_link = f"https://t.me/{chan_name}/{fwd.id}"
            
            await event.reply(config["promo_message"])
            await asyncio.sleep(1)
            await event.respond("Go")
            await asyncio.sleep(1)
            await event.respond(f"Done {done_link}")
            add_log(f"✅ Karşılıklı reklam yapıldı: {event.chat_id} -> {done_link}")
        except Exception as e:
            add_log(f"❌ Yanıt hatası ({event.chat_id}): {e}")

@app.on_event("startup")
async def startup():
    try:
        await client.connect()
        if await client.is_user_authorized():
            add_log("🚀 Telethon AKTİF, oturum hazır!")
    except Exception as e:
        add_log(f"⚠️ Başlangıç bağlantı hatası: {e}")

# --- WEB PANEL GİRİŞ ENDPOINTLERİ ---
@app.post("/auth/send-code")
async def send_code(data: dict):
    phone = data.get("phone", "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Telefon numarası gerekli!")
    
    if not client.is_connected():
        await client.connect()
        
    try:
        res = await client.send_code_request(phone)
        auth_state["phone"] = phone
        auth_state["phone_code_hash"] = res.phone_code_hash
        add_log(f"📩 Giriş kodu gönderildi: {phone}")
        return {"status": "ok", "message": "Kod gönderildi!"}
    except Exception as e:
        add_log(f"❌ Kod gönderme hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/verify")
async def verify_code(data: dict):
    code = data.get("code", "").strip()
    password = data.get("password", "").strip() # 2FA varsa
    
    if not auth_state["phone"] or not auth_state["phone_code_hash"]:
        raise HTTPException(status_code=400, detail="Önce kod göndermelisiniz!")
        
    try:
        await client.sign_in(
            phone=auth_state["phone"],
            code=code,
            phone_code_hash=auth_state["phone_code_hash"]
        )
    except errors.SessionPasswordNeededError:
        if not password:
            return {"status": "2fa_required", "message": "2 Adımlı Doğrulama (2FA) şifresi gerekli!"}
        await client.sign_in(password=password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Oturum String'ini al
    string_session = ""
    if isinstance(client.session, StringSession):
        string_session = client.session.save()

    add_log("🎉 TEBRİKLER! Telegram girişi başarıyla tamamlandı.")
    return {
        "status": "ok",
        "message": "Giriş Başarılı!",
        "session_string": string_session
    }

# --- WEB PANEL YOLLARI ---
@app.get("/")
async def index():
    if not os.path.exists("index.html"):
        return HTMLResponse("<h3>index.html bulunamadı!</h3>", status_code=404)
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-data")
async def get_data():
    is_auth = False
    try:
        if not client.is_connected():
            await client.connect()
        is_auth = await client.is_user_authorized()
    except:
        pass

    return {
        "logs": config["logs"],
        "is_auto": config["is_auto_pilot_on"],
        "is_auth": is_auth,
        "promo_link": config["promo_message"],
        "target_count": len(get_targets())
    }

@app.post("/toggle")
async def toggle():
    global broadcast_task
    config["is_auto_pilot_on"] = not config["is_auto_pilot_on"]
    
    if config["is_auto_pilot_on"]:
        if broadcast_task is None or broadcast_task.done():
            broadcast_task = asyncio.create_task(hourly_broadcast_task())
            add_log("▶️ Otomatik Pilot BAŞLATILDI.")
    else:
        if broadcast_task and not broadcast_task.done():
            broadcast_task.cancel()
            broadcast_task = None
        add_log("⏸️ Otomatik Pilot DURDURULDU.")
        
    return {"status": "ok", "is_auto": config["is_auto_pilot_on"]}

@app.post("/update")
async def update(data: dict):
    if "link" in data and data["link"].strip():
        config["promo_message"] = data.get("link").strip()
        add_log(f"🔗 Mesaj güncellendi: {config['promo_message']}")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
