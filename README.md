# Tarcoin Core & Global Database Node

Tarcoin is a lightweight, quantum-resistant, and distributed blockchain designed to operate securely with an external database architecture (via Flask-SQLAlchemy). It combines post-quantum security measures, hash-based signatures, strict input sanitization, and P2P node synchronization backed by global database storage.

## System Architecture

The project relies on a centralized or distributed relational database backend (such as PostgreSQL, MySQL, or server-hosted SQLite) mapped via SQLAlchemy to manage blocks, nonces, and network nodes persistently and concurrently.

## Key Features

* **Quantum Resistance**: Employs SHA3-512 hashing and post-quantum HMAC-SHA3-512 derivations to mitigate threats from Shor’s and Grover’s algorithms.
* **Global Database Storage**: Replaces fragile local JSON file storage with robust SQL-backed database mapping (`flask-sqlalchemy`) for multi-node scalability and data integrity.
* **Distributed P2P Consensus**: Implements the longest-chain rule and peer discovery via Flask REST endpoints.
* **Hardened Security**: Features regex input sanitization, nonce-based replay attack tracking stored in database tables, and strict payload type-checking.

## Installation

Ensure Python and pip are installed in your environment, then install the required dependencies:

```bash
pip install flask flask-sqlalchemy requests

```
Before running wallet.py, set the environment variable to point to your global node server (such as a cloud VPS, Heroku, or AWS server):

```bash
export TARCOIN_NODE_URL="http://your-server-ip:5000"
python wallet.py
