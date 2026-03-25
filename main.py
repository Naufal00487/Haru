import logging
import sys
import os
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import sesuai variabel di config
from config import TOKEN, WHITELIST 
from handlers import start_handler, help_handler, handle_callback
from engine import engine
from formatter import build_report_text
from database import db

# 1. LOGGING SETUP
os.environ['PYTHONUNBUFFERED'] = '1'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("HaruMain")

# 2. BACKGROUND TASKS
async def scheduled_scan(app):
    logger.info("🔍 Background: Scanning market (10 min cycle)...")
    try:
        raw_data = await engine.get_market_data()
        signals = engine.calculate_smart_score(*raw_data)
        high_score = [s for s in signals if s['score'] >= 5]
        if high_score:
            logger.info(f"🔥 Alert: Found {len(high_score)} high score coins!")
    except Exception as e:
        logger.error(f"❌ Scan error: {e}")

# Di dalam nightly_report
async def nightly_report(app):
    try:
        raw_data = await engine.get_market_data()
        
        # FIX: Ambil cuma 3 data awal (CG, HL, DEX)
        # Jangan pakai *raw_data karena isinya sekarang ada 5!
        signals = engine.calculate_smart_score(raw_data[0], raw_data[1], raw_data[2])
        
        for user_id in WHITELIST:
            lang = db.get_user_lang(user_id)
            # Pastikan signals tidak kosong sebelum diproses
            if signals:
                report = build_report_text(signals, lang, is_final=True)
                await app.bot.send_message(chat_id=user_id, text=report, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Nightly report error: {e}", exc_info=True)

# 3. RUNNER ASYNC
async def run_bot():
    if not TOKEN:
        logger.error("🚫 TOKEN tidak ditemukan!")
        return

    # Inisialisasi App
    app = ApplicationBuilder().token(TOKEN).build()

    # SETUP SCHEDULER DI DALAM LOOP ASYNC
    scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
    scheduler.add_job(scheduled_scan, 'interval', minutes=10, args=[app])
    scheduler.add_job(nightly_report, 'cron', hour=21, minute=30, args=[app])
    
    scheduler.start()
    logger.info("⏰ Scheduler started successfully.")

    # REGISTER HANDLERS
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("\n" + "="*45)
    print("🚀 HARU TERMINAL v11.8 - FINAL STABLE")
    print(f"Status: Full Async Loop Active")
    print("="*45 + "\n")

    # Jalankan bot
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        # Biar bot tetep jalan terus
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")



