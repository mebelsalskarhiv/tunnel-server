"""
TunnelFlow WebSocket Handler - Manages client connections and traffic routing
Handles bidirectional communication between clients and incoming HTTP requests.
"""
import asyncio
import json
import logging
from typing import Dict, Optional
from datetime import datetime
import aiohttp
from aiohttp import web, WSMsgType

from ..core.tunnel_manager import tunnel_manager, TunnelConnection

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket connections from tunnel clients"""
    
    def __init__(self):
        self.client_sessions: Dict[str, aiohttp.ClientSession] = {}
    
    async def handle_client_connection(self, request: web.Request) -> web.WebSocketResponse:
        """Handle incoming WebSocket connection from a tunnel client"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Get tunnel token from query params or headers
        tunnel_id = request.query.get('tunnel_id')
        client_token = request.headers.get('X-Client-Token', '')
        
        if not tunnel_id:
            await ws.send_json({'error': 'Missing tunnel_id'})
            await ws.close()
            return ws
        
        # Validate token (in production, verify against database)
        # For now, we'll accept the connection if tunnel exists
        tunnel = tunnel_manager.tunnels.get(tunnel_id)
        if not tunnel:
            await ws.send_json({'error': 'Invalid tunnel_id'})
            await ws.close()
            return ws
        
        # Generate unique client ID
        client_id = f"{tunnel_id}_{datetime.utcnow().timestamp()}"
        
        try:
            # Register connection with tunnel manager
            connection = await tunnel_manager.register_connection(
                tunnel_id=tunnel_id,
                client_id=client_id,
                client_ws=ws
            )
            
            if not connection:
                await ws.send_json({'error': 'Failed to register connection'})
                await ws.close()
                return ws
            
            logger.info(f"Client {client_id} connected to tunnel {tunnel_id}")
            
            # Send connection confirmation
            await ws.send_json({
                'status': 'connected',
                'client_id': client_id,
                'tunnel_url': tunnel.public_url,
                'message': 'Successfully connected to TunnelFlow'
            })
            
            # Handle incoming messages from client
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_client_message(ws, tunnel_id, client_id, data)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from client {client_id}")
                
                elif msg.type == WSMsgType.BINARY:
                    # Handle binary data (for future protocol extensions)
                    await self.handle_binary_data(ws, tunnel_id, client_id, msg.data)
                
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error for client {client_id}: {ws.exception()}")
                    break
        
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        
        finally:
            # Cleanup on disconnect
            await tunnel_manager.unregister_connection(tunnel_id, client_id)
            logger.info(f"Client {client_id} disconnected from tunnel {tunnel_id}")
        
        return ws
    
    async def handle_client_message(
        self,
        ws: web.WebSocketResponse,
        tunnel_id: str,
        client_id: str,
        data: dict
    ):
        """Handle messages from tunnel client"""
        msg_type = data.get('type')
        
        if msg_type == 'heartbeat':
            # Respond to heartbeat
            await ws.send_json({
                'type': 'heartbeat_ack',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        elif msg_type == 'request_response':
            # Client is responding to an HTTP request forwarded to it
            request_id = data.get('request_id')
            status_code = data.get('status', 200)
            headers = data.get('headers', {})
            body = data.get('body', '')
            
            # Store response for retrieval by HTTP handler
            # This would typically use Redis or similar for cross-process communication
            logger.debug(f"Request {request_id} completed with status {status_code}")
            
            # Update stats
            body_size = len(body.encode('utf-8')) if isinstance(body, str) else len(body)
            await tunnel_manager.update_tunnel_stats(
                tunnel_id=tunnel_id,
                client_id=client_id,
                bytes_sent=body_size
            )
        
        elif msg_type == 'stats_update':
            # Client sending periodic stats
            sent = data.get('bytes_sent', 0)
            received = data.get('bytes_received', 0)
            await tunnel_manager.update_tunnel_stats(
                tunnel_id=tunnel_id,
                client_id=client_id,
                bytes_sent=sent,
                bytes_received=received
            )
        
        else:
            logger.warning(f"Unknown message type from client {client_id}: {msg_type}")
    
    async def handle_binary_data(
        self,
        ws: web.WebSocketResponse,
        tunnel_id: str,
        client_id: str,
        data: bytes
    ):
        """Handle binary data from client"""
        # For future implementation of binary protocols
        await tunnel_manager.update_tunnel_stats(
            tunnel_id=tunnel_id,
            client_id=client_id,
            bytes_received=len(data)
        )
    
    async def forward_request_to_client(
        self,
        connection: TunnelConnection,
        request_id: str,
        method: str,
        path: str,
        headers: dict,
        body: bytes = None
    ) -> Optional[dict]:
        """Forward an incoming HTTP request to the tunnel client"""
        try:
            # Send request to client via WebSocket
            await connection.client_ws.send_json({
                'type': 'http_request',
                'request_id': request_id,
                'method': method,
                'path': path,
                'headers': headers,
                'body': body.decode('utf-8') if body else None
            })
            
            # Wait for response with timeout
            # In a real implementation, this would use a more sophisticated mechanism
            # like a Future or Redis pub/sub
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # This is a placeholder - actual implementation would wait for WS response
                pass
            
            return {'status': 200, 'body': 'OK'}
            
        except asyncio.TimeoutError:
            logger.warning(f"Request {request_id} timed out waiting for client response")
            return {'status': 504, 'body': 'Gateway Timeout'}
        except Exception as e:
            logger.error(f"Error forwarding request {request_id}: {e}")
            return {'status': 502, 'body': 'Bad Gateway'}


# Global WebSocket handler instance
ws_handler = WebSocketHandler()


async def websocket_endpoint(request: web.Request) -> web.WebSocketResponse:
    """AIOHTTP endpoint for WebSocket connections"""
    return await ws_handler.handle_client_connection(request)
