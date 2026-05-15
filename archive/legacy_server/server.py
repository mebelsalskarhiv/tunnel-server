import asyncio
import json
import logging
import uuid
import secrets
import os
import sqlite3
import base64
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from aiohttp import web
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tunnel-server")

# База данных
Base = declarative_base()

class Client(Base):
    __tablename__ = 'clients'
    id = Column(String, primary_key=True)
    name = Column(String)
    token = Column(String)
    created_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    max_tunnels = Column(Integer, default=5)

class Tunnel(Base):
    __tablename__ = 'tunnels'
    id = Column(String, primary_key=True)
    subdomain = Column(String, unique=True, nullable=False)
    client_id = Column(String, nullable=False)
    local_port = Column(Integer, nullable=False)
    local_host = Column(String, default="localhost")
    protocol = Column(String, default="http")
    created_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

@dataclass
class ClientConfig:
    id: str
    name: str
    token: str
    created_at: datetime
    is_active: bool = True
    max_tunnels: int = 5
    subdomains: List[str] = None
    
    def __post_init__(self):
        if self.subdomains is None:
            self.subdomains = []

@dataclass
class TunnelConfig:
    id: str
    subdomain: str
    client_id: str
    local_port: int
    local_host: str
    protocol: str
    created_at: datetime
    is_active: bool = True

class DatabaseManager:
    def __init__(self, db_url: str = "sqlite:///data/tunnel.db"):
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.init_db()
    
    def init_db(self):
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            self.recreate_db()
    
    def recreate_db(self):
        try:
            Base.metadata.drop_all(self.engine)
            Base.metadata.create_all(self.engine)
            logger.info("Database recreated successfully")
        except Exception as e:
            logger.error(f"Error recreating database: {e}")
            raise
    
    def create_client(self, name: str, max_tunnels: int = 5) -> Optional[ClientConfig]:
        session = self.Session()
        try:
            client_id = str(uuid.uuid4())[:8]
            token = secrets.token_urlsafe(32)
            
            client = Client(
                id=client_id,
                name=name,
                token=token,
                created_at=datetime.now(),
                max_tunnels=max_tunnels
            )
            
            session.add(client)
            session.commit()
            
            return ClientConfig(
                id=client_id,
                name=name,
                token=token,
                created_at=client.created_at,
                max_tunnels=max_tunnels
            )
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating client: {e}")
            return None
        finally:
            session.close()
    
    def get_client(self, client_id: str) -> Optional[ClientConfig]:
        session = self.Session()
        try:
            client = session.query(Client).filter(Client.id == client_id).first()
            if client:
                tunnels = session.query(Tunnel).filter(Tunnel.client_id == client_id).all()
                subdomains = [tunnel.subdomain for tunnel in tunnels]
                
                return ClientConfig(
                    id=client.id,
                    name=client.name,
                    token=client.token,
                    created_at=client.created_at,
                    is_active=client.is_active,
                    max_tunnels=client.max_tunnels,
                    subdomains=subdomains
                )
            return None
        except Exception as e:
            logger.error(f"Error getting client: {e}")
            return None
        finally:
            session.close()
    
    def delete_client(self, client_id: str) -> bool:
        session = self.Session()
        try:
            client = session.query(Client).filter(Client.id == client_id).first()
            if client:
                session.query(Tunnel).filter(Tunnel.client_id == client_id).delete()
                session.delete(client)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting client: {e}")
            return False
        finally:
            session.close()
    
    def create_tunnel(self, client_id: str, subdomain: str, local_port: int, 
                     local_host: str = "localhost", protocol: str = "http") -> Optional[TunnelConfig]:
        session = self.Session()
        try:
            client = session.query(Client).filter(Client.id == client_id).first()
            if not client:
                logger.error(f"Client {client_id} not found")
                return None
            
            tunnels_count = session.query(Tunnel).filter(Tunnel.client_id == client_id).count()
            if tunnels_count >= client.max_tunnels:
                logger.error(f"Client {client_id} has reached tunnel limit ({client.max_tunnels})")
                return None
            
            existing_tunnel = session.query(Tunnel).filter(Tunnel.subdomain == subdomain).first()
            if existing_tunnel:
                logger.error(f"Subdomain {subdomain} already taken")
                return None
            
            tunnel_id = str(uuid.uuid4())[:8]
            tunnel = Tunnel(
                id=tunnel_id,
                subdomain=subdomain,
                client_id=client_id,
                local_port=local_port,
                local_host=local_host,
                protocol=protocol,
                created_at=datetime.now()
            )
            
            session.add(tunnel)
            session.commit()
            
            return TunnelConfig(
                id=tunnel_id,
                subdomain=subdomain,
                client_id=client_id,
                local_port=local_port,
                local_host=local_host,
                protocol=protocol,
                created_at=tunnel.created_at
            )
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating tunnel: {e}")
            return None
        finally:
            session.close()
    
    def get_all_clients(self) -> List[ClientConfig]:
        session = self.Session()
        try:
            clients = session.query(Client).all()
            result = []
            for client in clients:
                tunnels = session.query(Tunnel).filter(Tunnel.client_id == client.id).all()
                subdomains = [tunnel.subdomain for tunnel in tunnels]
                
                result.append(ClientConfig(
                    id=client.id,
                    name=client.name,
                    token=client.token,
                    created_at=client.created_at,
                    is_active=client.is_active,
                    max_tunnels=client.max_tunnels,
                    subdomains=subdomains
                ))
            return result
        except Exception as e:
            logger.error(f"Error getting all clients: {e}")
            return []
        finally:
            session.close()
    
    def get_all_tunnels(self) -> List[TunnelConfig]:
        session = self.Session()
        try:
            tunnels = session.query(Tunnel).all()
            result = []
            for tunnel in tunnels:
                result.append(TunnelConfig(
                    id=tunnel.id,
                    subdomain=tunnel.subdomain,
                    client_id=tunnel.client_id,
                    local_port=tunnel.local_port,
                    local_host=tunnel.local_host,
                    protocol=tunnel.protocol,
                    created_at=tunnel.created_at,
                    is_active=tunnel.is_active
                ))
            return result
        except Exception as e:
            logger.error(f"Error getting all tunnels: {e}")
            return []
        finally:
            session.close()
    
    def delete_tunnel(self, tunnel_id: str) -> bool:
        session = self.Session()
        try:
            tunnel = session.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
            if tunnel:
                session.delete(tunnel)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting tunnel: {e}")
            return False
        finally:
            session.close()

