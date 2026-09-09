<div align="center">

# 🪙 Tarcoin Core 🪙
### **Blockchain 2.0 Quantum Resistant**

<p align="center">
   width="300px" style="border-radius: 15px;">
</p>

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Framework-lightgrey.svg)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red.svg)](https://www.sqlalchemy.org/)
[![Quantum Resistant](https://img.shields.io/badge/Security-Quantum%20Resistant-success.svg)](https://github.com/)

</div>

---

## 📖 About Project

**Tarcoin** is a lightweight, quantum-resistant, and distributed blockchain designed to operate securely with an external global database architecture (via Flask-SQLAlchemy). It combines post-quantum security measures, hash-based signatures, and strict input validation.

---

## 🏗️ System Architecture

The project relies on a centralized or distributed relational database backend (such as PostgreSQL, MySQL, or server-hosted SQLite) mapped via SQLAlchemy to persistently and concurrently manage blocks, nonces, and network nodes.

---

## ✨ Key Features

- 🛡️ **Quantum Resistance**: Employs SHA3-512 hashing and post-quantum HMAC-SHA3-512 derivations to mitigate threats from Shor’s and Grover’s algorithms.
- 🗄️ **Global Database Storage**: Replaces fragile local JSON file storage with robust SQL-backed database mapping (`flask-sqlalchemy`) to support multi-node scalability and data integrity.
- 🌐 **Distributed P2P Consensus**: Implements the longest-chain rule and peer discovery via Flask REST endpoints.
- 🔒 **Enhanced Security**: Features regex input sanitization, nonce-based replay attack tracking stored in database tables, and strict payload type-checking.

---

## 📦 Installation & Dependencies

Ensure Python and `pip` are installed in your environment, then run the following command to install the required dependencies:

```bash
pip install flask flask-sqlalchemy requests
