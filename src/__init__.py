"""
Tarcoin - Quantum-Resistant ASIC-Native Cryptocurrency
Main package initialization
"""

__version__ = "1.0.0"
__author__ = "Tarcoin Community"
__license__ = "MIT"

# Core exports
from src.core.blockchain import Blockchain, Block, Transaction, HashAlgorithm
from src.crypto.wallet import Wallet, CryptoManager, KeyType, KeyPair
from src.node.network import TarcoinNode, NetworkMessage, MessageType, PeerInfo

__all__ = [
    # Blockchain
    'Blockchain',
    'Block',
    'Transaction',
    'HashAlgorithm',
    
    # Cryptography
    'Wallet',
    'CryptoManager',
    'KeyType',
    'KeyPair',
    
    # Network
    'TarcoinNode',
    'NetworkMessage',
    'MessageType',
    'PeerInfo',
]
