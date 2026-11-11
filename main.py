import os
import re
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
import uvicorn
import urllib.request

app = FastAPI()

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

# --- YAPAY ZEKA MÜDAHALE MOTORU (AI SELF-HEALING) ---
class AIAgent:
    def __init__(self):
        self.blacklist = set() # Sorunlu/DM kapalı kullanıcıları kara listeye alır
        self.safe_delay = 15   # AI dinamik hız kontrolü

    def handle_error(self, user: str, exc: Exception) -> dict:
        """Hata olduğunda yapay zeka müdahale eder ve kararlar alır."""
        exc_str = str(exc)
        
        # 1. DM Gizlilik Engeli
        if isinstance(exc, errors.UserPrivacyRestrictedError):
            self.blacklist.add(str(user).lower())
            add_log(f"🤖 [AI MÜDAHALE]: @{user} DM'lerini gizlemiş. AI bu hesabı kara listeye aldı, bir daha mesaj atılmayacak.")
            return {"action": "skip", "wait": 1}

        # 2. Kullanıcı Adı Geçersiz / Silinmiş
        elif isinstance(exc, (errors.UsernameNotOccupiedError, errors.UsernameInvalidError)):
            self.blacklist.add(str(user).lower())
            add_log(f"🤖 [AI MÜDAHALE]: @{user} hesabı silinmiş veya geçersiz. AI hedefi eledi.")
            return {"action": "skip", "wait": 1}

        # 3. Spam Tehlikesi (PeerFlood)
        elif isinstance(exc, errors.PeerFloodError):
            self.safe_delay = max(self.safe_delay + 5, 25)
            add_log(f"🚨 [AI ACİL FREN]: Telegram spam filtresi uyarısı verdi! AI hesabı korumak için hızı düşürdü ve 10 dk uykuya aldı.")
            return {"action": "sleep", "wait": 600}

        # 4. Telegram FloodWait
        elif isinstance(exc, errors.FloodWaitError):
            wait_time = exc.seconds + 5
            add_log(f"🤖 [AI MÜDAHALE]: Telegram {exc.seconds} sn bekleme istedi. AI güvenli uyku modunu aktif etti ({wait_time} sn).")
            return {"action": "sleep", "wait": wait_time}

        # 5. Diğer Beklenmeyen Hatalar
        else:
            add_log(f"🤖 [AI TEŞHİS]: @{user} için beklenmeyen hata: {exc_str}. AI bu adımı atlayıp sistemi koruyor.")
            return {"action": "skip", "wait": 5}

    def generate_reply_fallback(self, text: str) -> str:
        """Karşı taraf soru sorarsa AI'nın ikna edici hazır yanıtı"""
        lower = text.lower()
        if any(w in lower for w in ["kimsin", "bot musun", "bot musunuz"]):
            return "Kanal yöneticisiyim dostum, @ratlogscloud ve ana kanalım için karşılıklı reklam (Ads to ads) yapıyorum. Linkini atarsan hemen paylaşayım."
        elif any(w in lower for w in ["kaç k", "kac k", "abone", "uye", "üye", "istatistik"]):
            return f"Aktif kitlemiz var dostum, linkini gönder hemen @ratlogscloud kanalıma atıp Done linkini vereyim, sen de bizimkini paylaş: {config['channel_link']}"
        else:
            return f"Karşılıklı reklam yapıyoruz dostum. Sen linkini gönder, ben hemen kanalıma iletip kanıtını atayım. Bizim reklam: {config['promo_message']}"

    async def get_ai_response(self, incoming_text: str) -> str:
        """Gemini API anahtarı varsa gerçek LLM ile yanıt üretir, yoksa Fallback AI devreye girer"""
        if not config["gemini_api_key"]:
            return self.generate_reply_fallback(incoming_text)

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={config['gemini_api_key']}"
            prompt = (
                f"Sen bir Telegram kanal yöneticisisin. Karşıdaki kullanıcı Telegram'da sana şu mesajı yazdı: '{incoming_text}'. "
                f"Amacın onunla karşılıklı reklam (Ads to ads) yapmak. Kendi reklam linkin: '{config['channel_link']}'. "
                f"Ona çok kısa, samimi, Türkçe ve net bir şekilde reklam linkini atmasını ve karşılıklı paylaşacağımızı söyle. 1-2 cümleyi geçme."
            )
            payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=5))
            data = json.loads(res.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            add_log(f"⚠️ Gemini API hatası: {e}, yerel AI devreye girdi.")
            return self.generate_reply_fallback(incoming_text)

ai_engine = AIAgent()

def get_targets():
    targets = []
    try:
        if os.path.exists("ids.txt"):
            with open("ids.txt", "r", encoding="utf-8") as f:
                for line in f:
                    val = line.strip().replace("https://t.me/", "").replace("@", "")
                    if val and val.lower() not in ai_engine.blacklist:
                        targets.append(int(val) if val.isdigit() else val)
    except Exception as e:
        add_log(f"❌ ids.txt hatası: {e}")
    return targets

def get_client(session_str: str) -> TelegramClient:
    if not session_str:
        raise HTTPException(status_code=401, detail="Oturum anahtarı yok!")
    return TelegramClient(StringSession(session_str), API_ID, API_HASH)

# --- GELEN MESAJLARI YAPAY ZEKA İLE YANITLAMA ---
async def process_incoming_replies(client: TelegramClient):
    try:
        async for dialog in client.iter_dialogs(limit=15):
            if not dialog.is_user or dialog.entity.bot:
                continue
            
            msgs = await client.get_messages(dialog.id, limit=1)
            if not msgs or msgs[0].out:
                continue

            msg = msgs[0]
            text = (msg.raw_text or "").strip()
            lower_text = text.lower()

            # 1. Reklam Linki Geldiyse -> Kanala at, Done ver
            if "t.me/" in lower_text or "telegram.me/" in lower_text:
                fwd = await client.forward_messages(config["storage_channel"], msg)
                chan_name = config["storage_channel"].replace("@", "").strip()
                done_link = f"https://t.me/{chan_name}/{fwd.id}"
                
                await msg.reply(config["promo_message"])
                await asyncio.sleep(0.5)
                await client.send_message(dialog.id, "Go")
                await asyncio.sleep(0.5)
                await client.send_message(dialog.id, f"Done {done_link}")
                add_log(f"✅ Karşılıklı Reklam Yapıldı: {dialog.name} -> {done_link}")
                await client.send_read_acknowledge(dialog.id)

            # 2. Karşı taraf soru veya yazı yazdıysa -> AI Cevaplasın
            elif len(lower_text) > 1:
                smart_reply = await ai_engine.get_ai_response(text)
                await msg.reply(smart_reply)
                add_log(f"🤖 [AI AKILLI YANIT] {dialog.name} mesajına yanıt verdi: \"{smart_reply}\"")
                await client.send_read_acknowledge(dialog.id)

    except Exception as e:
        print(f"Gelen mesaj kontrol hatası: {e}")

# --- TEK TEK MESAJ GÖNDERME (AI KONTROLLÜ) ---
@app.post("/api/send-step")
async def send_step(data: dict):
    session_str = data.get("session_string", "").strip()
    target_index = data.get("index", 0)
    targets = get_targets()

    if not targets:
        return {"status": "error", "message": "Hedef listesi boş veya tümü AI tarafından elendi!"}

    if target_index >= len(targets):
        target_index = 0

    target_user = targets[target_index]
    client = get_client(session_str)

    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        return {"status": "unauthorized", "message": "Oturum düşmüş."}

    # Gelen kutusunu AI ile tara
    await process_incoming_replies(client)

    try:
        # En fazla 8 saniye bekle
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
            "delay": ai_engine.safe_delay
        }

    except Exception as e:
        # HATA OLDUĞUNDA YAPAY ZEKA DEVREYE GİRER
        decision = ai_engine.handle_error(target_user, e)
        next_idx = (target_index + 1) % len(targets)

        if decision["action"] == "sleep":
            return {"status": "flood", "wait": decision["wait"], "next_index": target_index}
        else:
            return {"status": "ok", "next_index": next_idx, "round_finished": (next_idx == 0), "delay": decision["wait"]}

    finally:
        await client.disconnect()

