# 🪙 Tarcoin 🪙 Post-Quantum Blockchain & CLI Wallet

Tarcoin is an experimental blockchain implementation integrating a **Lamport Signature Scheme**-based Post-Quantum Cryptography protocol (utilizing SHA3-512 and SHA3-256 hash functions). This system is designed to secure transactions against future quantum computing decryption threats.

---

## Key Features

* **Post-Quantum Lamport Signatures**: Utilizes hash-based signature schemes (256 key pairs per signature) for high-level quantum resistance.
* **Global Database (SQLite & SQLAlchemy)**: Persistently stores block history, address balances, transactions, and network nodes.
* **P2P Socket Manager**: Automated synchronization across network nodes via peer-to-peer TCP socket communication.
* **Flexible CLI Wallet**: Command-line wallet utility for key management, balance checking, fund transfers, token swaps, and local or background daemon mining control.

---

## Project File Structure

* `tarcoin.py`: Core blockchain node code, Flask REST API, PoW consensus logic, and P2P server manager.
* `wallet.py`: Wallet command-line interface (CLI) to interact with the Tarcoin node.

---

## Installation & Running the Node (`tarcoin.py`)

1. Ensure the required Python libraries are installed:
   ```bash
   pip install flask flask_sqlalchemy requests
