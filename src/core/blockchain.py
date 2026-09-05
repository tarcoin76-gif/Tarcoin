"""
Tarcoin Core Blockchain Implementation
Quantum-resistant ASIC-native cryptocurrency
"""

import hashlib
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class HashAlgorithm(Enum):
    """Supported hash algorithms for quantum resistance"""
    SHA3_256 = "SHA3-256"
    SHA3_512 = "SHA3-512"
    BLAKE3 = "BLAKE3"


@dataclass
class Transaction:
    """Represents a single transaction in the blockchain"""
    tx_id: str
    sender: str
    receiver: str
    amount: float
    timestamp: float
    nonce: int
    signature: Optional[str] = None
    fee: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to dictionary"""
        return {
            'tx_id': self.tx_id,
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'timestamp': self.timestamp,
            'nonce': self.nonce,
            'signature': self.signature,
            'fee': self.fee
        }
    
    def calculate_hash(self) -> str:
        """Calculate transaction hash"""
        tx_string = str(self.to_dict())
        return hashlib.sha3_256(tx_string.encode()).hexdigest()


@dataclass
class Block:
    """Represents a single block in the blockchain"""
    block_index: int
    timestamp: float
    transactions: List[Transaction] = field(default_factory=list)
    previous_hash: str = ""
    nonce: int = 0
    difficulty: int = 4
    hash: str = ""
    miner_address: str = ""
    
    def calculate_block_hash(self) -> str:
        """Calculate block hash using quantum-resistant algorithm"""
        block_data = {
            'index': self.block_index,
            'timestamp': self.timestamp,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'miner': self.miner_address
        }
        block_string = str(block_data)
        return hashlib.sha3_256(block_string.encode()).hexdigest()
    
    def mine_block(self) -> None:
        """Proof of Work mining for this block"""
        target = '0' * self.difficulty
        
        while self.hash[:self.difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_block_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary"""
        return {
            'index': self.block_index,
            'timestamp': self.timestamp,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
            'difficulty': self.difficulty,
            'hash': self.hash,
            'miner': self.miner_address
        }


class Blockchain:
    """Main Blockchain implementation for Tarcoin"""
    
    # Fixed supply constants
    TOTAL_SUPPLY = 17_000_000  # 17 million TRC
    INITIAL_REWARD = 50  # Initial block reward
    HALVING_INTERVAL = 210_000  # Blocks between halvings
    MAX_BLOCK_SIZE = 1_000_000  # Bytes
    TARGET_BLOCK_TIME = 600  # 10 minutes in seconds
    
    def __init__(self):
        """Initialize a new blockchain"""
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.difficulty = 4
        self.mining_reward = self.INITIAL_REWARD
        self.total_supply_mined = 0
        
        # Create genesis block
        self.create_genesis_block()
    
    def create_genesis_block(self) -> None:
        """Create the first block in the blockchain"""
        genesis_block = Block(
            block_index=0,
            timestamp=time.time(),
            previous_hash="0",
            difficulty=self.difficulty,
            miner_address="GENESIS"
        )
        genesis_block.mine_block()
        self.chain.append(genesis_block)
    
    def get_latest_block(self) -> Block:
        """Return the latest block in the chain"""
        return self.chain[-1]
    
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add a new transaction to pending transactions"""
        if self.validate_transaction(transaction):
            self.pending_transactions.append(transaction)
            return True
        return False
    
    def validate_transaction(self, transaction: Transaction) -> bool:
        """Validate a transaction"""
        # Check if sender has sufficient balance
        sender_balance = self.get_balance(transaction.sender)
        
        if sender_balance < (transaction.amount + transaction.fee):
            return False
        
        # Check if transaction is not too old
        current_time = time.time()
        if current_time - transaction.timestamp > 3600:  # 1 hour
            return False
        
        return True
    
    def mine_pending_transactions(self, miner_address: str) -> Optional[Block]:
        """Mine pending transactions into a new block"""
        if not self.pending_transactions:
            return None
        
        new_block = Block(
            block_index=len(self.chain),
            timestamp=time.time(),
            transactions=self.pending_transactions.copy(),
            previous_hash=self.get_latest_block().hash,
            difficulty=self.difficulty,
            miner_address=miner_address
        )
        
        # Mine the block
        new_block.mine_block()
        
        # Add block to chain
        self.chain.append(new_block)
        
        # Update supply and reward
        self.total_supply_mined += self.mining_reward
        self.pending_transactions = []
        
        # Adjust difficulty based on block time
        self.adjust_difficulty()
        
        return new_block
    
    def adjust_difficulty(self) -> None:
        """Adjust difficulty based on average block time"""
        if len(self.chain) < 2:
            return
        
        # Check every 2016 blocks (Bitcoin's adjustment interval)
        if len(self.chain) % 2016 == 0:
            time_taken = (
                self.chain[-1].timestamp - 
                self.chain[-2016].timestamp
            )
            expected_time = self.TARGET_BLOCK_TIME * 2016
            
            if time_taken < expected_time / 4:
                self.difficulty += 1
            elif time_taken > expected_time * 4:
                self.difficulty = max(1, self.difficulty - 1)
    
    def update_mining_reward(self) -> None:
        """Update mining reward based on halving schedule"""
        halvings = len(self.chain) // self.HALVING_INTERVAL
        self.mining_reward = self.INITIAL_REWARD / (2 ** halvings)
        
        # Stop mining if total supply reached
        if self.total_supply_mined >= self.TOTAL_SUPPLY:
            self.mining_reward = 0
    
    def get_balance(self, address: str) -> float:
        """Get the balance of an address"""
        balance = 0.0
        
        for block in self.chain:
            for transaction in block.transactions:
                if transaction.sender == address:
                    balance -= (transaction.amount + transaction.fee)
                if transaction.receiver == address:
                    balance += transaction.amount
        
        return balance
    
    def is_chain_valid(self) -> bool:
        """Validate the entire blockchain"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # Verify current block hash
            if current_block.hash != current_block.calculate_block_hash():
                return False
            
            # Verify link to previous block
            if current_block.previous_hash != previous_block.hash:
                return False
            
            # Verify proof of work
            if not current_block.hash.startswith('0' * current_block.difficulty):
                return False
        
        return True
    
    def get_chain_data(self) -> List[Dict[str, Any]]:
        """Get all blocks in the chain as dictionaries"""
        return [block.to_dict() for block in self.chain]