# --- GİRİŞ & LOG YOLLARI ---
@app.post("/auth/send-code")
async def send_code(data: dict):
    phone = data.get("phone", "").strip()
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        res = await client.send_code_request(phone)
        temp_session = client.session.save()
        add_log(f"📩 Doğrulama kodu istendi: {phone}")
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

        final_token = client.session.save()
        add_log("🎉 GİRİŞ BAŞARILI! Oturum kaydedildi.")
        return {"status": "ok", "session_string": final_token}
    except Exception as e:
        add_log(f"❌ Giriş hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.disconnect()

@app.get("/")
async def index():
    if not os.path.exists("index.html"):
        return HTMLResponse("<h3>index.html bulunamadı!</h3>", status_code=404)
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/get-logs")
async def get_logs():
    return {
        "logs": config["logs"],
        "promo_link": config["promo_message"],
        "target_count": len(get_targets()),
        "blacklisted_count": len(ai_engine.blacklist),
        "ai_delay": ai_engine.safe_delay
    }

@app.post("/update")
async def update(data: dict):
    if "link" in data and data["link"].strip():
        config["promo_message"] = data.get("link").strip()
    if "gemini_key" in data:
        config["gemini_api_key"] = data.get("gemini_key").strip()
        add_log("🤖 Gemini API Anahtarı güncellendi.")
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
