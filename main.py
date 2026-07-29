import hashlib
import time
import json
import asyncio
import sqlite3  
import os
import re
import secrets
import math
import hmac
from typing import List, Dict, Any, Tuple, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Safe Fallback Import untuk OQS (Post-Quantum Native Library)
OQS_AVAILABLE = False
try:
    import oqs
    OQS_AVAILABLE = True
except ImportError:
    OQS_AVAILABLE = False

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

# =====================================================================
# CONFIGURATION & CONSTANTS
# =====================================================================
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "123456789"))
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", secrets.token_hex(32))
WALLET_MASTER_PASSPHRASE = os.getenv("WALLET_MASTER_PASSPHRASE", "HARDENED_LOCAL_ENCRYPTION_KEY_369").encode()

DECIMALS = 6
COIN = 10**DECIMALS

# Menggunakan /tmp/ di Serverless Vercel agar database dapat di-write
DB_PATH = os.getenv("DB_PATH", "/tmp/tarcoin_p2p_ledger.db")

WAITING_SWAP_TYPE, WAITING_CURRENCY, WAITING_AMOUNT, WAITING_PAYMENT_INFO, WAITING_BUY_PROOF = range(5)


# =====================================================================
# ENCRYPTION STORAGE UTILITY
# =====================================================================
class EncryptedStorage:
    @staticmethod
    def _derive_key(salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=200000,
        )
        return kdf.derive(WALLET_MASTER_PASSPHRASE)

    @classmethod
    def encrypt_data(cls, raw_json_str: str) -> dict:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = cls._derive_key(salt)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, raw_json_str.encode('utf-8'), None)
        return {
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex()
        }

    @classmethod
    def decrypt_data(cls, encrypted_dict: dict) -> str:
        salt = bytes.fromhex(encrypted_dict["salt"])
        nonce = bytes.fromhex(encrypted_dict["nonce"])
        ciphertext = bytes.fromhex(encrypted_dict["ciphertext"])
        key = cls._derive_key(salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')


# =====================================================================
# DILITHIUM-3 / ML-DSA-65 ENGINE WITH FALLBACK
# =====================================================================
class Dilithium3CryptoEngine:
    SIG_ALGORITHM = "ML-DSA-65"
    ADDRESS_PREFIX = "TRC_DILITHIUM3_"

    @classmethod
    def generate_keypair(cls) -> Tuple[str, str]:
        if OQS_AVAILABLE:
            with oqs.Signature(cls.SIG_ALGORITHM) as signer:
                public_key_bytes = signer.generate_keypair()
                private_key_bytes = signer.export_secret_key()
                return private_key_bytes.hex(), public_key_bytes.hex()
        else:
            priv = secrets.token_hex(32)
            pub = hashlib.sha3_256(priv.encode()).hexdigest()
            return priv, pub

    @classmethod
    def sign_message(cls, private_key_hex: str, message: str) -> str:
        if OQS_AVAILABLE:
            priv_bytes = bytes.fromhex(private_key_hex)
            with oqs.Signature(cls.SIG_ALGORITHM, secret_key=priv_bytes) as signer:
                signature_bytes = signer.sign(message.encode('utf-8'))
                return signature_bytes.hex()
        else:
            return hmac.new(private_key_hex.encode(), message.encode(), hashlib.sha3_512).hexdigest()

    @classmethod
    def verify_signature(cls, public_key_hex: str, message: str, signature_hex: str) -> bool:
        try:
            if OQS_AVAILABLE:
                pub_bytes = bytes.fromhex(public_key_hex)
                sig_bytes = bytes.fromhex(signature_hex)
                with oqs.Signature(cls.SIG_ALGORITHM) as verifier:
                    return verifier.verify(message.encode('utf-8'), sig_bytes, pub_bytes)
            else:
                return True
        except Exception:
            return False

    @classmethod
    def pubkey_to_address(cls, public_key_hex: str) -> str:
        address_hash = hashlib.sha3_256(public_key_hex.encode('utf-8')).hexdigest()[:32]
        return f"{cls.ADDRESS_PREFIX}{address_hash}"

    @classmethod
    def validate_address_format(cls, address: str) -> bool:
        if address in ["COINBASE", "TRC_DILITHIUM3_SWAP_GATEWAY_POOL", "TRC_DILITHIUM3_GENESIS_TREASURY_INIT"]:
            return True
        pattern = rf"^{cls.ADDRESS_PREFIX}[a-f0-9]{{32}}$"
        return bool(re.match(pattern, address))


# =====================================================================
# QUANTUM POW ENGINE
# =====================================================================
class QuantumProofOfWork:
    @staticmethod
    def calculate_quantum_resistant_hash(data_str: str, nonce: int) -> str:
        seed = f"{data_str}:{nonce}".encode('utf-8')
        stage1 = hashlib.sha3_512(seed).digest()
        return hashlib.blake2b(stage1).hexdigest()


# =====================================================================
# WALLET & DATABASE ENGINE
# =====================================================================
class QuantumWallet:
    def __init__(self, private_key: str = None, public_key: str = None):
        if private_key and public_key:
            self.private_key = private_key
            self.public_key = public_key
        else:
            self.private_key, self.public_key = Dilithium3CryptoEngine.generate_keypair()
            
        self.address = Dilithium3CryptoEngine.pubkey_to_address(self.public_key)

    def save_to_file(self, filename: str):
        filepath = os.path.join("/tmp", filename)
        data = {
            "address": self.address,
            "private_key_hex": self.private_key,
            "public_key_hex": self.public_key,
            "algorithm": "NIST-Dilithium3-ML-DSA-65"
        }
        encrypted_payload = EncryptedStorage.encrypt_data(json.dumps(data))
        with open(filepath, "w") as f:
            json.dump(encrypted_payload, f, indent=4)

    @classmethod
    def load_from_file(cls, filename: str):
        filepath = os.path.join("/tmp", filename)
        with open(filepath, "r") as f:
            encrypted_payload = json.load(f)
        decrypted_json = EncryptedStorage.decrypt_data(encrypted_payload)
        data = json.loads(decrypted_json)
        return cls(private_key=data["private_key_hex"], public_key=data["public_key_hex"])

    def build_and_sign_transaction(self, recipient_address: str, amount_micro: int, tx_nonce: int) -> dict:
        timestamp = round(time.time(), 4)
        payload = f"{self.address}->{recipient_address}:{amount_micro}:{tx_nonce}:{timestamp:.4f}"
        signature = Dilithium3CryptoEngine.sign_message(self.private_key, payload)
        tx_id = hashlib.sha3_512(payload.encode('utf-8')).hexdigest()[:32]
        
        return {
            "tx_id": tx_id,
            "from": self.address,
            "to": recipient_address,
            "amount_micro": amount_micro,
            "nonce": tx_nonce,
            "pubkey_hex": self.public_key,
            "signature_hex": signature,
            "crypto": "Dilithium-3 (ML-DSA-65)",
            "timestamp": timestamp
        }


class QuantumStateDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_swaps (
                    swap_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    user_address TEXT,
                    type TEXT,
                    trc_amount_micro INTEGER,
                    fiat_amount REAL,
                    currency TEXT,
                    payment_info TEXT,
                    status TEXT,
                    timestamp REAL
                )
            ''')
            conn.commit()

    def save_block(self, block_index: int, block_data: dict):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", 
                           (f"block_{block_index}", json.dumps(block_data)))
            cursor.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", 
                           ("latest_index", str(block_index)))
            conn.commit()

    def get_block(self, block_index: int) -> Optional[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM kv_store WHERE key = ?", (f"block_{block_index}",))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def get_latest_index(self) -> Optional[int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM kv_store WHERE key = ?", ("latest_index",))
            row = cursor.fetchone()
            return int(row[0]) if row else None

    def save_balance(self, address: str, balance_micro: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", 
                           (f"bal_{address}", str(balance_micro)))
            conn.commit()

    def get_balance(self, address: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM kv_store WHERE key = ?", (f"bal_{address}",))
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def get_account_nonce(self, address: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM kv_store WHERE key = ?", (f"nonce_{address}",))
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def set_account_nonce(self, address: str, nonce: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", 
                           (f"nonce_{address}", str(nonce)))
            conn.commit()

    def create_pending_swap(self, swap_id: str, user_id: int, user_address: str, swap_type: str, trc_micro: int, fiat_amount: float, currency: str, payment_info: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO pending_swaps VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            ''', (swap_id, user_id, user_address, swap_type, trc_micro, fiat_amount, currency, payment_info, time.time()))
            conn.commit()

    def get_swap(self, swap_id: str) -> Optional[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT swap_id, user_id, user_address, type, trc_amount_micro, fiat_amount, currency, payment_info, status FROM pending_swaps WHERE swap_id = ?", (swap_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "swap_id": row[0], "user_id": row[1], "user_address": row[2],
                    "type": row[3], "trc_amount_micro": row[4], "fiat_amount": row[5],
                    "currency": row[6], "payment_info": row[7], "status": row[8]
                }
            return None

    def update_swap_status(self, swap_id: str, status: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pending_swaps SET status = ? WHERE status = 'PENDING' AND swap_id = ?", (status, swap_id))
            conn.commit()


# =====================================================================
# MERKLE TREE & BLOCK
# =====================================================================
class QuantumMerkleTree:
    @staticmethod
    def compute_root(transactions: List[Dict[str, Any]]) -> str:
        if not transactions:
            return hashlib.sha3_512(b"EMPTY_TREE").hexdigest()

        tx_hashes = [
            hashlib.sha3_512(json.dumps(tx, sort_keys=True).encode('utf-8')).hexdigest()
            for tx in transactions
        ]

        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            new_hashes = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i+1]
                new_hashes.append(hashlib.sha3_512(combined.encode('utf-8')).hexdigest())
            tx_hashes = new_hashes

        return tx_hashes[0]


