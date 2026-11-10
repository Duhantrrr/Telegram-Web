 import os
import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
import uvicorn

# --- TELEGRAM API BİLGİLERİ ---
API_ID = int(os.environ.get("API_ID", 16896485))
API_HASH = os.environ.get("API_HASH", "29b5bb9351b4cb3738d73abaf5eb28ca")
SESSION_NAME = os.environ.get("SESSION_NAME", "bot_session")

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

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

# ids.txt dosyasından hem ID hem de Kullanıcı Adlarını okur
def get_targets():
    targets = []
    try:
        if os.path.exists("ids.txt"):
            with open("ids.txt", "r", encoding="utf-8") as f:
                for line in f:
                    val = line.strip().replace("https://t.me/", "").replace("@", "")
                    if val:
                        targets.append(int(val) if val.isdigit() else val)
        else:
            add_log("⚠️ ids.txt bulunamadı!")
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
                    
                    # Spam koruması (6-12 saniye bekleme)
                    await asyncio.sleep(random.uniform(6, 12))
                except errors.FloodWaitError as e:
                    add_log(f"🕒 Spam engeli: {e.seconds} saniye bekleniyor...")
                    await asyncio.sleep(e.seconds + 5)
                except errors.UserDeactivatedBanError:
                    add_log("❌ Hesap Telegram tarafından sınırlandırıldı!")
                    config["is_auto_pilot_on"] = False
                    break
                except Exception as e:
                    add_log(f"⚠️ Hata ({user}): {e}")
                    continue

            if config["is_auto_pilot_on"]:
                add_log("💤 Tur bitti. 1 saat (3600 sn) uyku modu.")
                await asyncio.sleep(3600)
    except asyncio.CancelledError:
        add_log("🛑 Broadcast döngüsü durduruldu.")
    except Exception as e:
        add_log(f"❌ Kritik hata (Broadcast): {e}")

# --- TETİKLENME (KARŞI TARAF LİNK ATTIĞINDA) ---
@client.on(events.NewMessage(incoming=True))
async def handle_response(event):
    if not event.is_private:
        return
    
    text = (event.raw_text or "").lower()
    if "t.me/" in text or "telegram.me/" in text:
        try:
            # 1. Gelen mesajı @ratlogscloud kanalına ilet
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            
            # 2. Mesaj linkini çıkar
            chan_name = config["storage_channel"].replace("@", "").strip()
            done_link = f"https://t.me/{chan_name}/{fwd.id}"
            
            # 3. Sırayla yanıt gönder
            await event.reply(config["promo_message"])
            await asyncio.sleep(1)
            await event.respond("Go")
            await asyncio.sleep(1)
            await event.respond(f"Done {done_link}")
            
            add_log(f"✅ Karşılıklı reklam tamamlandı: {event.chat_id} -> {done_link}")
        except errors.FloodWaitError as e:
            add_log(f"🕒 FloodWait: {e.seconds} sn")
        except Exception as e:
            add_log(f"❌ Yanıt hatası ({event.chat_id}): {e}")

# --- FASTAPI LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await client.connect()
    if await client.is_user_authorized():
        add_log("🚀 Telethon bağlandı, oturum AKTİF.")
    else:
        add_log("⚠️ Oturum açık değil! Session dosyasını kontrol edin.")
    
    yield
    
    global broadcast_task
    if broadcast_task and not broadcast_task.done():
        broadcast_task.cancel()
    await client.disconnect()
    add_log("🔌 Telethon bağlantısı kapatıldı.")

app = FastAPI(lifespan=lifespan)

# --- PANEL YOLLARI ---
@app.get("/")
async def index():
    if not os.path.exists("index.html"):
        return HTMLResponse("<h3>index.html dosyası bulunamadı!</h3>", status_code=404)
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-data")
async def get_data():
    return {
        "logs": config["logs"],
        "is_auto": config["is_auto_pilot_on"],
        "is_auth": await client.is_user_authorized() if client.is_connected() else False,
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
    uvicorn.run(app, host="0.0.0.0", port=port)
