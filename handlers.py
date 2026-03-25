import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import WHITELIST
from database import db
from engine import engine
from ai_logic import get_trading_insight
from formatter import STRINGS

logger = logging.getLogger("HaruTerminal")

# ===========================================================================
# HELPER
# ===========================================================================

def format_status(coin):
    """Status koin berdasarkan score."""
    score = coin.get('score', 0)
    if score >= 4:
        return "💎 TRENDING"
    return "⚖️ CONSOLIDATION"

def has_signal(sigs, keyword):
    """Cek sinyal dengan keyword partial agar tidak false-negative."""
    return any(keyword.lower() in s.lower() for s in sigs)

def build_start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Scan Market", callback_data='scan')],
        [InlineKeyboardButton("🌐 Language", callback_data='lang'),
         InlineKeyboardButton("📖 Help", callback_data='help_call')]
    ])

# ===========================================================================
# COMMAND HANDLERS
# ===========================================================================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_authorized(uid, WHITELIST):
        await update.message.reply_text("🚫 *Access Denied.*", parse_mode='Markdown')
        return
    try:
        await update.message.delete()
    except Exception:
        pass
    sent = await update.message.reply_text(
        "⚡ *Haru AI Terminal v11.8*",
        reply_markup=build_start_keyboard(),
        parse_mode='Markdown'
    )
    context.user_data['main_msg_id'] = sent.message_id
    context.user_data['main_chat_id'] = sent.chat_id

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = db.get_user_lang(uid)
    l = STRINGS.get(lang, STRINGS['id'])
    await update.message.reply_text(
        l['help_msg'],
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(l['back'], callback_data='back_start')]]),
        parse_mode='Markdown'
    )