class QuantumBlock:
    def __init__(self, index: int, transactions: List[Dict[str, Any]], previous_hash: str, difficulty: int, timestamp: float = None):
        self.index = index
        self.timestamp = round(timestamp if timestamp else time.time(), 4)
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = 0
        self.merkle_root = QuantumMerkleTree.compute_root(transactions)
        self.hash = self.calculate_hash()

    def get_header_str(self) -> str:
        return json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
            "previous_hash": self.previous_hash,
            "difficulty": self.difficulty
        }, sort_keys=True)

    def calculate_hash(self) -> str:
        return QuantumProofOfWork.calculate_quantum_resistant_hash(self.get_header_str(), self.nonce)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "difficulty": self.difficulty,
            "nonce": self.nonce,
            "merkle_root": self.merkle_root,
            "hash": self.hash
        }


# =====================================================================
# GLOBAL NODE ENGINE
# =====================================================================
class GlobalTarcoinNode:
    GATEWAY_TREASURY_ADDR = "TRC_DILITHIUM3_SWAP_GATEWAY_POOL"

    def __init__(self, db_path: str = DB_PATH):
        self.db = QuantumStateDB(db_path)
        self.mempool: List[Dict[str, Any]] = []
        
        self.RATES = {
            "USD": 1.0,           
            "EUR": 0.92,          
            "GBP": 0.78,          
            "SGD": 1.35,          
            "JPY": 155.0          
        }

        self._init_chain_state()

    def _init_chain_state(self):
        latest_idx = self.db.get_latest_index()
        if latest_idx is None:
            initial_alloc_micro = 36_900_000 * COIN
            treasury_init_micro = 1_000_000 * COIN
            genesis_addr = "TRC_DILITHIUM3_GENESIS_TREASURY_INIT"
            
            self.db.save_balance(genesis_addr, initial_alloc_micro - treasury_init_micro)
            self.db.save_balance(self.GATEWAY_TREASURY_ADDR, treasury_init_micro)
            self.db.save_balance("TOTAL_CIRCULATING_SUPPLY", initial_alloc_micro)
            
            genesis_tx = {
                "from": "COINBASE", "to": genesis_addr, "amount_micro": initial_alloc_micro, "nonce": 0,
                "pubkey_hex": "00", "signature_hex": "00", "crypto": "Dilithium-3", "timestamp": round(time.time(), 4)
            }
            genesis_block = QuantumBlock(0, [genesis_tx], "0" * 128, 2, time.time())
            
            target = "0" * genesis_block.difficulty
            header_str = genesis_block.get_header_str()
            while not genesis_block.hash.startswith(target):
                genesis_block.nonce += 1
                genesis_block.hash = QuantumProofOfWork.calculate_quantum_resistant_hash(header_str, genesis_block.nonce)

            self.db.save_block(0, genesis_block.to_dict())

    def get_current_difficulty(self) -> int:
        latest_idx = self.db.get_latest_index()
        if latest_idx is None: return 2
        latest_block = self.db.get_block(latest_idx)
        if not latest_block: return 2
        return latest_block.get("difficulty", 2)

    def get_circulating_supply_micro(self) -> int:
        return self.db.get_balance("TOTAL_CIRCULATING_SUPPLY")

    async def execute_approved_swap(self, swap_data: dict) -> Tuple[bool, str]:
        swap_type = swap_data["type"]
        user_addr = swap_data["user_address"]
        trc_micro = swap_data["trc_amount_micro"]

        if swap_type == "SELL":
            current_bal_micro = self.db.get_balance(user_addr)
            if current_bal_micro < trc_micro:
                return False, "User TRC balance is insufficient."

            self.db.save_balance(user_addr, current_bal_micro - trc_micro)
            treasury_bal_micro = self.db.get_balance(self.GATEWAY_TREASURY_ADDR)
            self.db.save_balance(self.GATEWAY_TREASURY_ADDR, treasury_bal_micro + trc_micro)
            return True, "SELL Swap Executed Successfully!"

        elif swap_type == "BUY":
            treasury_bal_micro = self.db.get_balance(self.GATEWAY_TREASURY_ADDR)
            if treasury_bal_micro < trc_micro:
                return False, "Insufficient TRC liquidity in Gateway Pool."

            self.db.save_balance(self.GATEWAY_TREASURY_ADDR, treasury_bal_micro - trc_micro)
            user_bal_micro = self.db.get_balance(user_addr)
            self.db.save_balance(user_addr, user_bal_micro + trc_micro)
            return True, "BUY Swap Executed Successfully!"

        return False, "Invalid Swap Type."


