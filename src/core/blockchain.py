import hashlib
import time
import json
import os
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
        self.hash = self.calculate_block_hash()
        
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
    """Main Blockchain implementation for Tarcoin with Persistence"""
    
    TOTAL_SUPPLY = 17_000_000
    INITIAL_REWARD = 50
    HALVING_INTERVAL = 210_000
    TARGET_BLOCK_TIME = 600
    STORAGE_FILE = "tarcoin_chain.json"
    
    def __init__(self):
        """Initialize a new blockchain or load from file if exists"""
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.difficulty = 4
        self.mining_reward = self.INITIAL_REWARD
        self.total_supply_mined = 0
        
        if os.path.exists(self.STORAGE_FILE):
            self.load_from_file()
        else:
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
        self.save_to_file()
    
    def get_latest_block(self) -> Block:
        """Return the latest block in the chain"""
        return self.chain[-1]
    
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add a new transaction to pending transactions after validation"""
        if self.validate_transaction(transaction):
            self.pending_transactions.append(transaction)
            return True
        return False
    
    def validate_transaction(self, transaction: Transaction) -> bool:
        """Validate transaction logic (Balance check & Time check)"""
        if transaction.sender == "GENESIS" or transaction.sender == "MINING_REWARD":
            return True
            
        sender_balance = self.get_balance(transaction.sender)
        if sender_balance < (transaction.amount + transaction.fee):
            return False
        
        if time.time() - transaction.timestamp > 86400:  # 24 hours
            return False
            
        return True
    
    def mine_pending_transactions(self, miner_address: str) -> Optional[Block]:
        """Mine pending transactions and include mining reward"""
        reward_tx = Transaction(
            tx_id=hashlib.sha256(f"{miner_address}{time.time()}".encode()).hexdigest()[:16],
            sender="MINING_REWARD",
            receiver=miner_address,
            amount=self.mining_reward,
            timestamp=time.time(),
            nonce=0
        )
        
        block_transactions = [reward_tx] + self.pending_transactions
        
        new_block = Block(
            block_index=len(self.chain),
            timestamp=time.time(),
            transactions=block_transactions,
            previous_hash=self.get_latest_block().hash,
            difficulty=self.difficulty,
            miner_address=miner_address
        )
        
        new_block.mine_block()
        self.chain.append(new_block)
        
        self.total_supply_mined += self.mining_reward
        self.pending_transactions = []
        self.save_to_file()
        
        return new_block
    
    def get_balance(self, address: str) -> float:
        """Calculate address balance from the entire chain"""
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.sender == address:
                    balance -= (tx.amount + tx.fee)
                if tx.receiver == address:
                    balance += tx.amount
        return balance
    
    def is_chain_valid(self) -> bool:
        """Validate integrity of the entire chain"""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            
            if current.hash != current.calculate_block_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not current.hash.startswith('0' * current.difficulty):
                return False
        return True
    
    def save_to_file(self) -> None:
        """Save blockchain state to JSON file"""
        data = {
            'difficulty': self.difficulty,
            'total_supply_mined': self.total_supply_mined,
            'chain': [block.to_dict() for block in self.chain]
        }
        with open(self.STORAGE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
            
    def load_from_file(self) -> None:
        """Load blockchain state from JSON file"""
        with open(self.STORAGE_FILE, 'r') as f:
            data = json.load(f)
            self.difficulty = data['difficulty']
            self.total_supply_mined = data['total_supply_mined']
            self.chain = []
            for b_data in data['chain']:
                transactions = [
                    Transaction(**tx) for tx in b_data['transactions']
                ]
                block = Block(
                    block_index=b_data['index'],
                    timestamp=b_data['timestamp'],
                    transactions=transactions,
                    previous_hash=b_data['previous_hash'],
                    nonce=b_data['nonce'],
                    difficulty=b_data['difficulty'],
                    hash=b_data['hash'],
                    miner_address=b_data['miner']
                )
                self.chain.append(block)


if __name__ == "__main__":
    tarcoin = Blockchain()
    
    while True:
        print("\n=== TARCOIN CORE CLI MENU ===")
        print("1. View Blockchain Status & Validity")
        print("2. Check Address Balance")
        print("3. Create New Transaction")
        print("4. Mine Pending Blocks (Mining)")
        print("5. Exit")
        
        choice = input("Select menu (1-5): ").strip()
        
        if choice == "1":
            print(f"\nTotal Blocks in Chain: {len(tarcoin.chain)}")
            print(f"Chain Validity Status: {tarcoin.is_chain_valid()}")
            print(f"Total Mined Supply: {tarcoin.total_supply_mined} TRC")
        elif choice == "2":
            addr = input("Enter account name/address: ").strip()
            print(f"Balance of {addr}: {tarcoin.get_balance(addr)} TRC")
        elif choice == "3":
            sender = input("Sender Address: ").strip()
            receiver = input("Receiver Address: ").strip()
            amount = float(input("Amount in TRC: "))
            tx_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]
            
            tx = Transaction(
                tx_id=tx_id,
                sender=sender,
                receiver=receiver,
                amount=amount,
                timestamp=time.time(),
                nonce=0
            )
            
            if tarcoin.add_transaction(tx):
                print("Transaction successfully added to mempool!")
            else:
                print("Transaction failed! Insufficient balance or invalid.")
        elif choice == "4":
            miner = input("Enter Miner Address: ").strip()
            print("Mining new block (Proof of Work)...")
            mined = tarcoin.mine_pending_transactions(miner)
            if mined:
                print(f"Successfully mined! Block Hash: {mined.hash}")
            else:
                print("No pending transactions to mine.")
        elif choice == "5":
            print("Exiting program. Data saved safely.")
            break
        else:
            print("Invalid choice, try again.")
