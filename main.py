from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events
import asyncio
import re
import uvicorn

app = FastAPI()

# --- VERDİĞİN BİLGİLER ---
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
client = TelegramClient('operasyon_oturum', api_id, api_hash)

# Sistem Hafızası
chat_states = {}
config = {
    "my_promo_link": "https://t.me/kanalim",
    "storage_channel": "@kayit_kanali",
    "is_running": False
}

@app.on_event("startup")
async def startup_event():
    await client.connect()

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# --- OPERASYON: İsminde 'ads' geçenlere "Ad Today" yaz ---
@app.post("/start-ads-now")
async def start_ads_now(background_tasks: BackgroundTasks):
    if not await client.is_user_authorized():
        return {"status": "error", "message": "Giriş yapılmamış!"}

    async def run_operation():
        config["is_running"] = True
        print("Operasyon başladı: 'ads' içerenler taranıyor...")
        
        async for dialog in client.iter_dialogs():
            name = (dialog.name or "").lower()
            if "ads" in name:
                try:
                    # Mesajı gönder
                    await client.send_message(dialog.id, "Ad Today")
                    # Bu kişiyi takibe al (Cevap gelirse süreç ilerlesin)
                    chat_states[dialog.id] = "INITIATED"
                    print(f"Mesaj gönderildi: {dialog.name}")
                    await asyncio.sleep(3) # Ban yememek için 3 saniye bekle
                except Exception as e:
                    print(f"Hata ({dialog.name}): {e}")

    background_tasks.add_task(run_operation)
    return {"status": "success", "message": "Operasyon Başlatıldı!"}

# --- OTOMATİK CEVAP VE TAKİP MEKANİZMASI ---
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not config["is_running"]: return
    
    sid = event.chat_id
    msg = event.raw_text.lower()

    # EĞER karşı taraf "add to" yazarsa (Süreç başlasın)
    if "add to" in msg:
        chat_states[sid] = "WAITING_LINK"
        await event.reply(f"Sure! Add mine first: {config['my_promo_link']} \nSend your link when done!")

    # EĞER karşı taraf link gönderirse (Yakalayıp kanala at)
    elif sid in chat_states and chat_states[sid] == "WAITING_LINK":
        link_match = re.search(r'(t\.me/[\w/]+|https?://t\.me/[\w/]+)', msg)
        if link_match:
            await client.forward_messages(config["storage_channel"], event.message)
            chat_states[sid] = "DONE"
            await event.reply("Done! I added yours too. Any more channels?")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