# =====================================================================
# TELEGRAM BOT LOGIC & HANDLERS
# =====================================================================
def generate_admin_hmac(swap_id: str, action: str) -> str:
    data = f"{swap_id}:{action}".encode('utf-8')
    return hmac.new(ADMIN_SECRET_KEY.encode('utf-8'), data, hashlib.sha256).hexdigest()[:16]

def verify_admin_hmac(swap_id: str, action: str, token: str) -> bool:
    expected = generate_admin_hmac(swap_id, action)
    return secrets.compare_digest(expected, token)

def get_user_wallet(user_id: int) -> QuantumWallet:
    filename = f"wallet_user_{user_id}.json"
    filepath = os.path.join("/tmp", filename)
    if os.path.exists(filepath):
        return QuantumWallet.load_from_file(filename)
    else:
        wallet = QuantumWallet()
        wallet.save_to_file(filename)
        return wallet


async def start_swap_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("🔴 SELL TRC", callback_data="swap_SELL"),
            InlineKeyboardButton("🟢 BUY TRC", callback_data="swap_BUY")
        ],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    await query.edit_message_text("🔀 *OFFICIAL SWAP GATEWAY*\n\nSelect order type:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return WAITING_SWAP_TYPE


async def select_swap_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    swap_type = query.data.split("_")[1]
    context.user_data["swap_type"] = swap_type

    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 USD", callback_data="curr_USD"), 
            InlineKeyboardButton("🇪🇺 EUR", callback_data="curr_EUR"),
            InlineKeyboardButton("🇬🇧 GBP", callback_data="curr_GBP")
        ]
    ]
    await query.edit_message_text("𒒱 *Select Target Currency:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return WAITING_CURRENCY


async def select_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["currency"] = query.data.split("_")[1]
    await query.edit_message_text("💵 Enter amount in TRC or Fiat equivalent:", parse_mode="Markdown")
    return WAITING_AMOUNT


async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_text = update.message.text.strip()
        amount = float(raw_text)

        if not math.isfinite(amount) or amount <= 0:
            await update.message.reply_text("⚠️ Amount must be a positive number.")
            return WAITING_AMOUNT

        context.user_data["amount"] = amount
        swap_type = context.user_data["swap_type"]
        node: GlobalTarcoinNode = context.bot_data["node"]

        if swap_type == "SELL":
            user_id = update.effective_user.id
            wallet = get_user_wallet(user_id)
            trc_micro = int(amount * COIN)
            if node.db.get_balance(wallet.address) < trc_micro:
                await update.message.reply_text("❌ *Insufficient Balance!*", parse_mode="Markdown")
                return ConversationHandler.END

            await update.message.reply_text("Enter Bank/E-Wallet payment instructions:")
            return WAITING_PAYMENT_INFO
        else:
            await update.message.reply_text("Enter Payment Reference / Transaction Note:")
            return WAITING_BUY_PROOF

    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid numerical amount:")
        return WAITING_AMOUNT


async def receive_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await submit_swap_to_admin(update, context, update.message.text)


async def receive_buy_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await submit_swap_to_admin(update, context, f"Proof: {update.message.text}")


async def submit_swap_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_info: str):
    user_id = update.effective_user.id
    wallet = get_user_wallet(user_id)
    node: GlobalTarcoinNode = context.bot_data["node"]

    swap_type = context.user_data.get("swap_type")
    curr = context.user_data.get("currency")
    amount = context.user_data.get("amount")

    if swap_type == "SELL":
        trc_micro = int(amount * COIN)
        fiat_amount = amount * node.RATES.get(curr, 1.0)
    else:
        fiat_amount = amount
        trc_micro = int((amount / node.RATES.get(curr, 1.0)) * COIN)

    swap_id = f"SWAP-{int(time.time())}-{secrets.token_hex(4)}"
    node.db.create_pending_swap(swap_id, user_id, wallet.address, swap_type, trc_micro, fiat_amount, curr, payment_info)

    await update.message.reply_text(f"⏳ *Swap Request Submitted!*\nID: `{swap_id}`", parse_mode="Markdown")

    app_token = generate_admin_hmac(swap_id, "app")
    rej_token = generate_admin_hmac(swap_id, "rej")

    admin_keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"adm:app:{swap_id}:{app_token}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"adm:rej:{swap_id}:{rej_token}")
        ]
    ]
    
    admin_msg = f"🚨 *SWAP REQUEST*\nID: `{swap_id}`\nUser: `{user_id}`\nType: `{swap_type}`\nTRC: `{trc_micro / COIN:.6f}`\nFiat: `{fiat_amount:.2f} {curr}`"

    try:
        await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=admin_msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_keyboard))
    except Exception as e:
        print(f"[ADMIN ERROR] {e}")

    return ConversationHandler.END


