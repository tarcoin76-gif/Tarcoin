import hashlib
import time
import json
import os
import re
import hmac
import secrets
import requests
import threading
import socket
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from flask import Flask, jsonify, request, current_app
from flask_sqlalchemy import SQLAlchemy

# --- GLOBAL DATABASE CONFIGURATION ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///tarcoin_global_node.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DATABASE MODELS ---
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
    transactions_json = db.Column(db.Text, nullable=False)

class NonceModel(db.Model):
    __tablename__ = 'used_nonces'
    id = db.Column(db.Integer, primary_key=True)
    signature_fingerprint = db.Column(db.String(256), unique=True, nullable=False)

class NodeModel(db.Model):
    __tablename__ = 'nodes'
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(255), unique=True, nullable=False)


# --- SECURE STATEFUL POST-QUANTUM CRYPTOGRAPHY (Lamport with Index Offset) ---
class QuantumResistantCrypto:
    KEY_PAIRS_COUNT = 256  # 256 bits for SHA3-256 equivalent security layer inside SHA3-512

    @staticmethod
    def generate_quantum_keys() -> Dict[str, Any]:
        master_seed = secrets.token_hex(64)
        # Menggunakan index 0 untuk pembuatan kunci publik awal dompet
        initial_index = 0
        public_keys = []
        
        for i in range(QuantumResistantCrypto.KEY_PAIRS_COUNT):
            priv_0 = hashlib.sha3_512(f"{master_seed}_{initial_index}_0_{i}".encode()).hexdigest()
            priv_1 = hashlib.sha3_512(f"{master_seed}_{initial_index}_1_{i}".encode()).hexdigest()
            
            pub_0 = hashlib.sha3_512(priv_0.encode()).hexdigest()
            pub_1 = hashlib.sha3_512(priv_1.encode()).hexdigest()
            public_keys.append((pub_0, pub_1))

        pub_key_serialized = json.dumps(public_keys)
        public_key_hash = hashlib.sha3_512(pub_key_serialized.encode()).hexdigest()
        
        return {
            'private_key': master_seed,
            'public_key': public_key_hash,
            'raw_public_keys': pub_key_serialized,
            'key_index': initial_index
        }

    @staticmethod
    def sign_message(master_seed: str, message: str, key_index: int = 0) -> str:
        msg_hash = hashlib.sha3_256(message.encode()).hexdigest()
        binary_msg = ''.join(format(int(c, 16), '04b') for c in msg_hash)[:256]
        
        signature_parts = []
        for i, bit in enumerate(binary_msg):
            # Kunci privat diturunkan menggunakan key_index yang unik per transaksi (mencegah kebocoran key reuse)
            priv_0 = hashlib.sha3_512(f"{master_seed}_{key_index}_0_{i}".encode()).hexdigest()
            priv_1 = hashlib.sha3_512(f"{master_seed}_{key_index}_1_{i}".encode()).hexdigest()
            
            if bit == '0':
                signature_parts.append(priv_0)
            else:
                signature_parts.append(priv_1)
                
        return json.dumps(signature_parts)

    @staticmethod
    def verify_signature(public_key_hash: str, message: str, signature: str, raw_public_keys_json: str) -> bool:
        try:
            if not signature or not raw_public_keys_json:
                return False
            
            public_keys = json.loads(raw_public_keys_json)
            signature_parts = json.loads(signature)
            
            if len(public_keys) != 256 or len(signature_parts) != 256:
                return False

            calculated_pub_hash = hashlib.sha3_512(raw_public_keys_json.encode()).hexdigest()
            if calculated_pub_hash != public_key_hash:
                return False

            msg_hash = hashlib.sha3_256(message.encode()).hexdigest()
            binary_msg = ''.join(format(int(c, 16), '04b') for c in msg_hash)[:256]

            for i, bit in enumerate(binary_msg):
                sig_part = signature_parts[i]
                expected_pub = public_keys[i][0] if bit == '0' else public_keys[i][1]
                derived_pub = hashlib.sha3_512(sig_part.encode()).hexdigest()
                if derived_pub != expected_pub:
                    return False
            return True
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
    raw_public_keys: str = ""
    key_index: int = 0  # Ditambahkan untuk melacak index kunci Lamport yang aktif
    
    def __post_init__(self):
        if not isinstance(self.amount, (int, float)) or self.amount <= 0:
            raise ValueError("Invalid transaction amount.")
        if not isinstance(self.fee, (int, float)) or self.fee < 0:
            raise ValueError("Invalid transaction fee.")
        if not re.match(r"^[a-fA-F0-9]{128}$", self.sender) and self.sender not in ["GENESIS", "MINING_REWARD"]:
            raise ValueError("Malformed sender address format.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': float(self.amount),
            'fee': float(self.fee),
            'timestamp': float(self.timestamp),
            'nonce': int(self.nonce),
            'signature': str(self.signature),
            'raw_public_keys': str(self.raw_public_keys),
            'key_index': int(self.key_index)
        }
    
    def calculate_hash(self) -> str:
        tx_data = f"{self.sender}{self.receiver}{self.amount}{self.fee}{self.timestamp}{self.nonce}{self.key_index}"
        return hashlib.sha3_512(tx_data.encode()).hexdigest()

    def sign_transaction(self, private_seed: str) -> None:
        message = self.calculate_hash()
        self.signature = QuantumResistantCrypto.sign_message(private_seed, message, self.key_index)

    def verify_signature(self) -> bool:
        if self.sender in ["GENESIS", "MINING_REWARD"]:
            return True
        message = self.calculate_hash()
        return QuantumResistantCrypto.verify_signature(self.sender, message, self.signature, self.raw_public_keys)


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


