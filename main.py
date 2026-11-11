import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
import httpx
import uvicorn

app = FastAPI()

# --- DOSYA VE DİZİN AYARLARI (VERCEL ÇÖKME KORUMASI) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

API_ID = int(os.environ.get("API_ID", 16896485))
API_HASH = os.environ.get("API_HASH", "29b5bb9351b4cb3738d73abaf5eb28ca")

config = {
    "channel_link": "https://t.me/+vbR5re1Xa-VkOWE0",
    "storage_channel": "@ratlogscloud",
    "promo_message": "Ads to ads @tgciyim https://t.me/+vbR5re1Xa-VkOWE0",
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "logs": []
}

def add_log(msg: str):
    time_str = datetime.now().strftime("%H:%M:%S")
    entry = f"[{time_str}] {msg}"
    config["logs"].append(entry)
    if len(config["logs"]) > 100:
        config["logs"].pop(0)
    print(entry)

# Güvenli ids.txt okuma
def get_targets():
    targets = []
    file_path = os.path.join(BASE_DIR, "ids.txt")
    if not os.path.exists(file_path):
        file_path = "ids.txt"

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    val = line.strip().replace("https://t.me/", "").replace("@", "")
                    if val:
                        targets.append(int(val) if val.isdigit() else val)
        except Exception as e:
            add_log(f"❌ ids.txt okuma hatası: {e}")
    return targets

# --- GERÇEK GOOGLE GEMINI AI MOTORU ---
class RealGeminiAI:
    def __init__(self):
        self.blacklist = set()

    async def call_gemini(self, prompt: str, api_key: str) -> str:
        key = api_key or config["gemini_api_key"]
        if not key:
            return ""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4}
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                else:
                    add_log(f"⚠️ Gemini API Yanıtı ({res.status_code}): {res.text[:100]}")
        except Exception as e:
            add_log(f"⚠️ Gemini Bağlantı Hatası: {e}")
        return ""

    async def decide_on_error(self, user: str, error_msg: str, api_key: str) -> dict:
        """Hata olduğunda Yapay Zeka teşhis koyar ve ne yapacağını koda söyler."""
        prompt = (
            f"You are the autonomous incident commander for a Telegram bot. An error occurred while messaging @{user}.\n"
            f"Error details: '{error_msg}'.\n"
            f"Analyze the error and decide the action. Respond ONLY with a valid JSON in this exact format:\n"
            f'{{"action": "skip" or "sleep", "wait_seconds": 15, "blacklist": true or false, "reason": "Short explanation in Turkish"}}\n'
            f"Rules:\n"
            f"- If user restricted DMs or not found: action='skip', wait_seconds=1, blacklist=true.\n"
            f"- If FloodWait or spam restriction: action='sleep', wait_seconds=(seconds required or 300), blacklist=false.\n"
            f"- If network or unknown: action='skip', wait_seconds=5, blacklist=false."
        )
        raw = await self.call_gemini(prompt, api_key)
        try:
            # Markdown json bloklarını temizle
            clean = raw.replace("```json", "").replace("```", "").strip()
            decision = json.loads(clean)
            if decision.get("blacklist"):
                self.blacklist.add(str(user).lower())
            add_log(f"🤖 [AI MÜDAHALE]: {decision.get('reason')} (Bekleme: {decision.get('wait_seconds')}s)")
            return decision
        except:
            # Fallback
            if "privacy" in error_msg.lower() or "not occupied" in error_msg.lower():
                self.blacklist.add(str(user).lower())
                return {"action": "skip", "wait_seconds": 1, "reason": "DM kapalı veya hesap silinmiş, atlandı."}
            return {"action": "skip", "wait_seconds": 5, "reason": "Bilinmeyen hata, sonraki kişiye geçiliyor."}

    async def reply_to_english_user(self, text: str, user_name: str, api_key: str) -> str:
        """İngiliz hedefler mesaj attığında Gemini ikna edici İngilizce yanıt üretir."""
        prompt = (
            f"You are @tgciyim, a top-tier Telegram channel owner doing 'Ads to ads' (cross-promotion) with other channel admins.\n"
            f"Your channel link to promote: {config['channel_link']}\n"
            f"Your proof channel where you forward their ad: {config['storage_channel']}\n"
            f"An English-speaking channel owner named '{user_name}' sent you this message: '{text}'\n\n"
            f"Task: Write a short, natural, convincing English reply (1-2 sentences max). "
            f"Direct them to drop their channel link so we can exchange right now (done for done). "
            f"Do not sound robotic. Sound like a real busy admin."
        )
        reply = await self.call_gemini(prompt, api_key)
        if not reply:
            return f"Hey mate! Let's do ads to ads. Drop your link and I'll post it on {config['storage_channel']} with proof link right away. Here's ours: {config['channel_link']}"
        return reply

gemini_ai = RealGeminiAI()

