import re
from config import SCORE_THRESHOLD

def escape_md(text):
    if not text: return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

def format_currency(val):
    if val is None: return "N/A"
    if val >= 1e9: return f"${val/1e9:.1f}B"
    if val >= 1e6: return f"${val/1e6:.1f}M"
    if val >= 1e3: return f"${val/1e3:.1f}K"
    return f"${val:.1f}"

STRINGS = {
    'id': {
        'start_msg': "⚡ *Haru AI Terminal*",
        'searching': "🔍 _Sedang memindai bursa & on-chain..._",
        'no_data': "📭 *Market sedang sepi momentum.*",
        'disclaimer_btn': "⚖️ Disclaimer",
        'disclaimer_short': "\n^Disclaimer Alert.",
        'help_msg': (
            "📖 *PANDUAN OPERASIONAL*\n"
            "`----------------------------` \n\n"
            "1️⃣ *Scan Market*: Klik manual kapanpun untuk mencari momentum.\n"
            "2️⃣ *Scan Otomatis*: Bot memindai market secara background setiap **10 Menit**.\n"
            "3️⃣ *Laporan Final*: Sinyal terbaik dikirim otomatis setiap **Jam 14:30 UTC**.\n"
            "4️⃣ *Skor*: Skor **4-6/6** adalah konfirmasi kuat untuk eksekusi.\n\n"
            "💡 *Tips:* Gunakan **Moobang Strategy** (Out 50% di TP1) untuk amankan modal."
        ),
        'disclaimer_text': (
            "⚖️ *HARU TERMINAL OFFICIAL DISCLAIMER*\n\n"
            "*#1 Not a Financial Advice*\n"
            "Sinyal bot adalah filter algoritma internal, bukan ajakan jual/beli. Keputusan ada di tangan Anda.\n\n"
            "*#2 No Affiliation*\n"
            "Segala bentuk analisa bersifat objektif. Kami tidak terafiliasi atau melakukan promosi terhadap token/project manapun.\n\n"
            "*#3 Money Management*\n"
            "• **Alokasi Ideal:** 70% Bitcoin & 30% Altcoins (Maks 3% per koin).\n"
            "• **Trading Strategy:** 70% Spot & 30% Futures.\n"
            "• **Risk per Trade (RPT):** 1-2% dari modal Futures.\n"
            "• **Max Positions:** Maksimal tiga (3) posisi terbuka (Anti-Overtrading).\n"
            "• **Exit Strategy:** Hit TP1 keluar 25% dan set SL di BEP. Scalper bisa TP 100% di TP1.\n\n"
            "*#4 Beginner's Advice*\n"
            "Gunakan **Moobang Strategy**: Setelah naik 100%, jual 50% posisi dan biarkan sisanya jalan. User <1 tahun dilarang pakai leverage tinggi.\n\n"
            "*#5 Tidak Ada Jaminan*\n"
            "Hanya gunakan dana dingin. Crypto sangat volatil dan tidak ada pihak yang bisa menjamin hasil."
        ),
        'back': "⬅️ Kembali"
    },
    'en': {
        'start_msg': "⚡ *Haru AI Terminal*",
        'searching': "🔍 _Scanning exchanges & on-chain..._",
        'no_data': "📭 *Market zero momentum.*",
        'disclaimer_btn': "⚖️ Disclaimer",
        'disclaimer_short': "\n^Disclaimer Alert.",
        'help_msg': (
            "📖 *OPERATIONAL GUIDE*\n"
            "`----------------------------` \n\n"
            "1️⃣ *Scan Market*: Click manually anytime to search for momentum.\n"
            "2️⃣ *Auto Scan*: Bot scans the market in the background every **10 Minutes**.\n"
            "3️⃣ *Final Report*: Best signals sent automatically every day at **14:30 UTC**.\n"
            "4️⃣ *Score*: A score of **4-6/6** is a strong confirmation for execution.\n\n"
            "💡 *Tip:* Always use **Moobang Strategy** (Out 50% at TP1) to secure capital."
        ),
        'disclaimer_text': (
            "⚖️ *HARU TERMINAL OFFICIAL DISCLAIMER*\n\n"
            "*#1 Not a Financial Advice*\n"
            "Bot signals are internal algorithmic filters, not a buy/sell call. Decisions are yours.\n\n"
            "*#2 No Affiliation*\n"
            "All analyses are objective. We are not affiliated with or promoting any tokens/projects.\n\n"
            "*#3 Money Management*\n"
            "• **Ideal Allocation:** 70% Bitcoin & 30% Altcoins (Max 3% per coin).\n"
            "• **Trading Strategy:** 70% Spot & 30% Futures.\n"
            "• **Risk per Trade (RPT):** 1-2% of Futures capital.\n"
            "• **Max Positions:** Maximum of three (3) open positions (Anti-Overtrading).\n"
            "• **Exit Strategy:** At TP1 exit 25% and set SL to BEP. Scalpers can exit 100% at TP1.\n\n"
            "*#4 Beginner's Advice*\n"
            "Use **Moobang Strategy**: After 100% gain, sell 50% and let the rest run. Users <1 year experience should avoid high leverage.\n\n"
            "*#5 No Guarantees*\n"
            "Use risk capital only. Crypto is highly volatile and no one can guarantee results."
        ),
        'back': "⬅️ Back"
    },
    'ru': {
        'start_msg': "⚡ *Терминал Haru AI*",
        'searching': "🔍 _Сканирование бирж и сети..._",
        'no_data': "📭 *На рынке нет импульса.*",
        'disclaimer_btn': "⚖️ Дисклеймер",
        'disclaimer_short': "\n^Disclaimer Alert.",
        'help_msg': (
            "📖 *РУКОВОДСТВО ПО ЭКСПЛУАТАЦИИ*\n"
            "`----------------------------` \n\n"
            "1️⃣ *Scan Market*: Нажмите вручную в любое время для поиска импульса.\n"
            "2️⃣ *Авто-скан*: Бот сканирует рынок в фоновом режиме каждые **10 минут**.\n"
            "3️⃣ *Финальный отчет*: Лучшие сигналы отправляются автоматически в **14:30 UTC**.\n"
            "4️⃣ *Счет*: Счет **4-6/6** является сильным подтверждением для входа.\n\n"
            "💡 *Совет:* Используйте **Moobang Strategy** (Выход 50% на TP1) для защиты капитала."
        ),
        'disclaimer_text': (
            "⚖️ *ОФИЦИАЛЬНЫЙ ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ*\n\n"
            "*#1 Не финансовый совет*\n"
            "Сигналы бота — это внутренние алгоритмы, а не призыв к сделке. Решения за вами.\n\n"
            "*#2 Без аффилиации*\n"
            "Все анализы объективны. Мы не связаны с какими-либо токенами или проектами.\n\n"
            "*#3 Управление капиталом*\n"
            "• **Распределение:** 70% Bitcoin и 30% Altcoins (макс. 3% на монету).\n"
            "• **Стратегия:** 70% спот и 30% фьючерсы.\n"
            "• **Риск на сделку (RPT):** 1-2% от капитала на фьючерсах.\n"
            "• **Макс. позиции:** Не более трех (3) открытых позиций.\n"
            "• **Выход:** На TP1 закрыть 25% и стоп-лосс в безубыток. Скальперы: 100% на TP1.\n\n"
            "*#4 Совет новичкам*\n"
            "**Moobang Strategy**: При росте на 100% продайте 50% и держите остаток. Опыт <1 года — без плеч.\n\n"
            "*#5 Без гарантий*\n"
            "Используйте только свободные средства. Рынок волатилен, гарантий нет."
        ),
        'back': "⬅️ Назад"
    }
}

