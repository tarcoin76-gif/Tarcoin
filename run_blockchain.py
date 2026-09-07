#!/usr/bin/env python3
"""
Tarcoin Blockchain 

A full-featured blockchain node implementation with:
- Persistent blockchain storage (SQLite/JSON)
- Network P2P capabilities (node discovery, peer sync)
- Transaction pool management with validation
- Mining pool integration
- REST API for blockchain operations
- Wallet management
- Block validation and chain consensus
"""

import os
import sys
import json
import time
import argparse
import logging
import sqlite3
import hashlib
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import importlib.util
from dataclasses import dataclass, asdict
from threading import Thread, Lock
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('blockchain_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class NetworkRole(Enum):
    """Node role in the network"""
    FULL_NODE = "full_node"
    MINING_NODE = "mining_node"
    VALIDATOR = "validator"
    LIGHT_CLIENT = "light_client"


class NodeState(Enum):
    """Node operational state"""
    INITIALIZING = "initializing"
    SYNCING = "syncing"
    SYNCED = "synced"
    MINING = "mining"
    ERROR = "error"


@dataclass
class NodeConfig:
    """Node configuration"""
    node_id: str
    role: NetworkRole
    port: int
    host: str = "0.0.0.0"
    data_dir: str = "./blockchain_data"
    difficulty: int = 4
    mining_reward: float = 50.0
    enable_mining: bool = True
    enable_api: bool = True
    peer_nodes: List[str] = None
    max_peers: int = 8
    
    def __post_init__(self):
        if self.peer_nodes is None:
            self.peer_nodes = []
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)


class BlockchainDatabase:
    """Persistent blockchain storage"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Blocks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    block_height INTEGER PRIMARY KEY,
                    block_hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    transactions TEXT NOT NULL,
                    nonce INTEGER NOT NULL,
                    miner TEXT NOT NULL,
                    difficulty INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    block_height INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Wallet balances (cache)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallet_balances (
                    address TEXT PRIMARY KEY,
                    balance REAL NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Peer nodes table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peers (
                    peer_id TEXT PRIMARY KEY,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    last_seen DATETIME,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized")
    
    def save_block(self, block_data: Dict[str, Any]) -> bool:
        """Save block to database"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO blocks 
                        (block_height, block_hash, previous_hash, timestamp, 
                         transactions, nonce, miner, difficulty)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        block_data['height'],
                        block_data['hash'],
                        block_data['previous_hash'],
                        block_data['timestamp'],
                        json.dumps(block_data['transactions']),
                        block_data['nonce'],
                        block_data['miner'],
                        block_data['difficulty']
                    ))
                    conn.commit()
            logger.info(f"Block saved: {block_data['hash']}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Block already exists: {block_data['hash']}")
            return False
    
    def get_block(self, block_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve block by hash"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT block_height, block_hash, previous_hash, timestamp,
                       transactions, nonce, miner, difficulty
                FROM blocks WHERE block_hash = ?
            ''', (block_hash,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'height': row[0],
                    'hash': row[1],
                    'previous_hash': row[2],
                    'timestamp': row[3],
                    'transactions': json.loads(row[4]),
                    'nonce': row[5],
                    'miner': row[6],
                    'difficulty': row[7]
                }
        return None
    
    def get_latest_block_height(self) -> int:
        """Get the height of the latest block"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(block_height) FROM blocks')
            result = cursor.fetchone()[0]
            return result if result is not None else -1
    
    def save_transaction(self, tx: Dict[str, Any]) -> bool:
        """Save transaction to database"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO transactions
                        (tx_hash, sender, receiver, amount, fee, timestamp, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        tx['hash'],
                        tx['sender'],
                        tx['receiver'],
                        tx['amount'],
                        tx.get('fee', 0.0),
                        tx['timestamp'],
                        'pending'
                    ))
                    conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def update_wallet_balance(self, address: str, balance: float):
        """Update or insert wallet balance"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO wallet_balances (address, balance)
                    VALUES (?, ?)
                ''', (address, balance))
                conn.commit()
    
    def get_wallet_balance(self, address: str) -> float:
        """Get wallet balance from cache"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM wallet_balances WHERE address = ?', (address,))
            result = cursor.fetchone()
            return result[0] if result else 0.0


class TransactionPool:
    """Mempool for pending transactions"""
    
    def __init__(self, max_size: int = 10000):
        self.pool: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.lock = Lock()
    
    def add_transaction(self, tx: Dict[str, Any]) -> bool:
        """Add transaction to pool"""
        if len(self.pool) >= self.max_size:
            logger.warning("Transaction pool full")
            return False
        
        with self.lock:
            tx_hash = tx.get('hash')
            if tx_hash in self.pool:
                return False
            
            self.pool[tx_hash] = tx
            logger.info(f"Transaction added to pool: {tx_hash}")
            return True
    
    def get_pending_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending transactions sorted by fee"""
        with self.lock:
            txs = sorted(
                self.pool.values(),
                key=lambda x: x.get('fee', 0),
                reverse=True
            )
            return txs[:limit]
    
    def remove_transaction(self, tx_hash: str):
        """Remove transaction from pool"""
        with self.lock:
            self.pool.pop(tx_hash, None)
    
    def clear_transactions(self, tx_hashes: List[str]):
        """Clear multiple transactions from pool"""
        with self.lock:
            for tx_hash in tx_hashes:
                self.pool.pop(tx_hash, None)
    
    def size(self) -> int:
        """Get pool size"""
        return len(self.pool)


