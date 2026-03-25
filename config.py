import os
import sys
import logging
import httpx
from dotenv import load_dotenv

# 1. LOAD ENVIRONMENT
load_dotenv(dotenv_path="API.env")

# 2. CORE IDENTITY & API KEYS
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEXCHECK_API_KEY = os.getenv("DEXCHECK_API_KEY")
NANSEN_KEY = os.getenv("NANSEN_API_KEY")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")

# 3. VALIDATION FUNCTION
def validate_config():
    """Validasi keberadaan dan tipe data environment variables."""
    required_vars = {
        "TELEGRAM_TOKEN": TOKEN,
        "ADMIN_CHAT_ID": ADMIN_ID_RAW
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print(f"❌ ERROR: Variable berikut hilang di API.env: {', '.join(missing)}")
        sys.exit(1)
    
    try:
        int(ADMIN_ID_RAW)
    except (ValueError, TypeError):
        print("❌ ERROR: ADMIN_CHAT_ID harus berupa angka (ID Telegram)!")
        sys.exit(1)

# Jalankan validasi
validate_config()

# 4. WHITELIST AUTHENTICATION (Poin Kritis: Anti-Spam)
# Gabungkan ADMIN_ID dan ID partner dalam satu list agar tidak saling overwrite.
ADMIN_ID = int(ADMIN_ID_RAW)
WHITELIST = [
    ADMIN_ID,    # ID Utama
    5795232177,  # ID Kakak
]

# 5. STRATEGY PARAMETERS
SCORE_THRESHOLD = 3  
VOL_MIN = 3_000_000  
OI_MIN = 1_000_000   

# 6. LOGGING CONFIGURATION
LOG_FILE = "haru_v10.log"
MAX_LOG_SIZE = 5 * 1024 * 1024 
BACKUP_COUNT = 3                

# 7. EXTERNAL API FUNCTIONS
async def fetch_dexcheck_trending():
    """Mengambil data token trending dari DexCheck secara non-blocking."""
    if not DEXCHECK_API_KEY:
        return []
        
    url = "https://api.dexcheck.ai/v1/trending-tokens"
    headers = {"X-API-KEY": DEXCHECK_API_KEY}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=15.0)
            if response.status_code == 200:
                data = response.json()
                return [{
                    'symbol': token.get('symbol'),
                    'volume': token.get('volume24h'),
                    'smart_money_signal': True 
                } for token in data[:5]]
            return []
        except Exception as e:
            print(f"⚠️ DexCheck Error: {str(e)}")
            return []
        