def build_report_text(analyzed_data, lang_code='id', is_final=False):
    l = STRINGS.get(lang_code, STRINGS['id'])
    header = "🏆 *FINAL RADAR REPORT*" if is_final else "⏳ *TEMPORARY RADAR REPORT*"
    msg = f"{header}\n`{'='*28}`\n\n"
    if not analyzed_data:
        return msg + l['no_data'] + l['disclaimer_short']
    for coin in analyzed_data[:10]:
        sym = escape_md(coin['symbol'])
        score = coin['score']
        # Di formatter.py baris 130, ubah menjadi:
        metrics = coin.get('metrics', []) # Pakai .get() biar gak KeyError
        m_list = " ".join(metrics) if metrics else "No metrics available"
        h, d, w = coin['trend']
        status = "💎 *TRENDING*" if score >= 4 else "⚖️ *CONSOLIDATION*"
        hl = coin['hl_data']
        vol_f = format_currency(hl['vol']) if hl else "N/A"
        oi_f = format_currency(hl['oi']) if hl else "N/A"
        msg += f"🔹 *${sym}* ({status})\n ├ 📊 `Trend: {h:+.1f}% | {d:+.1f}% | {w:+.1f}%` \n ├ 💸 `Vol: {vol_f} | OI: {oi_f}` \n └ 📝 `Metriks: {m_list} ({score}/6)` \n\n"
    msg += l['disclaimer_short']
    return msg