# --- GELEN MESAJLARI İNCELE VE CEVAPLA ---
async def inspect_and_reply(client: TelegramClient, api_key: str):
    try:
        async for dialog in client.iter_dialogs(limit=10):
            if not dialog.is_user or dialog.entity.bot:
                continue

            msgs = await client.get_messages(dialog.id, limit=1)
            if not msgs or msgs[0].out:
                continue

            msg = msgs[0]
            text = (msg.raw_text or "").strip()
            lower = text.lower()
            name = dialog.name or "User"

            # 1. Kullanıcı link attıysa -> Ratlogscloud'a ilet ve Done ver
            if "t.me/" in lower or "telegram.me/" in lower:
                fwd = await client.forward_messages(config["storage_channel"], msg)
                chan_name = config["storage_channel"].replace("@", "").strip()
                done_link = f"https://t.me/{chan_name}/{fwd.id}"

                await msg.reply(config["promo_message"])
                await asyncio.sleep(0.5)
                await client.send_message(dialog.id, "Go")
                await asyncio.sleep(0.5)
                await client.send_message(dialog.id, f"Done {done_link}")
                add_log(f"✅ Karşılıklı Reklam Yapıldı: {name} -> {done_link}")
                await client.send_read_acknowledge(dialog.id)

            # 2. Karşı taraf İngilizce soru sorduysa -> Yapay Zeka cevaplasın
            elif len(lower) > 1:
                add_log(f"📩 {name} yazdı: \"{text}\" -> Yapay Zeka inceliyor...")
                ai_answer = await gemini_ai.reply_to_english_user(text, name, api_key)
                await msg.reply(ai_answer)
                add_log(f"🤖 [AI İNGİLİZCE YANIT] {name}: \"{ai_answer}\"")
                await client.send_read_acknowledge(dialog.id)

    except Exception as e:
        print(f"Gelen kutusu kontrol hatası: {e}")

# --- TEK TEK MESAJ GÖNDERME ADIMI (AI GÖZETİMİNDE) ---
@app.post("/api/send-step")
async def send_step(data: dict):
    session_str = data.get("session_string", "").strip()
    api_key = data.get("gemini_key", "").strip()
    target_index = data.get("index", 0)
    
    all_targets = get_targets()
    targets = [t for t in all_targets if str(t).lower() not in gemini_ai.blacklist]

    if not targets:
        return {"status": "error", "message": "Hedef listesi boş veya tümü AI tarafından elendi!"}

    if target_index >= len(targets):
        target_index = 0

    target_user = targets[target_index]
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {"status": "unauthorized", "message": "Oturum düşmüş."}

        # Gelen kutusunu yapay zekaya devret
        await inspect_and_reply(client, api_key)

        # Mesajı gönder (8 saniye zaman aşımı korumalı)
        await asyncio.wait_for(
            client.send_message(target_user, config["promo_message"]),
            timeout=8.0
        )
        add_log(f"✉️ ({target_index + 1}/{len(targets)}) Gönderildi: @{target_user}")
        next_idx = (target_index + 1) % len(targets)
        return {
            "status": "ok",
            "next_index": next_idx,
            "round_finished": (next_idx == 0),
            "delay": 15
        }

    except Exception as exc:
        # BİR HATA OLDUĞUNDA GEMINI'YE BİLDİRİM GİDER
        add_log(f"⚠️ Hata oluştu (@{target_user}). Yapay Zekaya bildiriliyor...")
        decision = await gemini_ai.decide_on_error(str(target_user), str(exc), api_key)
        next_idx = (target_index + 1) % len(targets)

        if decision.get("action") == "sleep":
            return {"status": "flood", "wait": decision.get("wait_seconds", 300), "next_index": target_index}
        else:
            return {"status": "ok", "next_index": next_idx, "round_finished": (next_idx == 0), "delay": decision.get("wait_seconds", 5)}

    finally:
        if client.is_connected():
            await client.disconnect()

# --- GİRİŞ & PANEL YOLLARI ---
@app.post("/auth/send-code")
async def send_code(data: dict):
    phone = data.get("phone", "").strip()
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        res = await client.send_code_request(phone)
        temp_session = client.session.save()
        add_log(f"📩 Giriş kodu istendi: {phone}")
        return {
            "status": "ok",
            "phone": phone,
            "phone_code_hash": res.phone_code_hash,
            "temp_session": temp_session
        }
    except Exception as e:
        add_log(f"❌ Kod hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.disconnect()

@app.post("/auth/verify")
async def verify_code(data: dict):
    phone = data.get("phone", "").strip()
    code = data.get("code", "").strip()
    password = data.get("password", "").strip()
    phone_code_hash = data.get("phone_code_hash", "").strip()
    temp_session = data.get("temp_session", "").strip()

    client = TelegramClient(StringSession(temp_session), API_ID, API_HASH)
    await client.connect()
    try:
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except errors.SessionPasswordNeededError:
            if not password:
                return {"status": "2fa_required", "detail": "2FA Şifresi gerekli!"}
            await client.sign_in(password=password)

        token = client.session.save()
        add_log("🎉 GİRİŞ BAŞARILI! Oturum tarayıcıya kilitlendi.")
        return {"status": "ok", "session_string": token}
    except Exception as e:
        add_log(f"❌ Giriş hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.disconnect()

@app.get("/")
async def index():
    html_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(html_path):
        html_path = "index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-logs")
async def get_logs():
    return {
        "logs": config["logs"],
        "promo_link": config["promo_message"],
        "target_count": len(get_targets()),
        "blacklisted_count": len(gemini_ai.blacklist)
    }

@app.post("/update")
async def update(data: dict):
    if "link" in data and data["link"].strip():
        config["promo_message"] = data.get("link").strip()
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