class TraefikConfigManager:
    """Управление динамическими конфигурациями Traefik для туннелей"""
    def __init__(self, config_dir: str = "/app/traefik-configs", domain: str = "localhost"):
        self.config_dir = Path(config_dir)
        self.domain = domain
        self.config_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"TraefikConfigManager initialized with config_dir={config_dir}, domain={domain}")
    
    def create_tunnel_config(self, subdomain: str, enable_ssl: bool = True) -> bool:
        """Создание конфигурации Traefik для туннеля"""
        try:
            full_domain = f"{subdomain}.{self.domain}"
            config_file = self.config_dir / f"tunnel-{subdomain}.yml"
            
            # Service для проксирования на tunnel-server
            service = {
                "loadBalancer": {
                    "servers": [
                        {
                            "url": "http://tunnel-server:8081"
                        }
                    ]
                }
            }
            
            # HTTP router (для редиректа на HTTPS)
            http_router = {
                "rule": f"Host(`{full_domain}`)",
                "entryPoints": ["web"],
                "service": f"tunnel-{subdomain}",
                "middlewares": [f"redirect-to-https-{subdomain}"]
            }
            
            # HTTPS router с SSL
            https_router = None
            if enable_ssl:
                https_router = {
                    "rule": f"Host(`{full_domain}`)",
                    "entryPoints": ["websecure"],
                    "service": f"tunnel-{subdomain}",
                    "tls": {
                        "certResolver": "letsencrypt"
                    }
                }
            
            # Middleware для редиректа
            redirect_middleware = {
                "redirectScheme": {
                    "scheme": "https",
                    "permanent": True
                }
            }
            
            # Убеждаемся, что service указан в HTTP router
            if "service" not in http_router:
                http_router["service"] = f"tunnel-{subdomain}"
            
            config = {
                "http": {
                    "routers": {
                        f"tunnel-{subdomain}-http": http_router
                    },
                    "services": {
                        f"tunnel-{subdomain}": service
                    },
                    "middlewares": {
                        f"redirect-to-https-{subdomain}": redirect_middleware
                    }
                }
            }
            
            # Добавляем HTTPS router только если SSL включен
            if https_router:
                config["http"]["routers"][f"tunnel-{subdomain}-https"] = https_router
            else:
                # Для localhost просто используем HTTP без редиректа
                config["http"]["routers"][f"tunnel-{subdomain}-http"]["middlewares"] = []
            
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Created Traefik config for tunnel {subdomain} -> {full_domain}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating Traefik config for {subdomain}: {e}")
            return False
    
    def delete_tunnel_config(self, subdomain: str) -> bool:
        """Удаление конфигурации Traefik для туннеля"""
        try:
            config_file = self.config_dir / f"tunnel-{subdomain}.yml"
            if config_file.exists():
                config_file.unlink()
                logger.info(f"Deleted Traefik config for tunnel {subdomain}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting Traefik config for {subdomain}: {e}")
            return False
    
    def reload_all_tunnels(self, tunnels: List[TunnelConfig], enable_ssl: bool = False):
        """Перезагрузка всех конфигураций туннелей"""
        try:
            # Удаляем все существующие конфигурации туннелей
            for config_file in self.config_dir.glob("tunnel-*.yml"):
                config_file.unlink()
            
            # Создаем новые конфигурации
            for tunnel in tunnels:
                if tunnel.is_active:
                    self.create_tunnel_config(tunnel.subdomain, enable_ssl)
            
            logger.info(f"Reloaded {len(tunnels)} tunnel configurations")
        except Exception as e:
            logger.error(f"Error reloading tunnel configurations: {e}")

