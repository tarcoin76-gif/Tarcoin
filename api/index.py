from http.server import BaseHTTPRequestHandler
import json
import asyncio
from main import build_application

# Inisialisasi Telegram Application
app = build_application()

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        response_text = "<h1>🤖 Tarcoin Telegram Bot Serverless Node is Running!</h1>"
        self.wfile.write(response_text.encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            update_data = json.loads(post_data.decode('utf-8'))
            
            # Jalankan event loop untuk memproses Webhook dari Telegram
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
