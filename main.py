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

auth_state = {"phone": None, "hash": None}
config = {
    "my_promo_link": "https://t.me/kanalim",
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

# ids.txt içindeki USERNAME'leri oku
def get_usernames():
    users = []
    if os.path.exists("ids.txt"):
        with open("ids.txt", "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip().replace("@", "") # @ varsa temizle
                if u: users.append(u)
    return users

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem hazır. Username pususu aktif.")

# --- LİNK GELDİĞİNDE: LİNK + GO + DONE + YOU ---
@client.on(events.NewMessage(incoming=True))
async def handle_incoming(event):
    if not event.is_private: return 
    text = event.raw_text.lower()
    if "t.me/" in text or "telegram.me/" in text:
        try:
            # 1. Kendi linkini at
            await event.reply(config["my_promo_link"])
            await asyncio.sleep(1)
            # 2. Go? yaz
            await event.respond("Go?")
            await asyncio.sleep(1)
            # 3. Kanala ilet
            fwd = await client.forward_messages(config["storage_channel"], event.message)
            # 4. Done + Kanıt linki
            chan = config["storage_channel"].replace("@", "")
            await event.respond(f"Done https://t.me/{chan}/{fwd.id}")
            await asyncio.sleep(1)
            # 5. You? yaz
            await event.respond("You?")
            add_log(f"🎯 Yanlama yapıldı: {event.chat_id}")
        except: pass

# --- SAATLİK OPERASYON (USERNAME ÜZERİNDEN) ---
async def hourly_broadcast():
    while config["is_auto_pilot_on"]:
        targets = get_usernames()
        add_log(f"📢 Operasyon: {len(targets)} kullanıcı hedefleniyor.")
        sent = 0
        fail = 0
        
        for username in targets:
            if not config["is_auto_pilot_on"]: break
            try:
                # Username üzerinden mesaj gönder
                await client.send_message(username, "Ads to ads?")
                sent += 1
                add_log(f"✅ Gitti: @{username} ({sent}/{len(targets)})")
                await asyncio.sleep(7) # Spam yememek için süreyi artırdık
            except errors.FloodWaitError as e:
                add_log(f"🕒 Telegram engeli: {e.seconds} sn bekleme...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                fail += 1
                continue
        
        add_log(f"🏁 Tur bitti. Başarılı: {sent} | Başarısız: {fail}")
        await asyncio.sleep(3600)

# --- WEB PANEL API (Arayüz aynı kalabilir) ---
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
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-code")
async def verify_code(data: dict):
    try:
        await client.sign_in(auth_state["phone"], data.get("code"), phone_code_hash=auth_state["hash"])
        return {"status": "success"}
    except SessionPasswordNeededError: return {"status": "2fa_required"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-2fa")
async def verify_2fa(data: dict):
    try:
        await client.sign_in(password=data.get("password"))
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/toggle")
async def toggle(background_tasks: BackgroundTasks):
    config["is_auto_pilot_on"] = not config["is_auto_pilot_on"]
    if config["is_auto_pilot_on"]:
        background_tasks.add_task(hourly_broadcast)
    return {"status": "ok"}

@app.post("/update")
async def update(data: dict):
    config["my_promo_link"] = data.get("link")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
