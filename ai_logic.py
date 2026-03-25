import httpx
import asyncio
import logging
import time
import os
import re
from dotenv import load_dotenv

# Import fungsi fetcher dari engine (Pastikan engine.py sudah ada fungsi ini)
# Kita import di dalam fungsi atau di atas tetap aman
try:
    from engine import fetch_news_sentiment, fetch_macro_calendar
except ImportError:
    logger = logging.getLogger(__name__)
    logger.error("Gagal import fetcher dari engine.py")

load_dotenv("API.env")

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Penting: Tetap pertahankan cache agar tidak boros kuota API
analysis_cache = {}

# ===========================================================================
# 1. PROMPT DEFINITION (Ditingkatkan dengan hirarki keputusan)
# ===========================================================================

LANG_PROMPTS = {
    'id': (
        "Lu adalah analis crypto senior (Haru AI). Jawab dalam Bahasa Indonesia, singkat, formal-casual, dan tajam. "
        "Jangan pakai bullet point atau header. Tulis dalam 3 paragraf pendek:\n\n"
        "Paragraf 1: Rekomendasi (BUY/SELL/WAIT) berdasarkan integrasi data Teknikal + News + Macro.\n"
        "Paragraf 2: Analisa mendalam kenapa sinyal ini muncul. Hubungkan Price Action dengan Funding Rate/OI atau News yang ada.\n"
        "Paragraf 3: Kesimpulan 1 kalimat tegas dan objektif.\n\n"
        "ATURAN KRITIS (Wajib Patuh):\n"
        "- Jika ada event High Impact (FOMC, CPI, NFP) di data Makro, lu WAJIB sarankan WAIT AND SEE.\n"
        "- Jika ada news negatif (Hack/FUD), abaikan skor teknikal tinggi dan sarankan WAIT/SELL.\n"
        "- Jika Funding Rate sangat positif tapi harga stagnan/turun, peringatkan potensi Long Squeeze.\n"
        "- Jangan bombastis, tetap realistis, dan hindari membuat user FOMO."
    ),
    'en': (
        "You are a senior crypto analyst (Haru AI). Answer in English, short, professional, and sharp. "
        "No bullet points or headers. Write in 3 short paragraphs:\n\n"
        "Paragraph 1: Recommendation (BUY/SELL/WAIT) integrating Technical + News + Macro data.\n"
        "Paragraph 2: Deep analysis of why this signal appeared. Link Price Action with Funding/OI or current News.\n"
        "Paragraph 3: One firm, objective concluding sentence.\n\n"
        "CRITICAL RULES:\n"
        "- If High Impact events (FOMC, CPI) are present in Macro data, you MUST recommend WAIT AND SEE.\n"
        "- If there is negative news (Hack/FUD), ignore high technical scores and suggest WAIT/SELL.\n"
        "- If Funding Rate is highly positive but price is stagnant, warn about a potential Long Squeeze.\n"
        "- Be realistic, avoid being over-optimistic, and prevent user FOMO."
    ),
    'ru': (
        "Ты старший криптоаналитик (Haru AI). Отвечай по-русски, кратко, официально-деловым стилем. "
        "Без списков и заголовков. 3 коротких абзаца:\n\n"
        "Абзац 1: Рекомендация (BUY/SELL/WAIT) на основе тех. анализа, новостей и макроданных.\n"
        "Абзац 2: Анализ причин сигнала. Свяжи цену с Funding Rate/OI или новостями.\n"
        "Абзац 3: Одно четкое и объективное итоговое предложение.\n\n"
        "КРИТИЧЕСКИЕ ПРАВИЛА:\n"
        "- Если в макроданных есть важные события (FOMC, CPI), ОБЯЗАТЕЛЬНО рекомендуй WAIT AND SEE.\n"
        "- При негативных новостях (взлом/FUD) игнорируй тех. баллы и советуй WAIT/SELL.\n"
        "- Если фандинг высокий, а цена падает, предупреди о Long Squeeze."
    ),
}

# ===========================================================================
# 2. CORE UTILITIES (Caching & AI Fetchers)
# ===========================================================================

def get_cached_insight(symbol, lang):
    key = f"{symbol}_{lang}"
    if key in analysis_cache:
        cached = analysis_cache[key]
        if time.time() - cached['timestamp'] < 600: # 10 Menit
            return cached['insight']
    return None

def set_cached_insight(symbol, lang, insight):
    key = f"{symbol}_{lang}"
    analysis_cache[key] = {'insight': insight, 'timestamp': time.time()}

def strip_markdown_fences(text: str) -> str:
    """Membersihkan tag markdown agar tidak merusak parsing Telegram."""
    text = re.sub(r'^```[a-zA-Z]*\n?', '', text.strip())
    text = re.sub(r'\n?```$', '', text.strip())
    return text.strip()

async def fetch_gemini_ai(prompt):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=15.0)
            if response.status_code == 200:
                data = response.json()
                raw = data['candidates'][0]['content']['parts'][0]['text']
                return strip_markdown_fences(raw)
            return None
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            return None

