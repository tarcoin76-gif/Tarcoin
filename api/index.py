from http.server import BaseHTTPRequestHandler
import json
import asyncio
from main import build_application

# Inisialisasi Telegram Application dari main.py
app = build_application()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Jalur tes biasa jika URL dibuka via Browser
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        response_text = "<h1>🤖 Tarcoin Telegram Bot Serverless Node Active!</h1>"
        self.wfile.write(response_text.encode('utf-8'))

    def do_POST(self):
        # Menangani Webhook update yang dikirim otomatis oleh Telegram
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            update_data = json.loads(post_data.decode('utf-8'))
            
            async def process():
                await app.initialize()
                from telegram import Update
                update = Update.de_json(update_data, app.bot)
                await app.process_update(update)
                await app.shutdown()

            asyncio.run(process())

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
