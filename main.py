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

auth_cache = {"phone": None, "hash": None}
config = {
    "my_link": "https://t.me/+TwaTRIkzseJINTdk",
    "storage": "@adscloud1",
    "ids_file": "ids.txt",
    "logs": []
}

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    entry = f"[{time_str}] {msg}"
    config["logs"].append(entry)
    if len(config["logs"]) > 50: config["logs"].pop(0)
    print(entry)

# ids.txt dosyasını temiz ve güvenli oku
def get_list():
    if not os.path.exists(config["ids_file"]): 
        return []
    with open(config["ids_file"], "r", encoding="utf-8") as f:
        # Satırları temizle, @ işaretini kaldır ve küçük harfe çevir
        return [line.strip().replace("@", "").lower() for line in f if line.strip()]

# ids.txt dosyasını kaydet
def save_list(lst):
    with open(config["ids_file"], "w", encoding="utf-8") as f:
        for u in sorted(set(lst)): # Tekrarları sil ve alfabetik diz
            f.write(f"{u}\n")

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem Başlatıldı. Komutlar aktif.")

# --- 1. TELEGRAM KOMUTLARI (.add, .delete, .all, .ads) ---
@client.on(events.NewMessage(outgoing=True, pattern=r'^\.'))
async def cmd_handler(event):
    text = event.raw_text.lower().split()
    cmd = text[0]
    
    # Her komutta listeyi taze oku
    users = get_list()

    # --- EKLEME ---
    if cmd == ".add" and len(text) > 1:
        u = text[1].replace("@", "").strip()
        if u not in users:
            users.append(u)
            save_list(users)
            await event.edit(f"✅ **@{u}** listeye eklendi.\n📊 Toplam: {len(users)}")
        else: 
            await event.edit(f"⚠️ **@{u}** zaten listede var.")
    
    # --- SİLME (DÜZELTİLDİ) ---
    elif cmd == ".delete" and len(text) > 1:
        u_to_del = text[1].replace("@", "").strip()
        if u_to_del in users:
            users.remove(u_to_del)
            save_list(users)
            await event.edit(f"🗑️ **@{u_to_del}** listeden silindi.\n📊 Kalan: {len(users)}")
            add_log(f"🗑️ @{u_to_del} silindi.")
        else:
            await event.edit(f"❌ **@{u_to_del}** listede bulunamadı.\n💡 `.all` yazarak listeyi kontrol et.")

    # --- LİSTE GÖRÜNTÜLEME ---
    elif cmd == ".all":
        if not users:
            await event.edit("📂 Liste şu an tamamen boş.")
        else:
            msg = f"📋 **GÜNCEL HEDEF LİSTESİ ({len(users)} kişi)**\n"
            msg += "--------------------------------\n"
            msg += "\n".join([f"{i+1}. @{u}" for i, u in enumerate(users)])
            await event.edit(msg)

    # --- TOPLU MESAJ ---
    elif cmd == ".ads":
        await event.edit(f"🚀 **Operasyon Başladı!**\n{len(users)} kişiye 6sn arayla yazılıyor...")
        sent = 0
        for u in users:
            try:
                await client.send_message(u, "Ads to ads?")
                sent += 1
                await asyncio.sleep(6)
            except: continue
        await client.respond(f"🏁 **Bitti!**\nToplam {sent} kişiye mesaj iletildi.")

# --- 2. LİNK PUSUSU (SİLSİLE CEVAP) ---
@client.on(events.NewMessage(incoming=True))
async def responder(event):
    if not event.is_private: return
    text = event.raw_text.lower()
    sender = await event.get_sender()
    
    if "t.me/" in text or "telegram.me/" in text:
        try:
            await event.reply(config["my_link"])
            await asyncio.sleep(1)
            await event.respond("Go?")
            await asyncio.sleep(1)
            fwd = await client.forward_messages(config["storage"], event.message)
            chan = config["storage"].replace("@", "")
            await event.respond(f"Done https://t.me/{chan}/{fwd.id}")
            await asyncio.sleep(1)
            await event.respond("You?")
            add_log(f"🎯 Silsile Tamamlandı: {sender.id}")
        except: pass
    elif any(w in text for w in ["ads", "go", "link", "ok"]):
        await event.reply(config["my_link"])
        await asyncio.sleep(1)
        await event.respond("Go?")

# --- PANEL YOLLARI ---
@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/status")
async def get_status():
    return {
        "logs": config["logs"],
        "is_auth": await client.is_user_authorized(),
        "my_link": config["my_link"],
        "users": get_list()
    }

@app.post("/update-link")
async def update_link(data: dict):
    config["my_link"] = data.get("link")
    return {"status": "ok"}

@app.post("/login/send-code")
async def send_code(data: dict):
    phone = data.get("phone")
    auth_cache["phone"] = phone
    try:
        res = await client.send_code_request(phone)
        auth_cache["hash"] = res.phone_code_hash
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-code")
async def verify_code(data: dict):
    try:
        await client.sign_in(auth_cache["phone"], data.get("code"), phone_code_hash=auth_cache["hash"])
        return {"status": "success"}
    except SessionPasswordNeededError: return {"status": "2fa_required"}
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/login/verify-2fa")
async def verify_2fa(data: dict):
    try:
        await client.sign_in(password=data.get("password"))
        return {"status": "success"}
    except Exception as e: return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
