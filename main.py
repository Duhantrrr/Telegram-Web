from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
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
    add_log("🚀 Sistem Başlatıldı. Pusu ve Panel aktif.")

# --- 1. TELEGRAM KOMUTLARI (.add, .all, .ads, .setlink) ---
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
            await event.edit(f"✅ **@{u}** listeye eklendi.")
        else: await event.edit("⚠️ Zaten listede.")
    elif cmd == ".all":
        msg = f"📋 **LİSTE:**\n\n" + "\n".join([f"@{u}" for u in users])
        await event.edit(msg)
    elif cmd == ".setlink" and len(text) > 1:
        config["my_link"] = text[1]
        await event.edit(f"🔗 Link Güncellendi: {text[1]}")
    elif cmd == ".ads":
        await event.edit("🚀 Manuel Operasyon Başladı...")
        for u in users:
            try:
                await client.send_message(u, "Ads to ads?")
                await asyncio.sleep(6)
            except: continue
        await client.respond("🏁 İşlem bitti.")

# --- 2. LİNK PUSUSU VE OTOMATİK CEVAP ---
@client.on(events.NewMessage(incoming=True))
async def responder(event):
    if not event.is_private: return
    text = event.raw_text.lower()
    sender = await event.get_sender()
    name = sender.first_name or "Biri"

    # DURUM A: Link Atılırsa
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

    # DURUM B: Kelime Tetiklenirse
    elif any(w in text for w in ["ads", "go", "link", "ok", "sure", "done"]):
        await event.reply(config["my_link"])
        await asyncio.sleep(1)
        await event.respond("Go?")
        add_log(f"⚡ Kelime Tetiklendi: {name}")

# --- 3. WEB PANEL YOLLARI ---
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
        "count": len(get_list())
    }

@app.post("/update-link")
async def update_link(data: dict):
    config["my_link"] = data.get("link")
    add_log("⚙️ Link panelden güncellendi.")
    return {"status": "ok"}

@app.post("/manual-ads")
async def manual_ads(background_tasks: BackgroundTasks):
    async def run():
        users = get_list()
        add_log(f"📢 Panelden manuel operasyon başlatıldı: {len(users)} kişi.")
        for u in users:
            try:
                await client.send_message(u, "Ads to ads?")
                await asyncio.sleep(6)
            except: continue
        add_log("🏁 Manuel operasyon tamamlandı.")
    background_tasks.add_task(run)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
