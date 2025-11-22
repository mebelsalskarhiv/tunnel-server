#!/usr/bin/env python3
import asyncio
import json
import logging
import sys
import signal
import time
import base64
from pathlib import Path
from typing import Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tunnel-client")

class TunnelClient:
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.is_running = True
        self.control_reader: Optional[asyncio.StreamReader] = None
        self.control_writer: Optional[asyncio.StreamWriter] = None
        
    def load_config(self, config_path: str) -> dict:
        """Загрузка конфигурации из файла"""
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        logger.info(f"Loaded configuration from {config_path}")
        return config
    
    async def connect_to_server(self) -> bool:
        """Подключение к серверу туннелей"""
        server_config = self.config['server']
        client_config = self.config['client']
        
        try:
            self.control_reader, self.control_writer = await asyncio.open_connection(
                server_config['host'], server_config['control_port']
            )
            
            # Аутентификация
            auth_message = {
                'action': 'authenticate',
                'client_id': client_config['id'],
                'token': client_config['token']
            }
            
            self.control_writer.write(json.dumps(auth_message).encode())
            await self.control_writer.drain()
            
            # Чтение ответа
            data = await self.control_reader.read(1024)
            response = json.loads(data.decode())
            
            if response.get('status') == 'authenticated':
                logger.info("Successfully authenticated with tunnel server")
                return True
            else:
                logger.error(f"Authentication failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
    
    async def send_heartbeat(self):
        """Отправка heartbeat сообщений для поддержания соединения"""
        while self.is_running and self.control_writer:
            try:
                ping_message = {'action': 'ping'}
                self.control_writer.write(json.dumps(ping_message).encode() + b'\n')
                await self.control_writer.drain()
                await asyncio.sleep(30)  # Каждые 30 секунд
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break
    
    async def handle_server_messages(self):
        """Обработка сообщений от сервера"""
        buffer = b''
        while self.is_running and self.control_reader:
            try:
                # Читаем данные по частям
                chunk = await self.control_reader.read(8192)
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
                        
                        if action == 'pong':
                            logger.debug("Received pong from server")
                        elif action == 'proxy_request':
                            # Обрабатываем запрос на проксирование
                            asyncio.create_task(self.handle_proxy_request(message))
                        # Здесь можно добавить обработку других сообщений от сервера
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON from server: {e}, line: {line[:100]}")
                        continue
                    except Exception as e:
                        logger.error(f"Error handling server message: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error reading from server: {e}")
                break
    
    async def handle_proxy_request(self, message: dict):
        """Обработка запроса на проксирование от сервера"""
        connection_id = message.get('connection_id')
        tunnel_id = message.get('tunnel_id')
        http_data = base64.b64decode(message.get('data', ''))
        
        # Находим туннель в конфигурации
        tunnel_config = None
        for tunnel in self.config.get('tunnels', []):
            # Нужно найти туннель по tunnel_id, но в конфиге его нет
            # Используем первый туннель или ищем по другим параметрам
            tunnel_config = tunnel
            break
        
        if not tunnel_config:
            logger.error(f"No tunnel configuration found for tunnel_id {tunnel_id}")
            return
        
        local_host = tunnel_config.get('local_host', 'localhost')
        local_port = tunnel_config.get('local_port')
        
        try:
            # Подключаемся к локальному сервису
            local_reader, local_writer = await asyncio.open_connection(
                local_host, local_port
            )
            
            # Отправляем HTTP запрос на локальный сервис
            local_writer.write(http_data)
            await local_writer.drain()
            
            # Читаем ответ от локального сервиса
            response_data = b''
            try:
                # Читаем заголовки (минимум до \r\n\r\n)
                header_data = b''
                max_header_size = 65536
                timeout = 10.0
                
                # Читаем до получения полных заголовков
                while b'\r\n\r\n' not in header_data and len(header_data) < max_header_size:
                    try:
                        chunk = await asyncio.wait_for(local_reader.read(4096), timeout=timeout)
                        if not chunk:
                            break
                        header_data += chunk
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout reading headers from {local_host}:{local_port}")
                        break
                
                if b'\r\n\r\n' not in header_data:
                    logger.error(f"Incomplete headers from {local_host}:{local_port}")
                    response_data = header_data
                else:
                    headers_end = header_data.find(b'\r\n\r\n')
                    response_data = header_data[:headers_end + 4]
                    headers_text = header_data[:headers_end].decode('utf-8', errors='ignore')
                    
                    # Парсим заголовки
                    content_length = 0
                    transfer_encoding = None
                    connection_close = False
                    
                    for line in headers_text.split('\r\n'):
                        line_lower = line.lower()
                        if line_lower.startswith('content-length:'):
                            try:
                                content_length = int(line.split(':', 1)[1].strip())
                            except:
                                pass
                        elif line_lower.startswith('transfer-encoding:'):
                            transfer_encoding = line.split(':', 1)[1].strip().lower()
                        elif line_lower.startswith('connection:'):
                            if 'close' in line_lower:
                                connection_close = True
                    
                    # Читаем body
                    body_received = len(header_data) - (headers_end + 4)
                    
                    if transfer_encoding == 'chunked':
                        # Читаем chunked encoding
                        chunk_buffer = header_data[headers_end + 4:]
                        max_size = 10 * 1024 * 1024  # 10MB максимум
                        
                        while len(chunk_buffer) < max_size:
                            try:
                                # Проверяем, закончился ли последний chunk
                                if chunk_buffer.endswith(b'0\r\n\r\n'):
                                    response_data = header_data[:headers_end + 4] + chunk_buffer
                                    break
                                
                                chunk = await asyncio.wait_for(local_reader.read(4096), timeout=2.0)
                                if not chunk:
                                    # Соединение закрыто, берем что есть
                                    response_data = header_data[:headers_end + 4] + chunk_buffer
                                    break
                                chunk_buffer += chunk
                                
                                # Проверяем окончание после каждого chunk
                                if chunk_buffer.endswith(b'0\r\n\r\n'):
                                    response_data = header_data[:headers_end + 4] + chunk_buffer
                                    break
                            except asyncio.TimeoutError:
                                # Если таймаут, но есть данные, используем их
                                if chunk_buffer:
                                    response_data = header_data[:headers_end + 4] + chunk_buffer
                                break
                    elif content_length > 0:
                        # Читаем по Content-Length
                        if body_received < content_length:
                            remaining = content_length - body_received
                            while remaining > 0:
                                try:
                                    chunk = await asyncio.wait_for(
                                        local_reader.read(min(remaining, 4096)), 
                                        timeout=10.0
                                    )
                                    if not chunk:
                                        break
                                    response_data += chunk
                                    remaining -= len(chunk)
                                except asyncio.TimeoutError:
                                    logger.warning(f"Timeout reading body from {local_host}:{local_port}, remaining: {remaining}")
                                    break
                        elif body_received > content_length:
                            # Если уже прочитали больше чем нужно, берем только нужное
                            response_data = header_data[:headers_end + 4] + header_data[headers_end + 4:headers_end + 4 + content_length]
                    elif connection_close:
                        # Если Connection: close, читаем до закрытия соединения
                        chunk_buffer = header_data[headers_end + 4:]
                        try:
                            while True:
                                try:
                                    chunk = await asyncio.wait_for(local_reader.read(4096), timeout=2.0)
                                    if not chunk:
                                        break
                                    chunk_buffer += chunk
                                    if len(chunk_buffer) > 10 * 1024 * 1024:  # 10MB максимум
                                        break
                                except asyncio.TimeoutError:
                                    # Если таймаут, но есть данные, используем их
                                    break
                            response_data = header_data[:headers_end + 4] + chunk_buffer
                        except Exception as e:
                            logger.error(f"Error reading with connection close: {e}")
                            response_data = header_data[:headers_end + 4] + chunk_buffer
                    else:
                        # Если нет Content-Length и не chunked, пробуем прочитать еще немного
                        chunk_buffer = header_data[headers_end + 4:]
                        try:
                            # Читаем еще немного данных (может быть небольшой body без Content-Length)
                            for _ in range(3):  # Максимум 3 попытки
                                try:
                                    chunk = await asyncio.wait_for(local_reader.read(4096), timeout=0.5)
                                    if not chunk:
                                        break
                                    chunk_buffer += chunk
                                except asyncio.TimeoutError:
                                    break
                            response_data = header_data[:headers_end + 4] + chunk_buffer
                        except Exception as e:
                            logger.error(f"Error reading additional data: {e}")
                            response_data = header_data
            except Exception as e:
                logger.error(f"Error reading response from {local_host}:{local_port}: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            local_writer.close()
            await local_writer.wait_closed()
            
            # Отправляем ответ на сервер
            response_message = {
                'action': 'proxy_response',
                'connection_id': connection_id,
                'data': base64.b64encode(response_data).decode('utf-8')
            }
            
            if self.control_writer:
                # Проверяем размер ответа перед кодированием
                response_size = len(response_data)
                encoded_size = len(base64.b64encode(response_data))
                json_size = len(json.dumps(response_message))
                
                if json_size > 10 * 1024 * 1024:  # 10MB
                    logger.warning(f"Response too large: {response_size} bytes (encoded: {encoded_size}, json: {json_size})")
                
                response_json = json.dumps(response_message)
                self.control_writer.write(response_json.encode() + b'\n')
                await self.control_writer.drain()
                logger.info(f"Proxied request for connection {connection_id} to {local_host}:{local_port}, response size: {response_size} bytes (json: {json_size} bytes)")
            
        except Exception as e:
            logger.error(f"Error proxying request to {local_host}:{local_port}: {e}")
            # Отправляем ошибку на сервер
            error_response = b"HTTP/1.1 502 Bad Gateway\r\n\r\nBad Gateway"
            response_message = {
                'action': 'proxy_response',
                'connection_id': connection_id,
                'data': base64.b64encode(error_response).decode('utf-8')
            }
            if self.control_writer:
                try:
                    self.control_writer.write(json.dumps(response_message).encode() + b'\n')
                    await self.control_writer.drain()
                except:
                    pass
    
    async def start(self):
        """Запуск клиента"""
        logger.info("Starting tunnel client...")
        
        # Обработка сигналов для graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            self.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        while self.is_running:
            try:
                # Подключаемся к серверу
                if await self.connect_to_server():
                    # Запускаем задачи
                    heartbeat_task = asyncio.create_task(self.send_heartbeat())
                    message_task = asyncio.create_task(self.handle_server_messages())
                    
                    # Ожидаем завершения задач
                    await asyncio.gather(heartbeat_task, message_task)
                else:
                    logger.error("Failed to connect to server, retrying in 10 seconds...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"Client error: {e}")
                await asyncio.sleep(10)
        
        # Завершение работы
        if self.control_writer:
            self.control_writer.close()
            await self.control_writer.wait_closed()
        
        logger.info("Tunnel client stopped")

def main():
    if len(sys.argv) != 2:
        print("Usage: python tunnel_client.py <config_file>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    try:
        client = TunnelClient(config_path)
        asyncio.run(client.start())
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
    except Exception as e:
        logger.error(f"Failed to start client: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()