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

# Geçici hafıza (Giriş süreci için)
auth_state = {"phone": None, "hash": None}

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

def get_ids():
    ids = []
    try:
        if os.path.exists("ids.txt"):
            with open("ids.txt", "r") as f:
                ids = [int(line.strip()) for line in f if line.strip().isdigit()]
    except: pass
    return ids

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem Başlatıldı.")

# --- GİRİŞ API'LERİ (WEB PANEL İÇİN) ---

@app.post("/login/send-code")
async def send_code(data: dict):
    phone = data.get("phone")
    auth_state["phone"] = phone
    try:
        res = await client.send_code_request(phone)
        auth_state["hash"] = res.phone_code_hash
        return {"status": "success", "message": "Kod gönderildi!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/login/verify-code")
async def verify_code(data: dict):
    code = data.get("code")
    try:
        await client.sign_in(auth_state["phone"], code, phone_code_hash=auth_state["hash"])
        return {"status": "success", "message": "Giriş başarılı!"}
    except SessionPasswordNeededError:
        return {"status": "2fa_required", "message": "2FA Şifresi gerekli."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/login/verify-2fa")
async def verify_2fa(data: dict):
    password = data.get("password")
    try:
        await client.sign_in(password=password)
        return {"status": "success", "message": "2FA ile giriş başarılı!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- DİĞER FONKSİYONLAR ---

async def hourly_broadcast_task():
    while config["is_auto_pilot_on"]:
        targets = get_ids()
        if not targets:
            await asyncio.sleep(600)
            continue
        add_log(f"📢 Operasyon: {len(targets)} kişi.")
        for uid in targets:
            if not config["is_auto_pilot_on"]: break
            try:
                await client.send_message(uid, "Ads to ads?")
                await asyncio.sleep(2.5)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except: continue
        await asyncio.sleep(3600)

@client.on(events.NewMessage(incoming=True))
async def handle_response(event):
    if not event.is_private: return
    text = event.raw_text.lower()
    if "t.me/" in text or "telegram.me/" in text:
        try:
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            chan_name = config["storage_channel"].replace("@", "")
            done_link = f"https://t.me/{chan_name}/{fwd.id}"
            await event.reply(config["my_promo_link"])
            await event.respond("Go")
            await event.respond(f"Done {done_link}")
            add_log(f"✅ Link kapıldı: {event.chat_id}")
        except: pass

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
        background_tasks.add_task(hourly_broadcast_task)
    return {"status": "ok"}

@app.post("/update")
async def update(data: dict):
    config["my_promo_link"] = data.get("link")
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
