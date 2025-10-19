import pygame
import sys
import time
import math
from typing import Optional, TYPE_CHECKING
from .reliable_udp import ReliableUDP
from .unit import Unit
from .grid_manager import GridManager
from .bullet import Bullet

if TYPE_CHECKING:
    from .input_handler import InputHandler

# 比较两个角色id是一致的，使用str比较
def same_player_id(id1, id2) -> bool:
    return str(id1) == str(id2)


class FrameSyncClient:
    def __init__(self, server_host='127.0.0.1', server_port=8888):
        self.server_addr = (server_host, server_port)
        self.udp = ReliableUDP(is_server=False)
        self.udp.register_callback('on_message', self._handle_server_message)
        self.udp.register_callback('on_disconnect', self._handle_disconnect)
        
        # 游戏状态
        self.player_id = None
        self.room_id = None
        self.player_name = "Player"
        self.players = {}
        self.game_state = {
            'units': {},
            'buildings': {},
            'resources': []
        }
        
        # 网格管理系统
        self.grid_manager = GridManager()
        
        # 帧同步数据
        self.current_frame = 0
        self.server_frame = -1
        self.received_inputs = {}  # {frame: inputs}
        self.pending_inputs = {}  # {frame: inputs} 等待确认的输入
        
        # 输入管理
        self.input_buffer = []
        self.input_handler: Optional['InputHandler'] = None  # 添加input_handler属性定义
        
        # 游戏状态
        self.connected = False
        self.game_started = False
        self.in_lobby = True  # 是否在大厅中
        
        # 房间相关
        self.room_list = []  # 房间列表
        self.selected_room_id = None  # 选中的房间ID
        
        # 网络状态
        self.ping = 0  # ping值（毫秒）
        self.last_ping_time = 0
        self.ping_sent_time = 0
        self.ping_interval = 10.0  # 每10秒发送一次ping
        
        # 重连相关
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2.0  # 重连间隔（秒）
        self.last_reconnect_time = 0
        self.is_reconnecting = False
        
        # 渲染相关
        self.screen = None
        self.selected_units = []
        
        # 帧率控制
        self.frame_interval = 1.0 / 20  # 20 FPS
        self.last_frame_time = time.time()
        
        # 逻辑帧率计算
        self.last_logic_frame_time = time.time()
        self.logic_frame_count = 0
        self.logic_fps = 0.0
        self.logic_fps_update_interval = 1.0  # 每1秒更新一次逻辑帧率
        
        # 房间列表更新
        self.last_room_list_update = 0  # 上次获取房间列表的时间
        self.room_list_update_interval = 3.0  # 每3秒获取一次房间列表
        
        # 子弹管理
        self.bullets = {}  # 存储所有活动的子弹
        self.last_bullet_time = 0  # 上次发射子弹的时间
        self.bullet_interval = 1.0  # 每秒发射一颗子弹
        
        print("帧同步客户端初始化完成")
        
        # 初始化UDP连接
        self.udp.connect(self.server_addr[0], self.server_addr[1])
    
    def connect(self, player_name="Player", room_id=None):
        """连接到服务器"""
        # 如果没有指定房间ID，则不执行连接操作
        if not room_id:
            print("请先选择或创建一个房间")
            return True
        
        self.player_name = player_name
        
        connect_data = {
            'type': 'connect',
            'name': player_name,
            'room_id': room_id
        }
        
        # 发送连接请求
        self.udp.send_reliable(connect_data, self.server_addr)
        
        # 等待连接响应
        print("连接服务器中...")
        return True
    
    def reconnect(self):
        """尝试重连"""
        current_time = time.time()
        if self.is_reconnecting and (current_time - self.last_reconnect_time) >= self.reconnect_delay:
            if self.reconnect_attempts < self.max_reconnect_attempts:
                print(f"尝试重连 ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                self.reconnect_attempts += 1
                self.last_reconnect_time = current_time
                
                # 重新创建UDP连接
                self.udp.close()
                self.udp = ReliableUDP(is_server=False)
                self.udp.register_callback('on_message', self._handle_server_message)
                self.udp.register_callback('on_disconnect', self._handle_disconnect)
                self.udp.connect(self.server_addr[0], self.server_addr[1])
                
                # 尝试重新连接
                self.connect(self.player_name, self.room_id)
            else:
                print("重连尝试次数已用完，连接失败")
                self.is_reconnecting = False
                self.reconnect_attempts = 0
    
    def force_reconnect(self):
        """强制重连"""
        print("用户触发强制重连")
        # 重置游戏状态
        self.connected = False
        self.is_reconnecting = True
        self.reconnect_attempts = 0
        self.last_reconnect_time = time.time() - self.reconnect_delay  # 立即尝试重连
    
    def _handle_disconnect(self, addr):
        """处理断开连接"""
        print(f"与服务器 {addr} 断开连接")
        if self.connected and not self.is_reconnecting:
            print("开始尝试重连...")
            # 重置游戏状态
            self.connected = False
            self.is_reconnecting = True
            self.reconnect_attempts = 0
            self.last_reconnect_time = time.time() - self.reconnect_delay  # 立即尝试第一次重连
    
    def create_room(self, player_name="Player"):
        """创建房间"""
        create_data = {
            'type': 'create_room',
            'name': player_name
        }
        
        self.udp.send_reliable(create_data, self.server_addr)
        print("创建房间请求已发送")
    
    def join_room(self, room_id, player_name="Player"):
        """加入房间"""
        join_data = {
            'type': 'join_room',
            'room_id': room_id,
            'name': player_name
        }
        
        self.udp.send_reliable(join_data, self.server_addr)
        print(f"加入房间请求已发送: {room_id}")
    
    def get_room_list(self):
        """获取房间列表"""
        room_list_data = {
            'type': 'get_room_list'
        }
        
        self.udp.send_reliable(room_list_data, self.server_addr)
        print("获取房间列表请求已发送")
    
    def _handle_server_message(self, data: dict, addr: tuple):
        # print(f"收到服务器消息: {data}")
        """处理服务器消息"""
        msg_type = data.get('type')
        
        if msg_type == 'connect_success':
            self._handle_connect_success(data)
            # 重置重连状态
            self.is_reconnecting = False
            self.reconnect_attempts = 0
        elif msg_type == 'connect_failed':
            self._handle_connect_failed(data)
        elif msg_type == 'game_start':
            self._handle_game_start(data)
        elif msg_type == 'frame_inputs':
            self._handle_frame_inputs(data)
        elif msg_type == 'input_ack':
            self._handle_input_ack(data)
        elif msg_type == 'pong':
            self._handle_pong(data)
        elif msg_type == 'create_room_success':
            self._handle_create_room_success(data)
        elif msg_type == 'join_room_success':
            self._handle_join_room_success(data)
        elif msg_type == 'join_room_failed':
            self._handle_join_room_failed(data)
        elif msg_type == 'room_list':
            self._handle_room_list(data)
        elif msg_type == 'player_list':
            self._handle_player_list(data)

    def _handle_connect_failed(self, data: dict):
        """处理连接失败"""
        reason = data.get('reason', '未知错误')
        print(f"连接失败: {reason}")
        
        # 如果正在重连，则继续重连流程
        if self.is_reconnecting:
            current_time = time.time()
            if (current_time - self.last_reconnect_time) >= self.reconnect_delay:
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    print(f"重连尝试 {self.reconnect_attempts + 1}/{self.max_reconnect_attempts}")
                    self.reconnect_attempts += 1
                    self.last_reconnect_time = current_time
                    
                    # 尝试重新连接
                    self.connect(self.player_name, self.room_id)
                else:
                    print("重连尝试次数已用完，连接失败")
                    self.is_reconnecting = False
                    self.reconnect_attempts = 0
    
    def _handle_create_room_success(self, data: dict):
        """处理创建房间成功"""
        self.room_id = data['room_id']
        self.in_lobby = False
        # 创建房间后自动连接到该房间
        self.connect("Player", self.room_id)
        print(f"房间创建成功: {self.room_id}")
    
    def _handle_join_room_success(self, data: dict):
        """处理加入房间成功"""
        self.player_id = data['player_id']
        self.room_id = data['room_id']
        self.in_lobby = False
        # 加入房间后自动连接到该房间
        # 不再自动调用connect，因为服务器已经在join_room_success响应中包含了连接成功所需的信息
        self.connected = True
        print(f"成功加入房间: {self.room_id}")
    
    def _handle_join_room_failed(self, data: dict):
        """处理加入房间失败"""
        reason = data.get('reason', '未知错误')
        print(f"加入房间失败: {reason}")
    
    def _handle_room_list(self, data: dict):
        """处理房间列表"""
        self.room_list = data.get('rooms', [])
        print(f"收到房间列表: {self.room_list}")
    
    def _handle_connect_success(self, data: dict):
        """处理连接成功"""
        self.player_id = data['player_id']
        self.room_id = data.get('room_id')
        self.connected = True
        self.in_lobby = False  # 直接进入游戏，不在大厅
        
        # 根据服务端的游戏状态设置客户端的游戏状态
        game_state = data['game_state']
        self.current_frame = game_state['frame']
        self.server_frame = self.current_frame - 1
        self.game_started = game_state.get('game_started', False)
        
        # 清理旧的状态数据
        self.received_inputs.clear()
        self.pending_inputs.clear()
        self.input_buffer.clear()
        
        print(f"连接成功! 玩家ID: {self.player_id}, 房间ID: {self.room_id}, 当前帧: {self.current_frame}")


    
    def _handle_game_start(self, data: dict):
        """处理游戏开始"""
        self.game_started = True
        # 只有当当前帧小于起始帧时才更新当前帧
        if self.current_frame < data['start_frame']:
            self.current_frame = data['start_frame']
        self.server_frame = self.current_frame - 1
        
        # 获取玩家列表并创建初始游戏对象
        players = data.get('players', {})
        self._create_initial_game_objects_for_all_players(players)
        
        print(f"游戏开始! 起始帧: {data['start_frame']}, 当前帧: {self.current_frame}")
        # ping
        self.send_ping()

    def _create_initial_game_objects_for_all_players(self, players: dict):
        """为所有玩家创建初始游戏对象"""
        # 清空现有的单位和建筑
        self.game_state['units'].clear()
        self.game_state['buildings'].clear()
        self.bullets.clear()  # 同时清空子弹
        
        # 为每个玩家创建初始单位和建筑
        for player_id, player_info in players.items():
            # 根据玩家ID确定基地位置
            if 1 == int(player_id):
                base_x = 96 - 16
                base_y = 640 - 16
            elif 2 == int(player_id):
                base_x = 640 - 16
                base_y = 640 - 16
            elif 3 == int(player_id):
                base_x = 96 - 16
                base_y = 192 - 16
            else:
                base_x = 640 - 16
                base_y = 192 - 16

            
            # 创建初始单位
            for i in range(5):
                unit_id = f"{player_id}_{i}"
                unit = Unit(
                    unit_id=unit_id,
                    player_id=int(player_id),
                    unit_type='infantry',
                    x=base_x + i * 32,
                    y=base_y
                )
                # 绑定单位到网格
                self.grid_manager.bind_unit_to_grid(unit)
                self.game_state['units'][unit_id] = unit
            
            # 创建初始建筑
            building_id = f"{player_id}_base"
            self.game_state['buildings'][building_id] = {
                'id': building_id,
                'player_id': int(player_id),
                'type': 'base',
                'x': base_x,
                'y': base_y - 96,
                'health': 1000
            }
    
    def _handle_frame_inputs(self, data: dict):
        """处理帧输入"""
        frame = data['frame']
        inputs = data['inputs']

        # inputs数组中的元素的数组大于0，则说明有输入
        hasInput = False
        for player_id, player_inputs in inputs.items():
            for input_data in player_inputs:
                if len(input_data) > 0:
                    hasInput = True
                    break
            

        if hasInput:
            print(f"收到帧输入: {data}, current_frame: {self.current_frame}")
        
        # 存储输入
        self.received_inputs[frame] = inputs
        # print(f"保存帧输入: {frame}, inputs: {inputs}")
        
        # 更新server_frame
        if frame > self.server_frame:
            self.server_frame = frame
            

    
    def _handle_input_ack(self, data: dict):
        """处理输入确认"""
        frame = data['frame']
        if frame in self.pending_inputs:
            del self.pending_inputs[frame]

    
    def send_inputs(self):
        """发送输入到服务器"""
        if not self.connected or not self.game_started:
            return
        
        predicted_frame = self.server_frame + 2

        # 判断pending_inputs是否存在预测帧
        if predicted_frame in self.pending_inputs:
            print(f"预测帧已存在: {predicted_frame}")
            return
            
        input_data = {
            'type': 'player_input',
            'frame': predicted_frame,
            'inputs': self.input_buffer.copy()
        }

        # 非空帧打印日志
        if len(input_data['inputs']) > 0:
            print(f"发送非空输入: {input_data}, 当前帧: {self.current_frame}")
        
        # 使用可靠传输发送
        self.udp.send_reliable(input_data, self.server_addr)
        
        # 添加到等待确认列表
        self.pending_inputs[predicted_frame] = self.input_buffer.copy()
        
        # 清空输入缓冲区
        self.input_buffer.clear()
    
    def apply_inputs(self, frame: int):
        """应用输入到游戏状态"""
        if frame not in self.received_inputs:
            print(f"没有输入帧: {frame}")
            return
        
        inputs = self.received_inputs[frame]
        
        # 应用输入
        for player_id, player_inputs in inputs.items():
            for input_data in player_inputs:
                print(f"处理输入: {input_data}, current_frame: {self.current_frame}")
                # player_id转为整数
                player_id = int(player_id)
                self._process_single_input(player_id, input_data)
    
    def _process_single_input(self, player_id: int, input_data: dict):
        print(f"处理具体输入: {input_data}")
        """处理单个输入"""
        input_type = input_data.get('type')
        
        if input_type == 'move_units':
            unit_ids = input_data.get('unit_ids', [])
            target_x = input_data.get('x')
            target_y = input_data.get('y')
            
            for unit_id in unit_ids:
                if unit_id in self.game_state['units']:
                    unit = self.game_state['units'][unit_id]
                    if same_player_id(unit.player_id, player_id):
                        unit.move_to(target_x, target_y)
                        # 解绑单位从网格（开始移动时）
                        self.grid_manager.unbind_unit_from_grid(unit)
                        print(f"移动单位: {unit_id}, 目标位置: ({target_x}, {target_y})")
        
        elif input_type == 'produce_unit':
            building_id = input_data.get('building_id')
            unit_type = input_data.get('unit_type')
            
            if building_id in self.game_state['buildings']:
                building = self.game_state['buildings'][building_id]
                if same_player_id(building['player_id'], player_id):
                    unit_id = f"{player_id}_{len(self.game_state['units'])}"
                    unit = Unit(
                        unit_id=unit_id,
                        player_id=player_id,
                        unit_type=unit_type,
                        x=building['x'] + 64,
                        y=building['y']
                    )
                    # 绑定单位到网格
                    self.grid_manager.bind_unit_to_grid(unit, teleport=True)
                    self.game_state['units'][unit_id] = unit
                    print(f"生产单位: {unit_id}, 类型: {unit_type}")
    
    def adjust_bullet_position(self, x: float, y: float):
        """调整子弹位置到格子中心点"""
        x = x // 32 * 32 + 16
        y = y // 32 * 32 + 16
        return x, y

    def update_game_state(self):
        """更新游戏状态"""
        # 更新单位位置
        for unit_id, unit in self.game_state['units'].items():
            old_x, old_y = unit.x, unit.y
            unit.update_position()
            
            # 检查单位是否停止移动
            if not unit.is_moving and (old_x != unit.x or old_y != unit.y):
                # 单位停止移动，绑定到网格
                self.grid_manager.bind_unit_to_grid(unit)
        
        # 更新子弹状态
        current_time = time.time()
        # 检查是否有选中的单位且距离上次发射子弹已经过了指定间隔
        if (self.selected_units and 
            current_time - self.last_bullet_time >= self.bullet_interval):
            # 获取鼠标位置
            mouse_x, mouse_y = pygame.mouse.get_pos()
            # 调整子弹在格子中心点
            mouse_x, mouse_y = self.adjust_bullet_position(mouse_x, mouse_y)
            # 从选中的单位中选择一个发射子弹
            shooter_unit = self.game_state['units'][self.selected_units[0]]
            # 创建子弹ID
            bullet_id = f"bullet_{int(current_time * 1000)}"
            # 创建子弹对象
            bullet = Bullet(bullet_id, shooter_unit.x, shooter_unit.y, mouse_x, mouse_y)
            # 添加到子弹列表
            self.bullets[bullet_id] = bullet
            # 更新上次发射子弹时间
            self.last_bullet_time = current_time
            # TODO调整unit朝向子弹方向
            direction = shooter_unit.cal_direction(shooter_unit.x, shooter_unit.y, mouse_x, mouse_y)
            shooter_unit.direction = direction

        
        # 更新所有子弹
        bullets_to_remove = []
        for bullet_id, bullet in self.bullets.items():
            bullet.update()
            if not bullet.is_active:
                bullets_to_remove.append(bullet_id)
        
        # 移除不活动的子弹
        for bullet_id in bullets_to_remove:
            if bullet_id in self.bullets:
                del self.bullets[bullet_id]


    def run_frame(self):
        """运行客户端帧逻辑"""
        current_time = time.time()
        
        # 处理重连
        if self.is_reconnecting:
            self.reconnect()
            return False
        
        # 定期更新逻辑帧率
        if current_time - self.last_logic_frame_time >= self.logic_fps_update_interval:
            self.logic_fps = self.logic_frame_count / (current_time - self.last_logic_frame_time)
            self.logic_frame_count = 0
            self.last_logic_frame_time = current_time
        
        # 在大厅中时定期获取房间列表
        if self.in_lobby and current_time - self.last_room_list_update >= self.room_list_update_interval:
            self.get_room_list()
            self.last_room_list_update = current_time
        
        if not self.game_started:
            # 即使游戏未开始也发送ping
            self.send_ping()
            return False
        
        # 锁帧
        if self.current_frame >= self.server_frame:
            return False
        
        # 服务器帧与当前帧的差
        gap = self.server_frame - self.current_frame

        if gap >= 10:
            # 多处理30帧
            run_frames = min(gap - 1, 30)
            print(f"服务器帧与当前帧的差过大: {gap}，多处理{run_frames}帧，当前帧： {self.current_frame}")
            for i in range(run_frames):
                self.run_one_frame()
            should_process_frame = True
        elif gap >= 2:
            # 多处理一帧
            if gap > 3:
                print(f"服务器帧与当前帧的差超过2帧，每帧多处理一帧: {gap}，当前帧： {self.current_frame}")
            self.run_one_frame()
            should_process_frame = True
        else:
            # 限制帧率
            elapsed_time = current_time - self.last_frame_time
            if elapsed_time >= self.frame_interval:
                self.last_frame_time = current_time
                should_process_frame = True
            else:
                should_process_frame = False

        if not should_process_frame:
            return False
        
        # 每帧都上报输入，包括空输入
        self.send_inputs()
        
        self.run_one_frame()

        self.send_ping()

        return True

    def run_one_frame(self):
        if self.current_frame in self.received_inputs:
            self.apply_inputs(self.current_frame)
        else:
            print(f"2没有输入帧: {self.current_frame}")
        
        # 更新游戏状态
        self.update_game_state()
        
        old_pending = [f for f in self.pending_inputs if f < self.current_frame - 20]
        for frame in old_pending:
            del self.pending_inputs[frame]
        
        self.current_frame += 1
        # 只有当真正处理了一个游戏逻辑帧后，才增加逻辑帧计数
        self.logic_frame_count += 1
       
    def send_ping(self):
        """发送ping请求"""
        current_time = time.time()
        if current_time - self.last_ping_time >= self.ping_interval and self.connected:
            ping_data = {
                'type': 'ping',
                'timestamp': current_time
            }
            self.udp.send_reliable(ping_data, self.server_addr)
            self.ping_sent_time = current_time
            self.last_ping_time = current_time
            
            # 每次ping时上报当前帧信息，帮助服务器同步
            if self.connected and hasattr(self, 'server_frame'):
                ping_data['server_frame'] = self.server_frame
    
    def _handle_pong(self, data: dict):
        """处理pong响应"""
        current_time = time.time()
        sent_time = data['timestamp']
        self.ping = (current_time - sent_time) * 1000  # 转换为毫秒
        server_frame = data['server_frame']
        # print(f"Ping: {self.ping:.2f}ms, self.current_frame: {self.current_frame}, server_frame: {server_frame}")
        # self.current_frame = server_frame - 1
    
    def send_start_game_request(self):
        """发送开始游戏请求到服务器"""
        if not self.connected:
            return False
        
        start_request = {
            'type': 'game_start'
        }
        self.udp.send_reliable(start_request, self.server_addr)
        print("已发送开始游戏请求")
        return True
    
    def _handle_player_list(self, data: dict):
        """处理玩家列表"""
        self.players = data.get('players', {})
        print(f"收到玩家列表: {self.players}")
        
        # 如果游戏已经开始，更新游戏对象
        if self.game_started:
            self._update_game_objects_with_players()
    
    def _update_game_objects_with_players(self):
        """根据玩家列表更新游戏对象"""
        # 这里可以添加根据玩家列表更新游戏对象的逻辑
        pass