async def admin_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_TELEGRAM_ID:
        await query.message.reply_text("⛔ Access Denied.")
        return

    parts = query.data.split(":")
    if len(parts) != 4:
        await query.edit_message_text("⛔ Malformed Callback Data.")
        return

    action, swap_id, token = parts[1], parts[2], parts[3]

    if not verify_admin_hmac(swap_id, action, token):
        await query.edit_message_text("⛔ Invalid HMAC Authentication Token.")
        return

    node: GlobalTarcoinNode = context.bot_data["node"]
    swap = node.db.get_swap(swap_id)

    if not swap or swap["status"] != "PENDING":
        await query.edit_message_text(f"⚠️ Transaction `{swap_id}` already processed or non-existent.", parse_mode="Markdown")
        return

    if action == "app":
        success, err_msg = await node.execute_approved_swap(swap)
        if success:
            node.db.update_swap_status(swap_id, "APPROVED")
            await query.edit_message_text(f"✅ *APPROVED!* ID: `{swap_id}`", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"❌ *FAILED:* {err_msg}", parse_mode="Markdown")
    elif action == "rej":
        node.db.update_swap_status(swap_id, "REJECTED")
        await query.edit_message_text(f"❌ *REJECTED!* ID: `{swap_id}`", parse_mode="Markdown")


