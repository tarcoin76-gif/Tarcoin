# Tarcoin Core & Wallet

Tarcoin is a lightweight, quantum-resistant, and distributed blockchain designed to operate securely on mobile environments like Termux and resource-constrained systems. It combines post-quantum security measures, hash-based signatures, strict input sanitization, and P2P node synchronization.

## System Architecture

The project consists of two main components:
1. **`tarcoin.py`**: The core blockchain node server, managing the ledger, Proof of Work mining, P2P consensus, and REST API endpoints.
2. **`tarcoin_wallet.py`**: The interactive command-line wallet client used to generate quantum-safe keys, check balances, and submit transactions.

## Key Features

* **Quantum Resistance**: Employs SHA3-512 hashing and hash-based key derivation to mitigate threats from Shor’s and Grover’s algorithms.
* **Distributed P2P Consensus**: Implements the longest-chain rule and peer discovery via Flask REST endpoints.
* **Hardened Security**: Features regex input sanitization, nonce-based replay attack prevention, and strict payload type-checking.
* **Persistent Storage**: Automatically saves and loads blockchain states using local JSON storage.

## Installation

Ensure Python and pip are installed in your Termux or Linux environment, then install the required dependencies:

```bash
pip install flask requests ecdsa