class TunnelConnection:
    """Класс для управления одним туннельным соединением"""
    def __init__(self, connection_id: str, client_id: str, tunnel_id: str, 
                 user_reader: asyncio.StreamReader, user_writer: asyncio.StreamWriter):
        self.connection_id = connection_id
        self.client_id = client_id
        self.tunnel_id = tunnel_id
        self.user_reader = user_reader
        self.user_writer = user_writer
        self.local_reader: Optional[asyncio.StreamReader] = None
        self.local_writer: Optional[asyncio.StreamWriter] = None
        self.is_active = True
        
    async def connect_to_local(self, local_host: str, local_port: int) -> bool:
        """Подключение к локальному сервису"""
        try:
            self.local_reader, self.local_writer = await asyncio.open_connection(
                local_host, local_port
            )
            logger.info(f"Connected to local service {local_host}:{local_port} for connection {self.connection_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to local service {local_host}:{local_port}: {e}")
            return False
    
    async def forward_data(self, data: bytes):
        """Пересылка данных от пользователя к локальному сервису"""
        if self.local_writer and not self.local_writer.is_closing():
            try:
                self.local_writer.write(data)
                await self.local_writer.drain()
            except Exception as e:
                logger.error(f"Error forwarding data to local service: {e}")
                await self.close()
    
    async def receive_from_local(self):
        """Получение данных от локального сервиса и пересылка пользователю"""
        try:
            while self.is_active and self.local_reader and not self.user_writer.is_closing():
                data = await self.local_reader.read(4096)
                if not data:
                    break
                
                if self.user_writer and not self.user_writer.is_closing():
                    self.user_writer.write(data)
                    await self.user_writer.drain()
        except Exception as e:
            logger.error(f"Error receiving from local service: {e}")
        finally:
            await self.close()
    
    async def close(self):
        """Закрытие соединения"""
        self.is_active = False
        
        if self.local_writer and not self.local_writer.is_closing():
            self.local_writer.close()
            await self.local_writer.wait_closed()
        
        if self.user_writer and not self.user_writer.is_closing():
            self.user_writer.close()
            await self.user_writer.wait_closed()
        
        logger.info(f"Connection {self.connection_id} closed")

