import httpx
import asyncio
import logging
import os
from datetime import datetime
from cachetools import TTLCache
from config import VOL_MIN, OI_MIN, SCORE_THRESHOLD

logger = logging.getLogger("HaruEngine")

# ===========================================================================
# STANDALONE: DEXPAPRIKA FETCHER (di luar class, dipanggil oleh engine)
# ===========================================================================

async def fetch_dexpaprika_stats(network="solana", token_address=""):
    """
    Mengambil data detail token dari DexPaprika (Gratis & No-Key).
    Gunakan ini untuk cari Buy/Sell Ratio.
    """
    if not token_address:
        return None

    url = f"https://api.dexpaprika.com/networks/{network}/tokens/{token_address}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                summary = data.get('summary', {}).get('24h', {})

                buys  = summary.get('buys', 0)
                sells = summary.get('sells', 0)
                ratio = buys / sells if sells > 0 else buys

                return {
                    'price':          data.get('price_usd'),
                    'liquidity':      data.get('liquidity_usd'),
                    'volume_24h':     summary.get('volume_usd'),
                    'buy_sell_ratio': round(ratio, 2),
                    'source':         'DexPaprika'
                }
            return None
        except Exception as e:
            logger.warning(f"⚠️ DexPaprika Error: {e}")
            return None


# ===========================================================================
# STANDALONE: NEWS & SENTIMENT FETCHER (CryptoPanic)
# ===========================================================================

async def fetch_news_sentiment(symbol):
    """Ambil berita & sentimen dari CryptoPanic."""
    api_key = os.getenv("CRYPTOPANIC_API_KEY")
    # Mapping symbol ke currency code (contoh: BTC, ETH)
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={api_key}&currencies={symbol}&kind=news&filter=hot"

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, timeout=10.0)
            data = res.json()
            # Ambil 3 berita teratas
            news_items = []
            for post in data.get('results', [])[:3]:
                title = post.get('title')
                votes = post.get('votes', {})
                sentiment = "Positive" if votes.get('bullish', 0) > votes.get('bearish', 0) else "Neutral/Negative"
                news_items.append(f"{title} ({sentiment})")
            return news_items
        except:
            return []


# ===========================================================================
# STANDALONE: MACRO CALENDAR FETCHER (Finnhub)
# ===========================================================================

async def fetch_macro_calendar():
    """Ambil kalender ekonomi High Impact dari Finnhub."""
    api_key = os.getenv("FINNHUB_API_KEY")
    # Kita cek event hari ini
    url = f"https://finnhub.io/api/v1/calendar/economic?token={api_key}"

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, timeout=10.0)
            events = res.json().get('economicCalendar', [])
            # Filter hanya yang impact-nya 'high' (biasanya bintang 3 di Forex Factory)
            high_impact = [e['event'] for e in events if e.get('impact') == 'high']
            return high_impact[:3]
        except:
            return []


# ===========================================================================
# HARU ENGINE CLASS
# ===========================================================================

