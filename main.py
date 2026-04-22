from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
from telethon.errors import SessionPasswordNeededError
import asyncio
import os
import uvicorn
import re
from datetime import datetime

app = FastAPI()

# --- AYARLAR ---
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
client = TelegramClient('railway_session', api_id, api_hash)

# Geçici Giriş Hafızası
auth_state = {"phone": None, "hash": None}

config = {
    "my_promo_link": "https://t.me/kanalim",
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
    add_log("🚀 Sistem hazır. Giriş yapılınca pusuya yatacak.")

# --- GİRİŞ MODÜLÜ API ---
@app.post("/login/send-code")
async def send_code(data: dict):
    phone = data.get("phone")
    auth_state["phone"] = phone
    try:
        res = await client.send_code_request(phone)
        auth_state["hash"] = res.phone_code_hash
        add_log(f"📲 Kod istendi: {phone}")
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-code")
async def verify_code(data: dict):
    try:
        await client.sign_in(auth_state["phone"], data.get("code"), phone_code_hash=auth_state["hash"])
        add_log("✅ Giriş başarılı! Bot aktif.")
        return {"status": "success"}
    except SessionPasswordNeededError: return {"status": "2fa_required"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-2fa")
async def verify_2fa(data: dict):
    try:
        await client.sign_in(password=data.get("password"))
        add_log("✅ 2FA Doğrulandı. Bot aktif.")
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

# --- SİLSİLE CEVAP: LİNK GELİNCE YAPILACAKLAR ---
@client.on(events.NewMessage(incoming=True))
async def handle_sudden_link(event):
    if not event.is_private: return 
    
    text = event.raw_text.lower()
    if "t.me/" in text or "telegram.me/" in text:
        try:
            add_log(f"🔥 Link Yakalandı: {event.chat_id}")
            
            # 1. Kendi linkini at
            await event.reply(config["my_promo_link"])
            await asyncio.sleep(1)

            # 2. "Go?" yaz
            await event.respond("Go?")
            await asyncio.sleep(1)

            # 3. Gelen linki @cloudads1 kanalına ilet (Forward)
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            
            # 4. Kanıt linkini at
            chan_name = config["storage_channel"].replace("@", "")
            proof_link = f"https://t.me/{chan_name}/{fwd.id}"
            await event.respond(f"Done {proof_link}")
            await asyncio.sleep(1)

            # 5. "You?" yaz
            await event.respond("You?")
            add_log(f"🎯 Silsile cevap tamamlandı -> {event.chat_id}")

        except Exception as e:
            add_log(f"❌ Hata: {str(e)[:50]}")

# --- SAATLİK OPERASYON ---
async def hourly_broadcast():
    while config["is_auto_pilot_on"]:
        targets = get_ids()
        add_log(f"📢 Operasyon: {len(targets)} kişi.")
        sent = 0
        for uid in targets:
            if not config["is_auto_pilot_on"]: break
            try:
                await client.send_message(uid, "Ads to ads?")
                sent += 1
                await asyncio.sleep(5) # Güvenli hız
            except errors.FloodWaitError as e:
                add_log(f"🕒 Spam engeli: {e.seconds} sn.")
                await asyncio.sleep(e.seconds)
            except: continue
        add_log(f"🏁 Tur bitti. Başarılı: {sent}")
        await asyncio.sleep(3600)

# --- WEB PANEL YOLLARI ---
@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-data")
async def get_data():
    return {"logs": config["logs"], "is_auto": config["is_auto_pilot_on"], "is_auth": await client.is_user_authorized()}

@app.post("/toggle")
async def toggle(background_tasks: BackgroundTasks):
    config["is_auto_pilot_on"] = not config["is_auto_pilot_on"]
    if config["is_auto_pilot_on"]:
        background_tasks.add_task(hourly_broadcast)
    return {"status": "ok"}

@app.post("/update")
async def update(data: dict):
    config["my_promo_link"] = data.get("link")
    add_log("⚙️ Link kaydedildi.")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
