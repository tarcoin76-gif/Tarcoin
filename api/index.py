import sys
import os

# Tambahkan root directory ke sys.path agar main.py bisa terbaca
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
from http.server import BaseHTTPRequestHandler
from telegram import Update
from main import build_application

# Global instance
app = build_application()
initialized = False

async def setup():
    global initialized
    if not initialized:
        await app.initialize()
        initialized = True

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(setup())

        try:
            update_data = json.loads(post_data.decode('utf-8'))
            update = Update.de_json(update_data, app.bot)

            loop.run_until_complete(app.process_update(update))

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Tarcoin Vercel Serverless Webhook Bot is Running!")
