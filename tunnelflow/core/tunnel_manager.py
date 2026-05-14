"""
TunnelFlow Core - Tunnel Manager and Connection Handler
Handles tunnel lifecycle, connection routing, and traffic management.
"""
import asyncio
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TunnelConnection:
    """Represents an active tunnel connection"""
    tunnel_id: str
    client_id: str
    client_ws: object  # WebSocket connection
    connected_at: datetime = field(default_factory=datetime.utcnow)
    bytes_sent: int = 0
    bytes_received: int = 0
    requests_count: int = 0
    
    def update_stats(self, sent: int = 0, received: int = 0):
        self.bytes_sent += sent
        self.bytes_received += received
        if sent > 0 or received > 0:
            self.requests_count += 1


@dataclass
class Tunnel:
    """Represents a configured tunnel"""
    id: str
    user_id: str
    subdomain: str
    custom_domain: Optional[str] = None
    target_port: int = 80
    protocol: str = "http"  # http, https, tls
    is_active: bool = False
    connections: Dict[str, TunnelConnection] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: Optional[datetime] = None
    
    @property
    def public_url(self) -> str:
        if self.custom_domain:
            return f"{self.protocol}://{self.custom_domain}"
        return f"{self.protocol}://{self.subdomain}.tunnelflow.io"
    
    @property
    def active_connections(self) -> int:
        return len(self.connections)


class TunnelManager:
    """Manages all tunnels and their connections"""
    
    def __init__(self):
        self.tunnels: Dict[str, Tunnel] = {}
        self.user_tunnels: Dict[str, set] = {}  # user_id -> set of tunnel_ids
        self.subdomain_map: Dict[str, str] = {}  # subdomain -> tunnel_id
        self.domain_map: Dict[str, str] = {}  # custom_domain -> tunnel_id
        self._lock = asyncio.Lock()
        
    async def create_tunnel(
        self,
        user_id: str,
        subdomain: str,
        custom_domain: Optional[str] = None,
        target_port: int = 80,
        protocol: str = "http"
    ) -> Tunnel:
        """Create a new tunnel for a user"""
        async with self._lock:
            tunnel_id = str(uuid.uuid4())
            
            # Check subdomain availability
            if subdomain in self.subdomain_map:
                raise ValueError(f"Subdomain {subdomain} already taken")
            
            # Check custom domain availability
            if custom_domain and custom_domain in self.domain_map:
                raise ValueError(f"Domain {custom_domain} already taken")
            
            tunnel = Tunnel(
                id=tunnel_id,
                user_id=user_id,
                subdomain=subdomain,
                custom_domain=custom_domain,
                target_port=target_port,
                protocol=protocol
            )
            
            self.tunnels[tunnel_id] = tunnel
            self.subdomain_map[subdomain] = tunnel_id
            
            if custom_domain:
                self.domain_map[custom_domain] = tunnel_id
            
            # Track user's tunnels
            if user_id not in self.user_tunnels:
                self.user_tunnels[user_id] = set()
            self.user_tunnels[user_id].add(tunnel_id)
            
            logger.info(f"Created tunnel {tunnel_id} for user {user_id}: {tunnel.public_url}")
            return tunnel
    
    async def delete_tunnel(self, tunnel_id: str) -> bool:
        """Delete a tunnel and close all connections"""
        async with self._lock:
            if tunnel_id not in self.tunnels:
                return False
            
            tunnel = self.tunnels[tunnel_id]
            
            # Close all active connections
            for conn in list(tunnel.connections.values()):
                try:
                    await conn.client_ws.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            
            # Remove from maps
            del self.subdomain_map[tunnel.subdomain]
            if tunnel.custom_domain:
                del self.domain_map[tunnel.custom_domain]
            
            # Remove from user's tunnels
            if tunnel.user_id in self.user_tunnels:
                self.user_tunnels[tunnel.user_id].discard(tunnel_id)
            
            del self.tunnels[tunnel_id]
            logger.info(f"Deleted tunnel {tunnel_id}")
            return True
    
    async def register_connection(
        self,
        tunnel_id: str,
        client_id: str,
        client_ws: object
    ) -> Optional[TunnelConnection]:
        """Register a new client connection to a tunnel"""
        async with self._lock:
            if tunnel_id not in self.tunnels:
                logger.warning(f"Tunnel {tunnel_id} not found")
                return None
            
            tunnel = self.tunnels[tunnel_id]
            tunnel.is_active = True
            tunnel.last_activity = datetime.utcnow()
            
            connection = TunnelConnection(
                tunnel_id=tunnel_id,
                client_id=client_id,
                client_ws=client_ws
            )
            
            tunnel.connections[client_id] = connection
            logger.info(f"Client {client_id} connected to tunnel {tunnel_id}")
            return connection
    
    async def unregister_connection(self, tunnel_id: str, client_id: str):
        """Remove a client connection from a tunnel"""
        async with self._lock:
            if tunnel_id not in self.tunnels:
                return
            
            tunnel = self.tunnels[tunnel_id]
            if client_id in tunnel.connections:
                del tunnel.connections[client_id]
                
                # Mark tunnel as inactive if no connections
                if not tunnel.connections:
                    tunnel.is_active = False
                
                logger.info(f"Client {client_id} disconnected from tunnel {tunnel_id}")
    
    def get_tunnel_by_subdomain(self, subdomain: str) -> Optional[Tunnel]:
        """Get tunnel by subdomain"""
        tunnel_id = self.subdomain_map.get(subdomain)
        if tunnel_id:
            return self.tunnels.get(tunnel_id)
        return None
    
    def get_tunnel_by_domain(self, domain: str) -> Optional[Tunnel]:
        """Get tunnel by custom domain"""
        tunnel_id = self.domain_map.get(domain)
        if tunnel_id:
            return self.tunnels.get(tunnel_id)
        return None
    
    def get_user_tunnels(self, user_id: str) -> list:
        """Get all tunnels for a user"""
        tunnel_ids = self.user_tunnels.get(user_id, set())
        return [self.tunnels[tid] for tid in tunnel_ids if tid in self.tunnels]
    
    async def update_tunnel_stats(
        self,
        tunnel_id: str,
        client_id: str,
        bytes_sent: int = 0,
        bytes_received: int = 0
    ):
        """Update traffic statistics for a tunnel connection"""
        async with self._lock:
            if tunnel_id not in self.tunnels:
                return
            
            tunnel = self.tunnels[tunnel_id]
            if client_id in tunnel.connections:
                tunnel.connections[client_id].update_stats(bytes_sent, bytes_received)
                tunnel.last_activity = datetime.utcnow()
    
    def get_total_stats(self) -> dict:
        """Get aggregated statistics across all tunnels"""
        total_connections = 0
        total_bytes_sent = 0
        total_bytes_received = 0
        total_requests = 0
        active_tunnels = 0
        
        for tunnel in self.tunnels.values():
            if tunnel.is_active:
                active_tunnels += 1
            
            for conn in tunnel.connections.values():
                total_connections += 1
                total_bytes_sent += conn.bytes_sent
                total_bytes_received += conn.bytes_received
                total_requests += conn.requests_count
        
        return {
            "total_tunnels": len(self.tunnels),
            "active_tunnels": active_tunnels,
            "total_connections": total_connections,
            "total_bytes_sent": total_bytes_sent,
            "total_bytes_received": total_bytes_received,
            "total_requests": total_requests
        }


# Global tunnel manager instance
tunnel_manager = TunnelManager()