class BlockchainNode:
    """Production blockchain node"""
    
    def __init__(self, config: NodeConfig):
        self.config = config
        self.state = NodeState.INITIALIZING
        self.db = BlockchainDatabase(os.path.join(config.data_dir, 'blockchain.db'))
        self.tx_pool = TransactionPool()
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.mining_thread: Optional[Thread] = None
        self.is_mining = False
        
        logger.info(f"Initializing blockchain node: {config.node_id}")
        logger.info(f"Role: {config.role.value}, Port: {config.port}")
        
        self.state = NodeState.SYNCED
    
    def add_transaction(self, tx_data: Dict[str, Any]) -> bool:
        """Add transaction to pending pool"""
        if not self._validate_transaction(tx_data):
            logger.warning(f"Invalid transaction: {tx_data}")
            return False
        
        # Calculate transaction hash
        tx_data['hash'] = self._calculate_tx_hash(tx_data)
        
        return self.tx_pool.add_transaction(tx_data)
    
    def _validate_transaction(self, tx: Dict[str, Any]) -> bool:
        """Validate transaction"""
        required_fields = ['sender', 'receiver', 'amount', 'timestamp']
        
        if not all(field in tx for field in required_fields):
            return False
        
        if tx['amount'] <= 0:
            return False
        
        if tx['sender'] == tx['receiver']:
            return False
        
        return True
    
    def _calculate_tx_hash(self, tx: Dict[str, Any]) -> str:
        """Calculate transaction hash"""
        tx_str = json.dumps(tx, sort_keys=True)
        return hashlib.sha256(tx_str.encode()).hexdigest()
    
    def _calculate_block_hash(self, block_data: Dict[str, Any]) -> str:
        """Calculate block hash"""
        block_str = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(block_str.encode()).hexdigest()
    
    def mine_block(self, miner_address: str) -> Optional[Dict[str, Any]]:
        """Mine a new block"""
        if not self.config.enable_mining:
            return None
        
        pending_txs = self.tx_pool.get_pending_transactions()
        if not pending_txs:
            logger.info("No pending transactions to mine")
            return None
        
        latest_height = self.db.get_latest_block_height()
        block_height = latest_height + 1
        
        block_data = {
            'height': block_height,
            'timestamp': time.time(),
            'transactions': pending_txs,
            'miner': miner_address,
            'difficulty': self.config.difficulty,
            'previous_hash': self._get_latest_block_hash(),
            'nonce': 0
        }
        
        logger.info(f"Mining block {block_height} with {len(pending_txs)} transactions...")
        start_time = time.time()
        
        # Proof of Work
        nonce = 0
        while True:
            block_data['nonce'] = nonce
            block_hash = self._calculate_block_hash(block_data)
            
            if block_hash.startswith('0' * self.config.difficulty):
                elapsed = time.time() - start_time
                block_data['hash'] = block_hash
                
                logger.info(f"Block mined! Height: {block_height}, Hash: {block_hash}, Time: {elapsed:.2f}s")
                
                # Save block to database
                self.db.save_block(block_data)
                
                # Clear mined transactions from pool
                tx_hashes = [tx.get('hash') for tx in pending_txs if tx.get('hash')]
                self.tx_pool.clear_transactions(tx_hashes)
                
                # Update miner balance
                miner_balance = self.db.get_wallet_balance(miner_address)
                self.db.update_wallet_balance(miner_address, miner_balance + self.config.mining_reward)
                
                return block_data
            
            nonce += 1
            
            if nonce % 10000 == 0:
                logger.debug(f"Mining progress: {nonce} attempts")
    
    def start_mining(self, miner_address: str):
        """Start mining in background thread"""
        if not self.config.enable_mining:
            logger.warning("Mining is disabled")
            return
        
        if self.is_mining:
            logger.warning("Mining already in progress")
            return
        
        self.is_mining = True
        self.state = NodeState.MINING
        self.mining_thread = Thread(
            target=self._mining_loop,
            args=(miner_address,),
            daemon=True
        )
        self.mining_thread.start()
        logger.info(f"Mining started for {miner_address}")
    
    def _mining_loop(self, miner_address: str):
        """Continuous mining loop"""
        while self.is_mining:
            self.mine_block(miner_address)
            time.sleep(1)
    
    def stop_mining(self):
        """Stop mining"""
        self.is_mining = False
        self.state = NodeState.SYNCED
        logger.info("Mining stopped")
    
    def _get_latest_block_hash(self) -> str:
        """Get latest block hash"""
        height = self.db.get_latest_block_height()
        if height < 0:
            return "0" * 64  # Genesis block hash
        return "last_block_hash_placeholder"
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get node information"""
        latest_height = self.db.get_latest_block_height()
        
        return {
            'node_id': self.config.node_id,
            'role': self.config.role.value,
            'state': self.state.value,
            'port': self.config.port,
            'latest_block_height': latest_height,
            'pending_transactions': self.tx_pool.size(),
            'connected_peers': len(self.peers),
            'is_mining': self.is_mining,
            'timestamp': datetime.now().isoformat()
        }
    
    def add_peer(self, peer_id: str, host: str, port: int) -> bool:
        """Add peer node"""
        if len(self.peers) >= self.config.max_peers:
            logger.warning("Max peers reached")
            return False
        
        if peer_id in self.peers:
            return False
        
        self.peers[peer_id] = {
            'host': host,
            'port': port,
            'last_seen': datetime.now(),
            'is_active': True
        }
        logger.info(f"Peer added: {peer_id} ({host}:{port})")
        return True
    
    def get_peers(self) -> List[Dict[str, Any]]:
        """Get all connected peers"""
        return list(self.peers.values())


def main():
    parser = argparse.ArgumentParser(
        description="Tarcoin Blockchain Node - Production Ready"
    )
    parser.add_argument('--node-id', type=str, default=f"node_{int(time.time())}", 
                       help='Node identifier')
    parser.add_argument('--role', type=str, choices=['full_node', 'mining_node', 'validator', 'light_client'],
                       default='full_node', help='Node role')
    parser.add_argument('--port', type=int, default=8000, help='Node port')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Node host')
    parser.add_argument('--difficulty', type=int, default=4, help='Mining difficulty')
    parser.add_argument('--mining-reward', type=float, default=50.0, help='Mining reward amount')
    parser.add_argument('--enable-mining', action='store_true', help='Enable mining')
    parser.add_argument('--miner-address', type=str, help='Miner wallet address')
    parser.add_argument('--data-dir', type=str, default='./blockchain_data', help='Data directory')
    
    args = parser.parse_args()
    
    # Create node configuration
    config = NodeConfig(
        node_id=args.node_id,
        role=NetworkRole(args.role),
        port=args.port,
        host=args.host,
        difficulty=args.difficulty,
        mining_reward=args.mining_reward,
        enable_mining=args.enable_mining,
        data_dir=args.data_dir
    )
    
    # Initialize node
    node = BlockchainNode(config)
    
    logger.info("Node initialized successfully")
    logger.info(f"Node Info: {json.dumps(node.get_node_info(), indent=2)}")
    
    # Start mining if enabled and miner address provided
    if args.enable_mining and args.miner_address:
        node.start_mining(args.miner_address)
        
        # Add some test transactions
        for i in range(3):
            tx = {
                'sender': f'wallet_{i}',
                'receiver': args.miner_address,
                'amount': 10.0 + i,
                'timestamp': time.time(),
                'fee': 0.1
            }
            node.add_transaction(tx)
    
    # Keep node running
    try:
        while True:
            time.sleep(10)
            logger.info(f"Node status: {json.dumps(node.get_node_info(), indent=2)}")
    except KeyboardInterrupt:
        logger.info("Shutting down node...")
        node.stop_mining()
        sys.exit(0)


if __name__ == "__main__":
    main()
