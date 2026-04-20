from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events
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

# Sistem Logları ve Hafıza
logs = []
waiting_for_link = {}
config = {
    "my_promo_link": "https://t.me/senin_kanalin",
    "storage_channel": "@kayit_kanali",
    "keywords": ["vouchs", "vouch", "ads", "dragon", "proof"],
    "is_active": True
}

def add_log(msg):
    time_str = datetime.now().strftime("%H:%M:%S")
    full_msg = f"[{time_str}] {msg}"
    logs.append(full_msg)
    if len(logs) > 30: logs.pop(0) # Sadece son 30 logu tut
    print(full_msg)

@app.on_event("startup")
async def startup():
    await client.connect()
    add_log("🚀 Sistem Başlatıldı. Telegram Bağlantısı Hazır.")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# Web panelinin logları çekmesi için API
@app.get("/get-logs")
async def get_logs():
    is_auth = await client.is_user_authorized()
    return {"logs": logs, "is_auth": is_auth}

@app.post("/update-settings")
async def update_settings(data: dict):
    config["my_promo_link"] = data.get("my_link", config["my_promo_link"])
    config["storage_channel"] = data.get("storage", config["storage_channel"])
    if data.get("keywords"):
        config["keywords"] = [k.strip().lower() for k in data.get("keywords").split(",")]
    add_log("⚙️ Ayarlar Güncellendi.")
    return {"status": "success"}

# --- ANA OTOMASYON MOTORU ---
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.is_private: return
    
    sender = await event.get_sender()
    if not sender: return
    
    sid = event.chat_id
    msg_text = event.raw_text.lower()
    
    # Kimlik Bilgilerini Birleştir (Ad + Soyad + Username)
    fname = (sender.first_name or "").lower()
    lname = (sender.last_name or "").lower()
    uname = (sender.username or "").lower()
    identity = f"{fname} {lname} @{uname}"

    # Filtreleme Kontrolü
    search_area = f"{msg_text} {identity}"
    found_keyword = next((kw for kw in config["keywords"] if kw in search_area), None)

    # DURUM 1: Anahtar kelime yakalandı ve henüz link atmadık
    if found_keyword and sid not in waiting_for_link:
        add_log(f"🔍 YAKALANDI: '{found_keyword}' kelimesi bulundu. Kişi: {identity}")
        try:
            await event.reply(f"Ads to ads? Okay, add mine first:\n{config['my_promo_link']}\n\nSend your link when you're done!")
            waiting_for_link[sid] = True
            add_log(f"✅ Yanıt verildi, link bekleniyor: {sender.first_name}")
        except Exception as e:
            add_log(f"❌ Mesaj Hatası: {e}")

    # DURUM 2: Link beklediğimiz kişiden link gelirse
    elif sid in waiting_for_link:
        link_match = re.search(r'(t\.me/[\w/]+|https?://t\.me/[\w/]+)', msg_text)
        if link_match:
            captured_link = link_match.group(0)
            add_log(f"🔗 Link Tespit Edildi: {captured_link}")
            try:
                # Kanala ilet
                await client.send_message(
                    config["storage_channel"], 
                    f"📥 YENİ YANLAMA\n👤 Kişi: {identity}\n🔗 Link: {captured_link}"
                )
                await event.reply("Done! I added yours to my channel too. Thanks!")
                add_log(f"🎯 İŞLEM TAMAM: {sender.first_name} linki kanala yönlendirildi.")
                del waiting_for_link[sid]
            except Exception as e:
                add_log(f"❌ Kanala İletme Hatası: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
