"""
TunnelFlow Client - Lightweight tunnel client for Windows/Linux/macOS
Connects to TunnelFlow server and forwards traffic to local services.
Features: Auto-reconnect, heartbeat, configurable via JSON.
"""
import asyncio
import json
import logging
import sys
import os
import signal
import argparse
from datetime import datetime
from typing import Optional
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TunnelClient:
    """TunnelFlow client that maintains WebSocket connection to server"""
    
    def __init__(
        self,
        server_url: str,
        tunnel_id: str,
        client_token: str,
        local_host: str = 'localhost',
        local_port: int = 80,
        reconnect_delay: int = 5,
        max_reconnect_delay: int = 60,
        heartbeat_interval: int = 30
    ):
        self.server_url = server_url.rstrip('/')
        self.tunnel_id = tunnel_id
        self.client_token = client_token
        self.local_host = local_host
        self.local_port = local_port
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.heartbeat_interval = heartbeat_interval
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.running = False
        self.current_reconnect_delay = reconnect_delay
        self.last_heartbeat = datetime.utcnow()
    
    async def connect(self):
        """Establish WebSocket connection to server"""
        ws_url = f"{self.server_url.replace('http', 'ws')}/ws/tunnel"
        params = {'tunnel_id': self.tunnel_id}
        headers = {'X-Client-Token': self.client_token}
        
        logger.info(f"Connecting to {ws_url}")
        
        try:
            self.ws = await self.session.ws_connect(
                ws_url,
                params=params,
                headers=headers,
                heartbeat=self.heartbeat_interval
            )
            
            # Wait for connection confirmation
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get('status') == 'connected':
                        logger.info(f"✅ Connected! Tunnel URL: {data.get('tunnel_url')}")
                        self.current_reconnect_delay = self.reconnect_delay
                        return True
                    elif data.get('error'):
                        logger.error(f"❌ Connection failed: {data['error']}")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    async def send_heartbeat(self):
        """Send periodic heartbeat to server"""
        while self.running and self.ws and not self.ws.closed:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                if self.ws and not self.ws.closed:
                    await self.ws.send_json({
                        'type': 'heartbeat',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    self.last_heartbeat = datetime.utcnow()
                    logger.debug("❤️ Heartbeat sent")
            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
                break
    
    async def handle_incoming_request(self, data: dict):
        """Handle HTTP request forwarded from server"""
        request_id = data.get('request_id')
        method = data.get('method', 'GET')
        path = data.get('path', '/')
        headers = data.get('headers', {})
        body = data.get('body')
        
        logger.debug(f"📥 Request: {method} {path}")
        
        try:
            # Forward request to local service
            url = f"http://{self.local_host}:{self.local_port}{path}"
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers={k: v for k, v in headers.items() 
                            if k.lower() not in ['host']},
                    data=body.encode('utf-8') if body else None
                ) as response:
                    resp_body = await response.text()
                    resp_headers = dict(response.headers)
                    
                    # Send response back to server
                    await self.ws.send_json({
                        'type': 'request_response',
                        'request_id': request_id,
                        'status': response.status,
                        'headers': resp_headers,
                        'body': resp_body
                    })
                    
                    logger.debug(f"📤 Response: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error forwarding request: {e}")
            # Send error response
            await self.ws.send_json({
                'type': 'request_response',
                'request_id': request_id,
                'status': 502,
                'headers': {},
                'body': f'Error connecting to local service: {str(e)}'
            })
    
    async def run(self):
        """Main client loop with auto-reconnect"""
        self.running = True
        
        async with aiohttp.ClientSession() as self.session:
            while self.running:
                try:
                    # Attempt to connect
                    connected = await self.connect()
                    
                    if not connected:
                        logger.warning(f"Connection failed, retrying in {self.current_reconnect_delay}s...")
                        await asyncio.sleep(self.current_reconnect_delay)
                        # Exponential backoff
                        self.current_reconnect_delay = min(
                            self.current_reconnect_delay * 2,
                            self.max_reconnect_delay
                        )
                        continue
                    
                    # Start heartbeat task
                    heartbeat_task = asyncio.create_task(self.send_heartbeat())
                    
                    # Handle incoming messages
                    async for msg in self.ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                msg_type = data.get('type')
                                
                                if msg_type == 'http_request':
                                    await self.handle_incoming_request(data)
                                elif msg_type == 'heartbeat_ack':
                                    logger.debug("💓 Heartbeat acknowledged")
                                else:
                                    logger.debug(f"Received: {msg_type}")
                                    
                            except json.JSONDecodeError:
                                logger.warning("Invalid JSON received")
                        
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logger.warning("WebSocket closed by server")
                            break
                        
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {self.ws.exception()}")
                            break
                    
                    # Connection lost, cleanup
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    
                    if self.running:
                        logger.warning(f"Disconnected, reconnecting in {self.current_reconnect_delay}s...")
                        await asyncio.sleep(self.current_reconnect_delay)
                        self.current_reconnect_delay = min(
                            self.current_reconnect_delay * 2,
                            self.max_reconnect_delay
                        )
                
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    if self.running:
                        await asyncio.sleep(self.current_reconnect_delay)
                        self.current_reconnect_delay = min(
                            self.current_reconnect_delay * 2,
                            self.max_reconnect_delay
                        )
    
    async def shutdown(self):
        """Gracefully shutdown the client"""
        logger.info("Shutting down...")
        self.running = False
        if self.ws and not self.ws.closed:
            await self.ws.close()
        if self.session and not self.session.closed:
            await self.session.close()


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


async def main_async():
    """Async main entry point"""
    parser = argparse.ArgumentParser(description='TunnelFlow Client')
    parser.add_argument('--config', '-c', default='config.json',
                       help='Path to config file (default: config.json)')
    parser.add_argument('--server', '-s', help='Server URL (overrides config)')
    parser.add_argument('--tunnel-id', '-t', help='Tunnel ID (overrides config)')
    parser.add_argument('--token', help='Client token (overrides config)')
    parser.add_argument('--local-port', '-p', type=int, help='Local port (overrides config)')
    parser.add_argument('--once', action='store_true',
                       help='Run once without auto-reconnect')
    
    args = parser.parse_args()
    
    # Load config
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
    
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid config file: {e}")
        sys.exit(1)
    
    # Override config with command line args
    server_url = args.server or config.get('server_url', 'https://tunnelflow.io')
    tunnel_id = args.tunnel_id or config.get('tunnel_id')
    client_token = args.token or config.get('client_token')
    local_port = args.local_port or config.get('local_port', 80)
    local_host = config.get('local_host', 'localhost')
    
    if not tunnel_id or not client_token:
        logger.error("Missing tunnel_id or client_token in config")
        sys.exit(1)
    
    # Create client
    client = TunnelClient(
        server_url=server_url,
        tunnel_id=tunnel_id,
        client_token=client_token,
        local_host=local_host,
        local_port=local_port,
        reconnect_delay=config.get('reconnect_delay', 5),
        max_reconnect_delay=config.get('max_reconnect_delay', 60),
        heartbeat_interval=config.get('heartbeat_interval', 30)
    )
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(client.shutdown())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    # Run client
    if args.once:
        logger.info("Running in single-connect mode (no auto-reconnect)")
        connected = await client.connect()
        if connected:
            logger.info("Connected successfully. Press Ctrl+C to exit.")
            # Keep running until interrupted
            while client.running and client.ws and not client.ws.closed:
                await asyncio.sleep(1)
        else:
            logger.error("Failed to connect")
            sys.exit(1)
    else:
        logger.info("Starting TunnelFlow client with auto-reconnect...")
        await client.run()
    
    await client.shutdown()


def main():
    """Main entry point"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
