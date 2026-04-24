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
# ... (Üst kısımlar aynı) ...

async def hourly_broadcast():
    while config["is_auto_pilot_on"]:
        targets = get_usernames()
        add_log(f"📢 Operasyon: {len(targets)} kişi (2 saatte bir döngüsü)")
        sent = 0
        
        for username in targets:
            if not config["is_auto_pilot_on"]: break
            try:
                await client.send_message(username, "Ads to ads?")
                sent += 1
                add_log(f"✅ İletildi: @{username}")
                await asyncio.sleep(6) # 6 saniye bekleme (Güvenli)
            except errors.FloodWaitError as e:
                add_log(f"🕒 Spam! {e.seconds} sn bekleniyor...")
                await asyncio.sleep(e.seconds)
            except: continue
        
        add_log(f"🏁 Tur bitti. Başarılı: {sent}. 2 SAAT UYKU MODU.")
        # 2 Saat Bekleme (7200 saniye)
        await asyncio.sleep(7200)

# ... (Alt kısımlar aynı) ...