class TunnelManager:
    def __init__(self, db_url: str = "sqlite:///data/tunnel.db", traefik_config_dir: str = "/app/traefik-configs", domain: str = "localhost"):
        self.db = DatabaseManager(db_url)
        self.traefik = TraefikConfigManager(traefik_config_dir, domain)
        self.connected_clients: Dict[str, asyncio.StreamWriter] = {}  # client_id -> writer
        self.connected_clients_readers: Dict[str, asyncio.StreamReader] = {}  # client_id -> reader
        self.tunnel_configs: Dict[str, TunnelConfig] = {}
        self.tunnel_connections: Dict[str, TunnelConnection] = {}  # connection_id -> TunnelConnection
        self.pending_requests: Dict[str, asyncio.Future] = {}  # connection_id -> Future для ожидания ответа
        
        self.load_tunnels_from_db()
    
    def load_tunnels_from_db(self):
        try:
            tunnels = self.db.get_all_tunnels()
            for tunnel in tunnels:
                self.tunnel_configs[tunnel.subdomain] = tunnel
            # Перезагружаем все конфигурации Traefik
            # SSL включается только для реальных доменов (не localhost)
            enable_ssl = os.getenv('ENABLE_SSL', 'false').lower() == 'true' or self.traefik.domain != 'localhost'
            self.traefik.reload_all_tunnels(tunnels, enable_ssl)
            logger.info(f"Loaded {len(tunnels)} tunnels from database")
        except Exception as e:
            logger.error(f"Error loading tunnels from database: {e}")
    
    def register_client(self, client_id: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Регистрация подключенного клиента"""
        self.connected_clients[client_id] = writer
        self.connected_clients_readers[client_id] = reader
        logger.info(f"Client {client_id} registered")
    
    def unregister_client(self, client_id: str):
        """Отключение клиента"""
        if client_id in self.connected_clients:
            del self.connected_clients[client_id]
        if client_id in self.connected_clients_readers:
            del self.connected_clients_readers[client_id]
            
            # Закрываем все соединения клиента
            for connection_id, conn in list(self.tunnel_connections.items()):
                if conn.client_id == client_id:
                    asyncio.create_task(conn.close())
                    del self.tunnel_connections[connection_id]
            
            # Отменяем все ожидающие запросы
            for connection_id, future in list(self.pending_requests.items()):
                if connection_id.startswith(client_id):
                    if not future.done():
                        future.cancel()
                    del self.pending_requests[connection_id]
            
            logger.info(f"Client {client_id} unregistered")
    
    def is_client_connected(self, client_id: str) -> bool:
        return client_id in self.connected_clients
    
    async def create_tunnel_connection(self, connection_id: str, client_id: str, 
                                     tunnel_id: str, user_reader: asyncio.StreamReader, 
                                     user_writer: asyncio.StreamWriter) -> bool:
        """Создание нового туннельного соединения"""
        # Находим конфигурацию туннеля
        tunnel_config = None
        for tunnel in self.tunnel_configs.values():
            if tunnel.id == tunnel_id and tunnel.client_id == client_id:
                tunnel_config = tunnel
                break
        
        if not tunnel_config:
            logger.error(f"Tunnel {tunnel_id} not found for client {client_id}")
            return False
        
        # Создаем соединение (не подключаемся к localhost, так как клиент за NAT)
        connection = TunnelConnection(
            connection_id, client_id, tunnel_id, user_reader, user_writer
        )
        
        self.tunnel_connections[connection_id] = connection
        return True
    
    def get_tunnel_by_subdomain(self, subdomain: str) -> Optional[TunnelConfig]:
        return self.tunnel_configs.get(subdomain)
    
    async def send_to_client(self, client_id: str, message: dict):
        """Отправка сообщения клиенту"""
        if client_id in self.connected_clients:
            writer = self.connected_clients[client_id]
            try:
                data = json.dumps(message).encode() + b'\n'
                writer.write(data)
                await writer.drain()
            except Exception as e:
                logger.error(f"Error sending message to client {client_id}: {e}")
                self.unregister_client(client_id)
    
    async def send_http_request_to_client(self, connection_id: str, client_id: str, 
                                         tunnel_id: str, http_data: bytes) -> Optional[bytes]:
        """Отправка HTTP запроса клиенту через control соединение и получение ответа"""
        if client_id not in self.connected_clients:
            logger.error(f"Client {client_id} is not connected")
            return None
        
        writer = self.connected_clients[client_id]
        reader = self.connected_clients_readers[client_id]
        
        # Создаем Future для ожидания ответа
        future = asyncio.Future()
        self.pending_requests[connection_id] = future
        
        try:
            # Отправляем запрос клиенту
            request_message = {
                'action': 'proxy_request',
                'connection_id': connection_id,
                'tunnel_id': tunnel_id,
                'data': base64.b64encode(http_data).decode('utf-8')
            }
            
            message_data = json.dumps(request_message).encode() + b'\n'
            writer.write(message_data)
            await writer.drain()
            
            logger.debug(f"Sent HTTP request to client {client_id} for connection {connection_id}")
            
            # Ждем ответ (с таймаутом 30 секунд)
            try:
                response_data = await asyncio.wait_for(future, timeout=30.0)
                logger.debug(f"Received {len(response_data)} bytes response from client {client_id} for connection {connection_id}")
                return response_data
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response from client {client_id} for connection {connection_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending HTTP request to client {client_id}: {e}")
            return None
        finally:
            if connection_id in self.pending_requests:
                del self.pending_requests[connection_id]
    
    async def handle_client_response(self, connection_id: str, response_data: bytes):
        """Обработка ответа от клиента"""
        if connection_id in self.pending_requests:
            future = self.pending_requests[connection_id]
            if not future.done():
                future.set_result(response_data)

# Утилиты для работы с шаблонами
def render_template(template_name, **context):
    """Простой рендеринг HTML шаблонов"""
    template_path = os.path.join('templates', template_name)
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Простая замена переменных
        for key, value in context.items():
            content = content.replace(f'{{{{ {key} }}}}', str(value))
        
        return content
    else:
        logger.error(f"Template not found: {template_path}")
        return f"<h1>Error: Template {template_name} not found</h1>"

class TunnelServer:
    def __init__(self, host='0.0.0.0', control_port=8080, proxy_port=8081, 
                 web_port=8082, domain="tunnel.example.com", db_url="sqlite:///data/tunnel.db"):
        self.host = host
        self.control_port = control_port
        self.proxy_port = proxy_port
        self.web_port = web_port
        self.domain = domain
        
        traefik_config_dir = os.getenv('TRAEFIK_DYNAMIC_CONFIG_DIR', '/app/traefik-configs')
        self.manager = TunnelManager(db_url, traefik_config_dir, domain)
        self.stats = {
            'connections_total': 0,
            'bytes_transferred': 0,
            'active_connections': 0,
            'clients_connected': 0
        }
        
        self.web_app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Настройка маршрутов"""
        # Основные страницы
        self.web_app.router.add_get('/', self.handle_index)
        self.web_app.router.add_get('/clients', self.handle_clients)
        self.web_app.router.add_get('/tunnels', self.handle_tunnels)
        
        # API endpoints
        self.web_app.router.add_get('/api/stats', self.handle_api_stats)
        self.web_app.router.add_get('/api/clients', self.handle_api_clients)
        self.web_app.router.add_post('/api/clients', self.handle_api_create_client)
        self.web_app.router.add_delete('/api/clients/{client_id}', self.handle_api_delete_client)
        self.web_app.router.add_get('/api/clients/{client_id}/config', self.handle_api_client_config)
        self.web_app.router.add_get('/api/tunnels', self.handle_api_tunnels)
        self.web_app.router.add_post('/api/tunnels', self.handle_api_create_tunnel)
        self.web_app.router.add_delete('/api/tunnels/{tunnel_id}', self.handle_api_delete_tunnel)
        
        # Статические файлы
        static_dir = 'static'
        if not os.path.exists(static_dir):
            os.makedirs(static_dir, exist_ok=True)
        
        self.web_app.router.add_static('/static', static_dir)
    
    # Основные страницы
    async def handle_index(self, request):
        html = render_template('index.html', domain=self.domain)
        return web.Response(text=html, content_type='text/html')
    
    async def handle_clients(self, request):
        html = render_template('clients.html', domain=self.domain)
        return web.Response(text=html, content_type='text/html')
    
    async def handle_tunnels(self, request):
        html = render_template('tunnels.html', domain=self.domain)
        return web.Response(text=html, content_type='text/html')
    
    # API endpoints
    async def handle_api_stats(self, request):
        try:
            stats = {
                'clients_total': len(self.manager.db.get_all_clients()),
                'clients_connected': len(self.manager.connected_clients),
                'active_tunnels': len([t for t in self.manager.tunnel_configs.values() 
                                     if self.manager.is_client_connected(t.client_id)]),
                'total_tunnels': len(self.manager.tunnel_configs),
                'active_connections': len(self.manager.tunnel_connections),
                'connections_total': self.stats['connections_total'],
                'bytes_transferred': self.stats['bytes_transferred']
            }
            return web.json_response(stats)
        except Exception as e:
            logger.error(f"Error in stats API: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def handle_api_clients(self, request):
        try:
            clients = self.manager.db.get_all_clients()
            clients_data = []
            
            for client in clients:
                is_connected = self.manager.is_client_connected(client.id)
                clients_data.append({
                    'id': client.id,
                    'name': client.name,
                    'created_at': client.created_at.isoformat(),
                    'is_connected': is_connected,
                    'tunnel_count': len(client.subdomains),
                    'max_tunnels': client.max_tunnels
                })
            
            return web.json_response(clients_data)
        except Exception as e:
            logger.error(f"Error in clients API: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def handle_api_create_client(self, request):
        try:
            data = await request.json()
            name = data.get('name', 'Unnamed Client')
            max_tunnels = int(data.get('max_tunnels', 5))
            
            client = self.manager.db.create_client(name, max_tunnels)
            if client:
                client_data = {
                    'id': client.id,
                    'name': client.name,
                    'token': client.token,
                    'created_at': client.created_at.isoformat(),
                    'max_tunnels': client.max_tunnels
                }
                return web.json_response({'status': 'success', 'client': client_data})
            else:
                return web.json_response({'status': 'error', 'message': 'Failed to create client'}, status=400)
                
        except Exception as e:
            logger.error(f"Error creating client: {e}")
            return web.json_response({'status': 'error', 'message': str(e)}, status=400)
    
    async def handle_api_delete_client(self, request):
        try:
            client_id = request.match_info['client_id']
            success = self.manager.db.delete_client(client_id)
            
            if success:
                return web.json_response({'status': 'success'})
            else:
                return web.json_response({'status': 'error', 'message': 'Client not found'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting client: {e}")
            return web.json_response({'status': 'error', 'message': str(e)}, status=500)
    
    async def handle_api_client_config(self, request):
        try:
            client_id = request.match_info['client_id']
            client = self.manager.db.get_client(client_id)
            
            if not client:
                return web.json_response({'error': 'Client not found'}, status=404)
            
            tunnels = [tunnel for tunnel in self.manager.db.get_all_tunnels() if tunnel.client_id == client_id]
            
            config = {
                'server': {
                    'host': os.getenv('TUNNEL_DOMAIN', 'your-domain.com'),
                    'control_port': 2222,
                    'proxy_port': 2223,
                    'domain': self.domain
                },
                'client': {
                    'id': client.id,
                    'name': client.name,
                    'token': client.token
                },
                'tunnels': [
                    {
                        'subdomain': tunnel.subdomain,
                        'local_port': tunnel.local_port,
                        'local_host': tunnel.local_host,
                        'protocol': tunnel.protocol
                    } for tunnel in tunnels
                ]
            }
            
            return web.json_response(config)
        except Exception as e:
            logger.error(f"Error getting client config: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def handle_api_tunnels(self, request):
        try:
            tunnels = self.manager.db.get_all_tunnels()
            clients = {client.id: client for client in self.manager.db.get_all_clients()}
            
            tunnels_data = []
            for tunnel in tunnels:
                client = clients.get(tunnel.client_id)
                tunnels_data.append({
                    'id': tunnel.id,
                    'subdomain': tunnel.subdomain,
                    'client_id': tunnel.client_id,
                    'client_name': client.name if client else 'Unknown',
                    'local_host': tunnel.local_host,
                    'local_port': tunnel.local_port,
                    'protocol': tunnel.protocol,
                    'created_at': tunnel.created_at.isoformat(),
                    'is_active': tunnel.is_active and self.manager.is_client_connected(tunnel.client_id),
                    'public_url': f"{tunnel.subdomain}.{self.domain}"
                })
            
            return web.json_response(tunnels_data)
        except Exception as e:
            logger.error(f"Error in tunnels API: {e}")
            return web.json_response({'error': 'Internal server error'}, status=500)
    
    async def handle_api_create_tunnel(self, request):
        try:
            data = await request.json()
            client_id = data.get('client_id')
            subdomain = data.get('subdomain')
            local_port = int(data.get('local_port'))
            local_host = data.get('local_host', 'localhost')
            protocol = data.get('protocol', 'http')
            
            tunnel = self.manager.db.create_tunnel(client_id, subdomain, local_port, local_host, protocol)
            
            if tunnel:
                # Обновляем конфигурации туннелей
                self.manager.tunnel_configs[subdomain] = tunnel
                
                # Создаем конфигурацию Traefik для нового туннеля
                # SSL включается только для реальных доменов (не localhost)
                enable_ssl = os.getenv('ENABLE_SSL', 'false').lower() == 'true' or self.domain != 'localhost'
                self.manager.traefik.create_tunnel_config(subdomain, enable_ssl)
                
                tunnel_data = {
                    'id': tunnel.id,
                    'subdomain': tunnel.subdomain,
                    'client_id': tunnel.client_id,
                    'local_port': tunnel.local_port,
                    'local_host': tunnel.local_host,
                    'protocol': tunnel.protocol,
                    'created_at': tunnel.created_at.isoformat()
                }
                return web.json_response({'status': 'success', 'tunnel': tunnel_data})
            else:
                return web.json_response({
                    'status': 'error',
                    'message': 'Failed to create tunnel. Check client existence and subdomain availability.'
                }, status=400)
        except Exception as e:
            logger.error(f"Error creating tunnel: {e}")
            return web.json_response({'status': 'error', 'message': str(e)}, status=400)
    
    async def handle_api_delete_tunnel(self, request):
        try:
            tunnel_id = request.match_info['tunnel_id']
            
            # Находим туннель перед удалением, чтобы получить subdomain
            tunnel_to_delete = None
            for subdomain, tunnel in self.manager.tunnel_configs.items():
                if tunnel.id == tunnel_id:
                    tunnel_to_delete = (subdomain, tunnel)
                    break
            
            success = self.manager.db.delete_tunnel(tunnel_id)
            
            if success:
                # Удаляем из конфигураций
                if tunnel_to_delete:
                    subdomain, tunnel = tunnel_to_delete
                    del self.manager.tunnel_configs[subdomain]
                    # Удаляем конфигурацию Traefik
                    self.manager.traefik.delete_tunnel_config(subdomain)
                
                return web.json_response({'status': 'success'})
            else:
                return web.json_response({'status': 'error', 'message': 'Tunnel not found'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting tunnel: {e}")
            return web.json_response({'status': 'error', 'message': str(e)}, status=500)
    
    # Control сервер - для подключения клиентов
    async def handle_control_connection(self, reader, writer):
        """Обработка control соединений от клиентов"""
        client_id = None
        try:
            # Первое сообщение должно быть аутентификацией
            data = await reader.read(1024)
            if not data:
                return
            
            try:
                auth_message = json.loads(data.decode())
            except json.JSONDecodeError:
                logger.error("Invalid authentication message")
                return
            
            if auth_message.get('action') != 'authenticate':
                logger.error("First message must be authentication")
                return
            
            client_id = auth_message.get('client_id')
            token = auth_message.get('token')
            
            # Проверяем аутентификацию
            client = self.manager.db.get_client(client_id)
            if not client or client.token != token:
                response = {'status': 'error', 'message': 'Authentication failed'}
                writer.write(json.dumps(response).encode())
                await writer.drain()
                return
            
            # Регистрируем клиента
            self.manager.register_client(client_id, reader, writer)
            self.stats['clients_connected'] = len(self.manager.connected_clients)
            
            # Отправляем подтверждение
            response = {
                'status': 'authenticated',
                'message': 'Authentication successful'
            }
            writer.write(json.dumps(response).encode() + b'\n')
            await writer.drain()
            
            logger.info(f"Client {client_id} authenticated successfully")
            
            # Ожидаем сообщения от клиента
            buffer = b''
            while True:
                try:
                    # Читаем данные по частям
                    chunk = await reader.read(8192)
                    if not chunk:
                        break
                    
                    buffer += chunk
                    
                    # Обрабатываем все полные сообщения (заканчивающиеся на \n)
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        if not line:
                            continue
                        
                        try:
                            message = json.loads(line.decode('utf-8'))
                            action = message.get('action')
                            
                            if action == 'ping':
                                # Отправляем pong
                                pong_response = {'action': 'pong'}
                                writer.write(json.dumps(pong_response).encode() + b'\n')
                                await writer.drain()
                            elif action == 'proxy_response':
                                # Обрабатываем ответ от клиента
                                connection_id = message.get('connection_id')
                                response_data = base64.b64decode(message.get('data', ''))
                                await self.manager.handle_client_response(connection_id, response_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON from client {client_id}: {e}, line: {line[:100]}")
                            continue
                        except Exception as e:
                            logger.error(f"Error handling message from client {client_id}: {e}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Error reading from client {client_id}: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Control connection error: {e}")
        finally:
            if client_id:
                self.manager.unregister_client(client_id)
                self.stats['clients_connected'] = len(self.manager.connected_clients)
            writer.close()
            await writer.wait_closed()
    
    # Proxy сервер - для входящего пользовательского трафика
    async def handle_proxy_connection(self, reader, writer):
        """Обработка proxy соединений (пользовательский трафик)"""
        connection_id = str(uuid.uuid4())
        try:
            # Получаем первый пакет данных для анализа
            data = await reader.read(4096)
            if not data:
                return
            
            # Пытаемся извлечь Host header для определения поддомена
            host = self.extract_host_from_http(data)
            if not host:
                logger.error("Could not extract host from request")
                return
            
            # Извлекаем поддомен
            subdomain = self.extract_subdomain(host)
            if not subdomain:
                logger.error(f"Could not extract subdomain from host: {host}")
                return
            
            # Находим туннель по поддомену
            tunnel_config = self.manager.get_tunnel_by_subdomain(subdomain)
            if not tunnel_config:
                logger.error(f"No tunnel found for subdomain: {subdomain}")
                return
            
            # Проверяем, подключен ли клиент
            if not self.manager.is_client_connected(tunnel_config.client_id):
                logger.error(f"Client {tunnel_config.client_id} is not connected")
                return
            
            # Создаем туннельное соединение
            success = await self.manager.create_tunnel_connection(
                connection_id, tunnel_config.client_id, tunnel_config.id, reader, writer
            )
            
            if success:
                self.stats['connections_total'] += 1
                self.stats['active_connections'] = len(self.manager.tunnel_connections)
                
                logger.info(f"Tunnel connection established: {connection_id} for {subdomain}")
                
                # Читаем весь HTTP запрос
                http_request = data
                try:
                    # Парсим заголовки для определения Content-Length
                    request_text = data.decode('utf-8', errors='ignore')
                    headers_end = request_text.find('\r\n\r\n')
                    if headers_end != -1:
                        headers_text = request_text[:headers_end]
                        content_length = 0
                        for line in headers_text.split('\r\n'):
                            if line.lower().startswith('content-length:'):
                                try:
                                    content_length = int(line.split(':', 1)[1].strip())
                                except:
                                    pass
                        
                        # Если есть body, читаем его
                        body_start = headers_end + 4
                        body_received = len(data) - body_start
                        if body_received < content_length:
                            remaining = content_length - body_received
                            while remaining > 0:
                                chunk = await asyncio.wait_for(reader.read(min(remaining, 4096)), timeout=5.0)
                                if not chunk:
                                    break
                                http_request += chunk
                                remaining -= len(chunk)
                    else:
                        # Если нет полных заголовков, читаем еще немного
                        try:
                            more_data = await asyncio.wait_for(reader.read(4096), timeout=0.5)
                            if more_data:
                                http_request += more_data
                        except asyncio.TimeoutError:
                            pass
                except Exception as e:
                    logger.error(f"Error reading HTTP request: {e}")
                
                # Отправляем запрос клиенту через control соединение
                response_data = await self.manager.send_http_request_to_client(
                    connection_id, tunnel_config.client_id, tunnel_config.id, http_request
                )
                
                if response_data:
                    # Отправляем ответ пользователю
                    logger.info(f"Sending {len(response_data)} bytes response for {subdomain}")
                    writer.write(response_data)
                    await writer.drain()
                    self.stats['bytes_transferred'] += len(response_data)
                    logger.info(f"Sent {len(response_data)} bytes response for {subdomain}")
                else:
                    logger.error(f"Failed to get response from client for {subdomain}")
                    error_response = b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 11\r\nConnection: close\r\n\r\nBad Gateway"
                    writer.write(error_response)
                    await writer.drain()
            else:
                logger.error(f"Failed to create tunnel connection for {subdomain}")
                error_response = b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 11\r\n\r\nBad Gateway"
                writer.write(error_response)
                await writer.drain()
            
            # НЕ закрываем writer сразу - Traefik сам закроет соединение после чтения ответа
            # Закрываем только если соединение уже закрыто с другой стороны
            try:
                # Даем время Traefik прочитать ответ
                await asyncio.sleep(0.1)
                if writer.is_closing():
                    await writer.wait_closed()
                else:
                    # Закрываем writer только если он еще открыт
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
            except Exception as e:
                logger.debug(f"Error closing writer: {e}")
                
        except Exception as e:
            logger.error(f"Proxy connection error: {e}")
            try:
                if not writer.is_closing():
                    error_response = b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 21\r\n\r\nInternal Server Error"
                    writer.write(error_response)
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
            except:
                pass
        finally:
            if connection_id in self.manager.tunnel_connections:
                await self.manager.tunnel_connections[connection_id].close()
                del self.manager.tunnel_connections[connection_id]
                self.stats['active_connections'] = len(self.manager.tunnel_connections)
    
    def extract_host_from_http(self, data: bytes) -> Optional[str]:
        """Извлечение Host header из HTTP запроса"""
        try:
            headers = data.decode().split('\r\n')
            for header in headers:
                if header.lower().startswith('host:'):
                    return header.split(':', 1)[1].strip()
        except:
            pass
        return None
    
    def extract_subdomain(self, host: str) -> Optional[str]:
        """Извлечение поддомена из полного доменного имени"""
        if self.domain in host:
            return host.replace(f'.{self.domain}', '')
        return host
    
    async def start_control_server(self):
        server = await asyncio.start_server(
            self.handle_control_connection, 
            self.host, 
            self.control_port
        )
        logger.info(f"Control server started on {self.host}:{self.control_port}")
        return server
    
    async def start_proxy_server(self):
        server = await asyncio.start_server(
            self.handle_proxy_connection,
            self.host,
            self.proxy_port
        )
        logger.info(f"Proxy server started on {self.host}:{self.proxy_port}")
        return server
    
    async def start_web_server(self):
        runner = web.AppRunner(self.web_app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.web_port)
        await site.start()
        logger.info(f"Web server started on {self.host}:{self.web_port}")
        return runner
    
    async def start(self):
        """Запуск всех серверов"""
        logger.info(f"Starting Tunnel Server...")
        logger.info(f"Web interface: http://{self.host}:{self.web_port}")
        logger.info(f"Control port: {self.control_port}")
        logger.info(f"Proxy port: {self.proxy_port}")
        logger.info(f"Domain: {self.domain}")
        
        # Создаем необходимые директории
        os.makedirs('templates', exist_ok=True)
        os.makedirs('static/css', exist_ok=True)
        os.makedirs('static/js', exist_ok=True)
        os.makedirs('static/images', exist_ok=True)
        
        # Запускаем серверы
        control_server = await self.start_control_server()
        proxy_server = await self.start_proxy_server()
        web_runner = await self.start_web_server()
        
        logger.info("All servers started successfully")
        
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Shutting down servers...")
        finally:
            control_server.close()
            proxy_server.close()
            await control_server.wait_closed()
            await proxy_server.wait_closed()
            await web_runner.cleanup()

if __name__ == "__main__":
    host = os.getenv('TUNNEL_HOST', '0.0.0.0')
    control_port = int(os.getenv('TUNNEL_CONTROL_PORT', 8080))
    proxy_port = int(os.getenv('TUNNEL_PROXY_PORT', 8081))
    web_port = int(os.getenv('TUNNEL_WEB_PORT', 8082))
    domain = os.getenv('TUNNEL_DOMAIN', 'tunnel.example.com')
    db_url = os.getenv('DATABASE_URL', 'sqlite:///data/tunnel.db')
    
    server = TunnelServer(
        host=host,
        control_port=control_port,
        proxy_port=proxy_port,
        web_port=web_port,
        domain=domain,
        db_url=db_url
    )
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")