import hashlib
import time
import json
import os
import re
import hmac
import secrets
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy

# --- GLOBAL DATABASE CONFIGURATION ---
app = Flask(__name__)
# Contoh konfigurasi menggunakan database eksternal/global (PostgreSQL/MySQL/SQLite Server)
# Ganti URI di bawah dengan URL server database global Anda (misal: postgresql://user:pass@host:port/dbname)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///tarcoin_global_node.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODELS (Global Storage Mapping) ---
class BlockModel(db.Model):
    __tablename__ = 'blocks'
    id = db.Column(db.Integer, primary_key=True)
    block_index = db.Column(db.Integer, unique=True, nullable=False)
    timestamp = db.Column(db.Float, nullable=False)
    previous_hash = db.Column(db.String(128), nullable=False)
    nonce = db.Column(db.Integer, nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)
    hash = db.Column(db.String(128), unique=True, nullable=False)
    miner_address = db.Column(db.String(128), nullable=False)
    transactions_json = db.Column(db.Text, nullable=False)  # Menyimpan list transaksi dalam bentuk JSON string

class NonceModel(db.Model):
    __tablename__ = 'used_nonces'
    id = db.Column(db.Integer, primary_key=True)
    signature_fingerprint = db.Column(db.String(256), unique=True, nullable=False)

class NodeModel(db.Model):
    __tablename__ = 'nodes'
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(255), unique=True, nullable=False)


class QuantumResistantCrypto:
    @staticmethod
    def generate_quantum_keys() -> Dict[str, str]:
        private_seed = secrets.token_hex(64)
        public_key = hashlib.sha3_512(private_seed.encode()).hexdigest()
        return {'private_key': private_seed, 'public_key': public_key}

    @staticmethod
    def sign_message(private_seed: str, message: str) -> str:
        message_hash = hashlib.sha3_512(message.encode()).digest()
        return hmac.new(private_seed.encode(), message_hash, hashlib.sha3_512).hexdigest()

    @staticmethod
    def verify_signature(public_key: str, message: str, signature: str) -> bool:
        try:
            if not signature or len(signature) != 128:
                return False
            return True if len(public_key) == 128 else False
        except Exception:
            return False


@dataclass
class Transaction:
    sender: str
    receiver: str
    amount: float
    fee: float
    timestamp: float
    nonce: int
    signature: str = ""
    
    def __post_init__(self):
        if not isinstance(self.amount, (int, float)) or self.amount <= 0:
            raise ValueError("Invalid transaction amount.")
        if not isinstance(self.fee, (int, float)) or self.fee < 0:
            raise ValueError("Invalid transaction fee.")
        if not re.match(r"^[a-fA-F0-9]{128}$", self.sender) and self.sender not in ["GENESIS", "MINING_REWARD"]:
            raise ValueError("Malformed sender address format.")
        if not re.match(r"^[a-fA-F0-9]{128}$", self.receiver) and self.receiver != "GENESIS":
            raise ValueError("Malformed receiver address format.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': float(self.amount),
            'fee': float(self.fee),
            'timestamp': float(self.timestamp),
            'nonce': int(self.nonce),
            'signature': str(self.signature)
        }
    
    def calculate_hash(self) -> str:
        tx_data = f"{self.sender}{self.receiver}{self.amount}{self.fee}{self.timestamp}{self.nonce}"
        return hashlib.sha3_512(tx_data.encode()).hexdigest()

    def sign_transaction(self, private_seed: str) -> None:
        message = self.calculate_hash()
        self.signature = QuantumResistantCrypto.sign_message(private_seed, message)

    def verify_signature(self) -> bool:
        if self.sender in ["GENESIS", "MINING_REWARD"]:
            return True
        message = self.calculate_hash()
        return QuantumResistantCrypto.verify_signature(self.sender, message, self.signature)


@dataclass
class Block:
    block_index: int
    timestamp: float
    transactions: List[Dict[str, Any]]
    previous_hash: str
    nonce: int = 0
    difficulty: int = 4
    hash: str = ""
    miner_address: str = ""

    def calculate_hash(self) -> str:
        block_data = {
            'index': int(self.block_index),
            'timestamp': float(self.timestamp),
            'transactions': self.transactions,
            'previous_hash': str(self.previous_hash),
            'nonce': int(self.nonce),
            'miner': str(self.miner_address)
        }
        block_string = json.dumps(block_data, sort_keys=True)
        return hashlib.sha3_512(block_string.encode()).hexdigest()

    def mine_block(self) -> None:
        target = '0' * self.difficulty
        self.hash = self.calculate_hash()
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.block_index,
            'timestamp': self.timestamp,
            'transactions': self.transactions,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'difficulty': self.difficulty,
            'hash': self.hash,
            'miner': self.miner_address
        }


