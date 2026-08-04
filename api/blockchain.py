from http.server import BaseHTTPRequestHandler
import json
import hashlib

CONFIG = {
    "name": "Tarcoin",
    "symbol": "TRC",
    "max_supply": 17_000_000.0,
    "initial_reward": 50.0,
    "algorithm": "SHA3-256 (Fallback)"
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        path = self.path
        if "/api/status" in path:
            data = {
                "coin": CONFIG["name"],
                "symbol": CONFIG["symbol"],
                "max_supply": CONFIG["max_supply"],
                "total_mined": 1_000_050.0,
                "height": 1050,
                "current_reward": CONFIG["initial_reward"],
                "algorithm": CONFIG["algorithm"]
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        elif "/api/wallet/create" in path:
            # Menggunakan hashlib bawaan Python agar aman di Vercel
            random_data = hashlib.sha256(str(hashlib.sha3_256()).encode()).digest()
            public_key = random_data
            pub_hash = hashlib.sha3_256(public_key).hexdigest()
            address = "trc1" + pub_hash[:38]
            
            data = {
                "address": address,
                "public_key": public_key.hex(),
                "crypto": "SHA3-256",
                "status": "success"
            }
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        else:
            home_page = {
                "message": "Tarcoin (TRC) Serverless Node is Live on Vercel",
                "endpoints": ["/api/status", "/api/wallet/create"]
            }
            self.wfile.write(json.dumps(home_page).encode('utf-8'))
        return
