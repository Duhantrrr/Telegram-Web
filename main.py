from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
import asyncio
import re
import uvicorn
import os

app = FastAPI()

# --- VERDİĞİN BİLGİLER ---
api_id = 27861882
api_hash = 'd1c630d699c775e846bf64aadd18aefd'
# Railway'de dosya kalıcı olsun diye session adını sabitliyoruz
client = TelegramClient('railway_session', api_id, api_hash)

config = {
    "my_promo_link": "https://t.me/kanalim",
    "storage_channel": "@kayit_kanali",
    "is_running": False,
    "phone": None,
    "phone_code_hash": None
}

@app.on_event("startup")
async def startup_event():
    await client.connect()

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# --- ADIM 1: TELEFON NUMARASI GÖNDER ---
@app.post("/send-code")
async def send_code(data: dict):
    phone = data.get("phone")
    config["phone"] = phone
    try:
        result = await client.send_code_request(phone)
        config["phone_code_hash"] = result.phone_code_hash
        return {"status": "success", "message": "Kod Telegram'dan gönderildi!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- ADIM 2: GELEN KODU GİR VE GİRİŞ YAP ---
@app.post("/verify-login")
async def verify_login(data: dict):
    code = data.get("code")
    try:
        await client.sign_in(config["phone"], code, phone_code_hash=config["phone_code_hash"])
        return {"status": "success", "message": "Giriş Başarılı! Artık operasyonu başlatabilirsiniz."}
    except SessionPasswordNeededError:
        return {"status": "error", "message": "İki aşamalı doğrulama (2FA) gerekli. Lütfen kaldırın veya kodu ona göre güncelleyin."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- ADIM 3: OPERASYONU BAŞLAT ---
@app.post("/start-ads-now")
async def start_ads_now(background_tasks: BackgroundTasks):
    if not await client.is_user_authorized():
        return {"status": "error", "message": "Önce giriş yapmalısınız!"}

    async def run_operation():
        config["is_running"] = True
        async for dialog in client.iter_dialogs():
            if "ads" in (dialog.name or "").lower():
                try:
                    await client.send_message(dialog.id, "Ad Today")
                    await asyncio.sleep(3)
                except: continue

    background_tasks.add_task(run_operation)
    return {"status": "success", "message": "Operasyon Başlatıldı!"}

if __name__ == "__main__":
    # Railway PORT değişkenini kullanır
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
