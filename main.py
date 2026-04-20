from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events
import asyncio
import re
import uvicorn
import os

app = FastAPI()

# --- AYARLAR ---
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
client = TelegramClient('railway_session', api_id, api_hash)

# Dinamik Ayarlar
config = {
    "my_promo_link": "https://t.me/kanalim",
    "storage_channel": "@kayit_kanali",
    "keywords": ["vouchs", "vouch", "ads", "dragon", "proof"],
    "is_running": True
}

# Link beklediğimiz kullanıcılar
waiting_for_link = {}

@app.on_event("startup")
async def startup_event():
    await client.connect()
    print("Sistem Aktif: Filtreler ve Dinleme Başlatıldı.")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/update-settings")
async def update_settings(data: dict):
    config["my_promo_link"] = data.get("my_link", config["my_promo_link"])
    config["storage_channel"] = data.get("storage", config["storage_channel"])
    if data.get("keywords"):
        config["keywords"] = [k.strip().lower() for k in data.get("keywords").split(",")]
    return {"status": "success", "message": "Ayarlar güncellendi!"}

# --- GELİŞMİŞ OTOMATİK DİNLEME ---
@client.on(events.NewMessage(incoming=True))
async def auto_handler(event):
    if not event.is_private: return
    
    sender = await event.get_sender()
    if not sender: return

    chat_id = event.chat_id
    msg_text = event.raw_text.lower()
    
    # Kullanıcı bilgilerini topla (Ad, Soyad, Username)
    first_name = (sender.first_name or "").lower()
    last_name = (sender.last_name or "").lower()
    username = (sender.username or "").lower()
    
    # Arama yapılacak havuz: Mesaj + Ad + Soyad + Username
    search_pool = f"{msg_text} {first_name} {last_name} {username}"

    # Filtre kontrolü: Havuzda anahtar kelimelerden biri var mı?
    has_keyword = any(kw in search_pool for kw in config["keywords"])

    # 1. DURUM: Kelime eşleşti ve henüz link istemedik
    if has_keyword and chat_id not in waiting_for_link:
        await event.reply(f"Ads to ads? Okay, add mine first:\n{config['my_promo_link']}\n\nSend your link when you're done!")
        waiting_for_link[chat_id] = True
        print(f"-> Eşleşme Bulundu ({sender.first_name}): {search_pool}")

    # 2. DURUM: Link beklediğimiz kişiden mesaj geldi
    elif chat_id in waiting_for_link:
        link_match = re.search(r'(t\.me/[\w/]+|https?://t\.me/[\w/]+)', msg_text)
        if link_match:
            captured_link = link_match.group(0)
            # Kayıt kanalına gönder
            await client.send_message(
                config["storage_channel"], 
                f"📥 YANLAMA GELDİ!\n👤 Kişi: {sender.first_name} (@{sender.username})\n🔗 Link: {captured_link}"
            )
            await event.reply("Done! I added yours too. Thanks!")
            del waiting_for_link[chat_id] # Takibi bitir

# --- MANUEL TOPLU TARAMA ---
@app.post("/start-ads-now")
async def broadcast(background_tasks: BackgroundTasks):
    async def run():
        async for dialog in client.iter_dialogs():
            name = (dialog.name or "").lower()
            # Diyalog isminde (takma ad) kelime kontrolü
            if any(kw in name for kw in config["keywords"]):
                try:
                    await client.send_message(dialog.id, "Ads to ads?")
                    await asyncio.sleep(3)
                except: continue
    background_tasks.add_task(run)
    return {"status": "success"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
