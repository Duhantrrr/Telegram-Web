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

# Vercel'in ilk okuduğu nesne
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

# Güvenli Hedef Listesi Okuma (Dosya yoksa bile çökmez)
DEFAULT_USERS = [
    "ThinkCaptain01", "BayGeneral", "AdsbyAdsmy", "xDarkLogx3", "GTX_E",
    "notdelo", "DK_CE", "ansuport", "griftking", "BASEDCLOUD",
    "Crax_GoCloud", "therealcapybara", "sabs_gp", "Jeremy_UHQ", "cc_card_pro",
    "ssoup7744", "GHO_ST1", "SyntaXHunt5r", "BeastCloudAdmin", "Valid_source_data",
    "Rocheman7", "darui_owner", "skylinesup", "lucifersupportcl", "Army_dat4",
    "ciasty", "Kommander0", "cTL1337x", "OGvalid", "saya_owner",
    "BaseCloudAdmin", "arealProxy_Support", "marco_controller1", "Kraken_Cloud_Admin", "Validmail_Boss",
    "ZEWX00", "linuxdebain", "Jayvxxtenxx", "BAT_CLOUD_ADS", "HellSkeyBreach",
    "ZeroSheII", "WAS_LOST", "Vonez438", "Zero_Trace9", "AccessVortex"
]

def get_targets():
    targets = []
    try:
        if os.path.exists("ids.txt"):
            with open("ids.txt", "r", encoding="utf-8") as f:
                for line in f:
                    val = line.strip().replace("https://t.me/", "").replace("@", "")
                    if val:
                        targets.append(int(val) if val.isdigit() else val)
    except:
        pass
    return targets if targets else DEFAULT_USERS

