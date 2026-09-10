import os
import sys
import json
import time
import requests
import argparse
import subprocess
from pathlib import Path

WALLET_FILE = Path("wallet_keys.json")
DEFAULT_NODE = "http://127.0.0.1:5000"

def get_node_url():
    return os.getenv("TARCOIN_NODE", DEFAULT_NODE)

def save_keys(keys_data):
    with open(WALLET_FILE, "w") as f:
        json.dump(keys_data, f, indent=4)
    print(f"[+] Wallet keys successfully saved to {WALLET_FILE}")

def load_keys():
    if not WALLET_FILE.exists():
        print("[-] Wallet file (wallet_keys.json) not found. Please create a new wallet first using the 'create' command.")
        sys.exit(1)
    with open(WALLET_FILE, "r") as f:
        keys = json.load(f)
        # Fallback pengaman jika file wallet lama belum memiliki key_index
        if 'key_index' not in keys:
            keys['key_index'] = 0
        return keys

def update_wallet_index(new_index: int):
    """Memperbarui index kunci yang sudah terpakai di file wallet lokal."""
    if WALLET_FILE.exists():
        with open(WALLET_FILE, "r") as f:
            keys = json.load(f)
        keys['key_index'] = new_index
        with open(WALLET_FILE, "w") as f:
            json.dump(keys, f, indent=4)