# ===========================================================================
# CALLBACK HANDLER
# ===========================================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    lang = db.get_user_lang(uid)
    l = STRINGS.get(lang, STRINGS['id'])

    await query.answer()

    if not db.is_authorized(uid, WHITELIST):
        await query.answer("🚫 Access Denied.", show_alert=True)
        return

    # -------------------------------------------------------------------
    # SCAN MARKET
    # -------------------------------------------------------------------
    if query.data == 'scan':
        await query.edit_message_text(text=l['searching'], parse_mode='Markdown')
        msg = query.message
        try:
            # FIX: Tangkap hasil sebagai list untuk menghindari ValueError unpack
            all_data = await engine.get_market_data()
            
            # Pastikan urutan index sesuai dengan return di engine.py
            cg   = all_data[0]
            hl   = all_data[1]
            dex  = all_data[2]
            # data[3] (news) & data[4] (macro) tidak ditampilkan di report list
            # tapi sudah tersimpan di memori untuk diproses AI nanti.

            hot_coins = engine.calculate_smart_score(cg, hl, dex)

            if not hot_coins:
                await msg.edit_text(
                    l['no_data'],
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(l['disclaimer_btn'], callback_data='disclaimer'),
                         InlineKeyboardButton("⬅️ Kembali", callback_data='back_start')]
                    ])
                )
                return

            # Simpan 5 koin terbaik untuk referensi AI Analyze
            engine.last_scan_results = hot_coins[:5]

            report = "⏳ *TEMPORARY RADAR REPORT*\n"

            for coin in hot_coins[:6]:
                sym     = coin.get('symbol', '???').upper()
                status  = format_status(coin)
                sigs    = coin.get('signals', [])
                t       = coin.get('trend', (0.0, 0.0, 0.0))

                hl_data = coin.get('hl_data') or {}
                v_raw   = float(hl_data.get('vol', 0) or 0)
                o_raw   = float(hl_data.get('oi', 0)  or 0)

                # Format Million ($M)
                v_m = v_raw / 1_000_000 if v_raw >= 1_000_000 else v_raw / 1_000
                o_m = o_raw / 1_000_000 if o_raw >= 1_000_000 else o_raw / 1_000

                e_p = "📈" if has_signal(sigs, "Price") or has_signal(sigs, "Buy") else "📉"
                e_v = "💰" if has_signal(sigs, "Vol")   else "📊"
                e_o = "🔍" if has_signal(sigs, "OI")    else "🔭"
                e_f = "🟢" if has_signal(sigs, "Fund")  else "🔴"

                report += (
                    f"\n🔹 *${sym}* ({status})\n"
                    f"├─ 📊 Trend: `{t[0]:+.2f}% | {t[1]:+.2f}% | {t[2]:+.2f}%`\n"
                    f"├─ 💸 Vol: `${v_m:.2f}M` | OI: `${o_m:.2f}M`\n"
                    f"└─ 📝 {e_p} Price {e_v} Vol {e_o} OI {e_f} Fund ({len(sigs)}/6)\n"
                )

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🧠 Minta Opini AI (Beta)", callback_data='ai_analyze')],
                [InlineKeyboardButton(l['disclaimer_btn'], callback_data='disclaimer'),
                 InlineKeyboardButton("⬅️ Kembali", callback_data='back_start')]
            ])

            await msg.edit_text(text=report, parse_mode='Markdown', reply_markup=kb)

        except Exception as e:
            logger.error(f"Scan Error: {e}", exc_info=True)
            await msg.edit_text(f"⚠️ Haru AI Error:\n`{e}`", parse_mode='Markdown')

    # -------------------------------------------------------------------
    # AI ANALYZE (Titik temu AI + News + Macro)
    # -------------------------------------------------------------------
    elif query.data == 'ai_analyze':
        if not engine.last_scan_results:
            await query.answer("❌ Lakukan Scan dulu!", show_alert=True)
            return

        await query.edit_message_text(text="🧠 *Haru AI sedang menganalisa...*", parse_mode='Markdown')
        try:
            # get_trading_insight sekarang sudah panggil fetch_news_sentiment & fetch_macro_calendar di dalamnya
            insight = await get_trading_insight(engine.last_scan_results, lang)
            kb_back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali", callback_data='back_start')]])
            
            try:
                await query.edit_message_text(insight, parse_mode='Markdown', reply_markup=kb_back)
            except Exception:
                # Fallback jika ada karakter Markdown yang bikin Telegram error
                plain = insight.replace('**', '').replace('*', '').replace('`', '').replace('_', '')
                await query.edit_message_text(plain, reply_markup=kb_back)
        except Exception as e:
            logger.error(f"AI Analyze Error: {e}", exc_info=True)
            await query.edit_message_text(f"⚠️ AI Error: {str(e)}")

    # -------------------------------------------------------------------
    # OTHERS (Language, Help, Disclaimer, Back)
    # -------------------------------------------------------------------
    elif query.data == 'lang':
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇮🇩 Indonesia", callback_data='set_lang_id'),
                InlineKeyboardButton("🇬🇧 English",   callback_data='set_lang_en'),
                InlineKeyboardButton("🇷🇺 Русский",   callback_data='set_lang_ru'),
            ],
            [InlineKeyboardButton(l['back'], callback_data='back_start')]
        ])
        await query.edit_message_text("🌐 *Pilih Bahasa / Select Language:*", reply_markup=kb, parse_mode='Markdown')

    elif query.data.startswith('set_lang_'):
        new_lang = query.data.replace('set_lang_', '')
        db.update_user_lang(uid, new_lang)
        l_new = STRINGS.get(new_lang, STRINGS['id'])
        await query.edit_message_text(
            f"✅ Bahasa diubah ke *{new_lang.upper()}*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(l_new['back'], callback_data='back_start')]]),
            parse_mode='Markdown'
        )

    elif query.data == 'help_call':
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(l['back'], callback_data='back_start')]])
        await query.edit_message_text(l['help_msg'], reply_markup=kb, parse_mode='Markdown')

    elif query.data == 'disclaimer':
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(l['back'], callback_data='back_start')]])
        await query.edit_message_text(l['disclaimer_text'], reply_markup=kb, parse_mode='Markdown')

    elif query.data == 'back_start':
        await query.edit_message_text(l['start_msg'], reply_markup=build_start_keyboard(), parse_mode='Markdown')





        