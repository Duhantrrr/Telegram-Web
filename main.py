from fastapi import FastAPI, BackgroundTasks
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

auth_state = {"phone": None, "hash": None}
config = {
    "my_promo_link": "https://t.me/kanalim", # Panelden kaydedilecek
    "storage_channel": "@adscloud1",
    "is_auto_pilot_on": False,
    "logs": []
}

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    entry = f"[{time_str}] {msg}"
    config["logs"].append(entry)
    if len(config["logs"]) > 50: config["logs"].pop(0)
    print(entry)

def get_usernames():
    users = []
    if os.path.exists("ids.txt"):
        with open("ids.txt", "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip().replace("@", "")
                if u: users.append(u)
    return users

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Bot Gözlerini Açtı. Pusuda Bekliyor...")

# --- ANA ZEKA: MESAJLARI ANALİZ ET VE CEVAP VER ---
@client.on(events.NewMessage(incoming=True))
async def intelligent_handler(event):
    if not event.is_private: return 
    
    text = event.raw_text.lower()
    chat_id = event.chat_id
    sender = await event.get_sender()
    name = (sender.first_name or "Biri")

    # 1. DURUM: BİRİ LİNK ATARSA (YANLAMA VE KANIT)
    if "t.me/" in text or "telegram.me/" in text:
        try:
            add_log(f"🔥 Link Yakalandı: {name}")
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            chan = config["storage_channel"].replace("@", "")
            proof_link = f"https://t.me/{chan}/{fwd.id}"
            
            await event.respond(f"Done {proof_link}")
            await asyncio.sleep(1)
            await event.respond("You?")
            add_log(f"🎯 Yanlama OK & 'You?' Soruldu: {name}")
        except Exception as e:
            add_log(f"❌ Link Hatası: {str(e)[:40]}")

    # 2. DURUM: "ads", "go", "link", "ok" KELİMELERİ GEÇERSE (LİNKİMİZİ ATALIM)
    elif any(word in text for word in ["ads", "go", "link", "ok", "sure", "send"]):
        try:
            add_log(f"⚡ Kelime Tetiklendi ({text}): {name}")
            await event.reply(config["my_promo_link"])
            await asyncio.sleep(1)
            await event.respond("Go?")
            add_log(f"📤 Linkim + 'Go?' Gönderildi: {name}")
        except Exception as e:
            add_log(f"❌ Cevap Hatası: {str(e)[:40]}")

# --- 2 SAATTE BİR TOPLU MESAJ (BROADCAST) ---
async def broadcast_loop():
    while config["is_auto_pilot_on"]:
        targets = get_usernames()
        add_log(f"📢 Operasyon: {len(targets)} kişi (2 saatlik döngü)")
        sent = 0
        
        for username in targets:
            if not config["is_auto_pilot_on"]: break
            try:
                await client.send_message(username, "Ads to ads?")
                sent += 1
                add_log(f"✉️ Gitti: @{username}")
                await asyncio.sleep(6) # Güvenli hız
            except errors.FloodWaitError as e:
                add_log(f"🕒 Spam engeli: {e.seconds} sn bekleme...")
                await asyncio.sleep(e.seconds)
            except: continue
        
        add_log(f"🏁 Tur bitti. Başarılı: {sent}. 2 saat uyku.")
        await asyncio.sleep(7200) # 2 Saat Bekleme

# --- WEB PANEL YOLLARI ---
@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-data")
async def get_data():
    return {"logs": config["logs"], "is_auto": config["is_auto_pilot_on"], "is_auth": await client.is_user_authorized()}

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
        add_log("✅ Giriş başarılı!")
        return {"status": "success"}
    except SessionPasswordNeededError: return {"status": "2fa_required"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-2fa")
async def verify_2fa(data: dict):
    try:
        await client.sign_in(password=data.get("password"))
        add_log("✅ 2FA Doğrulandı.")
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/toggle")
async def toggle(background_tasks: BackgroundTasks):
    config["is_auto_pilot_on"] = not config["is_auto_pilot_on"]
    if config["is_auto_pilot_on"]:
        background_tasks.add_task(broadcast_loop)
    return {"status": "ok"}

@app.post("/update")
async def update(data: dict):
    config["my_promo_link"] = data.get("link")
    add_log("⚙️ Yeni link kaydedildi.")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
