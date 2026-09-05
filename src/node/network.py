"""
Tarcoin Network Node Implementation
Peer-to-peer network communication
"""

import socket
import json
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class MessageType(Enum):
    """Types of network messages"""
    BLOCK = "block"
    TRANSACTION = "transaction"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    PING = "ping"
    PONG = "pong"
    PEER_DISCOVERY = "peer_discovery"


@dataclass
class PeerInfo:
    """Information about a peer node"""
    peer_id: str
    host: str
    port: int
    last_seen: float
    version: str
    is_active: bool = True
    height: int = 0  # Blockchain height
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'peer_id': self.peer_id,
            'host': self.host,
            'port': self.port,
            'last_seen': self.last_seen,
            'version': self.version,
            'is_active': self.is_active,
            'height': self.height
        }


@dataclass
class NetworkMessage:
    """A message to be sent over the network"""
    message_type: MessageType
    sender_id: str
    timestamp: float
    payload: Dict = field(default_factory=dict)
    signature: str = ""
    
    def to_json(self) -> str:
        """Convert message to JSON"""
        return json.dumps({
            'type': self.message_type.value,
            'sender_id': self.sender_id,
            'timestamp': self.timestamp,
            'payload': self.payload,
            'signature': self.signature
        })
    
    @staticmethod
    def from_json(json_data: str) -> 'NetworkMessage':
        """Create message from JSON"""
        data = json.loads(json_data)
        return NetworkMessage(
            message_type=MessageType(data['type']),
            sender_id=data['sender_id'],
            timestamp=data['timestamp'],
            payload=data.get('payload', {}),
            signature=data.get('signature', '')
        )


class NetworkNode(ABC):
    """Abstract base class for network nodes"""
    
    @abstractmethod
    def handle_block(self, block_data: Dict) -> None:
        """Handle incoming block"""
        pass
    
    @abstractmethod
    def handle_transaction(self, tx_data: Dict) -> None:
        """Handle incoming transaction"""
        pass
    
    @abstractmethod
    def handle_sync_request(self, peer_id: str, height: int) -> None:
        """Handle sync request from peer"""
        pass


class TarcoinNode(NetworkNode):
    """Tarcoin full node implementation"""
    
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 9999):
        """Initialize a Tarcoin node"""
        self.node_id = node_id
        self.host = host
        self.port = port
        self.version = "1.0.0"
        
        self.peers: Dict[str, PeerInfo] = {}
        self.message_handlers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        
        self.is_running = False
        self.server_socket: Optional[socket.socket] = None
        self.peer_threads: List[threading.Thread] = []
    
    def start(self) -> None:
        """Start the node"""
        self.is_running = True
        
        # Create server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        print(f"[NODE {self.node_id}] Started on {self.host}:{self.port}")
        
        # Start listening thread
        listen_thread = threading.Thread(target=self._listen_for_connections)
        listen_thread.daemon = True
        listen_thread.start()
        self.peer_threads.append(listen_thread)
    
    def stop(self) -> None:
        """Stop the node"""
        self.is_running = False
        if self.server_socket:
            self.server_socket.close()
        print(f"[NODE {self.node_id}] Stopped")
    
    def _listen_for_connections(self) -> None:
        """Listen for incoming peer connections"""
        while self.is_running:
            try:
                client_socket, address = self.server_socket.accept()
                peer_thread = threading.Thread(
                    target=self._handle_peer_connection,
                    args=(client_socket, address)
                )
                peer_thread.daemon = True
                peer_thread.start()
                self.peer_threads.append(peer_thread)
            except Exception as e:
                print(f"[NODE {self.node_id}] Error accepting connection: {e}")
    
    def _handle_peer_connection(self, client_socket: socket.socket, address: tuple) -> None:
        """Handle a peer connection"""
        try:
            while self.is_running:
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    message = NetworkMessage.from_json(data.decode())
                    self._process_message(message)
                except json.JSONDecodeError:
                    print(f"[NODE {self.node_id}] Invalid message from {address}")
        except Exception as e:
            print(f"[NODE {self.node_id}] Error handling peer: {e}")
        finally:
            client_socket.close()
    
    def _process_message(self, message: NetworkMessage) -> None:
        """Process an incoming message"""
        # Update peer info
        if message.sender_id not in self.peers:
            self.peers[message.sender_id] = PeerInfo(
                peer_id=message.sender_id,
                host="0.0.0.0",
                port=0,
                last_seen=message.timestamp,
                version="unknown"
            )
        
        self.peers[message.sender_id].last_seen = time.time()
        
        # Call registered handlers
        if message.message_type in self.message_handlers:
            for handler in self.message_handlers[message.message_type]:
                try:
                    handler(message.payload)
                except Exception as e:
                    print(f"[NODE {self.node_id}] Handler error: {e}")
    
    def connect_to_peer(self, peer_host: str, peer_port: int, peer_id: str) -> bool:
        """Connect to another peer"""
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect((peer_host, peer_port))
            
            # Add to peers list
            self.peers[peer_id] = PeerInfo(
                peer_id=peer_id,
                host=peer_host,
                port=peer_port,
                last_seen=time.time(),
                version="unknown"
            )
            
            print(f"[NODE {self.node_id}] Connected to peer {peer_id}")
            return True
        except Exception as e:
            print(f"[NODE {self.node_id}] Failed to connect to peer: {e}")
            return False
    
    def broadcast_message(self, message: NetworkMessage) -> None:
        """Broadcast a message to all peers"""
        for peer_id, peer_info in self.peers.items():
            self.send_message_to_peer(peer_id, message)
    
    def send_message_to_peer(self, peer_id: str, message: NetworkMessage) -> bool:
        """Send a message to a specific peer"""
        if peer_id not in self.peers:
            return False
        
        try:
            peer_info = self.peers[peer_id]
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect((peer_info.host, peer_info.port))
            peer_socket.sendall(message.to_json().encode())
            peer_socket.close()
            return True
        except Exception as e:
            print(f"[NODE {self.node_id}] Failed to send message to {peer_id}: {e}")
            return False
    
    def register_message_handler(
        self, 
        message_type: MessageType, 
        handler: Callable[[Dict], None]
    ) -> None:
        """Register a handler for a message type"""
        self.message_handlers[message_type].append(handler)
    
    def handle_block(self, block_data: Dict) -> None:
        """Handle incoming block"""
        print(f"[NODE {self.node_id}] Received block: {block_data.get('index')}")
    
    def handle_transaction(self, tx_data: Dict) -> None:
        """Handle incoming transaction"""
        print(f"[NODE {self.node_id}] Received transaction: {tx_data.get('tx_id')}")
    
    def handle_sync_request(self, peer_id: str, height: int) -> None:
        """Handle sync request from peer"""
        print(f"[NODE {self.node_id}] Sync request from {peer_id} at height {height}")
    
    def get_node_info(self) -> Dict:
        """Get information about this node"""
        return {
            'node_id': self.node_id,
            'host': self.host,
            'port': self.port,
            'version': self.version,
            'is_running': self.is_running,
            'peer_count': len(self.peers)
        }
    
    def get_peers(self) -> List[Dict]:
        """Get information about connected peers"""
        return [peer.to_dict() for peer in self.peers.values()]
