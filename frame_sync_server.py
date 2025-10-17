import time
import json
from collections import defaultdict
from reliable_udp import ReliableUDP

class GameRoom:
    """游戏房间类，每个房间有独立的帧同步状态"""
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = {}  # {addr: player_info}
        
        # 帧同步数据
        self.current_frame = 0
        self.frame_inputs = defaultdict(dict)  # {frame: {player_id: inputs}}
        self.history_frames = {}  # {frame: {player_id: inputs}} 已发送的帧及其输入
        
        # 游戏配置
        self.frame_interval = 1.0 / 20  # 20 FPS
        self.last_frame_time = time.time()
        self.game_started = False
        
        # 房间属性
        self.host_addr = None  # 房主地址
        
        # 房间销毁相关
        self.empty_since = None  # 房间变空的时间戳

class FrameSyncServer:
    def __init__(self, host='127.0.0.1', port=8888):
        self.udp = ReliableUDP(host, port, is_server=True)
        self.udp.register_callback('on_message', self._handle_message)
        self.udp.register_callback('on_disconnect', self._handle_disconnect)

        # 房间管理
        self.rooms = {}  # {room_id: GameRoom}
        self.player_rooms = {}  # {addr: room_id} 记录每个玩家所在的房间
        
        # 全局配置
        self.input_ack_timeout = 0.2  # 200ms
        
        print("帧同步服务器启动完成")
    
    def _handle_message(self, data: dict, addr: tuple):
        # print(f"收到来自 {addr} 的消息: {data}")
        """处理客户端消息"""
        msg_type = data.get('type')
        
        if msg_type == 'connect':
            self._handle_connect(addr, data)
        elif msg_type == 'player_input':
            self._handle_player_input(addr, data)
        elif msg_type == 'input_ack':
            self._handle_input_ack(addr, data)
        elif msg_type == 'ping':
            self._handle_ping(addr, data)
        elif msg_type == 'game_start':
            self._handle_start_game(addr, data)
        elif msg_type == 'create_room':
            self._handle_create_room(addr, data)
        elif msg_type == 'join_room':
            self._handle_join_room(addr, data)
        elif msg_type == 'get_room_list':
            self._handle_get_room_list(addr, data)
        elif msg_type == 'sync_request':
            self._handle_sync_request(addr, data)
    
    def _handle_create_room(self, addr: tuple, data: dict):
        """处理创建房间请求"""
        # 创建新的房间ID
        room_id = f"room_{int(time.time() * 1000)}"
        
        # 创建新房间
        room = GameRoom(room_id)
        room.host_addr = addr  # 设置房主
        self.rooms[room_id] = room
        
        print(f"创建新房间: {room_id}")
        
        # 返回创建房间成功响应
        response = {
            'type': 'create_room_success',
            'room_id': room_id
        }
        
        self.udp.send_reliable(response, addr)
    
    def _handle_join_room(self, addr: tuple, data: dict):
        """处理加入房间请求"""
        room_id = data.get('room_id')
        
        # 检查房间是否存在
        if room_id not in self.rooms:
            response = {
                'type': 'join_room_failed',
                'reason': '房间不存在'
            }
            self.udp.send_reliable(response, addr)
            return
        
        room = self.rooms[room_id]
        
        # 检查游戏是否已经开始
        if room.game_started:
            response = {
                'type': 'join_room_failed',
                'reason': '游戏已经开始'
            }
            self.udp.send_reliable(response, addr)
            return
        
        # 检查玩家是否已经在房间中
        if addr in room.players:
            response = {
                'type': 'join_room_failed',
                'reason': '玩家已在房间中'
            }
            self.udp.send_reliable(response, addr)
            return
        
        # 添加玩家到房间
        player_id = len(room.players) + 1
        
        room.players[addr] = {
            'id': player_id,
            'name': data.get('name', f'Player{player_id}'),
            'color': self._get_player_color(player_id),
            'connected': True,
            'last_input_frame': 0
        }
        
        # 记录玩家所在房间
        self.player_rooms[addr] = room_id

        print(f"player : {room.players[addr]} connected to room {room_id}")
        
        # 发送加入房间成功响应
        response = {
            'type': 'join_room_success',
            'player_id': player_id,
            'room_id': room_id
        }
        
        self.udp.send_reliable(response, addr)
        print(f"玩家 {player_id} 已加入房间 {room_id}: {addr}，玩家数量: {len(room.players)}")
    
    def _handle_get_room_list(self, addr: tuple, data: dict):
        """处理获取房间列表请求"""
        # 获取未开始游戏的房间列表
        room_list = []
        for room_id, room in self.rooms.items():
            if not room.game_started:
                room_list.append({
                    'room_id': room_id,
                    'player_count': len(room.players)
                })
        
        response = {
            'type': 'room_list',
            'rooms': room_list
        }
        
        self.udp.send_reliable(response, addr)
    
    def _handle_start_game(self, addr: tuple, data: dict):
        """处理开始游戏请求"""
        # 检查玩家是否已连接
        if addr not in self.player_rooms:
            print(f"玩家 {addr} 未连接，拒绝开始游戏请求. player_rooms.size={len(self.player_rooms)}")
            return
        
        room_id = self.player_rooms[addr]
        room = self.rooms[room_id]
        
        # 检查是否是房主发起的开始请求
        if addr != room.host_addr:
            return
        
        # 只有房间游戏未开始时才处理开始请求
        if not room.game_started:
            self._start_game(room)
    
    def _handle_connect(self, addr: tuple, data: dict):
        """处理玩家连接"""
        # 获取房间ID
        room_id = data.get('room_id')
        
        # 检查房间是否存在
        if not room_id or room_id not in self.rooms:
            # 房间不存在，拒绝连接
            response = {
                'type': 'connect_failed',
                'reason': '房间不存在'
            }
            self.udp.send_reliable(response, addr)
            return
        
        room = self.rooms[room_id]
        
        # 检查游戏是否已经开始
        if room.game_started:
            response = {
                'type': 'connect_failed',
                'reason': '游戏已经开始'
            }
            self.udp.send_reliable(response, addr)
            return
        
        # 检查玩家是否已经在房间中
        if addr in room.players:
            return
        
        # 添加玩家到房间
        player_id = len(room.players) + 1
        
        # 如果这是第一个玩家，则设置为房主
        if len(room.players) == 0:
            room.host_addr = addr
        
        room.players[addr] = {
            'id': player_id,
            'name': data.get('name', f'Player{player_id}'),
            'color': self._get_player_color(player_id),
            'connected': True,
            'last_input_frame': 0
        }
        
        # 记录玩家所在房间
        self.player_rooms[addr] = room_id

        print(f"player : {room.players[addr]} connected to room {room_id}")
        
        # 发送连接成功响应
        response = {
            'type': 'connect_success',
            'player_id': player_id,
            'room_id': room_id,
            'game_state': self._get_initial_game_state(room, player_id)
        }
        
        self.udp.send_reliable(response, addr)
        print(f"玩家 {player_id} 已连接到房间 {room_id}: {addr}，玩家数量: {len(room.players)}")
    
    def _handle_player_input(self, addr: tuple, data: dict):
        """处理玩家输入"""
        # 检查玩家是否已连接
        if addr not in self.player_rooms:
            return
        
        room_id = self.player_rooms[addr]
        room = self.rooms[room_id]
        
        if addr not in room.players:
            return
        
        player = room.players[addr]
        frame = data['frame']
        inputs = data['inputs']
        
        # 检查帧是否在有效范围（current_frame-3 到 current_frame+3）
        if frame < room.current_frame - 3 or frame > room.current_frame + 3:
            print(f"忽略超出范围的输入: 来自 {addr} 的帧 {frame}，有效范围 [{room.current_frame-3}, {room.current_frame+3}]")
            return
        
        # 检查是否已经处理过（存在于history_frames中）
        if frame in room.history_frames:
            print(f"忽略已处理的输入: 来自 {addr} 的帧 {frame}, data:{data}")
            return
        
        # 存储输入
        if frame not in room.frame_inputs:
            room.frame_inputs[frame] = {}
        room.frame_inputs[frame][player['id']] = inputs

        if len(inputs) > 0:
            print(f"收到来自 {addr} 的输入数据: {data}, 当前帧: {room.current_frame}, player_id: {player['id']}")
        
        # 记录最后输入帧
        player['last_input_frame'] = frame
        
        # 发送输入确认
        ack_data = {
            'type': 'input_ack',
            'frame': frame,
            'server_frame': room.current_frame,
            'player_id': player['id']
        }
        self.udp.send_reliable(ack_data, addr)
    
    def _handle_input_ack(self, addr: tuple, data: dict):
        """处理输入确认"""
        # 服务器不需要处理客户端的输入确认
        pass
    
    def _handle_disconnect(self, addr: tuple):
        """处理玩家断开连接"""
        # 检查玩家是否已连接
        if addr not in self.player_rooms:
            return
        
        room_id = self.player_rooms[addr]
        room = self.rooms[room_id]
        
        if addr in room.players:
            player = room.players[addr]
            player_id = player['id']
            print(f"房间 {room_id} 中的玩家 {player_id} 断开连接")
            
            # 检查是否是房主断开连接
            is_host = (addr == room.host_addr)
            
            # 从玩家列表中移除
            del room.players[addr]
            del self.player_rooms[addr]
            
            # 如果房主断开连接，指定新的房主（如果还有其他玩家）
            if is_host and len(room.players) > 0:
                # 选择第一个玩家作为新房主
                new_host_addr = list(room.players.keys())[0]
                room.host_addr = new_host_addr
                print(f"玩家 {room.players[new_host_addr]['id']} 成为新房主")
            
            # 通知房间内的其他客户端有玩家断开连接
            disconnect_msg = {
                'type': 'player_disconnect',
                'player_id': player_id
            }
            
            for client_addr in room.players:
                self.udp.send_reliable(disconnect_msg, client_addr)
            
            # 如果游戏正在进行且房间内所有玩家都断开了连接，则清理房间
            if room.game_started and len(room.players) == 0:
                room.game_started = False
                room.current_frame = 0
                room.frame_inputs.clear()
                # 记录房间变空的时间
                room.empty_since = time.time()
                print(f"房间 {room_id} 内所有玩家断开连接，房间重置")
            # 如果房间未开始游戏且所有玩家都离开了，也记录房间变空时间
            elif not room.game_started and len(room.players) == 0:
                room.empty_since = time.time()
                print(f"房间 {room_id} 内所有玩家离开，记录房间变空时间")
    
    def _get_player_color(self, player_id: int) -> list:
        """获取玩家颜色"""
        colors = [
            [0, 120, 255],   # 蓝色
            [255, 0, 0],     # 红色
            [0, 200, 0],     # 绿色
            [255, 255, 0]    # 黄色
        ]
        return colors[player_id % len(colors)]
    
    def _get_initial_game_state(self, room: GameRoom, player_id: int) -> dict:
        """获取初始游戏状态"""
        return {
            'frame': room.current_frame,
            'game_started': room.game_started,
            'units': {},  # 不再在服务器端创建单位
            'buildings': {}  # 不再在服务器端创建建筑
        }
    
    def _start_game(self, room: GameRoom):
        """开始游戏"""
        room.game_started = True
        room.current_frame = 0
        
        # 收集房间内所有玩家的信息
        players_info = {}
        for addr, player in room.players.items():
            players_info[player['id']] = {
                'id': player['id'],
                'name': player['name'],
                'color': player['color']
            }
        
        # 广播游戏开始
        start_data = {
            'type': 'game_start',
            'start_frame': room.current_frame,
            'players': players_info  # 添加玩家列表信息
        }
        
        for addr in room.players:
            print(f"房间 {room.room_id} 开始游戏:", addr)
            self.udp.send_reliable(start_data, addr)

        
        print(f"房间 {room.room_id} 游戏开始!")
    
    def _sync_delay_frame_to_client(self, room: GameRoom, frame: int):
        """同步指定帧到客户端"""
        # 使用history_frames中存储的已确认输入
        if frame not in room.history_frames:
            return
        
        frame_data = {
            'type': 'frame_inputs',
            'frame': frame,
            'inputs': room.history_frames[frame]
        }

        for addr in room.players:
            self.udp.send_reliable(frame_data, addr)

        # print(f"房间 {room.room_id} 帧 {frame} 广播帧输入 {frame_data}")
        
        # 检查非空帧
        not_empty_frame = False
        for player_id, player_inputs in frame_data['inputs'].items():
            if len(player_inputs) > 0:
                not_empty_frame = True
        
        if not_empty_frame:
            print(f"房间 {room.room_id} 广播非空帧: {frame_data}")
        
    
    def _handle_ping(self, addr: tuple, data: dict):
        """处理ping请求并返回pong响应"""
        # 检查玩家是否已连接
        if addr not in self.player_rooms:
            return
        
        room_id = self.player_rooms[addr]
        room = self.rooms[room_id]
        
        pong_data = {
            'type': 'pong',
            'timestamp': data['timestamp'],
            'server_frame': room.current_frame
        }
        self.udp.send_reliable(pong_data, addr)
    
    def _handle_sync_request(self, addr: tuple, data: dict):
        """处理同步请求"""
        # 检查玩家是否已连接
        if addr not in self.player_rooms:
            return
        
        room_id = self.player_rooms[addr]
        room = self.rooms[room_id]
        
        if addr not in room.players:
            return
        
        # 发送最近几帧的数据给客户端
        requested_frame = data.get('frame', 0)
        
        # 发送从 requested_frame 到 current_frame 的所有帧数据
        for frame in range(requested_frame, room.current_frame + 1):
            if frame in room.history_frames:
                frame_data = {
                    'type': 'frame_inputs',
                    'frame': frame,
                    'inputs': room.history_frames[frame]
                }
                self.udp.send_reliable(frame_data, addr)
                print(f"发送帧 {frame} 数据给客户端 {addr}")
    
    def run_frame(self):
        """运行所有房间的一帧"""
        for room_id, room in list(self.rooms.items()):
            # 检查是否需要销毁房间（房间为空且超过1分钟）
            if len(room.players) == 0 and room.empty_since is not None:
                if time.time() - room.empty_since >= 60:  # 60秒 = 1分钟
                    print(f"房间 {room_id} 已空置超过1分钟，自动销毁")
                    del self.rooms[room_id]
                    continue  # 跳过此房间的后续处理
            
            if not room.game_started:
                continue
            
            current_time = time.time()
            if current_time - room.last_frame_time < room.frame_interval:
                continue
            
            room.last_frame_time += room.frame_interval
            
            # 按顺序处理延迟帧：current_frame-3, current_frame-2, current_frame-1
            for offset in [3, 2, 1]:
                target_frame = room.current_frame - offset
                if target_frame < 0:
                    continue  # 跳过负帧
                
                # 检查该帧是否已处理
                if target_frame in room.history_frames:
                    continue
                
                # 确保target_frame在frame_inputs中
                if target_frame not in room.frame_inputs:
                    room.frame_inputs[target_frame] = {}

                # 处理current_frame-3帧，补空帧
                if offset == 3:
                    for addr, player in list(room.players.items()):
                        if player['id'] not in room.frame_inputs[target_frame]:
                            room.frame_inputs[target_frame][player['id']] = []
                
                # 检查是否所有玩家都提交了该帧的输入
                num_players = len(room.players)
                if len(room.frame_inputs[target_frame]) == num_players:
                    # 存储该帧输入到history_frames
                    room.history_frames[target_frame] = dict(room.frame_inputs[target_frame])
                    # 同步该帧到客户端
                    self._sync_delay_frame_to_client(room, target_frame)
                else:
                    # 如果当前offset的帧未集齐，停止处理后续offset的帧
                    break

            # 清理旧帧
            old_frames = [f for f in room.frame_inputs if f < room.current_frame - 60]
            for f in old_frames:
                del room.frame_inputs[f]

            room.current_frame += 1
    
    def run(self):
        """运行服务器"""
        print("帧同步服务器运行中...")
        try:
            while True:
                self.run_frame()
                time.sleep(0.001)  # 降低CPU占用
        except KeyboardInterrupt:
            print("服务器关闭")
        finally:
            self.udp.close()

# 添加main函数
def main():
    """服务器主入口函数"""
    server = FrameSyncServer("0.0.0.0", 8888)
    server.run()

if __name__ == "__main__":
    main()