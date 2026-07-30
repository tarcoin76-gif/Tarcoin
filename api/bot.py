from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data.decode('utf-8'))
            
            # Logika penanganan pesan masuk / klik tombol Telegram Bot GUI di sini
            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "")
                
                # Respon otomatis sederhana untuk perintah /start
                if text == "/start":
                    response_data = {
                        "method": "sendMessage",
                        "chat_id": chat_id,
                        "text": "🤖 Selamat Datang di Tarcoin (TRC) Bot!\nMax Supply: 17.000.000 TRC\nSilakan gunakan menu di bawah.",
                    }
                    print(f"Mengirim respon ke chat_id: {chat_id}")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        return
