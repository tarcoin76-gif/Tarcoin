import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Halo {user.first_name}! Selamat datang di Tarcoin Bot.\n"
        "Gunakan perintah yang tersedia untuk mulai berinteraksi."
    )

def create_bot_app():
    """Membuat dan mengonfigurasi aplikasi bot Telegram"""
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN belum disetel di Environment Variables!")
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Daftarkan handlers di sini
    application.add_handler(CommandHandler("start", start))
    
    return application

def main():
    """Menjalankan bot secara lokal (Long Polling)"""
    application = create_bot_app()
    logger.info("Memulai bot Tarcoin secara lokal...")
    application.run_polling()

if __name__ == "__main__":
    main()
