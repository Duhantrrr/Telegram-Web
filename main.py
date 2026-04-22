from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
import asyncio
import os
import uvicorn
import re
from datetime import datetime

app = FastAPI()

# --- AYARLAR ---
# Oturum ismini bozma (Daha önce giriş yaptığın isim)
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
client = TelegramClient('railway_session', api_id, api_hash)

config = {
    "my_promo_link": "https://t.me/senin_kanalin",
    "storage_channel": "@cloudads1", 
    "is_auto_pilot_on": False,
    "logs": []
}

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    entry = f"[{time_str}] {msg}"
    config["logs"].append(entry)
    if len(config["logs"]) > 50: config["logs"].pop(0)
    print(entry)

# ids.txt dosyasından ID'leri oku
def get_ids():
    ids = []
    try:
        if os.path.exists("ids.txt"):
            with open("ids.txt", "r") as f:
                ids = [int(line.strip()) for line in f if line.strip().isdigit()]
        else:
            add_log("⚠️ ids.txt bulunamadı!")
    except Exception as e:
        add_log(f"❌ Liste okuma hatası: {e}")
    return ids

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem Başlatıldı. Oturum korundu.")

# --- OTOMATİK PİLOT: 1 SAATTE BİR BROADCAST ---
async def hourly_broadcast_task():
    while config["is_auto_pilot_on"]:
        targets = get_ids()
        if not targets:
            add_log("⚠️ Liste boş, 15 dk sonra tekrar denenecek.")
            await asyncio.sleep(900)
            continue

        add_log(f"📢 Operasyon başladı: {len(targets)} kişi hedefleniyor.")
        for uid in targets:
            if not config["is_auto_pilot_on"]: break
            try:
                await client.send_message(uid, "Ads to ads?")
                await asyncio.sleep(2) # 2 saniye bekleme
            except errors.FloodWaitError as e:
                add_log(f"🕒 Spam engeli: {e.seconds} saniye bekleniyor...")
                await asyncio.sleep(e.seconds)
            except:
                continue

        add_log("💤 Tur bitti. 1 saat uyku modu.")
        await asyncio.sleep(3600)

# --- OTOMATİK CEVAP: LİNK -> LİNK + GO + DONE ---
@client.on(events.NewMessage(incoming=True))
async def handle_response(event):
    if not event.is_private: return
    
    text = event.raw_text.lower()
    if "t.me/" in text or "telegram.me/" in text:
        try:
            # 1. Linki @cloudads1 kanalına ilet
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            
            # 2. Mesajın kanaldaki linkini oluştur
            chan_name = config["storage_channel"].replace("@", "")
            done_link = f"https://t.me/{chan_name}/{fwd.id}"
            
            # 3. Yanıtları fırlat
            await event.reply(config["my_promo_link"])
            await event.respond("Go")
            await event.respond(f"Done {done_link}")
            
            add_log(f"✅ Link kapıldı: {event.chat_id} -> Done linki gönderildi.")
        except Exception as e:
            add_log(f"❌ Yanıt hatası: {e}")

# --- WEB PANEL YOLLARI ---
@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-data")
async def get_data():
    return {
        "logs": config["logs"],
        "is_auto": config["is_auto_pilot_on"],
        "is_auth": await client.is_user_authorized()
    }

@app.post("/toggle")
async def toggle(background_tasks: BackgroundTasks):
    config["is_auto_pilot_on"] = not config["is_auto_pilot_on"]
    if config["is_auto_pilot_on"]:
        background_tasks.add_task(hourly_broadcast_task)
    return {"status": "ok"}

@app.post("/update")
async def update(data: dict):
    config["my_promo_link"] = data.get("link")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
