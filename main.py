import os
import re
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
import uvicorn

app = FastAPI()

# --- DOSYA VE DİZİN YOLLARI ---
IS_VERCEL = bool(os.environ.get("VERCEL"))
BASE_DIR = "/tmp" if IS_VERCEL else "."
SESSION_FILE = os.path.join(BASE_DIR, "session_token.txt")
STATE_FILE = os.path.join(BASE_DIR, "bot_state.json")

# --- TELEGRAM BİLGİLERİ ---
API_ID = int(os.environ.get("API_ID", 16896485))
API_HASH = os.environ.get("API_HASH", "29b5bb9351b4cb3738d73abaf5eb28ca")

# Oturumu önce ENV'den, sonra dosyadan oku (Kalıcı Giriş)
def get_saved_session():
    env_sess = os.environ.get("SESSION_STRING", "").strip()
    if env_sess:
        return env_sess
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            pass
    return ""

saved_session = get_saved_session()
client = TelegramClient(StringSession(saved_session), API_ID, API_HASH)

auth_state = {"phone": None, "phone_code_hash": None}

config = {
    "channel_link": "https://t.me/+vbR5re1Xa-VkOWE0",
    "storage_channel": "@ratlogscloud",
    "promo_message": "Ads to ads @tgciyim https://t.me/+vbR5re1Xa-VkOWE0",
    "is_auto_pilot_on": False,
    "logs": []
}

broadcast_task: asyncio.Task | None = None

