from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
import asyncio
import re
import uvicorn
import os
from datetime import datetime

app = FastAPI()

# --- AYARLAR ---
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
client = TelegramClient('railway_session', api_id, api_hash)

# Sistem Hafızası
logs = []
waiting_for_link = {}
auth_data = {"phone": None, "phone_code_hash": None}
config = {
    "my_promo_link": "https://t.me/kanalim",
    "storage_channel": "@kayit_kanali",
    "keywords": ["vouchs", "vouch", "ads", "dragon", "proof"],
}

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{time_str}] {msg}")
    if len(logs) > 30: logs.pop(0)

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem hazır. Giriş bekleniyor...")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/get-logs")
async def get_logs():
    return {"logs": logs, "is_auth": await client.is_user_authorized()}

# --- GİRİŞ API'LERİ ---
@app.post("/send-code")
async def send_code(data: dict):
    phone = data.get("phone")
    auth_data["phone"] = phone
    try:
        res = await client.send_code_request(phone)
        auth_data["phone_code_hash"] = res.phone_code_hash
        add_log(f"📲 Kod gönderildi: {phone}")
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/verify-login")
async def verify_login(data: dict):
    code = data.get("code")
    try:
        await client.sign_in(auth_data["phone"], code, phone_code_hash=auth_data["phone_code_hash"])
        add_log("✅ Giriş başarılı!")
        return {"status": "success"}
    except SessionPasswordNeededError:
        return {"status": "2fa_required"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/verify-2fa")
async def verify_2fa(data: dict):
    try:
        await client.sign_in(password=data.get("password"))
        add_log("✅ 2FA ile giriş başarılı!")
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- AYAR GÜNCELLEME ---
@app.post("/update-settings")
async def update_settings(data: dict):
    config.update({
        "my_promo_link": data.get("my_link", config["my_promo_link"]),
        "storage_channel": data.get("storage", config["storage_channel"]),
        "keywords": [k.strip().lower() for k in data.get("keywords", "").split(",")]
    })
    add_log("⚙️ Ayarlar güncellendi.")
    return {"status": "success"}

# --- OTOMASYON MOTORU ---
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.is_private: return
    sender = await event.get_sender()
    if not sender: return
    
    sid = event.chat_id
    msg = event.raw_text.lower()
    identity = f"{(sender.first_name or '')} {(sender.last_name or '')} @{(sender.username or '')}".lower()
    
    search_area = f"{msg} {identity}"
    found = next((kw for kw in config["keywords"] if kw in search_area), None)

    if found and sid not in waiting_for_link:
        add_log(f"🔍 YAKALANDI: '{found}' | Kişi: {identity}")
        await event.reply(f"Ads to ads? Okay, add mine first:\n{config['my_promo_link']}\n\nSend your link when done!")
        waiting_for_link[sid] = True
    
    elif sid in waiting_for_link:
        link = re.search(r'(t\.me/[\w/]+|https?://t\.me/[\w/]+)', msg)
        if link:
            await client.send_message(config["storage_channel"], f"📥 S4S\n👤 {identity}\n🔗 {link.group(0)}")
            await event.reply("Done! I added yours too.")
            add_log(f"🎯 İŞLEM TAMAM: {identity}")
            del waiting_for_link[sid]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