async def fetch_backup_ai(prompt):
    if not OPENROUTER_API_KEY: return None
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "openrouter/auto",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=20.0)
            if response.status_code == 200:
                res_data = response.json()
                raw = res_data['choices'][0]['message']['content'].strip()
                return strip_markdown_fences(raw)
        except Exception as e:
            logger.error(f"OpenRouter Error: {e}")
    return None

# ===========================================================================
# 3. FORMATTING & LOGIC DECISION
# ===========================================================================

def format_insight(symbol, coin, raw_text):
    """Bungkus output AI jadi tampilan Telegram UI v11.8."""
    score   = coin.get('score', 0)
    price   = coin.get('price', 0)
    signals = coin.get('signals', [])
    sigs_str = '  '.join(signals) if signals else '-'

    # Deteksi Emoji Rekomendasi
    txt_lower = raw_text.lower()
    if any(w in txt_lower for w in ['wait', 'tunggu', 'see', 'nanti', 'ожидайте']):
        rec_emoji = "🟡" # Status: Abu-abu / Netral / Makro Panas
    elif any(w in txt_lower for w in ['buy', 'beli', 'long', 'покупать']):
        rec_emoji = "🟢" # Status: Bullish Confirmed
    elif any(w in txt_lower for w in ['sell', 'jual', 'short', 'продавать']):
        rec_emoji = "🔴" # Status: Bearish / Danger
    else:
        rec_emoji = "⚪"

    header = (
        f"{rec_emoji} *Haru AI Insight — ${symbol}*\n"
        f"`{'─' * 26}`\n"
        f"💵 `${price:,.4f}`  •  🎯 Score `{score}/6`\n"
        f"_{sigs_str}_\n"
        f"`{'─' * 26}`"
    )
    footer = f"\n`{'─' * 26}`\n_⚠️ Data based on L1 Hyperliquid & Sentiment._"
    return f"{header}\n\n{raw_text}\n{footer}"

# ===========================================================================
# 4. MAIN ENTRY POINT (Fungsi Utama)
# ===========================================================================

async def get_trading_insight(data_input, lang='id'):
    """
    Fungsi utama untuk generate analisa. 
    Menerima data koin dan menggabungkannya dengan data News & Macro secara real-time.
    """
    # 1. Parsing Input
    coin = None
    if isinstance(data_input, list) and len(data_input) > 0:
        item = data_input[0]
        coin = item[0] if isinstance(item, list) and len(item) > 0 else item
    elif isinstance(data_input, dict):
        coin = data_input

    if not isinstance(coin, dict) or not coin.get('symbol'):
        return "⚠️ Data market tidak valid."

    symbol = coin.get('symbol')
    
    # 2. Check Cache
    cached = get_cached_insight(symbol, lang)
    if cached: return f"♻️ **(Cached - {lang.upper()})**\n\n{cached}"

    # 3. Fetch External Data (News & Macro)
    # Ini yang bikin AI kita melek berita
    try:
        from engine import fetch_news_sentiment, fetch_macro_calendar
        news_data = await fetch_news_sentiment(symbol)
        macro_data = await fetch_macro_calendar()
    except:
        news_data = []
        macro_data = []

    news_text = "\n".join(news_data) if news_data else "No major news headlines."
    macro_text = ", ".join(macro_data) if macro_data else "No high impact macro events today."

    # 4. Data Technical Extraction
    sigs  = ', '.join(coin.get('signals', [])) or 'N/A'
    trend = coin.get('trend', (0, 0, 0))
    hl    = coin.get('hl_data', {})
    funding = hl.get('funding', 0)
    oi    = hl.get('oi', 0)
    bias  = hl.get('bias', 'Neutral')

    # 5. Build Final Prompt
    instruction = LANG_PROMPTS.get(lang, LANG_PROMPTS['id'])
    prompt = (
        f"{instruction}\n\n"
        f"--- REAL-TIME ON-CHAIN DATA ---\n"
        f"Asset: {symbol} | Price: ${coin.get('price', 0)}\n"
        f"Algo Score: {coin.get('score', 0)}/6 | Signals: {sigs}\n"
        f"Funding Rate: {funding:.4f}% | Open Interest: ${oi:,.0f}\n"
        f"Market Bias: {bias} | Trend (1h/24h/7d): {trend[0]:+.2f}% / {trend[1]:+.2f}% / {trend[2]:+.2f}%\n\n"
        
        f"--- EXTERNAL SENTIMENT ---\n"
        f"Recent News Headlines:\n{news_text}\n\n"
        
        f"--- MACRO CALENDAR (HIGH IMPACT) ---\n"
        f"Events: {macro_text}\n"
    )

    logger.info(f"🧠 Haru AI analyzing {symbol} (Lang: {lang})...")

    # 6. Execute AI Call
    insight = await fetch_gemini_ai(prompt)
    if not insight:
        logger.warning("Gemini failed, switching to backup...")
        insight = await fetch_backup_ai(prompt)

    if insight:
        formatted = format_insight(symbol, coin, insight)
        set_cached_insight(symbol, lang, formatted)
        return formatted

    return "⚠️ Maaf, Haru AI sedang mengalami gangguan koneksi."