class MainnetP2PManager:
    def __init__(self, blockchain_instance, host='0.0.0.0', p2p_port=6000):
        self.blockchain = blockchain_instance
        self.host = host
        self.p2p_port = p2p_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start_p2p_server(self):
        try:
            self.server_socket.bind((self.host, self.p2p_port))
            self.server_socket.listen(15)
            threading.Thread(target=self._listen_incoming_connections, daemon=True).start()
        except Exception:
            pass

    def _listen_incoming_connections(self):
        while True:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_peer_connection, args=(client_sock,), daemon=True).start()
            except Exception:
                break

    def _handle_peer_connection(self, client_sock):
        try:
            data = client_sock.recv(16384)
            if data:
                message = json.loads(data.decode('utf-8'))
                msg_type = message.get('type')
                payload = message.get('payload')

                if msg_type == 'BROADCAST_BLOCK':
                    self._process_incoming_block(payload)
                elif msg_type == 'BROADCAST_TRANSACTION':
                    self._process_incoming_transaction(payload)
            client_sock.close()
        except Exception:
            pass

    def _process_incoming_block(self, block_data):
        with app.app_context():
            latest = self.blockchain.get_latest_block()
            if latest and block_data['index'] == latest.block_index + 1:
                if block_data['previous_hash'] == latest.hash:
                    new_b = Block(**block_data)
                    target = '0' * new_b.difficulty
                    if new_b.hash.startswith(target):
                        self.blockchain.save_block_to_db(new_b)

    def _process_incoming_transaction(self, tx_data):
        with app.app_context():
            tx = Transaction(**tx_data)
            self.blockchain.add_transaction(tx)

    def broadcast(self, msg_type: str, payload: dict):
        nodes = self.blockchain.get_nodes()
        message = json.dumps({'type': msg_type, 'payload': payload})
        for node in nodes:
            try:
                host_ip, port_str = node.split(':')
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((host_ip, int(port_str)))
                s.sendall(message.encode('utf-8'))
                s.close()
            except Exception:
                continue


class Blockchain:
    TOTAL_SUPPLY = 17_000_000
    INITIAL_REWARD = 50

    def __init__(self, p2p_port=6000):
        self.pending_transactions: List[Transaction] = []
        self.difficulty = 4
        self.mining_reward = self.INITIAL_REWARD
        self.total_supply_mined = 0
        self.p2p_manager = MainnetP2PManager(self, p2p_port=p2p_port)
        self.p2p_manager.start_p2p_server()

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

    def add_transaction(self, tx: Transaction) -> bool:
        # Mengunci agar kombinasi sender dan key_index tidak pernah dipakai dua kali (Key Reuse Prevention)
        tx_signature_fingerprint = f"{tx.sender}_{tx.key_index}"
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
        self.p2p_manager.broadcast('BROADCAST_TRANSACTION', tx.to_dict())
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
            nonce=secrets.randbits(32),
            key_index=0
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
        self.p2p_manager.broadcast('BROADCAST_BLOCK', new_block.to_dict())
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


# Inisialisasi instance blockchain secara global di luar main scope
blockchain = Blockchain(p2p_port=6000)


# --- REST API SERVER ---
@app.route('/wallet/new', methods=['GET'])
def new_wallet():
    keys = QuantumResistantCrypto.generate_quantum_keys()
    return jsonify({
        'private_seed': keys['private_key'],
        'quantum_public_key': keys['public_key'],
        'raw_public_keys': keys['raw_public_keys'],
        'key_index': keys['key_index']
    }), 200


@app.route('/mine', methods=['GET'])
def mine():
    miner_address = request.args.get('miner')
    if not miner_address or len(miner_address) != 128:
        return jsonify({'message': 'Invalid or missing quantum miner address'}), 400
    
    block = blockchain.mine_block(miner_address)
    return jsonify({
        'message': 'Post-Quantum Safe Block Forged & Broadcasted',
        'index': block.block_index,
        'hash': block.hash,
        'transactions': block.transactions
    }), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    try:
        values = request.get_json()
        required = ['sender', 'receiver', 'amount', 'fee', 'timestamp', 'nonce', 'signature', 'raw_public_keys']
        if not all(k in values for k in required):
            return jsonify({'message': 'Missing payload values including post-quantum parameters'}), 400

        tx = Transaction(
            sender=values['sender'],
            receiver=values['receiver'],
            amount=float(values['amount']),
            fee=float(values['fee']),
            timestamp=float(values['timestamp']),
            nonce=int(values['nonce']),
            signature=str(values['signature']),
            raw_public_keys=str(values['raw_public_keys']),
            key_index=int(values.get('key_index', 0))
        )

        if blockchain.add_transaction(tx):
            return jsonify({'message': 'Quantum-safe transaction verified and broadcasted'}), 201
        else:
            return jsonify({'message': 'Rejected: Invalid post-quantum signature, key reuse, or balance'}), 400
    except Exception as e:
        return jsonify({'message': f'Sanitization error: {str(e)}'}), 400


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
    p2p_port = port + 1000
    blockchain.p2p_manager.p2p_port = p2p_port
    app.run(host='0.0.0.0', port=port, debug=True)
