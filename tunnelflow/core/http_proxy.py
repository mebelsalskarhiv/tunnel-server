"""
TunnelFlow HTTP Proxy - Routes incoming HTTP/HTTPS requests to tunnel clients
Handles domain-based routing and TLS termination.
"""
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime
import uuid
from aiohttp import web
import aiohttp

from ..core.tunnel_manager import tunnel_manager, TunnelConnection
from ..core.websocket_handler import ws_handler

logger = logging.getLogger(__name__)


class HTTPProxyHandler:
    """Handles incoming HTTP/HTTPS requests and routes them to tunnel clients"""
    
    def __init__(self):
        self.request_futures: Dict[str, asyncio.Future] = {}
    
    def extract_host(self, request: web.Request) -> str:
        """Extract host from request headers"""
        host = request.headers.get('Host', '')
        # Remove port if present
        if ':' in host:
            host = host.split(':')[0]
        return host.lower()
    
    def get_tunnel_for_request(self, request: web.Request) -> Optional[tuple]:
        """Find the appropriate tunnel for an incoming request"""
        host = self.extract_host(request)
        
        # Try custom domain first
        tunnel = tunnel_manager.get_tunnel_by_domain(host)
        if tunnel:
            return tunnel, host
        
        # Try subdomain
        # Handle .tunnelflow.io subdomains
        if '.tunnelflow.io' in host:
            subdomain = host.replace('.tunnelflow.io', '')
            tunnel = tunnel_manager.get_tunnel_by_subdomain(subdomain)
            if tunnel:
                return tunnel, subdomain
        
        return None, host
    
    async def handle_http_request(self, request: web.Request) -> web.Response:
        """Handle incoming HTTP request and forward to tunnel client"""
        tunnel, host = self.get_tunnel_for_request(request)
        
        if not tunnel:
            logger.warning(f"No tunnel found for host: {host}")
            return web.Response(
                text=f"TunnelFlow: No tunnel configured for {host}",
                status=404
            )
        
        if not tunnel.is_active or not tunnel.connections:
            logger.warning(f"Tunnel {tunnel.id} has no active connections")
            return web.Response(
                text="TunnelFlow: Tunnel is not connected",
                status=503
            )
        
        # Select a connection (round-robin or least connections could be implemented)
        connection = next(iter(tunnel.connections.values()))
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        try:
            # Read request body
            body = await request.read()
            
            # Prepare headers (remove hop-by-hop headers)
            headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ['host', 'connection', 'keep-alive', 
                                    'transfer-encoding', 'upgrade']
            }
            
            # Add TunnelFlow-specific headers
            headers['X-TunnelFlow-Request-ID'] = request_id
            headers['X-TunnelFlow-Original-Host'] = host
            headers['X-Forwarded-For'] = request.remote or ''
            headers['X-Forwarded-Proto'] = request.scheme
            
            # Forward request to client via WebSocket
            logger.debug(f"Forwarding request {request_id} to tunnel {tunnel.id}")
            
            await connection.client_ws.send_json({
                'type': 'http_request',
                'request_id': request_id,
                'method': request.method,
                'path': request.path_qs,
                'headers': headers,
                'body': body.decode('utf-8', errors='replace') if body else None
            })
            
            # Wait for response from client
            # In production, this would use a proper async mechanism
            response_data = await self.wait_for_response(request_id, timeout=30)
            
            if not response_data:
                logger.error(f"Timeout waiting for response to request {request_id}")
                return web.Response(
                    text="Gateway Timeout",
                    status=504
                )
            
            # Update stats
            request_size = len(body) if body else 0
            response_size = len(response_data.get('body', '').encode('utf-8'))
            await tunnel_manager.update_tunnel_stats(
                tunnel_id=tunnel.id,
                client_id=connection.client_id,
                bytes_sent=request_size,
                bytes_received=response_size
            )
            
            # Build response
            status = response_data.get('status', 200)
            resp_headers = response_data.get('headers', {})
            resp_body = response_data.get('body', '')
            
            # Create aiohttp response
            response = web.Response(
                status=status,
                text=resp_body if isinstance(resp_body, str) else resp_body.decode('utf-8'),
                headers=resp_headers
            )
            
            logger.info(f"Request {request_id} completed: {request.method} {request.path} -> {status}")
            return response
            
        except asyncio.TimeoutError:
            logger.error(f"Request {request_id} timed out")
            return web.Response(text="Gateway Timeout", status=504)
        except Exception as e:
            logger.error(f"Error handling request {request_id}: {e}")
            return web.Response(text="Bad Gateway", status=502)
    
    async def wait_for_response(self, request_id: str, timeout: int = 30) -> Optional[dict]:
        """
        Wait for response from tunnel client.
        
        Note: This is a simplified implementation. In production, you would:
        1. Use Redis pub/sub for cross-process communication
        2. Store response in a shared cache keyed by request_id
        3. Use asyncio.Future or similar for proper async waiting
        
        For now, this returns a mock response after a delay.
        """
        # Create a future for this request
        future = asyncio.Future()
        self.request_futures[request_id] = future
        
        try:
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            return None
        finally:
            self.request_futures.pop(request_id, None)
    
    async def receive_response(self, request_id: str, response_data: dict):
        """Called when a response is received from a tunnel client"""
        if request_id in self.request_futures:
            self.request_futures[request_id].set_result(response_data)


# Global HTTP proxy handler instance
http_proxy = HTTPProxyHandler()


async def http_proxy_endpoint(request: web.Request) -> web.Response:
    """AIOHTTP endpoint for all HTTP/HTTPS traffic"""
    return await http_proxy.handle_http_request(request)


def setup_proxy_routes(app: web.Application):
    """Setup HTTP proxy routes"""
    # Catch-all route for HTTP/HTTPS traffic
    app.router.add_route('*', '/{path:.*}', http_proxy_endpoint)
