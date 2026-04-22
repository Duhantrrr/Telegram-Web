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
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
# Railway'de taze giriş yaptıysan bu oturum ismini kullanır
client = TelegramClient('railway_session', api_id, api_hash)

config = {
    "my_promo_link": "https://t.me/kanaliniz", # Panelden kaydedilecek
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

def get_ids():
    if os.path.exists("ids.txt"):
        with open("ids.txt", "r") as f:
            return [int(l.strip()) for l in f if l.strip().isdigit()]
    return []

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem Başlatıldı. Link pususu aktif!")

# --- ANA TETİKLEYİCİ: ANİDEN GELEN LİNK VE SIRALI CEVAP ---
@client.on(events.NewMessage(incoming=True))
async def handle_sudden_link(event):
    if not event.is_private: return # Sadece DM
    
    text = event.raw_text.lower()
    # Mesajda Telegram linki yakalanırsa:
    if "t.me/" in text or "telegram.me/" in text:
        sender = await event.get_sender()
        name = sender.first_name or "Biri"
        add_log(f"🔥 Link Yakalandı: {name} (@{sender.username})")
        
        try:
            # 1. Kendi linkini at
            await event.reply(config["my_promo_link"])
            add_log(f"📤 Kendi linkim gönderildi -> {name}")
            await asyncio.sleep(1)

            # 2. "Go?" yaz
            await event.respond("Go?")
            add_log(f"💬 'Go?' soruldu -> {name}")
            await asyncio.sleep(1)

            # 3. Gelen linki kanala ilet (Forward)
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            
            # 4. Kanıt linkini al ve "Done" mesajını at
            chan_name = config["storage_channel"].replace("@", "")
            proof_link = f"https://t.me/{chan_name}/{fwd.id}"
            await event.respond(f"Done {proof_link}")
            add_log(f"🎯 Yanlama yapıldı, kanıt atıldı: {proof_link}")
            await asyncio.sleep(1)

            # 5. En son "You?" yaz
            await event.respond("You?")
            add_log(f"❓ 'You?' soruldu -> {name}")

        except Exception as e:
            add_log(f"❌ İşlem sırasında hata: {str(e)[:50]}")

# --- SAATLİK BROADCAST (ARKA PLAN GÖREVİ) ---
async def hourly_broadcast():
    while config["is_auto_pilot_on"]:
        targets = get_ids()
        add_log(f"📢 Saatlik operasyon başladı: {len(targets)} kişi.")
        sent = 0
        for uid in targets:
            if not config["is_auto_pilot_on"]: break
            try:
                await client.send_message(uid, "Ads to ads?")
                sent += 1
                add_log(f"✉️ {uid} mesaj atıldı.")
                await asyncio.sleep(3) # Güvenli hız
            except errors.FloodWaitError as e:
                add_log(f"🕒 Spam! {e.seconds} sn bekleme...")
                await asyncio.sleep(e.seconds)
            except: continue
        add_log(f"🏁 Tur bitti. Başarılı: {sent}")
        await asyncio.sleep(3600)

# --- API VE WEB PANEL ---
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
        background_tasks.add_task(hourly_broadcast)
    return {"status": "ok"}

@app.post("/update")
async def update(data: dict):
    config["my_promo_link"] = data.get("link")
    add_log("⚙️ Linkin başarıyla kaydedildi.")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
