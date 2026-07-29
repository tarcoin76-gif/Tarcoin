import os
import json
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application
# Impor class/handler dari file utama bot Anda (misal: bot_core.py)
# from bot_core import GlobalTarcoinNode, get_user_wallet, ...

app = FastAPI()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_app = None

async def get_telegram_app():
    global telegram_app
    if telegram_app is None:
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        # Daftarkan handler Anda di sini (CommandHandler, CallbackQueryHandler, dll)
        # contoh:
        # telegram_app.add_handler(CommandHandler("start", start_command))
        await telegram_app.initialize()
    return telegram_app

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        app_instance = await get_telegram_app()
        update = Update.de_json(data, app_instance.bot)
        await app_instance.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def index():
    return {"status": "Tarcoin Telegram Bot is active on Vercel!"}