# Durumu Kaydet & Yükle (Sayfa yenilenince durmaması için)
def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"is_auto": config["is_auto_pilot_on"], "promo": config["promo_message"]}, f)
    except Exception as e:
        print(f"State save error: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config["is_auto_pilot_on"] = data.get("is_auto", False)
                config["promo_message"] = data.get("promo", config["promo_message"])
        except Exception as e:
            print(f"State load error: {e}")

load_state()

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
        add_log(f"❌ ids.txt hatası: {e}")
    return targets

# --- 15 SANİYE ARAYLA BROADCAST ---
async def hourly_broadcast_task():
    try:
        while config["is_auto_pilot_on"]:
            targets = get_targets()
            if not targets:
                add_log("⚠️ Liste boş! ids.txt kontrol edin.")
                await asyncio.sleep(300)
                continue

            add_log(f"📢 Operasyon Başladı: {len(targets)} kullanıcı taranıyor (15 sn arayla).")
            for index, user in enumerate(targets, 1):
                if not config["is_auto_pilot_on"]:
                    break
                try:
                    await client.send_message(user, config["promo_message"])
                    add_log(f"✉️ ({index}/{len(targets)}) Gönderildi: @{user}")
                    
                    # TAM 15 SANİYE BEKLEME
                    add_log("⏳ 15 saniye bekleniyor...")
                    await asyncio.sleep(15)

                except errors.FloodWaitError as e:
                    add_log(f"🕒 Telegram FloodWait: {e.seconds} saniye bekleniyor...")
                    await asyncio.sleep(e.seconds + 5)
                except errors.UserDeactivatedBanError:
                    add_log("❌ HESAP SINIRLANDIRILDI! Sistem durduruldu.")
                    config["is_auto_pilot_on"] = False
                    save_state()
                    break
                except Exception as e:
                    add_log(f"⚠️ Hata (@{user}): {e}")
                    await asyncio.sleep(15)
                    continue

            if config["is_auto_pilot_on"]:
                add_log("💤 45 kişilik liste bitti. 1 saat (3600 sn) uyku modu başladı.")
                await asyncio.sleep(3600)
    except asyncio.CancelledError:
        add_log("🛑 Broadcast işlemi durduruldu.")
    except Exception as e:
        add_log(f"❌ Kritik Broadcast Hatası: {e}")

# --- TETİKLENME (LİNK VEYA ONAY KELİMELERİ) ---
@client.on(events.NewMessage(incoming=True))
async def handle_response(event):
    if not event.is_private:
        return
    
    text = (event.raw_text or "").strip()
    lower_text = text.lower()
    user_id = event.chat_id

    # Gelen her mesajı loga yaz
    add_log(f"📩 Gelen Mesaj ({user_id}): \"{text}\"")

    # 1. DURUM: Karşı taraf Link attıysa -> Ratlogscloud'a at ve Done linki ver
    if "t.me/" in lower_text or "telegram.me/" in lower_text:
        try:
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            chan_name = config["storage_channel"].replace("@", "").strip()
            done_link = f"https://t.me/{chan_name}/{fwd.id}"
            
            await event.reply(config["promo_message"])
            await asyncio.sleep(1)
            await event.respond("Go")
            await asyncio.sleep(1)
            await event.respond(f"Done {done_link}")
            add_log(f"✅ Reklam Takası Yapıldı! Kanıt: {done_link}")
        except Exception as e:
            add_log(f"❌ Link yanıtlama hatası ({user_id}): {e}")
        return

    # 2. DURUM: Karşı taraf onay kelimeleri yazdıysa (ok, ready, yes, yeah, go vb.)
    trigger_words = r'\b(ok|ready|yes|yeah|go|tamam|olur|send|link|yolla|at|anlastik|anlaştık)\b'
    if re.search(trigger_words, lower_text):
        try:
            await event.reply(config["promo_message"])
            add_log(f"💬 Tetikleyici kelime yakalandı (\"{text}\") -> Reklam linki gönderildi.")
        except Exception as e:
            add_log(f"❌ Kelime yanıt hatası ({user_id}): {e}")

# --- BAŞLANGIÇ ---
@app.on_event("startup")
async def startup():
    global broadcast_task
    try:
        await client.connect()
        if await client.is_user_authorized():
            add_log("🚀 Telegram oturumu AKTİF!")
            # Eğer önceki oturumda açık bırakıldıysa görevi otomatik yeniden başlat
            if config["is_auto_pilot_on"] and (broadcast_task is None or broadcast_task.done()):
                broadcast_task = asyncio.create_task(hourly_broadcast_task())
                add_log("▶️ Otomatik Pilot kaldığı yerden devam ediyor.")
        else:
            add_log("⚠️ Oturum açık değil. Lütfen panelden giriş yapın.")
    except Exception as e:
        add_log(f"⚠️ Bağlantı hatası: {e}")

# --- GİRİŞ İŞLEMLERİ ---
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
        add_log(f"📩 Doğrulama kodu gönderildi: {phone}")
        return {"status": "ok"}
    except Exception as e:
        add_log(f"❌ Kod isteme hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/verify")
async def verify_code(data: dict):
    code = data.get("code", "").strip()
    password = data.get("password", "").strip()
    try:
        await client.sign_in(phone=auth_state["phone"], code=code, phone_code_hash=auth_state["phone_code_hash"])
    except errors.SessionPasswordNeededError:
        if not password:
            return {"status": "2fa_required"}
        await client.sign_in(password=password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Kalıcı oturum stringini al ve kaydet
    token = client.session.save()
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            f.write(token)
    except:
        pass

    add_log("🎉 GİRİŞ BAŞARILI! Oturum kalıcı olarak kaydedildi.")
    return {"status": "ok", "session_string": token}

# --- WEB PANEL ENDPOINTLERİ ---
@app.get("/")
async def index():
    if not os.path.exists("index.html"):
        return HTMLResponse("<h3>index.html dosyası bulunamadı!</h3>", status_code=404)
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-data")
async def get_data():
    global broadcast_task
    is_auth = False
    try:
        if not client.is_connected():
            await client.connect()
        is_auth = await client.is_user_authorized()
    except:
        pass

    # Sayfa yenilendiğinde görev ölüyse ama config açıksa tekrar ayağa kaldır
    if is_auth and config["is_auto_pilot_on"] and (broadcast_task is None or broadcast_task.done()):
        broadcast_task = asyncio.create_task(hourly_broadcast_task())

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
    save_state()

    if config["is_auto_pilot_on"]:
        if broadcast_task is None or broadcast_task.done():
            broadcast_task = asyncio.create_task(hourly_broadcast_task())
            add_log("▶️ Otomatik Pilot BAŞLATILDI (15 sn döngüsü aktif).")
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
        save_state()
        add_log(f"🔗 Mesaj güncellendi: {config['promo_message']}")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
