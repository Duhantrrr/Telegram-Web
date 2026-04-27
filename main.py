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

# Sistem Belleği
auth_cache = {"phone": None, "hash": None}
config = {
    "my_link": "https://t.me/+TwaTRIkzseJINTdk",
    "storage": "@adscloud1",
    "ids_file": "ids.txt",
    "is_oto_active": False, # Oto pilot durumu
    "logs": []
}

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    entry = f"[{time_str}] {msg}"
    config["logs"].append(entry)
    if len(config["logs"]) > 50: config["logs"].pop(0)
    print(entry)

def get_list():
    if not os.path.exists(config["ids_file"]): return []
    with open(config["ids_file"], "r") as f:
        return [line.strip().replace("@", "") for line in f if line.strip()]

def save_list(lst):
    with open(config["ids_file"], "w") as f:
        for u in lst: f.write(f"{u}\n")

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem Başlatıldı. Giriş bekleniyor...")

# --- GİRİŞ API SİSTEMİ ---
@app.post("/login/send-code")
async def send_code(data: dict):
    phone = data.get("phone")
    auth_cache["phone"] = phone
    try:
        res = await client.send_code_request(phone)
        auth_cache["hash"] = res.phone_code_hash
        add_log(f"📲 Kod istendi: {phone}")
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-code")
async def verify_code(data: dict):
    try:
        await client.sign_in(auth_cache["phone"], data.get("code"), phone_code_hash=auth_cache["hash"])
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

# --- OTO PİLOT GÖREVİ (Arka Planda Sürekli Çalışır) ---
async def oto_pilot_loop():
    while True:
        if config["is_oto_active"]:
            users = get_list()
            add_log(f"🤖 Oto-Pilot turu başladı: {len(users)} kişi.")
            for u in users:
                if not config["is_oto_active"]: break
                try:
                    await client.send_message(u, "Ads to ads?")
                    await asyncio.sleep(8) # Güvenli hız
                except errors.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except: continue
            add_log("💤 Tur bitti. 1 saat uyku.")
            await asyncio.sleep(7200) # 1 saat bekleme
        else:
            await asyncio.sleep(10)

# --- TELEGRAM KOMUTLARI (.add, .delete, .all, .oto) ---
@client.on(events.NewMessage(outgoing=True, pattern=r'^\.'))
async def cmd_handler(event):
    text = event.raw_text.lower().split()
    cmd = text[0]
    users = get_list()

    if cmd == ".add" and len(text) > 1:
        u = text[1].replace("@", "")
        if u not in users:
            users.append(u)
            save_list(users)
            await event.edit(f"✅ **@{u}** eklendi.")
        else: await event.edit("⚠️ Zaten listede.")
    elif cmd == ".all":
        msg = f"📋 **LİSTE:**\n\n" + "\n".join([f"@{u}" for u in users])
        await event.edit(msg)
    elif cmd == ".oto":
        if len(text) > 1:
            config["is_oto_active"] = (text[1] == "on")
            await event.edit(f"🤖 **Oto-Pilot:** {'AÇIK' if config['is_oto_active'] else 'KAPALI'}")

# --- PUSU MODU (LİNK GELİNCE SİLSİLE CEVAP) ---
@client.on(events.NewMessage(incoming=True))
async def responder(event):
    if not event.is_private: return
    text = event.raw_text.lower()
    sender = await event.get_sender()
    name = (sender.first_name or "Biri")

    if "t.me/" in text or "telegram.me/" in text:
        try:
            add_log(f"🔥 Link Yakalandı: {name}")
            await event.reply(config["my_link"])
            await asyncio.sleep(1)
            await event.respond("Go?")
            await asyncio.sleep(1)
            fwd = await client.forward_messages(config["storage"], event.message)
            chan = config["storage"].replace("@", "")
            await event.respond(f"Done https://t.me/{chan}/{fwd.id}")
            await asyncio.sleep(1)
            await event.respond("You?")
            add_log(f"🎯 Silsile Tamamlandı: {name}")
        except: pass
    elif any(w in text for w in ["ads", "go", "link", "ok"]):
        await event.reply(config["my_link"])
        await asyncio.sleep(1)
        await event.respond("Go?")

# --- WEB PANEL YOLLARI ---
@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/status")
async def get_status():
    return {
        "logs": config["logs"],
        "is_auth": await client.is_user_authorized(),
        "is_oto": config["is_oto_active"],
        "my_link": config["my_link"]
    }

@app.post("/toggle-oto")
async def toggle_oto():
    config["is_oto_active"] = not config["is_oto_active"]
    return {"status": "ok"}

@app.post("/update-link")
async def update_link(data: dict):
    config["my_link"] = data.get("link")
    return {"status": "ok"}

if __name__ == "__main__":
    # Arka plan görevini başlat
    loop = asyncio.get_event_loop()
    loop.create_task(oto_pilot_loop())
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