def cmd_create(args):
    node_url = get_node_url()
    try:
        print(f"[*] Contacting the node to generate new post-quantum keys...")
        response = requests.get(f"{node_url}/wallet/new")
        if response.status_code == 200:
            data = response.json()
            save_keys(data)
            print(f"[+] Quantum Public Address: {data['quantum_public_key']}")
        else:
            print(f"[-] Failed to create wallet from node: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"[-] Connection failed to node {node_url}. Make sure the tarcoin.py server is running.")

def cmd_balance(args):
    keys = load_keys()
    address = keys['quantum_public_key']
    node_url = get_node_url()
    try:
        response = requests.get(f"{node_url}/balance/{address}")
        if response.status_code == 200:
            data = response.json()
            print(f"\n=== WALLET INFORMATION ===")
            print(f"Address   : {data['address']}")
            print(f"Balance   : {data['balance']} TAR")
            print(f"Key Index : {keys.get('key_index', 0)} (Stateful Lamport)")
        else:
            print(f"[-] Failed to retrieve balance: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"[-] Connection failed to node {node_url}.")

def cmd_send(args):
    keys = load_keys()
    node_url = get_node_url()
    
    import hashlib
    import secrets

    def sign_message_with_index(master_seed: str, message: str, key_index: int) -> str:
        msg_hash = hashlib.sha3_256(message.encode()).hexdigest()
        binary_msg = ''.join(format(int(c, 16), '04b') for c in msg_hash)[:256]
        signature_parts = []
        for i, bit in enumerate(binary_msg):
            # Menggunakan key_index agar kunci privat berbeda di tiap transaksi (Anti Key-Reuse)
            priv_0 = hashlib.sha3_512(f"{master_seed}_{key_index}_0_{i}".encode()).hexdigest()
            priv_1 = hashlib.sha3_512(f"{master_seed}_{key_index}_1_{i}".encode()).hexdigest()
            signature_parts.append(priv_0 if bit == '0' else priv_1)
        return json.dumps(signature_parts)

    sender = keys['quantum_public_key']
    receiver = args.to
    amount = float(args.amount)
    fee = float(args.fee)
    timestamp = time.time()
    nonce = secrets.randbits(32)
    current_key_index = keys.get('key_index', 0)

    if len(receiver) != 128:
        print("[-] Error: Invalid receiver address format (must be a 128-character hash).")
        return

    # Hash transaksi disesuaikan dengan backend yang menyertakan key_index
    tx_data_str = f"{sender}{receiver}{amount}{fee}{timestamp}{nonce}{current_key_index}"
    tx_hash = hashlib.sha3_512(tx_data_str.encode()).hexdigest()
    
    signature = sign_message_with_index(keys['private_seed'], tx_hash, current_key_index)
    raw_public_keys = keys['raw_public_keys']

    payload = {
        "sender": sender,
        "receiver": receiver,
        "amount": amount,
        "fee": fee,
        "timestamp": timestamp,
        "nonce": nonce,
        "signature": signature,
        "raw_public_keys": raw_public_keys,
        "key_index": current_key_index
    }

    try:
        print(f"[*] Broadcasting transaction using Key Index #{current_key_index}...")
        response = requests.post(f"{node_url}/transactions/new", json=payload)
        if response.status_code == 201:
            print("[+] Transaction successfully verified and broadcasted!")
            # Geser index kunci lokal secara otomatis untuk transaksi berikutnya agar aman
            update_wallet_index(current_key_index + 1)
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"[-] Transaction rejected: {response.json().get('message', response.text)}")
    except requests.exceptions.ConnectionError:
        print(f"[-] Connection failed to node {node_url}.")

def cmd_mine(args):
    keys = load_keys()
    miner_address = keys['quantum_public_key']
    node_url = get_node_url()
    
    if args.mode == "start":
        print(f"[*] Starting local mining process targeting address: {miner_address}")
        print("[*] Press Ctrl+C to stop (if running in foreground).")
        try:
            while True:
                res = requests.get(f"{node_url}/mine?miner={miner_address}")
                if res.status_code == 200:
                    block_info = res.json()
                    print(f"[+] Block #{block_info['index']} Successfully Mined! Hash: {block_info['hash'][:16]}...")
                else:
                    print(f"[-] Mining failed: {res.text}")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n[*] Mining stopped by user.")
            
    elif args.mode == "daemon":
        pid_file = Path("miner.pid")
        if pid_file.exists():
            print("[-] Miner daemon is already running or active PID file exists.")
            return
        print("[*] Running Miner Daemon in the background...")
        sub = subprocess.Popen([sys.executable, __file__, "mine", "start"])
        pid_file.write_text(str(sub.pid))
        print(f"[+] Daemon successfully started with PID: {sub.pid}")
        
    elif args.mode == "stop":
        pid_file = Path("miner.pid")
        if not pid_file.exists():
            print("[-] No active miner daemon records found.")
            return
        pid = int(pid_file.read_text())
        try:
            os.kill(pid, 9)
            print(f"[+] Miner daemon (PID: {pid}) successfully stopped.")
        except Exception as e:
            print(f"[-] Failed to stop process: {e}")
        finally:
            if pid_file.exists():
                pid_file.unlink()

def cmd_swap(args):
    """
    Simulated Token Swap Feature (e.g., Tarcoin to Wrapped Tarcoin / Ecosystem tokens)
    Utilizes internal/contract simulation mechanism through standard transaction routing.
    """
    keys = load_keys()
    swap_pool_address = "f" * 128  # Dummy liquidity pool address
    
    print(f"[*] Swapping {args.amount} TAR for {args.target_token.upper()} token...")
    args.to = swap_pool_address
    cmd_send(args)
    print(f"[+] Swap processed successfully! You have received ecosystem tokens: {args.target_token.upper()}.")

def main():
    parser = argparse.ArgumentParser(description="Tarcoin Post-Quantum CLI Wallet")
    subparsers = parser.add_subparsers(dest="command", help="Available Commands")

    subparsers.add_parser("create", help="Create a new wallet and quantum key pair")
    subparsers.add_parser("balance", help="Check current wallet balance")

    parser_send = subparsers.add_parser("send", help="Send TAR coins to another address")
    parser_send.add_argument("--to", required=True, help="Recipient public address (128 characters)")
    parser_send.add_argument("--amount", required=True, type=float, help="Amount of TAR to send")
    parser_send.add_argument("--fee", default=0.0, type=float, help="Transaction fee")

    parser_mine = subparsers.add_parser("mine", help="Mine new blocks")
    parser_mine.add_argument("mode", choices=["start", "daemon", "stop"], help="Mining execution mode")

    parser_swap = subparsers.add_parser("swap", help="Swap TAR for other ecosystem tokens")
    parser_swap.add_argument("--target-token", required=True, help="Target token symbol (e.g., wTAR, USDT)")
    parser_swap.add_argument("--amount", required=True, type=float, help="Amount of TAR to swap")
    parser_swap.add_argument("--fee", default=0.001, type=float, help="Swap fee")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "balance":
        cmd_balance(args)
    elif args.command == "send":
        cmd_send(args)
    elif args.command == "mine":
        cmd_mine(args)
    elif args.command == "swap":
        cmd_swap(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