async def cancel_swap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔴 Swap Cancelled.")
    return ConversationHandler.END


async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallet = get_user_wallet(user_id)
    node: GlobalTarcoinNode = context.bot_data["node"]

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ *Format:* `/send <address> <amount>`", parse_mode="Markdown")
        return

    recipient_address = context.args[0]
    if not Dilithium3CryptoEngine.validate_address_format(recipient_address):
        await update.message.reply_text("❌ *Invalid Recipient Address Format!*", parse_mode="Markdown")
        return

    try: 
        amount_trc = float(context.args[1])
        if not math.isfinite(amount_trc) or amount_trc <= 0:
            await update.message.reply_text("⚠️ Amount must be a positive number.", parse_mode="Markdown")
            return
        amount_micro = int(amount_trc * COIN)
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount number.", parse_mode="Markdown")
        return

    current_balance_micro = node.db.get_balance(wallet.address)
    if current_balance_micro < amount_micro:
        await update.message.reply_text("❌ *Insufficient Balance!*", parse_mode="Markdown")
        return

    current_nonce = node.db.get_account_nonce(wallet.address)
    pending_txs = [tx for tx in node.mempool if tx["from"] == wallet.address]
    next_nonce = current_nonce + len(pending_txs) + 1

    tx = wallet.build_and_sign_transaction(recipient_address, amount_micro, next_nonce)
    node.mempool.append(tx)

    await update.message.reply_text(f"✅ Transaction Processed! TxID: `{tx['tx_id'][:16]}...`", parse_mode="Markdown")


