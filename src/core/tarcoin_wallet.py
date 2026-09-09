import hashlib
import hmac
import secrets
import time
import requests
import os
import sys

class QuantumResistantWallet:
    """Client-side wallet utility for generating keys and signing Tarcoin transactions."""

    @staticmethod
    def generate_wallet() -> dict:
        """Generates a new quantum-resistant private seed and public key address."""
        private_seed = secrets.token_hex(64)
        public_key = hashlib.sha3_512(private_seed.encode()).hexdigest()
        return {
            'private_seed': private_seed,
            'public_key': public_key
        }

    @staticmethod
    def sign_message(private_seed: str, message: str) -> str:
        """Signs a transaction payload hash using HMAC-SHA3-512."""
        message_hash = hashlib.sha3_512(message.encode()).digest()
        return hmac.new(private_seed.encode(), message_hash, hashlib.sha3_512).hexdigest()

    @staticmethod
    def build_transaction(sender_pubkey: str, private_seed: str, receiver: str, amount: float, fee: float, nonce: int) -> dict:
        """Constructs and signs a transaction payload ready to be sent to the node."""
        timestamp = time.time()
        tx_data = f"{sender_pubkey}{receiver}{amount}{fee}{timestamp}{nonce}"
        message = hashlib.sha3_512(tx_data.encode()).hexdigest()
        signature = QuantumResistantWallet.sign_message(private_seed, message)

        return {
            'sender': sender_pubkey,
            'receiver': receiver,
            'amount': amount,
            'fee': fee,
            'timestamp': timestamp,
            'nonce': nonce,
            'signature': signature
        }


def get_node_url() -> str:
    # Mengambil URL dari environment variable global, atau fallback ke localhost jika tidak diset
    return os.getenv('TARCOIN_NODE_URL', 'http://127.0.0.1:5000')


def check_balance(node_url: str, address: str):
    try:
        response = requests.get(f"{node_url}/balance/{address}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Address: {data['address']}")
            print(f"Balance: {data['balance']} TAR")
        else:
            print(f"Error: {response.json().get('message')}")
    except requests.exceptions.RequestException as e:
        print(f"Connection to global node failed: {e}")


def send_transaction(node_url: str, sender_pubkey: str, private_seed: str, receiver: str, amount: float, fee: float):
    nonce = secrets.randbits(32)
    
    tx_payload = QuantumResistantWallet.build_transaction(
        sender_pubkey=sender_pubkey,
        private_seed=private_seed,
        receiver=receiver,
        amount=amount,
        fee=fee,
        nonce=nonce
    )

    try:
        response = requests.post(f"{node_url}/transactions/new", json=tx_payload, timeout=5)
        print(response.json().get('message'))
    except requests.exceptions.RequestException as e:
        print(f"Failed to submit transaction to global node: {e}")


if __name__ == '__main__':
    node = get_node_url()
    
    print(f"=== Tarcoin CLI Wallet (Connected to Node: {node}) ===")
    print("1. Generate New Wallet")
    print("2. Check Balance")
    print("3. Send Transaction")
    
    choice = input("Select an option (1-3): ").strip()
    
    if choice == '1':
        wallet = QuantumResistantWallet.generate_wallet()
        print("\n[New Wallet Created Successfully]")
        print(f"Private Seed (Keep Secret!): {wallet['private_seed']}")
        print(f"Public Key / Address: {wallet['public_key']}")
        
    elif choice == '2':
        addr = input("Enter wallet address (128 hex chars): ").strip()
        check_balance(node, addr)
        
    elif choice == '3':
        sender_key = input("Enter your Sender Public Key: ").strip()
        priv_seed = input("Enter your Private Seed: ").strip()
        recv_key = input("Enter Receiver Public Key: ").strip()
        amt = float(input("Enter Amount: ").strip())
        tx_fee = float(input("Enter Fee: ").strip())
        
        send_transaction(node, sender_key, priv_seed, recv_key, amt, tx_fee)
    else:
        print("Invalid option selected.")
