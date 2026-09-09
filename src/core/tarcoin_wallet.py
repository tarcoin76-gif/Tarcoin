import sys
import os
import time
import json
import requests
import argparse

# --- KLIENT KRIPTOGRAFI LAMPORT & WALLET ---
class TarcoinWalletCLI:
    def __init__(self, node_url="http://127.0.0.1:5000"):
        self.node_url = node_url
        self.wallet_file = "tarcoin_wallet.json"

    def create_wallet(self):
        try:
            response = requests.get(f"{self.node_url}/wallet/new")
            if response.status_code == 200:
                wallet_data = response.json()
                with open(self.wallet_file, "w") as f:
                    json.dump(wallet_data, f, indent=4)
                print("[+] Dompet baru berhasil dibuat dan disimpan ke 'tarcoin_wallet.json'!")
                print(f"    Alamat Publik (Sender): {wallet_data['quantum_public_key']}")
            else:
                print("[-] Gagal membuat dompet dari node:", response.text)
        except requests.exceptions.ConnectionError:
            print(f"[-] Error: Tidak dapat terhubung ke node Tarcoin di {self.node_url}")

    def load_wallet(self):
        if not os.path.exists(self.wallet_file):
            print("[-] File dompet tidak ditemukan. Buat dompet terlebih dahulu menggunakan perintah 'create-wallet'.")
            return None
        with open(self.wallet_file, "r") as f:
            return json.load(f)

    def check_balance(self):
        wallet = self.load_wallet()
        if not wallet:
            return
        address = wallet['quantum_public_key']
        try:
            response = requests.get(f"{self.node_url}/balance/{address}")
            if response.status_code == 200:
                data = response.json()
                print(f"\n[ Informasi Dompet Tarcoin ]")
                print(f" Alamat : {data['address']}")
                print(f" Saldo  : {data['balance']} TAR\n")
            else:
                print("[-] Gagal mengambil saldo:", response.text)
        except requests.exceptions.ConnectionError:
            print(f"[-] Error: Koneksi ke node terputus.")

    def send_token(self, receiver: str, amount: float, fee: float = 0.0):
        wallet = self.load_wallet()
        if not wallet:
            return

        # Import modul kriptografi lokal untuk penandatanganan transaksi
        import hashlib
        import hmac

        # Hitung tanda tangan Lamport secara lokal menggunakan private_seed
        private_seed = wallet['private_seed']
        raw_public_keys = wallet['raw_public_keys']
        sender_address = wallet['quantum_public_key']

        timestamp = time.time()
        # Mengambil nonce berbasis random aman atau counter sederhana
        import secrets
        nonce = secrets.randbits(32)

        # Buat payload pesan transaksi untuk ditandatangani
        tx_data_str = f"{sender_address}{receiver}{amount}{fee}{timestamp}{nonce}"
        message_hash = hashlib.sha3_512(tx_data_str.encode()).hexdigest()

        # Proses Tanda Tangan Lamport (256-bit)
        msg_hash_bin = hashlib.sha3_256(message_hash.encode()).hexdigest()
        binary_msg = ''.join(format(int(c, 16), '04b') for c in msg_hash_bin)[:256]

        signature_parts = []
        for i, bit in enumerate(binary_msg):
            priv_0 = hashlib.sha3_512(f"{private_seed}_0_{i}".encode()).hexdigest()
            priv_1 = hashlib.sha3_512(f"{private_seed}_1_{i}".encode()).hexdigest()
            signature_parts.append(priv_0 if bit == '0' else priv_1)

        signature_json = json.dumps(signature_parts)

        payload = {
            'sender': sender_address,
            'receiver': receiver,
            'amount': amount,
            'fee': fee,
            'timestamp': timestamp,
            'nonce': nonce,
            'signature': signature_json,
            'raw_public_keys': raw_public_keys
        }

        try:
            response = requests.post(f"{self.node_url}/transactions/new", json=payload)
            if response.status_code == 201:
                print("[+] Transaksi berhasil dikirim dan masuk mempool node!")
            else:
                print("[-] Transaksi ditolak oleh node:", response.json().get('message'))
        except requests.exceptions.ConnectionError:
            print(f"[-] Error: Tidak dapat terhubung ke jaringan node.")

    def auto_mining(self):
        wallet = self.load_wallet()
        if not wallet:
            return
        miner_address = wallet['quantum_public_key']
        print(f"[i] Memulai Auto-Mining ke alamat pribadi: {miner_address[:16]}... (Tekan Ctrl+C untuk berhenti)")
        
        try:
            while True:
                response = requests.get(f"{self.node_url}/mine?miner={miner_address}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"[+] Blok Baru Ditemukan! Index: {data['index']} | Hash: {data['hash'][:16]}...")
                else:
                    print("[-] Mining gagal:", response.json().get('message'))
                time.sleep(5) # Jeda antar iterasi penambangan
        except KeyboardInterrupt:
            print("\n[i] Auto-mining dihentikan oleh pengguna.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tarcoin CLI Wallet & Miner")
    parser.add_argument('action', choices=['create-wallet', 'balance', 'send', 'mining'], help="Aksi CLI yang diinginkan")
    parser.add_argument('--node', default="http://127.0.0.1:5000", help="URL Node Tarcoin (Default: http://127.0.0.1:5000)")
    parser.add_argument('--to', help="Alamat penerima token (128 karakter hex)")
    parser.add_argument('--amount', type=float, help="Jumlah token yang dikirim")
    parser.add_argument('--fee', type=float, default=0.0, help="Biaya transaksi (opsional)")

    args = parser.parse_args()
    cli = TarcoinWalletCLI(node_url=args.node)

    if args.action == 'create-wallet':
        cli.create_wallet()
    elif args.action == 'balance':
        cli.check_balance()
    elif args.action == 'send':
        if not args.to or args.amount is None:
            print("[-] Error: Perintah 'send' memerlukan parameter --to dan --amount.")
        else:
            cli.send_token(args.to, args.amount, args.fee)
    elif args.action == 'mining':
        cli.auto_mining()