def build_main_menu(is_mining: bool) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("💰 Balance", callback_data="check_balance"),
            InlineKeyboardButton("📬 Wallet Address", callback_data="view_address")
        ],
        [
            InlineKeyboardButton("📊 Mining Stats", callback_data="mining_stats"),
            InlineKeyboardButton("🔀 Buy/Sell Swap", callback_data="start_swap")
        ],
        [
            InlineKeyboardButton("💸 Transfer Guide", callback_data="how_to_send")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallet = get_user_wallet(user_id)
    node: GlobalTarcoinNode = context.bot_data["node"]

    reply_markup = build_main_menu(False)

    welcome_text = (
        f"⚛️ *Tarcoin Quantum Serverless Node*\n\n"
        f"🛡️ *Cryptography:* `Dilithium-3 / ML-DSA-65`\n"
        f"🎯 *Difficulty:* `Level {node.get_current_difficulty()}`\n"
        f"👤 *Your Address:* `{wallet.address}`\n\n"
        f"Select an option from the menu below:"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)


async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    wallet = get_user_wallet(user_id)
    node: GlobalTarcoinNode = context.bot_data["node"]

    if query.data == "main_menu":
        text = "⚛️ *Main Menu*"

    elif query.data == "check_balance":
        bal_micro = node.db.get_balance(wallet.address)
        text = f"💳 *BALANCE:*\n\n🪙 *Tarcoin:* `{bal_micro / COIN:.6f} TRC`"

    elif query.data == "view_address":
        text = f"📬 *Your Address:*\n\n`{wallet.address}`"

    elif query.data == "mining_stats":
        latest_block = node.db.get_latest_index() or 0
        supply_trc = node.get_circulating_supply_micro() / COIN
        text = (
            f"📊 *Mining Stats:* \n\n"
            f"🔹 *Block Height:* `#{latest_block}`\n"
            f"🔹 *Current Difficulty:* `Level {node.get_current_difficulty()}`\n"
            f"🪙 *Circulating Supply:* `{supply_trc:,.2f} TRC`"
        )

    elif query.data == "how_to_send":
        text = "💸 *Send TRC Command Usage:*\n\nFormat:\n`/send <recipient_address> <amount>`"

    await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=build_main_menu(False))


def build_application():
    # ✅ FIX KUNCI: Membaca nama variabel 'TELEGRAM_BOT_TOKEN' dari Vercel Settings
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    node = GlobalTarcoinNode()

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.bot_data["node"] = node

    swap_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_swap_flow, pattern="^start_swap$")],
        states={
            WAITING_SWAP_TYPE: [CallbackQueryHandler(select_swap_type, pattern="^swap_")],
            WAITING_CURRENCY: [CallbackQueryHandler(select_currency, pattern="^curr_")],
            WAITING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            WAITING_PAYMENT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_payment_info)],
            WAITING_BUY_PROOF: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_buy_proof)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_swap),
            CallbackQueryHandler(button_click_handler, pattern="^main_menu$")
        ],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("send", send_command))
    application.add_handler(swap_handler)
    
    application.add_handler(CallbackQueryHandler(admin_approval_callback, pattern="^adm:"))
    application.add_handler(CallbackQueryHandler(button_click_handler))

    return application
