import sys
import os
import time
import json
import requests
import argparse
import hashlib
import secrets

# --- TARCOIN CLI WALLET CLIENT ---
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
                print("[+] New wallet successfully created and saved to 'tarcoin_wallet.json'!")
                print(f"    Public Address (Sender): {wallet_data['quantum_public_key']}")
            else:
                print("[-] Failed to create wallet from node:", response.text)
        except requests.exceptions.ConnectionError:
            print(f"[-] Error: Could not connect to the Tarcoin node at {self.node_url}")

    def load_wallet(self):
        if not os.path.exists(self.wallet_file):
            print("[-] Wallet file not found. Please create a wallet first using the 'create-wallet' command.")
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
                print(f"\n[ Tarcoin Wallet Information ]")
                print(f" Address : {data['address']}")
                print(f" Balance : {data['balance']} TAR\n")
            else:
                print("[-] Failed to retrieve balance:", response.text)
        except requests.exceptions.ConnectionError:
            print("[-] Error: Connection to the node was lost.")

    def send_token(self, receiver: str, amount: float, fee: float = 0.0):
        wallet = self.load_wallet()
        if not wallet:
            return

        private_seed = wallet['private_seed']
        raw_public_keys = wallet['raw_public_keys']
        sender_address = wallet['quantum_public_key']

        timestamp = time.time()
        nonce = secrets.randbits(32)

        # Build transaction message payload to sign locally
        tx_data_str = f"{sender_address}{receiver}{amount}{fee}{timestamp}{nonce}"
        message_hash = hashlib.sha3_512(tx_data_str.encode()).hexdigest()

        # Compute Lamport Signature (256-bit)
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
                print("[+] Transaction successfully sent and added to the node's mempool!")
            else:
                print("[-] Transaction rejected by node:", response.json().get('message'))
        except requests.exceptions.ConnectionError:
            print("[-] Error: Could not connect to the node network.")

    def auto_mining(self):
        wallet = self.load_wallet()
        if not wallet:
            return
        miner_address = wallet['quantum_public_key']
        print(f"[i] Starting Auto-Mining to personal address: {miner_address[:16]}... (Press Ctrl+C to stop)")
        
        try:
            while True:
                response = requests.get(f"{self.node_url}/mine?miner={miner_address}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"[+] New Block Forged! Index: {data['index']} | Hash: {data['hash'][:16]}...")
                else:
                    print("[-] Mining failed:", response.json().get('message'))
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n[i] Auto-mining stopped by user.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tarcoin CLI Wallet & Miner")
    parser.add_argument('action', choices=['create-wallet', 'balance', 'send', 'mining'], help="Desired CLI action")
    parser.add_argument('--node', default="http://127.0.0.1:5000", help="Tarcoin Node URL (Default: http://127.0.0.1:5000)")
    parser.add_argument('--to', help="Recipient token address (128 hex characters)")
    parser.add_argument('--amount', type=float, help="Amount of tokens to send")
    parser.add_argument('--fee', type=float, default=0.0, help="Transaction fee (optional)")

    args = parser.parse_args()
    cli = TarcoinWalletCLI(node_url=args.node)

    if args.action == 'create-wallet':
        cli.create_wallet()
    elif args.action == 'balance':
        cli.check_balance()
    elif args.action == 'send':
        if not args.to or args.amount is None:
            print("[-] Error: The 'send' command requires both --to and --amount parameters.")
        else:
            cli.send_token(args.to, args.amount, args.fee)
    elif args.action == 'mining':
        cli.auto_mining()
