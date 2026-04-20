from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import PeerChannel
import asyncio
import re
import uvicorn
import os
from datetime import datetime

app = FastAPI()

# --- API BİLGİLERİN ---
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
client = TelegramClient('railway_session', api_id, api_hash)

# Sistem Belleği
logs = []
waiting_list = {} 
auth_data = {"phone": None, "phone_code_hash": None}

config = {
    "my_promo_link": "https://t.me/senin_kanalin",
    "storage_channel": "@kayit_kanali", # Linklerin iletileceği kanal
    "keywords": ["vouchs", "vouch", "ads", "dragon", "proof", "prof"]
}

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    logs.append(f"[{time_str}] {msg}")
    if len(logs) > 40: logs.pop(0)

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem Aktif. Operasyon ve Dinleme Hazır.")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/get-logs")
async def get_logs():
    return {"logs": logs, "is_auth": await client.is_user_authorized()}

# --- GİRİŞ VE AYARLAR ---
@app.post("/send-code")
async def send_code(data: dict):
    phone = data.get("phone")
    auth_data["phone"] = phone
    try:
        res = await client.send_code_request(phone)
        auth_data["phone_code_hash"] = res.phone_code_hash
        add_log(f"📲 Kod istendi: {phone}")
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/verify-login")
async def verify_login(data: dict):
    try:
        await client.sign_in(auth_data["phone"], data.get("code"), phone_code_hash=auth_data["phone_code_hash"])
        add_log("✅ Giriş başarılı!")
        return {"status": "success"}
    except SessionPasswordNeededError: return {"status": "2fa_required"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/verify-2fa")
async def verify_2fa(data: dict):
    try:
        await client.sign_in(password=data.get("password"))
        add_log("✅ 2FA Girişi başarılı!")
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/update-settings")
async def update_settings(data: dict):
    config["my_promo_link"] = data.get("my_link", config["my_promo_link"])
    config["storage_channel"] = data.get("storage", config["storage_channel"])
    add_log("⚙️ Ayarlar güncellendi.")
    return {"status": "success"}

# --- OPERASYON: GEÇMİŞİ TARA VE "Ads to ads?" YAZ ---
@app.post("/start-scan")
async def start_scan(background_tasks: BackgroundTasks):
    async def run_scan():
        add_log("🔍 Geçmiş DM'ler taranıyor...")
        count = 0
        async for dialog in client.iter_dialogs():
            if dialog.is_user:
                name = f"{dialog.name} {getattr(dialog.entity, 'username', '') or ''}".lower()
                if any(kw in name for kw in config["keywords"]):
                    try:
                        await client.send_message(dialog.id, "Ads to ads?")
                        waiting_list[dialog.id] = True
                        count += 1
                        add_log(f"✉️ Mesaj atıldı: {dialog.name}")
                        await asyncio.sleep(2.5) # Ban koruması
                    except: continue
        add_log(f"✅ Tarama bitti. {count} kişiye yazıldı.")
    background_tasks.add_task(run_scan)
    return {"status": "success"}

# --- ANA DİNLEME VE LİNK İLETME ---
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.is_private: return
    sender = await event.get_sender()
    sid = event.chat_id
    msg_text = event.raw_text.lower()
    
    # 1. TETİKLEYİCİ: İsminde keyword olan biri mesaj atarsa VEYA mesajda "ads" geçerse
    name_info = f"{sender.first_name or ''} {sender.last_name or ''} {sender.username or ''}".lower()
    is_target = any(kw in name_info for kw in config["keywords"]) or "ads" in msg_text

    if is_target and sid not in waiting_list:
        add_log(f"🔍 Yeni hedef: {sender.first_name}")
        await event.reply(f"Ads to ads? Okay, add mine first:\n{config['my_promo_link']}\n\nSend your link when done!")
        waiting_list[sid] = True

    # 2. LİNK YAKALAMA VE "DONE (LINK)" GÖNDERME
    elif sid in waiting_list and ("t.me/" in msg_text or "telegram.me/" in msg_text):
        try:
            # Mesajı kanala ilet
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            
            # Mesajın iletildiği kanaldaki linkini oluştur
            chan = config['storage_channel'].replace("@", "")
            msg_link = f"https://t.me/{chan}/{fwd.id}"
            
            # Kullanıcıya "Done (link)" mesajı at
            await event.reply(f"Done {msg_link}")
            
            add_log(f"🎯 Yanlama iletildi: {sender.first_name} -> {msg_link}")
            del waiting_list[sid]
        except Exception as e:
            add_log(f"❌ İletme hatası: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
