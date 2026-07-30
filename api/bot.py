from http.server import BaseHTTPRequestHandler
import json
import urllib.request

TELEGRAM_TOKEN = "8059211421:AAHUW4jx5_8mlURUDAwNlOsL2YKog9lBfQk"

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data.decode('utf-8'))
            
            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "")
                
                if text == "/start":
                    # Menyiapkan GUI Inline Keyboard & Web App Button
                    reply_markup = {
                        "inline_keyboard": [
                            [{"text": "📊 Cek Status TRC (17 Juta Supply)", "callback_data": "check_status"}],
                            [{"text": "👛 Buat Dompet ML-DSA-65", "callback_data": "create_wallet"}],
                            [{"text": "🌐 Buka Tarcoin Mini App Dashboard", "web_app": {"url": "https://url-vercel-anda.vercel.app/miniapp"}}]
                        ]
                    }
                    
                    payload = {
                        "chat_id": chat_id,
                        "text": "🤖 *Selamat Datang di Tarcoin (TRC) GUI Bot*\nAset Kripto Tahan Kuantum.\n\nSilakan pilih menu di bawah:",
                        "parse_mode": "Markdown",
                        "reply_markup": reply_markup
                    }
                    
                    # Kirim pesan kembali via Telegram API
                    req = urllib.request.Request(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        data=json.dumps(payload).encode('utf-8'),
                        headers={'Content-Type': 'application/json'}
                    )
                    urllib.request.urlopen(req)

            elif "callback_query" in update:
                # Menangani ketika pengguna menekan tombol Inline Keyboard
                query = update["callback_query"]
                chat_id = query["message"]["chat"]["id"]
                data = query["data"]
                
                answer_text = ""
                if data == "check_status":
                    answer_text = "📊 Status: Max Supply 17.000.000 TRC | Jaringan Aktif di Vercel Serverless."
                elif data == "create_wallet":
                    answer_text = "👛 Dompet Kuantum ML-DSA-65 berhasil diinisialisasi untuk akun Anda!"

                # Kirim balasan pop-up / ubah teks
                payload = {
                    "chat_id": chat_id,
                    "text": answer_text
                }
                req = urllib.request.Request(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                urllib.request.urlopen(req)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))
        return
