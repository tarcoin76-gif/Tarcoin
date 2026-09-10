import sys
import os
import json
import hashlib
import secrets
import requests
from typing import Dict, Any

# Ensure default node path points to your local Flask port
DEFAULT_NODE_URL = os.getenv('NODE_URL', 'http://127.0.0.1:5000')

class WalletClient:
    @staticmethod
    def create_new_wallet() -> Dict[str, str]:
        """Generates a new post-quantum key pair from the local node."""
        try:
            response = requests.get(f"{DEFAULT_NODE_URL}/wallet/new", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[X] Failed to create wallet from node: {response.text}")
                sys.exit(1)
        except requests.exceptions.ConnectionError:
            print(f"[X] Unable to connect to blockchain node at {DEFAULT_NODE_URL}. Ensure the node is running.")
            sys.exit(1)

    @staticmethod
    def get_balance(address: str) -> float:
        """Checks the balance of a specific address on the blockchain."""
        try:
            response = requests.get(f"{DEFAULT_NODE_URL}/balance/{address}", timeout=5)
            if response.status_code == 200:
                return response.json().get('balance', 0.0)
            else:
                print(f"[X] Server error: {response.text}")
                return 0.0
        except requests.exceptions.ConnectionError:
            print(f"[X] Connection to node failed at {DEFAULT_NODE_URL}.")
            return 0.0

    @staticmethod
    def sign_message(master_seed: str, message: str) -> str:
        """Signs a message hash using the Lamport Signature scheme identical to the node."""
        msg_hash = hashlib.sha3_256(message.encode()).hexdigest()
        binary_msg = ''.join(format(int(c, 16), '04b') for c in msg_hash)[:256]
        
        signature_parts = []
        for i, bit in enumerate(binary_msg):
            priv_0 = hashlib.sha3_512(f"{master_seed}_0_{i}".encode()).hexdigest()
            priv_1 = hashlib.sha3_512(f"{master_seed}_1_{i}".encode()).hexdigest()
            
            if bit == '0':
                signature_parts.append(priv_0)
            else:
                signature_parts.append(priv_1)
                
        return json.dumps(signature_parts)

    @staticmethod
    def send_transaction(sender_seed: str, sender_pub_key: str, raw_pub_keys: str, receiver: str, amount: float, fee: float) -> bool:
        """Creates, signs, and broadcasts a new transaction to the blockchain."""
        import time
        
        timestamp = time.time()
        nonce = secrets.randbits(32)
        
        # Calculate transaction data hash precisely like the node
        tx_data = f"{sender_pub_key}{receiver}{amount}{fee}{timestamp}{nonce}"
        message_hash = hashlib.sha3_512(tx_data.encode()).hexdigest()
        
        # Create post-quantum digital signature
        signature = WalletClient.sign_message(sender_seed, message_hash)
        
        payload = {
            'sender': sender_pub_key,
            'receiver': receiver,
            'amount': float(amount),
            'fee': float(fee),
            'timestamp': float(timestamp),
            'nonce': int(nonce),
            'signature': signature,
            'raw_public_keys': raw_pub_keys
        }
        
        try:
            response = requests.post(f"{DEFAULT_NODE_URL}/transactions/new", json=payload, timeout=5)
            if response.status_code == 201:
                print("[V] Transaction successfully sent and verified by the network!")
                print(json.dumps(response.json(), indent=2))
                return True
            else:
                print(f"[X] Transaction rejected: {response.text}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"[X] Failed to send transaction to {DEFAULT_NODE_URL}.")
            return False


def print_help():
    print("=== TARCOIN WALLET CLI GUIDE ===")
    print("1. Create New Wallet:")
    print("   python wallet.py create")
    print("\n2. Check Address Balance:")
    print("   python wallet.py balance <QUANTUM_PUBLIC_KEY>")
    print("\n3. Send Coins:")
    print("   python wallet.py send <PRIVATE_SEED> <SENDER_PUBLIC_KEY> <RAW_PUBLIC_KEYS_JSON> <RECEIVER_ADDRESS> <AMOUNT> <FEE>")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'create':
        print("[*] Generating new Post-Quantum (Lamport) keys...")
        wallet_data = WalletClient.create_new_wallet()
        print("\n--- WALLET SUCCESSFULLY CREATED ---")
        print(f"PRIVATE_SEED       : {wallet_data['private_key']}")
        print(f"PUBLIC_KEY (Address): {wallet_data['quantum_public_key']}")
        print(f"RAW_PUBLIC_KEYS    : {wallet_data['raw_public_keys']}")
        print("\nIMPORTANT: Keep your Private Seed safe! Never share it with anyone.")

    elif command == 'balance':
        if len(sys.argv) < 3:
            print("[X] Missing arguments. Usage: python wallet.py balance <PUBLIC_KEY_ADDRESS>")
            sys.exit(1)
        address = sys.argv[2]
        balance = WalletClient.get_balance(address)
        print(f"Address: {address}")
        print(f"Balance: {balance} TAR")

    elif command == 'send':
        if len(sys.argv) < 8:
            print("[X] Incomplete arguments.")
            print("Usage: python wallet.py send <PRIVATE_SEED> <SENDER_PUBKEY> <RAW_PUBKEYS> <RECEIVER> <AMOUNT> <FEE>")
            sys.exit(1)
        
        p_seed = sys.argv[2]
        s_pub = sys.argv[3]
        r_pubkeys = sys.argv[4]
        receiver = sys.argv[5]
        amount = float(sys.argv[6])
        fee = float(sys.argv[7])

        print("[*] Signing transaction with Post-Quantum cryptography...")
        WalletClient.send_transaction(p_seed, s_pub, r_pubkeys, receiver, amount, fee)

    else:
        print(f"[X] Unknown command: {command}")
        print_help()