class HaruEngine:
    def __init__(self):
        self.client           = httpx.AsyncClient(timeout=25.0)
        self.last_fetch       = None
        self.cooldown_cache   = TTLCache(maxsize=1000, ttl=5)
        self.last_scan_results = []  # Cache 5 sinyal teratas untuk AI Analysis

    # -----------------------------------------------------------------------
    # HELPER: Safe JSON Getter
    # -----------------------------------------------------------------------

    async def safe_get_json(self, request_task, source_name="API"):
        """Penanganan JSON dengan fallback agar tidak menghentikan flow."""
        try:
            resp = await request_task
            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 403:
                logger.warning(f"⚠️ {source_name} Credits Exhausted (403). Proceeding without {source_name} data.")
                return None

            logger.error(f"⚠️ {source_name} Error {resp.status_code}: {resp.text[:100]}")
            return None
        except Exception as e:
            logger.error(f"🚫 {source_name} Connection Failed: {str(e)}")
            return None

    # -----------------------------------------------------------------------
    # FETCHER: Ambil semua data market sekaligus (CG + HL + DEX)
    # -----------------------------------------------------------------------

    # Tambahkan/Update fungsi ini di engine.py

    async def fetch_news_sentiment(symbol):
        """Ambil berita & sentimen dari CryptoPanic V2."""
        api_key = os.getenv("CRYPTOPANIC_API_KEY")
        # Gunakan endpoint developer/v2 sesuai spek baru
        url = f"https://cryptopanic.com/api/developer/v2/posts/?auth_token={api_key}&currencies={symbol}&kind=news&public=true"
        
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(url, timeout=10.0)
                if res.status_code == 200:
                    data = res.json()
                    news_items = []
                    for post in data.get('results', [])[:3]:
                        title = post.get('title')
                        votes = post.get('votes', {})
                        # Logic sentimen sederhana
                        pos = votes.get('bullish', 0) + votes.get('positive', 0)
                        neg = votes.get('bearish', 0) + votes.get('negative', 0)
                        sent = "Bullish" if pos > neg else "Neutral/Bearish"
                        news_items.append(f"• {title} ({sent})")
                    return news_items
                return []
            except Exception as e:
                logger.error(f"CryptoPanic Error: {e}")
                return []

    async def fetch_macro_calendar():
        """Ambil kalender ekonomi High Impact (Finnhub/Alternative)."""
        api_key = os.getenv("FINNHUB_API_KEY")
        url = f"https://finnhub.io/api/v1/calendar/economic?token={api_key}"
        
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(url, timeout=10.0)
                if res.status_code == 200:
                    events = res.json().get('economicCalendar', [])
                    # Ambil yang impact-nya 'high'
                    high = [f"⚠️ {e['event']} ({e['country']})" for e in events if e.get('impact') == 'high']
                    return high[:2]
                return []
            except:
                return []

    # UPDATE FUNGSI UTAMA ENGINE
    async def get_market_data(self):
        """Mengambil semua data secara paralel."""
        # Bungkus dalam gather agar tidak crash jika salah satu fail
        results = await asyncio.gather(
            self.fetch_coingecko(),      # 0
            self.fetch_hyperliquid(),    # 1
            self.fetch_dexpaprika(),     # 2
            fetch_news_sentiment("BTC"), # 3 (Default BTC untuk info umum)
            fetch_macro_calendar(),      # 4
            return_exceptions=True
        )
        
        # Pastikan return selalu list dengan panjang 5
        cleaned = []
        for r in results:
            if isinstance(r, Exception):
                cleaned.append([]) # Jika error kasih list kosong
            else:
                cleaned.append(r)
        return cleaned


    async def get_market_data(self):
        """
        Fetch paralel dari CoinGecko, Hyperliquid, DexPaprika, CryptoPanic, & Finnhub.
        Return: (cg_data, hl_data, dex_data, news_data, macro_data)
        """
        logger.info("📡 Fetching: CoinGecko, Hyperliquid, DexPaprika, CryptoPanic & Finnhub...")

        cg_task  = self.client.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "per_page": 150, "price_change_percentage": "1h,24h,7d"}
        )
        hl_task  = self.client.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"}
        )

        results = await asyncio.gather(
            self.safe_get_json(cg_task, "CoinGecko"),
            self.safe_get_json(hl_task, "Hyperliquid"),
            fetch_dexpaprika_stats(),   # Standalone function, tetap di luar class
            fetch_news_sentiment("BTC,ETH"),  # Default broad sentiment
            fetch_macro_calendar(),
            return_exceptions=True
        )

        self.last_fetch = datetime.now()

        cg_data    = results[0] if not isinstance(results[0], Exception) else []
        hl_data    = results[1] if not isinstance(results[1], Exception) else {}
        extra_data = results[2] if not isinstance(results[2], Exception) else []
        news_data  = results[3] if not isinstance(results[3], Exception) else []
        macro_data = results[4] if not isinstance(results[4], Exception) else []

        return cg_data, hl_data, extra_data, news_data, macro_data

    # -----------------------------------------------------------------------
    # SCORER: Proses sinyal dari data mentah
    # -----------------------------------------------------------------------

    def calculate_smart_score(self, cg_data, hl_data, dex_data, news_data=None, macro_data=None):
        """
        Scoring Engine Haru Terminal.
        Kalkulasi bobot koin berdasarkan PA, Open Interest, DEX Volume, News & Macro.
        Return: list of dict (filtered & sorted by score desc)
        """
        if not cg_data:
            return []

        # --- Map Hyperliquid raw → dict {SYMBOL: {oi, vol, funding}} ---
        hl_map = {}
        if hl_data and isinstance(hl_data, list):
            try:
                # Loop universe untuk mapping nama aset ke context-nya
                for i, asset in enumerate(hl_data[0]['universe']):
                    name = asset['name']
                    ctx = hl_data[1][i]

                    funding_raw = float(ctx.get('funding', 0))

                    hl_map[name] = {
                        "oi":      float(ctx.get('openInterest', 0)),
                        "vol":     float(ctx.get('dayNtlVlm', 0)),
                        "funding": funding_raw * 100,  # Konversi ke %
                        # Tambahan untuk AI: interpretasi funding
                        "bias": "Shorts paying Longs" if funding_raw > 0 else "Longs paying Shorts"
                    }
            except Exception as e:
                logger.warning(f"Parsing HL failed: {e}")

        # --- Dex trending symbols ---
        dex_trending = [d.get('symbol', '').upper() for d in dex_data] if dex_data else []

        blacklist  = {'USDT', 'USDC', 'DAI', 'PAXG', 'WBTC', 'WETH'}
        scored     = []

        for coin in cg_data:
            symbol = coin.get('symbol', '').upper()
            if not symbol or symbol in blacklist:
                continue

            score   = 0
            signals = []

            # --- A. Price Action (CoinGecko) ---
            h1 = coin.get('price_change_percentage_1h_in_currency', 0)  or 0
            d1 = coin.get('price_change_percentage_24h_in_currency', 0) or 0
            w7 = coin.get('price_change_percentage_7d_in_currency', 0)  or 0

            if h1 > 0 and d1 > 0:
                score += 1
                signals.append("📈 Price")
            if h1 > 0 and d1 > 0 and w7 > 0:
                score += 1
                signals.append("🔥 Buy")

            # --- B. Futures / Open Interest (Hyperliquid) ---
            hl = hl_map.get(symbol)
            if hl:
                if hl['vol'] >= VOL_MIN:
                    score += 1
                    signals.append("💰 Vol")
                if hl['oi'] >= OI_MIN:
                    score += 1
                    signals.append("🔍 OI")
                if 0.0001 <= hl['funding'] <= 0.01:
                    score += 1
                    signals.append("🟢 Fund")

            # --- C. DEX Momentum (DexPaprika) ---
            if symbol in dex_trending:
                score += 1
                signals.append("🔥 DEX Trending")

            if score >= SCORE_THRESHOLD:
                scored.append({
                    'name':       coin['name'],
                    'symbol':     symbol,
                    'price':      coin.get('current_price', 0),
                    'score':      score,
                    'signals':    signals,
                    'trend':      (h1, d1, w7),
                    'hl_data':    hl,
                    'news':       news_data or [],
                    'macro':      macro_data or []
                })

        sorted_results = sorted(scored, key=lambda x: x['score'], reverse=True)

        # Simpan 5 teratas untuk AI Analysis
        self.last_scan_results = sorted_results[:5]

        return sorted_results


# Singleton — import ini di file lain
engine = HaruEngine()