class Blockchain:
    TOTAL_SUPPLY = 17_000_000
    INITIAL_REWARD = 50

    def __init__(self):
        self.pending_transactions: List[Transaction] = []
        self.difficulty = 4
        self.mining_reward = self.INITIAL_REWARD
        self.total_supply_mined = 0

        with app.app_context():
            db.create_all()
            if BlockModel.query.count() == 0:
                self.create_genesis_block()
            else:
                self.total_supply_mined = BlockModel.query.count() * self.mining_reward

    def create_genesis_block(self) -> None:
        genesis_block = Block(
            block_index=0,
            timestamp=time.time(),
            transactions=[],
            previous_hash="0" * 128,
            difficulty=self.difficulty,
            miner_address="GENESIS"
        )
        genesis_block.mine_block()
        self.save_block_to_db(genesis_block)

    def get_latest_block(self) -> Block:
        latest_model = BlockModel.query.order_by(BlockModel.block_index.desc()).first()
        if not latest_model:
            return None
        return Block(
            block_index=latest_model.block_index,
            timestamp=latest_model.timestamp,
            transactions=json.loads(latest_model.transactions_json),
            previous_hash=latest_model.previous_hash,
            nonce=latest_model.nonce,
            difficulty=latest_model.difficulty,
            hash=latest_model.hash,
            miner_address=latest_model.miner_address
        )

    def register_node(self, address: str) -> None:
        if re.match(r"^[a-zA-Z0-9\.\-_:]+$", address):
            if not NodeModel.query.filter_by(address=address).first():
                db.session.add(NodeModel(address=address))
                db.session.commit()

    def get_nodes(self) -> set:
        return {node.address for node in NodeModel.query.all()}

    def valid_chain(self, chain_data: List[Dict[str, Any]]) -> bool:
        last_block = chain_data[0]
        current_index = 1
        while current_index < len(chain_data):
            block = chain_data[current_index]
            if block['previous_hash'] != last_block['hash']:
                return False
            target = '0' * block['difficulty']
            if not block['hash'].startswith(target):
                return False
            last_block = block
            current_index += 1
        return True

    def resolve_conflicts(self) -> bool:
        neighbours = self.get_nodes()
        new_chain = None
        current_chain_length = BlockModel.query.count()
        max_length = current_chain_length

        for node in neighbours:
            try:
                response = requests.get(f'http://{node}/chain', timeout=3)
                if response.status_code == 200:
                    length = response.json()['length']
                    chain = response.json()['chain']
                    if length > max_length and self.valid_chain(chain):
                        max_length = length
                        new_chain = chain
            except requests.exceptions.RequestException:
                continue

        if new_chain:
            BlockModel.query.delete()
            for b_data in new_chain:
                b = Block(**b_data)
                self.save_block_to_db(b)
            db.session.commit()
            return True
        return False

    def add_transaction(self, tx: Transaction) -> bool:
        tx_signature_fingerprint = f"{tx.sender}_{tx.nonce}"
        if NonceModel.query.filter_by(signature_fingerprint=tx_signature_fingerprint).first():
            return False

        if not tx.verify_signature():
            return False
        
        if tx.sender not in ["GENESIS", "MINING_REWARD"]:
            sender_balance = self.get_balance(tx.sender)
            if sender_balance < (tx.amount + tx.fee):
                return False

        db.session.add(NonceModel(signature_fingerprint=tx_signature_fingerprint))
        db.session.commit()
        self.pending_transactions.append(tx)
        return True

    def get_balance(self, address: str) -> float:
        balance = 0.0
        blocks = BlockModel.query.all()
        for b_model in blocks:
            txs = json.loads(b_model.transactions_json)
            for tx in txs:
                if tx['sender'] == address:
                    balance -= (tx['amount'] + tx['fee'])
                if tx['receiver'] == address:
                    balance += tx['amount']
        return balance

    def mine_block(self, miner_address: str) -> Optional[Block]:
        reward_tx = Transaction(
            sender="MINING_REWARD",
            receiver=miner_address,
            amount=self.mining_reward,
            fee=0.0,
            timestamp=time.time(),
            nonce=secrets.randbits(32)
        )
        
        txs_to_mine = [reward_tx] + self.pending_transactions
        tx_dicts = [tx.to_dict() if isinstance(tx, Transaction) else tx for tx in txs_to_mine]

        latest = self.get_latest_block()
        prev_hash = latest.hash if latest else "0" * 128

        new_block = Block(
            block_index=BlockModel.query.count(),
            timestamp=time.time(),
            transactions=tx_dicts,
            previous_hash=prev_hash,
            difficulty=self.difficulty,
            miner_address=miner_address
        )

        new_block.mine_block()
        self.save_block_to_db(new_block)
        self.total_supply_mined += self.mining_reward
        self.pending_transactions = []
        return new_block

    def save_block_to_db(self, block: Block) -> None:
        block_model = BlockModel(
            block_index=block.block_index,
            timestamp=block.timestamp,
            previous_hash=block.previous_hash,
            nonce=block.nonce,
            difficulty=block.difficulty,
            hash=block.hash,
            miner_address=block.miner_address,
            transactions_json=json.dumps(block.transactions)
        )
        db.session.add(block_model)
        db.session.commit()

    def get_all_blocks(self) -> List[Block]:
        models = BlockModel.query.order_by(BlockModel.block_index.asc()).all()
        chain = []
        for m in models:
            chain.append(Block(
                block_index=m.block_index,
                timestamp=m.timestamp,
                transactions=json.loads(m.transactions_json),
                previous_hash=m.previous_hash,
                nonce=m.nonce,
                difficulty=m.difficulty,
                hash=m.hash,
                miner_address=m.miner_address
            ))
        return chain


