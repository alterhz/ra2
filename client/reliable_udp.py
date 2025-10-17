import socket
import time
import threading
import json
import zlib
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

class PacketType(Enum):
    UNRELIABLE = 0      # 不可靠数据包
    RELIABLE = 1        # 可靠数据包
    ACK = 2             # 确认包
    HEARTBEAT = 3       # 心跳包

class ReliableUDP:
    def __init__(self, host='localhost', port=8888, is_server=False):
        self.host = host
        self.port = port
        self.is_server = is_server
        
        # UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0.01)  # 设置超时，避免recvfrom阻塞
        if is_server:
            self.socket.bind((host, port))
        else:
            # 客户端不需要绑定特定端口，系统会分配
            pass
        
        # 可靠传输相关 - 为每个连接维护独立的状态
        self.connection_states = {}  # {addr: {'sequence_number', 'ack_history', 'received_packets', 'expected_sequence'}}
        self.local_sequence_number = 0  # 本地序列号
        
        # 接收缓冲区 - 存储序列号对应的数据和地址
        self.receive_buffer = {}  # {addr: {seq_num: {'data': data}}}
        
        # 连接管理
        self.connections = {}  # {addr: last_heartbeat}
        self.callbacks: Dict[str, Optional[Callable]] = {
            'on_message': None,
            'on_connect': None,
            'on_disconnect': None,
            'on_message_failed': None  # 新增：消息发送失败的回调
        }
        
        # 配置参数
        self.retry_timeout = 0.1  # 100ms重试
        self.max_retries = 10     # 增加重试次数到10次
        self.heartbeat_interval = 1.0  # 1秒心跳
        
        # 线程控制
        self.running = True
        self.last_heartbeat_time = time.time()
        
        # 启动处理线程
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        self.process_thread = threading.Thread(target=self._process_loop)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        print(f"ReliableUDP {'Server' if is_server else 'Client'} started on {host}:{port}")
    
    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self.callbacks:
            self.callbacks[event] = callback
    
    def _get_connection_state(self, addr: tuple) -> dict:
        """获取或创建连接状态"""
        if addr not in self.connection_states:
            self.connection_states[addr] = {
                'sequence_number': 0,
                'ack_history': {},  # {seq_num: (send_time, data, retry_count)}
                'received_packets': set(),  # 已接收的包序列号
                'expected_sequence': 0
            }
        return self.connection_states[addr]
    
    def _get_next_sequence(self, addr: tuple) -> int:
        """获取下一个序列号"""
        if self.is_server and addr:
            # 服务器为每个客户端维护独立的序列号
            state = self._get_connection_state(addr)
            seq = state['sequence_number']
            state['sequence_number'] = (state['sequence_number'] + 1) % 65536
            return seq
        else:
            # 客户端或者没有指定地址时使用本地序列号
            seq = self.local_sequence_number
            self.local_sequence_number = (self.local_sequence_number + 1) % 65536
            return seq
    
    def _create_packet(self, data: dict, packet_type: PacketType, seq_num: int) -> dict:
        """创建数据包"""
        if seq_num is None:
            seq_num = self._get_next_sequence()
        
        packet = {
            'type': packet_type.value,
            'seq': seq_num,
            'data': data,
            'timestamp': time.time()
        }
        return packet
    
    def send_reliable(self, data: dict, addr: tuple) -> int:
        """发送可靠数据包"""
        # 检查连接是否仍然有效
        if not self.is_server and addr not in self.connections:
            print(f"无法发送消息到 {addr}，连接已断开")
            return -1
            
        seq_num = self._get_next_sequence(addr)
        packet = self._create_packet(data, PacketType.RELIABLE, seq_num)
        
        # 添加到确认历史
        state = self._get_connection_state(addr)
        # print(f"send reliable packet: {packet}, addr: {addr}, state: {state}")
        state['ack_history'][seq_num] = {
            'send_time': time.time(),
            'data': packet,
            'retry_count': 0,
            'addr': addr
        }

        # print(f"发送可靠数据包: {packet}, 地址: {addr}, state: {state}")
        
        # 发送数据包
        self._send_packet(packet, addr)
        return seq_num
    
    def send_unreliable(self, data: dict, addr: tuple):
        """发送不可靠数据包"""
        packet = self._create_packet(data, PacketType.UNRELIABLE, 0)
        self._send_packet(packet, addr)
    
    def _send_packet(self, packet: dict, addr: tuple):
        """发送数据包"""
        try:
            # 压缩数据
            # print(f"发送数据包: {packet}, addr: {addr}")
            json_str = json.dumps(packet)
            compressed_data = zlib.compress(json_str.encode('utf-8'))
            self.socket.sendto(compressed_data, addr)
        except Exception as e:
            print(f"发送数据包 {packet} 错误: {e}, addr: {addr}")
    
    def send_ack(self, seq_num: int, addr: tuple):
        """发送确认包"""
        ack_packet = {
            'type': PacketType.ACK.value,
            'ack_seq': seq_num,
            'timestamp': time.time()
        }
        # print(f"发送确认包: {ack_packet}, 地址: {addr}")
        self._send_packet(ack_packet, addr)
    
    def _receive_loop(self):
        """接收循环"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65507)  # 最大UDP包大小
                self._handle_received_data(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:  # 只在运行状态下打印错误
                    print(f"接收数据错误: {e}")
    
    def _handle_received_data(self, data: bytes, addr: tuple):
        """处理接收到的数据"""
        try:
            # 解压数据
            decompressed = zlib.decompress(data)
            packet = json.loads(decompressed.decode())
            
            packet_type = PacketType(packet['type'])
            seq_num = packet.get('seq')
            
            # 更新连接状态
            self.connections[addr] = time.time()
            
            # 确保该地址的接收缓冲区存在
            if addr not in self.receive_buffer:
                self.receive_buffer[addr] = {}
            
            if packet_type == PacketType.RELIABLE:
                # 可靠数据包 - 发送ACK
                self.send_ack(seq_num, addr)
                
                # 获取连接状态
                state = self._get_connection_state(addr)
                
                # 检查是否已接收过
                if seq_num not in state['received_packets']:
                    state['received_packets'].add(seq_num)
                    
                    # 按顺序处理，同时保存数据和地址信息
                    self.receive_buffer[addr][seq_num] = {
                        'data': packet['data']
                    }
                    self._process_receive_buffer(addr)
            
            elif packet_type == PacketType.UNRELIABLE:
                # 不可靠数据包 - 直接处理
                if self.callbacks['on_message']:
                    self.callbacks['on_message'](packet['data'], addr)
            
            elif packet_type == PacketType.ACK:
                # 确认包 - 从确认历史中移除
                state = self._get_connection_state(addr)
                ack_seq = packet['ack_seq']
                if ack_seq in state['ack_history']:
                    del state['ack_history'][ack_seq]
                    # print(f"删除确认历史: {ack_seq}, 地址: {addr}")
                else:
                    print(f"确认包 {ack_seq} 不存在，地址: {addr}, state: {state}")
            
            elif packet_type == PacketType.HEARTBEAT:
                # 心跳包 - 更新连接状态
                self.connections[addr] = time.time()
                if self.is_server:
                    # 服务器回应心跳
                    self.send_unreliable({'type': 'heartbeat_ack'}, addr)
        
        except Exception as e:
            print(f"处理接收数据错误: {e}")
    
    def _process_receive_buffer(self, addr: tuple):
        """处理特定客户端的接收缓冲区，按顺序交付"""
        if addr not in self.receive_buffer:
            return
            
        state = self._get_connection_state(addr)
        buffer = self.receive_buffer[addr]
        
        while state['expected_sequence'] in buffer:
            try:
                item = buffer.pop(state['expected_sequence'])
                data = item['data']
                
                if self.callbacks['on_message']:
                    # print(f"处理接收数据: {data}, 源: {addr}")
                    self.callbacks['on_message'](data, addr)
                
                state['expected_sequence'] = (state['expected_sequence'] + 1) % 65536
            except Exception as e:
                print(f"处理接收缓冲区时出错: {e}")
    
    def _process_loop(self):
        """处理循环 - 重传和心跳"""
        while self.running:
            current_time = time.time()
            
            # 检查需要重传的数据包
            # 使用 list() 创建副本以避免在迭代时修改字典
            for addr, state in list(self.connection_states.items()):
                expired_packets = []
                for seq_num, info in list(state['ack_history'].items()):
                    if current_time - info['send_time'] > self.retry_timeout:
                        if info['retry_count'] < self.max_retries:
                            # 重传
                            info['retry_count'] += 1
                            info['send_time'] = current_time
                            self._send_packet(info['data'], info['addr'])
                        else:
                            # 超过最大重试次数
                            expired_packets.append(seq_num)
                            print(f"数据包 {seq_num} 超过最大重试次数")
                
                # 移除过期的数据包
                for seq_num in expired_packets:
                    # 首先尝试调用 on_message_failed 回调，告知特定消息发送失败
                    if self.callbacks['on_message_failed']:
                        try:
                            # 传递地址和序列号，以便上层应用识别是哪个消息失败了
                            self.callbacks['on_message_failed'](addr, seq_num)
                        except Exception as callback_error:
                            print(f"执行 on_message_failed 回调时出错: {callback_error}")
                    
                    # 然后从确认历史中移除该数据包
                    del state['ack_history'][seq_num]
                    print(f"过期，删除确认历史: {seq_num}, 地址: {addr}")
            
            # 发送心跳
            if current_time - self.last_heartbeat_time > self.heartbeat_interval:
                self._send_heartbeats()
                self.last_heartbeat_time = current_time
            
            # 检查连接超时
            self._check_connection_timeout()
            
            time.sleep(0.01)  # 10ms间隔
    
    def _send_heartbeats(self):
        """发送心跳包"""
        heartbeat_data = {'type': 'heartbeat'}
        if self.is_server:
            # 服务器向所有客户端发送心跳
            for addr in list(self.connections.keys()):
                self.send_unreliable(heartbeat_data, addr)
        else:
            # 客户端向服务器发送心跳
            if hasattr(self, 'server_addr'):
                self.send_unreliable(heartbeat_data, self.server_addr)
    
    def _check_connection_timeout(self):
        """检查连接超时"""
        current_time = time.time()
        timeout = self.heartbeat_interval * 3  # 3倍心跳间隔
        
        expired_connections = []
        for addr, last_time in self.connections.items():
            if current_time - last_time > timeout:
                expired_connections.append(addr)
        
        for addr in expired_connections:
            del self.connections[addr]
            # 从连接状态中移除
            if addr in self.connection_states:
                del self.connection_states[addr]
            # 从接收缓冲区中移除
            if addr in self.receive_buffer:
                del self.receive_buffer[addr]
            
            if self.callbacks['on_disconnect']:
                self.callbacks['on_disconnect'](addr)
    
    def connect(self, server_host: str, server_port: int):
        """客户端连接服务器"""
        if self.is_server:
            return
        
        self.server_addr = (server_host, server_port)
        self.connections[self.server_addr] = time.time()
        
        # 初始化服务器连接状态
        self._get_connection_state(self.server_addr)
        
        # 发送连接请求 TODO 外面发送了连接请求
        # connect_data = {'type': 'connect'}
        # self.send_reliable(connect_data, self.server_addr)
    
    def close(self):
        """关闭连接"""
        self.running = False
        if hasattr(self, 'socket'):
            self.socket.close()

# 添加main函数用于测试
def main():
    """测试可靠UDP"""
    import time
    
    def server_message_handler(data, addr):
        print(f"服务器收到消息: {data} 来自: {addr}")
    
    def client_message_handler(data, addr):
        print(f"客户端收到消息: {data}")
    
    # 测试服务器
    server = ReliableUDP(host='localhost', port=8888, is_server=True)
    server.register_callback('on_message', server_message_handler)
    
    # 测试客户端
    client = ReliableUDP(host='localhost', port=0, is_server=False)
    client.register_callback('on_message', client_message_handler)
    client.connect('localhost', 8888)
    
    # 发送测试消息
    time.sleep(1)  # 等待连接建立
    client.send_reliable({'test': 'hello'}, ('localhost', 8888))
    
    # 等待一段时间
    time.sleep(3)
    
    # 关闭
    server.close()
    client.close()

if __name__ == "__main__":
    main()