# --- GERÇEK GEMINI YAPAY ZEKA MOTORU ---
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
            async with httpx.AsyncClient(timeout=7.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except:
            pass
        return ""

    async def decide_on_error(self, user: str, error_msg: str, api_key: str) -> dict:
        prompt = (
            f"You are the incident commander for a Telegram bot. An error happened while messaging @{user}: '{error_msg}'.\n"
            f"Respond ONLY with a JSON:\n"
            f'{{"action": "skip" or "sleep", "wait_seconds": 15, "blacklist": true or false, "reason": "Explanation in Turkish"}}'
        )
        raw = await self.call_gemini(prompt, api_key)
        try:
            clean = raw.replace("```json", "").replace("```", "").strip()
            decision = json.loads(clean)
            if decision.get("blacklist"):
                self.blacklist.add(str(user).lower())
            add_log(f"🤖 [AI MÜDAHALE]: {decision.get('reason')} ({decision.get('wait_seconds')}s bekleme)")
            return decision
        except:
            if "privacy" in error_msg.lower() or "occupied" in error_msg.lower():
                self.blacklist.add(str(user).lower())
                return {"action": "skip", "wait_seconds": 1, "reason": "DM kapalı veya hesap silinmiş, atlandı."}
            return {"action": "skip", "wait_seconds": 5, "reason": "Bilinmeyen hata, sonraki kişiye geçildi."}

    async def reply_to_english_user(self, text: str, user_name: str, api_key: str) -> str:
        prompt = (
            f"You are @tgciyim, managing channel {config['channel_link']}. You are doing 'Ads to ads' cross promo.\n"
            f"An English channel owner named '{user_name}' sent: '{text}'\n"
            f"Task: Write a short, natural English reply (1-2 sentences). "
            f"Tell them to drop their channel link right now so we both post each other's ad (done for done). "
            f"Sound like a genuine busy admin, not a robot."
        )
        reply = await self.call_gemini(prompt, api_key)
        if not reply:
            return f"Hey! Let's do ads to ads. Drop your link and I'll forward it to {config['storage_channel']} with proof link now. Here's mine: {config['channel_link']}"
        return reply

gemini_ai = RealGeminiAI()

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

            elif len(lower) > 1:
                add_log(f"📩 {name} yazdı: \"{text}\" -> AI yanıtlıyor...")
                ai_answer = await gemini_ai.reply_to_english_user(text, name, api_key)
                await msg.reply(ai_answer)
                add_log(f"🤖 [AI İNGİLİZCE YANIT] {name}: \"{ai_answer}\"")
                await client.send_read_acknowledge(dialog.id)
    except:
        pass

@app.post("/api/send-step")
async def send_step(data: dict):
    session_str = data.get("session_string", "").strip()
    api_key = data.get("gemini_key", "").strip()
    target_index = data.get("index", 0)
    
    all_targets = get_targets()
    targets = [t for t in all_targets if str(t).lower() not in gemini_ai.blacklist]

    if not targets:
        return {"status": "error", "message": "Hedef kalmadı veya hepsi elendi!"}

    if target_index >= len(targets):
        target_index = 0

    target_user = targets[target_index]
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {"status": "unauthorized", "message": "Oturum açık değil."}

        await inspect_and_reply(client, api_key)

        await asyncio.wait_for(
            client.send_message(target_user, config["promo_message"]),
            timeout=8.0
        )
        add_log(f"✉️ ({target_index + 1}/{len(targets)}) Gönderildi: @{target_user}")
        next_idx = (target_index + 1) % len(targets)
        return {"status": "ok", "next_index": next_idx, "round_finished": (next_idx == 0), "delay": 15}

    except Exception as exc:
        add_log(f"⚠️ Hata oluştu (@{target_user}). Yapay zeka inceliyor...")
        decision = await gemini_ai.decide_on_error(str(target_user), str(exc), api_key)
        next_idx = (target_index + 1) % len(targets)

        if decision.get("action") == "sleep":
            return {"status": "flood", "wait": decision.get("wait_seconds", 300), "next_index": target_index}
        else:
            return {"status": "ok", "next_index": next_idx, "round_finished": (next_idx == 0), "delay": decision.get("wait_seconds", 5)}

    finally:
        if client.is_connected():
            await client.disconnect()

@app.post("/auth/send-code")
async def send_code(data: dict):
    phone = data.get("phone", "").strip()
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        res = await client.send_code_request(phone)
        temp_session = client.session.save()
        add_log(f"📩 Giriş kodu istendi: {phone}")
        return {"status": "ok", "phone": phone, "phone_code_hash": res.phone_code_hash, "temp_session": temp_session}
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
        add_log("🎉 GİRİŞ BAŞARILI! Oturum kaydedildi.")
        return {"status": "ok", "session_string": token}
    except Exception as e:
        add_log(f"❌ Giriş hatası: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await client.disconnect()

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

# HTML DOSYA BULUNAMADI HATASINI ÖNLEYEN GÖMÜLÜ ARAYÜZ
HTML_PAGE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real AI Ads Autopilot</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0f172a; color: #f8fafc; font-family: 'Inter', sans-serif; padding: 14px; }
        .container { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; }
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 10px; }
        h1 { font-size: 17px; font-weight: 700; color: #38bdf8; }
        .badge { font-size: 11px; font-weight: 600; padding: 4px 8px; border-radius: 9999px; }
        .badge-active { background: #064e3b; color: #34d399; }
        .badge-inactive { background: #7f1d1d; color: #f87171; }
        .badge-ai { background: #4c1d95; color: #c084fc; border: 1px solid #7c3aed; }
        .card { background: #1e293b; border-radius: 10px; padding: 14px; border: 1px solid #334155; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
        .stat-label { font-size: 11px; color: #94a3b8; }
        .stat-value { font-size: 15px; font-weight: 700; margin-top: 4px; color: #f1f5f9; }
        .btn { padding: 9px 14px; border-radius: 6px; font-weight: 600; cursor: pointer; border: none; font-size: 13px; }
        .btn-start { background: #10b981; color: #042f2e; }
        .btn-stop { background: #ef4444; color: #450a0a; }
        .btn-blue { background: #0284c7; color: white; }
        input { background: #0f172a; border: 1px solid #334155; padding: 9px; border-radius: 6px; color: #f8fafc; font-size: 13px; width: 100%; outline: none; }
        .input-group { display: flex; gap: 6px; margin-top: 6px; }
        .col-group { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
        #log-box { background: #020617; border-radius: 6px; padding: 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px; height: 300px; overflow-y: auto; color: #a5f3fc; border: 1px solid #0f172a; display: flex; flex-direction: column; gap: 4px; }
        .log-entry { word-break: break-all; }
        .countdown { color: #38bdf8; font-weight: 600; font-size: 12px; margin-top: 4px; }
        .ai-card { background: #1e1b4b; border: 1px solid #4338ca; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🤖 Real AI Ads Autopilot</h1>
                <p style="font-size: 11px; color: #94a3b8;">Gemini Destekli İngilizce İkna & Hata Komutanı</p>
            </div>
            <div style="display: flex; gap: 6px;">
                <span class="badge badge-ai">🤖 AI Hazır</span>
                <span id="authBadge" class="badge badge-inactive">Giriş Yok</span>
            </div>
        </header>

        <div class="card" id="loginCard">
            <h3 style="font-size: 13px; color: #f59e0b; margin-bottom: 4px;">🔑 Telegram Girişi (Kalıcı)</h3>
            <div id="stepPhone" class="input-group">
                <input type="text" id="phoneInput" value="+905315151419">
                <button class="btn btn-blue" onclick="sendCode()">Kod Gönder</button>
            </div>
            <div id="stepCode" style="display: none;">
                <div class="col-group">
                    <input type="text" id="codeInput" placeholder="Telegram kodu">
                    <input type="password" id="passInput" placeholder="2FA Şifresi (varsa)">
                    <button class="btn btn-start" onclick="verifyCode()">Giriş Yap</button>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="stat-label">Hedefler</div>
                <div class="stat-value" id="targetCount">...</div>
            </div>
            <div class="card ai-card">
                <div class="stat-label">AI Tarafından Elenenler</div>
                <div class="stat-value" id="aiBlacklist" style="color: #c084fc;">0 Kişi</div>
            </div>
            <div class="card">
                <div class="stat-label">Durum</div>
                <div class="stat-value" id="pilotStatus">Durduruldu</div>
                <div class="countdown" id="timerDisplay"></div>
            </div>
            <div class="card" style="display: flex; align-items: center; justify-content: center;">
                <button id="toggleBtn" class="btn btn-start" onclick="togglePilot()" style="width: 100%;">Başlat</button>
            </div>
        </div>

        <div class="card">
            <div class="stat-label">Google Gemini API Key (Gerçek AI Kararları ve İngilizce Sohbet):</div>
            <div class="input-group">
                <input type="password" id="geminiInput" placeholder="AIzaSy...">
                <button class="btn btn-blue" onclick="saveGeminiKey()">Kaydet</button>
            </div>
            <div class="stat-label" style="margin-top: 8px;">Gönderilen Reklam Metni:</div>
            <div class="input-group">
                <input type="text" id="promoInput">
                <button class="btn btn-blue" onclick="updatePromo()">Güncelle</button>
            </div>
        </div>

        <div class="card">
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                <span class="stat-label">Canlı Terminal & Gerçek AI Müdahale Logları</span>
                <span style="font-size: 11px; color: #64748b;">(2 sn)</span>
            </div>
            <div id="log-box"></div>
        </div>
    </div>

    <script>
        let isRunning = false;
        let currentIndex = 0;
        let countdownTimer = null;

        function getSession() { return localStorage.getItem('tg_session_string') || ''; }
        function getGeminiKey() { return localStorage.getItem('gemini_api_key') || ''; }

        function saveGeminiKey() {
            const k = document.getElementById('geminiInput').value.trim();
            if (k) {
                localStorage.setItem('gemini_api_key', k);
                alert("Gemini API Anahtarı kaydedildi!");
            }
        }

        function checkAuthUI() {
            const sess = getSession();
            const badge = document.getElementById('authBadge');
            const loginCard = document.getElementById('loginCard');
            if (sess) {
                badge.innerText = "Telegram Aktif";
                badge.className = "badge badge-active";
                loginCard.style.display = 'none';
            } else {
                badge.innerText = "Giriş Yok";
                badge.className = "badge badge-inactive";
                loginCard.style.display = 'block';
            }

            const k = getGeminiKey();
            if (k) document.getElementById('geminiInput').value = k;
        }

        async function sendCode() {
            const phone = document.getElementById('phoneInput').value.trim();
            const res = await fetch('/auth/send-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone })
            });
            const data = await res.json();
            if (res.ok) {
                sessionStorage.setItem('authTemp', JSON.stringify(data));
                alert("Kod Telegram uygulamana gönderildi!");
                document.getElementById('stepCode').style.display = 'block';
            } else {
                alert("Hata: " + (data.detail || "Kod gönderilemedi"));
            }
        }

        async function verifyCode() {
            const code = document.getElementById('codeInput').value.trim();
            const password = document.getElementById('passInput').value.trim();
            const temp = JSON.parse(sessionStorage.getItem('authTemp') || '{}');

            const res = await fetch('/auth/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phone: temp.phone,
                    phone_code_hash: temp.phone_code_hash,
                    temp_session: temp.temp_session,
                    code: code,
                    password: password
                })
            });

            const data = await res.json();
            if (res.ok && data.session_string) {
                localStorage.setItem('tg_session_string', data.session_string);
                alert("Giriş başarılı! Oturum kaydedildi.");
                checkAuthUI();
            } else {
                alert("Hata: " + (data.detail || "Giriş yapılamadı!"));
            }
        }

        async function runNextStep() {
            if (!isRunning) return;

            const sess = getSession();
            if (!sess) {
                alert("Önce giriş yapın!");
                togglePilot();
                return;
            }

            document.getElementById('timerDisplay').innerText = "AI devrede...";

            try {
                const res = await fetch('/api/send-step', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_string: sess,
                        gemini_key: getGeminiKey(),
                        index: currentIndex
                    })
                });

                const data = await res.json();

                if (data.status === "unauthorized") {
                    alert("Oturum düştü!");
                    localStorage.removeItem('tg_session_string');
                    checkAuthUI();
                    togglePilot();
                    return;
                }

                if (data.status === "flood") {
                    startCountdown(data.wait, runNextStep, "AI Acil Durum Uykusu");
                    return;
                }

                currentIndex = data.next_index;

                if (data.round_finished) {
                    startCountdown(3600, runNextStep, "1 Tur Bitti (1 Saat Bekleme)");
                } else {
                    const waitTime = data.delay || 15;
                    startCountdown(waitTime, runNextStep, "Sonraki Mesaj");
                }

            } catch (e) {
                startCountdown(10, runNextStep, "AI Yeniden Bağlanıyor");
            }
        }

        function startCountdown(seconds, callback, label) {
            let remain = seconds;
            const display = document.getElementById('timerDisplay');
            clearInterval(countdownTimer);

            countdownTimer = setInterval(() => {
                if (!isRunning) {
                    clearInterval(countdownTimer);
                    display.innerText = "";
                    return;
                }
                display.innerText = `⏳ ${label}: ${remain} sn`;
                remain--;
                if (remain < 0) {
                    clearInterval(countdownTimer);
                    display.innerText = "";
                    callback();
                }
            }, 1000);
        }

        function togglePilot() {
            isRunning = !isRunning;
            const btn = document.getElementById('toggleBtn');
            const pStatus = document.getElementById('pilotStatus');

            if (isRunning) {
                btn.innerText = "Durdur";
                btn.className = "btn btn-stop";
                pStatus.innerText = "AI Aktif";
                pStatus.style.color = "#34d399";
                runNextStep();
            } else {
                btn.innerText = "Başlat";
                btn.className = "btn btn-start";
                pStatus.innerText = "Durduruldu";
                pStatus.style.color = "#f87171";
                clearInterval(countdownTimer);
                document.getElementById('timerDisplay').innerText = "";
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/get-logs');
                const data = await res.json();
                
                document.getElementById('targetCount').innerText = data.target_count + " Kişi";
                document.getElementById('aiBlacklist').innerText = data.blacklisted_count + " Kişi";

                if (!document.getElementById('promoInput').value) {
                    document.getElementById('promoInput').value = data.promo_link;
                }

                const logBox = document.getElementById('log-box');
                logBox.innerHTML = data.logs.map(l => {
                    let color = "#a5f3fc";
                    if (l.includes("[AI MÜDAHALE]") || l.includes("⚠️")) color = "#f472b6";
                    if (l.includes("[AI İNGİLİZCE YANIT]")) color = "#c084fc";
                    if (l.includes("✅")) color = "#4ade80";
                    return `<div class="log-entry" style="color: ${color};">${l}</div>`;
                }).join('');
                logBox.scrollTop = logBox.scrollHeight;
            } catch (e) {}
        }

        async function updatePromo() {
            const link = document.getElementById('promoInput').value;
            await fetch('/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ link })
            });
            alert("Reklam metni güncellendi!");
        }

        checkAuthUI();
        setInterval(fetchLogs, 2000);
        fetchLogs();
    </script>
</body>
</html>
"""

@app.get("/")
async def index():
    return HTMLResponse(HTML_PAGE)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
