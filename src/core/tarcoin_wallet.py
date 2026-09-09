import requests
import sys

NODE_URL = "http://127.0.0.1:5000"

def create_wallet():
    response = requests.get(f"{NODE_URL}/wallet/new")
    if response.status_code == 200:
        data = response.json()
        print("\n--- NEW QUANTUM WALLET CREATED ---")
        print(f"Private Seed: {data['private_seed']}")
        print(f"Public Key (Address): {data['quantum_public_key']}")
    else:
        print("Failed to create wallet.")

def check_balance(address):
    response = requests.get(f"{NODE_URL}/balance/{address}")
    if response.status_code == 200:
        data = response.json()
        print(f"\nBalance for {address[:16]}...: {data['balance']} TRC")
    else:
        print(f"Error: {response.json().get('message', 'Unknown error')}")

if __name__ == "__main__":
    while True:
        print("\n=== TARCOIN WALLET CLI ===")
        print("1. Create New Wallet")
        print("2. Check Balance")
        print("3. Exit")
        
        choice = input("Select option (1-3): ").strip()
        if choice == "1":
            create_wallet()
        elif choice == "2":
            addr = input("Enter Quantum Public Key Address: ").strip()
            check_balance(addr)
        elif choice == "3":
            break
        else:
            print("Invalid choice.")