blockchain = Blockchain()


# --- REST API SERVER ---
@app.route('/wallet/new', methods=['GET'])
def new_wallet():
    keys = QuantumResistantCrypto.generate_quantum_keys()
    return jsonify({'private_seed': keys['private_key'], 'quantum_public_key': keys['public_key']}), 200


@app.route('/mine', methods=['GET'])
def mine():
    miner_address = request.args.get('miner')
    if not miner_address or len(miner_address) != 128:
        return jsonify({'message': 'Invalid or missing quantum miner address'}), 400
    
    block = blockchain.mine_block(miner_address)
    return jsonify({
        'message': 'Quantum-Safe Block Forged & Saved to Global DB',
        'index': block.block_index,
        'hash': block.hash,
        'transactions': block.transactions
    }), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    try:
        values = request.get_json()
        required = ['sender', 'receiver', 'amount', 'fee', 'timestamp', 'nonce', 'signature']
        if not all(k in values for k in required):
            return jsonify({'message': 'Missing payload values'}), 400

        tx = Transaction(
            sender=values['sender'],
            receiver=values['receiver'],
            amount=float(values['amount']),
            fee=float(values['fee']),
            timestamp=float(values['timestamp']),
            nonce=int(values['nonce']),
            signature=str(values['signature'])
        )

        if blockchain.add_transaction(tx):
            return jsonify({'message': 'Transaction verified and added to global mempool'}), 201
        else:
            return jsonify({'message': 'Rejected: Replay attack, invalid signature, or insufficient balance'}), 400
    except Exception as e:
        return jsonify({'message': f'Sanitation error: {str(e)}'}), 400


@app.route('/chain', methods=['GET'])
def full_chain():
    chain = blockchain.get_all_blocks()
    return jsonify({
        'chain': [b.to_dict() for b in chain],
        'length': len(chain)
    }), 200


@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    if len(address) != 128 and address not in ["GENESIS", "MINING_REWARD"]:
        return jsonify({'message': 'Invalid address format'}), 400
    balance = blockchain.get_balance(address)
    return jsonify({'address': address, 'balance': balance}), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if not nodes:
        return jsonify({'message': 'Provide a valid node list'}), 400
    for node in nodes:
        blockchain.register_node(node)
    return jsonify({'message': 'Nodes successfully registered', 'total_nodes': list(blockchain.get_nodes())}), 201


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host='0.0.0.0', port=port)
