import pygame
import sys
import time
import math
from typing import Optional
from reliable_udp import ReliableUDP


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
        
        # 帧同步数据
        self.current_frame = 0
        self.server_frame = -1
        self.received_inputs = {}  # {frame: inputs}
        self.pending_inputs = {}  # {frame: inputs} 等待确认的输入
        
        # 输入管理
        self.input_buffer = []
        self.input_handler: Optional[InputHandler] = None  # 添加input_handler属性定义
        
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
        
        # 为每个玩家创建初始单位和建筑
        for player_id, player_info in players.items():
            # 根据玩家ID确定基地位置
            base_x = 100 if int(player_id) == 1 else 500
            base_y = 500
            
            # 创建初始单位
            for i in range(5):
                unit_id = f"{player_id}_{i}"
                self.game_state['units'][unit_id] = {
                    'id': unit_id,
                    'player_id': int(player_id),
                    'type': 'infantry',
                    'x': base_x + i * 40,
                    'y': base_y,
                    'target_x': base_x + i * 40,
                    'target_y': base_y,
                    'health': 100,
                    'speed': 2.0
                }
            
            # 创建初始建筑
            building_id = f"{player_id}_base"
            self.game_state['buildings'][building_id] = {
                'id': building_id,
                'player_id': int(player_id),
                'type': 'base',
                'x': base_x,
                'y': base_y - 100,
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
                    if same_player_id(unit['player_id'], player_id):
                        unit['target_x'] = target_x
                        unit['target_y'] = target_y
                        print(f"移动单位: {unit_id}, 目标位置: ({target_x}, {target_y})")
        
        elif input_type == 'produce_unit':
            building_id = input_data.get('building_id')
            unit_type = input_data.get('unit_type')
            
            if building_id in self.game_state['buildings']:
                building = self.game_state['buildings'][building_id]
                if same_player_id(building['player_id'], player_id):
                    unit_id = f"{player_id}_{len(self.game_state['units'])}"
                    self.game_state['units'][unit_id] = {
                        'id': unit_id,
                        'player_id': player_id,
                        'type': unit_type,
                        'x': building['x'] + 50,
                        'y': building['y'],
                        'target_x': building['x'] + 50,
                        'target_y': building['y'],
                        'health': 100,
                        'speed': 2.0
                    }
                    print(f"生产单位: {unit_id}, 类型: {unit_type}")
    
    def update_game_state(self):
        """更新游戏状态"""
        # 更新单位位置
        for unit_id, unit in self.game_state['units'].items():
            dx = unit['target_x'] - unit['x']
            dy = unit['target_y'] - unit['y']
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance > 2:
                unit['x'] += (dx / distance) * min(unit['speed'], distance)
                unit['y'] += (dy / distance) * min(unit['speed'], distance)
    
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
            self.send_ping()
            return False
        
        # 每帧都上报输入，包括空输入
        self.send_inputs()
        
        self.run_one_frame()

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

class GameRenderer:
    def __init__(self, client):
        self.window_width = 1024
        self.window_height = 768
        self.client = client
        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        pygame.display.set_caption("红警 - 可靠帧同步")
        self.clock = pygame.time.Clock()
        
        # 改进字体初始化，增加错误处理和备选方案
        try:
            # 首先尝试使用系统默认字体
            self.font = pygame.font.SysFont("microsoftyahei", 24)
            # 测试字体是否能正常工作
            test_render = self.font.render("Test", True, (255, 255, 255))
        except Exception as e:
            print(f"使用系统默认字体失败: {e}")
            # 尝试使用备选字体
            fallback_fonts = ['arial', 'simhei', 'simsun', 'fangsong', 'calibri', 'consolas']
            self.font = None
            for font_name in fallback_fonts:
                try:
                    self.font = pygame.font.SysFont(font_name, 24)
                    test_render = self.font.render("Test", True, (255, 255, 255))
                    print(f"使用备选字体: {font_name}")
                    break
                except Exception as e:
                    print(f"无法使用字体 {font_name}: {e}")
                    continue
            
            # 如果所有字体都失败，则使用内置字体
            if self.font is None:
                print("使用内置默认字体")
                self.font = pygame.font.Font(None, 24)
        
        # FPS计算相关
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0
        self.fps_update_interval = 0.5  # 每0.5秒更新一次FPS
        
        # 按钮相关属性
        self.start_button_rect = pygame.Rect(650, 10, 140, 40)
        self.start_button_color = (0, 200, 0)  # 绿色
        self.start_button_hover_color = (0, 255, 0)  # 亮绿色
        self.start_button_text_color = (255, 255, 255)  # 白色
        
        # 大厅界面按钮
        self.create_room_button_rect = pygame.Rect(650, 100, 140, 40)
        self.join_room_button_rect = pygame.Rect(650, 160, 140, 40)
        self.refresh_room_button_rect = pygame.Rect(650, 220, 140, 40)
        
        # 断线重连按钮
        self.reconnect_button_rect = pygame.Rect(650, 280, 140, 40)
        
        self.colors = {
            'background': (0, 0, 0),
            'terrain1': (0, 100, 0),
            'terrain2': (0, 150, 0),
            'player0': (0, 120, 255),
            'player1': (255, 0, 0),
            'player2': (0, 255, 0),
            'player3': (255, 255, 0),
            'player4': (255, 0, 255),
            'player5': (0, 255, 255),
            'selected': (255, 255, 0),
            'ui_text': (255, 255, 255),
            'button': (70, 130, 180),  # Steel blue
            'button_hover': (100, 149, 237),  # Corn flower blue
            'button_text': (255, 255, 255),
            'reconnect_button': (200, 100, 0),  # 橙色
            'reconnect_button_hover': (255, 140, 0)  # 亮橙色
        }
    
    def render(self):
        # 处理窗口大小调整事件
        for event in pygame.event.get([pygame.VIDEORESIZE]):
            if event.type == pygame.VIDEORESIZE:
                self.window_width = event.w
                self.window_height = event.h
                self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
                # 窗口大小改变时，重置任何正在进行的拖拽操作
                if hasattr(self.client, 'input_handler'):
                    self.client.input_handler.dragging = False
        
        # 填充背景
        self.screen.fill(self.colors['background'])
        
        if self.client.in_lobby:
            # 绘制大厅界面
            self.draw_lobby()
        elif self.client.game_started:
            # 绘制游戏界面
            self.draw_terrain()
            # 绘制建筑
            for building in self.client.game_state['buildings'].values():
                self.draw_building(building)
            # 绘制单位
            for unit in self.client.game_state['units'].values():
                self.draw_unit(unit)
            self.draw_ui(self.client.input_handler if hasattr(self.client, 'input_handler') else None)
        else:
            # 在房间中但游戏未开始
            self.draw_waiting_room()
        
        pygame.display.flip()
        
        # 计算FPS
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_time >= self.fps_update_interval:
            self.fps = self.frame_count / (current_time - self.last_time)
            self.frame_count = 0
            self.last_time = current_time
        
        # 绘制FPS 每秒60帧
        self.clock.tick(60)
    
    def draw_lobby(self):
        """绘制大厅界面"""
        # 绘制房间列表标题
        try:
            title_text = self.font.render("房间列表", True, self.colors['ui_text'])
            self.screen.blit(title_text, (10, 10))
            
            # 绘制房间列表
            y_offset = 50
            for i, room in enumerate(self.client.room_list):
                room_text = self.font.render(f"{room['room_id']} ({room['player_count']} 玩家)", True, self.colors['ui_text'])
                room_rect = pygame.Rect(10, y_offset, 300, 30)
                
                # 检查是否被选中
                if self.client.selected_room_id == room['room_id']:
                    pygame.draw.rect(self.screen, (50, 50, 50), room_rect)
                
                self.screen.blit(room_text, (15, y_offset + 5))
                y_offset += 35
            
            # 绘制按钮
            self.draw_button(self.create_room_button_rect, "创建房间")
            self.draw_button(self.join_room_button_rect, "加入房间")
            self.draw_button(self.refresh_room_button_rect, "刷新列表")
            self.draw_button(self.reconnect_button_rect, "断线重连")
            
        except Exception as e:
            print(f"绘制大厅界面时出错: {e}")
    
    def draw_button(self, rect, text):
        """绘制按钮"""
        mouse_pos = pygame.mouse.get_pos()
        button_color = self.colors['button_hover'] if rect.collidepoint(mouse_pos) else self.colors['button']
        
        pygame.draw.rect(self.screen, button_color, rect)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
        
        try:
            text_surface = self.font.render(text, True, self.colors['button_text'])
            text_rect = text_surface.get_rect(center=rect.center)
            self.screen.blit(text_surface, text_rect)
        except Exception as e:
            print(f"绘制按钮文字时出错: {e}")
    
    def draw_waiting_room(self):
        """绘制等待房间界面"""
        try:
            # 显示房间信息
            room_text = self.font.render(f"房间ID: {self.client.room_id}", True, self.colors['ui_text'])
            self.screen.blit(room_text, (10, 10))
            
            player_text = self.font.render(f"玩家ID: {self.client.player_id}", True, self.colors['ui_text'])
            self.screen.blit(player_text, (10, 50))
            
            # 检查是否是房主（第一个加入房间的玩家）
            if hasattr(self.client, 'room_id') and self.client.room_id:
                # 获取房间中的所有玩家地址
                # 这里简化处理，通过player_id判断是否为房主（player_id为1的是房主）
                if str(self.client.player_id) == "1":
                    # 房主显示开始游戏按钮
                    self.draw_start_button()
                else:
                    # 非房主显示等待文本
                    wait_text = self.font.render("等待房主开始游戏...", True, self.colors['ui_text'])
                    # 在原来按钮的位置显示等待文本
                    wait_text_rect = wait_text.get_rect(center=self.start_button_rect.center)
                    self.screen.blit(wait_text, wait_text_rect)
                
        except Exception as e:
            print(f"绘制等待房间界面时出错: {e}")
    
    def draw_terrain(self):
        tile_size = 64
        for x in range(0, self.window_width, tile_size):
            for y in range(0, self.window_height, tile_size):
                color = self.colors['terrain1'] if (x//tile_size + y//tile_size) % 2 == 0 else self.colors['terrain2']
                pygame.draw.rect(self.screen, color, (x, y, tile_size, tile_size))
    
    def draw_unit(self, unit):
        player_color_key = f'player{unit["player_id"]}'
        player_color = self.colors.get(player_color_key, (128, 128, 128))  # 默认灰色
        x, y = unit['x'], unit['y']
        
        # 绘制单位形状
        if unit['type'] == 'miner':
            pygame.draw.circle(self.screen, player_color, (x, y), 10)
        elif unit['type'] == 'tank':
            pygame.draw.polygon(self.screen, player_color, [
                (x, y-12),
                (x-10, y+8),
                (x+10, y+8)
            ])
        else:
            pygame.draw.circle(self.screen, player_color, (x, y), 8)
        
        # 绘制血条
        health_width = 30
        health_ratio = unit['health'] / 100
        pygame.draw.rect(self.screen, (255, 0, 0), (x-15, y-20, health_width, 4))
        pygame.draw.rect(self.screen, (0, 255, 0), (x-15, y-20, health_width * health_ratio, 4))
        
        if unit['id'] in self.client.selected_units:
            pygame.draw.circle(self.screen, self.colors['selected'], (x, y), 15, 2)
    
    def draw_building(self, building):
        player_color_key = f'player{building["player_id"]}'
        player_color = self.colors.get(player_color_key, (128, 128, 128))  # 默认灰色
        x, y = building['x'], building['y']
        
        if building['type'] == 'base':
            pygame.draw.rect(self.screen, player_color, (x-40, y-30, 80, 60))
        
        health_width = 80
        health_ratio = building['health'] / 1000
        pygame.draw.rect(self.screen, (255, 0, 0), (x-40, y-40, health_width, 6))
        pygame.draw.rect(self.screen, (0, 255, 0), (x-40, y-40, health_width * health_ratio, 6))
    
    def draw_ui(self, input_handler=None):
        try:
            # 帧信息
            frame_text = self.font.render(f"逻辑帧: {self.client.current_frame} (服务器帧: {self.client.server_frame})", True, self.colors['ui_text'])
            self.screen.blit(frame_text, (10, 10))
            
            # 网络状态
            pending = len(self.client.pending_inputs)
            network_text = self.font.render(f"待确认输入: {pending}", True, self.colors['ui_text'])
            self.screen.blit(network_text, (10, 40))
            
            # Ping值显示
            ping_text = self.font.render(f"Ping: {self.client.ping:.0f}ms", True, self.colors['ui_text'])
            self.screen.blit(ping_text, (10, 130))
            
            # FPS显示
            fps_text = self.font.render(f"FPS: {self.fps:.1f}", True, self.colors['ui_text'])
            self.screen.blit(fps_text, (10, 160))
            
            # 逻辑帧率显示
            logic_fps_text = self.font.render(f"逻辑帧率: {self.client.logic_fps:.1f} FPS", True, self.colors['ui_text'])
            self.screen.blit(logic_fps_text, (10, 190))
            
            # 连接状态
            status = "已连接" if self.client.connected else "未连接"
            if self.client.is_reconnecting:
                status = "重连中..."
            status_text = self.font.render(f"状态: {status}", True, self.colors['ui_text'])
            self.screen.blit(status_text, (10, 70))
            
            if self.client.player_id is not None:
                player_text = self.font.render(f"玩家ID: {self.client.player_id}", True, self.colors['ui_text'])
                self.screen.blit(player_text, (10, 100))
            
            if self.client.selected_units:
                select_text = self.font.render(f"选中单位: {len(self.client.selected_units)}", True, self.colors['ui_text'])
                self.screen.blit(select_text, (self.window_width - 150, 10))
        except Exception as e:
            print(f"渲染文本时出错: {e}")
            # 渲染简单的错误提示文本
            error_text = self.font.render("渲染错误", True, self.colors['ui_text'])
            self.screen.blit(error_text, (10, 10))
        
        # 绘制选择矩形
        if input_handler:
            selection_rect = input_handler.get_selection_rect()
            if selection_rect:
                left, top, right, bottom = selection_rect
                pygame.draw.rect(self.screen, self.colors['selected'], 
                               (left, top, right-left, bottom-top), 2)
        
        # 绘制开始游戏按钮（仅在游戏未开始且已连接且是房主时显示）
        if self.client.connected and not self.client.game_started:
            # 只有房主才显示开始游戏按钮
            if str(self.client.player_id) == "1":
                self.draw_start_button()
            else:
                # 非房主显示等待文本
                try:
                    wait_text = self.font.render("等待房主开始游戏...", True, self.colors['ui_text'])
                    # 在原来按钮的位置显示等待文本
                    wait_text_rect = wait_text.get_rect(center=self.start_button_rect.center)
                    self.screen.blit(wait_text, wait_text_rect)
                except Exception as e:
                    print(f"渲染等待文本时出错: {e}")
        
        # 绘制断线重连按钮（在游戏房间中且未重连中时显示）
        if not self.client.in_lobby and not self.client.is_reconnecting:
            self.draw_reconnect_button()
    
    def draw_start_button(self):
        """绘制开始游戏按钮"""
        # 检查鼠标是否悬停在按钮上
        mouse_pos = pygame.mouse.get_pos()
        button_color = self.start_button_hover_color if self.start_button_rect.collidepoint(mouse_pos) else self.start_button_color
        
        # 绘制按钮
        pygame.draw.rect(self.screen, button_color, self.start_button_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), self.start_button_rect, 2)  # 边框
        
        # 绘制按钮文字
        try:
            start_text = self.font.render("开始游戏", True, self.start_button_text_color)
            text_rect = start_text.get_rect(center=self.start_button_rect.center)
            self.screen.blit(start_text, text_rect)
        except Exception as e:
            print(f"渲染按钮文字时出错: {e}")
            # 如果文字渲染失败，只绘制按钮框
            pass
    
    def draw_reconnect_button(self):
        """绘制断线重连按钮"""
        # 检查鼠标是否悬停在按钮上
        mouse_pos = pygame.mouse.get_pos()
        button_color = self.colors['reconnect_button_hover'] if self.reconnect_button_rect.collidepoint(mouse_pos) else self.colors['reconnect_button']
        
        # 绘制按钮
        pygame.draw.rect(self.screen, button_color, self.reconnect_button_rect)
        pygame.draw.rect(self.screen, (255, 255, 255), self.reconnect_button_rect, 2)  # 边框
        
        # 绘制按钮文字
        try:
            reconnect_text = self.font.render("断线重连", True, self.colors['button_text'])
            text_rect = reconnect_text.get_rect(center=self.reconnect_button_rect.center)
            self.screen.blit(reconnect_text, text_rect)
        except Exception as e:
            print(f"渲染按钮文字时出错: {e}")
            # 如果文字渲染失败，只绘制按钮框
            pass

class InputHandler:
    def __init__(self, client, renderer):
        self.client = client
        self.renderer = renderer
        self.dragging = False
        self.drag_start = (0, 0)
        self.drag_end = (0, 0)
        self.drag_threshold = 5  # 拖拽阈值，小于该距离认为是点击
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            elif event.type == pygame.VIDEORESIZE:
                # 窗口大小调整事件由GameRenderer处理
                pass
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # 检查是否点击了大厅界面的按钮
                    if self.client.in_lobby:
                        if self.renderer.create_room_button_rect.collidepoint(event.pos):
                            self.client.create_room("Player")
                        elif self.renderer.join_room_button_rect.collidepoint(event.pos):
                            if self.client.selected_room_id:
                                self.client.join_room(self.client.selected_room_id, "Player")
                        elif self.renderer.refresh_room_button_rect.collidepoint(event.pos):
                            self.client.get_room_list()
                        elif self.renderer.reconnect_button_rect.collidepoint(event.pos):
                            # 大厅界面点击断线重连按钮
                            self.client.force_reconnect()
                        else:
                            # 检查是否点击了房间列表项
                            self.handle_room_list_click(event.pos)
                    # 检查是否点击了开始游戏按钮（只有房主才能点击）
                    elif (hasattr(self.renderer, 'start_button_rect') and 
                        self.renderer.start_button_rect.collidepoint(event.pos) and
                        self.client.connected and not self.client.game_started and
                        str(self.client.player_id) == "1"):  # 只有房主可以点击开始游戏
                        self.client.send_start_game_request()
                    # 检查是否点击了断线重连按钮
                    elif (hasattr(self.renderer, 'reconnect_button_rect') and
                        self.renderer.reconnect_button_rect.collidepoint(event.pos) and
                        not self.client.in_lobby):
                        # 游戏界面点击断线重连按钮
                        self.client.force_reconnect()
                    else:
                        self.handle_left_click(event.pos)
                elif event.button == 3:
                    self.handle_right_click(event.pos)
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and self.dragging:
                    self.handle_drag_end(event.pos)
            
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    self.drag_end = event.pos
            
            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event.key)
        
        return True
    
    def handle_room_list_click(self, pos):
        """处理房间列表点击"""
        # 检查点击位置是否在房间列表项上
        y_offset = 50
        for room in self.client.room_list:
            room_rect = pygame.Rect(10, y_offset, 300, 30)
            if room_rect.collidepoint(pos):
                self.client.selected_room_id = room['room_id']
                break
            y_offset += 35
    
    def handle_left_click(self, pos):
        self.dragging = True
        self.drag_start = pos
        self.drag_end = pos
    
    def handle_right_click(self, pos):
        if not self.client.selected_units:
            return
        
        input_data = {
            'type': 'move_units',
            'unit_ids': self.client.selected_units,
            'x': pos[0],
            'y': pos[1]
        }
        
        self.client.input_buffer.append(input_data)
    
    def handle_drag_end(self, pos):
        self.dragging = False
        
        # 计算拖拽距离
        drag_distance = ((self.drag_start[0] - pos[0])**2 + (self.drag_start[1] - pos[1])**2)**0.5
        
        # 如果拖拽距离小于阈值，则认为是点击操作
        if drag_distance < self.drag_threshold:
            self.handle_click_selection(pos)
        else:
            # 原有的框选逻辑
            self.handle_box_selection(pos)
    
    def handle_click_selection(self, pos):
        """处理点击选择单个单位"""
        # 清空之前选择的单位
        self.client.selected_units.clear()
        
        # 查找点击位置附近的单位（在一定半径内）
        click_radius = 20
        closest_unit = None
        closest_distance = float('inf')
        
        for unit in self.client.game_state['units'].values():
            if same_player_id(unit['player_id'], self.client.player_id):
                distance = ((unit['x'] - pos[0])**2 + (unit['y'] - pos[1])**2)**0.5
                if distance <= click_radius and distance < closest_distance:
                    closest_unit = unit
                    closest_distance = distance
        
        # 如果找到单位，则选中它
        if closest_unit:
            self.client.selected_units.append(closest_unit['id'])
    
    def handle_box_selection(self, pos):
        """处理框选单位"""
        self.drag_end = pos
        
        left = min(self.drag_start[0], self.drag_end[0])
        right = max(self.drag_start[0], self.drag_end[0])
        top = min(self.drag_start[1], self.drag_end[1])
        bottom = max(self.drag_start[1], self.drag_end[1])
        
        self.client.selected_units.clear()
        for unit in self.client.game_state['units'].values():
            if same_player_id(unit['player_id'], self.client.player_id) and left <= unit['x'] <= right and top <= unit['y'] <= bottom:
                self.client.selected_units.append(unit['id'])
    
    def handle_keydown(self, key):
        if key == pygame.K_a:
            self.client.selected_units = []
            for unit in self.client.game_state['units'].values():
                if same_player_id(unit['player_id'], self.client.player_id):
                    self.client.selected_units.append(unit['id'])
        
        elif key == pygame.K_t:
            if self.client.player_id is not None:
                # 确保使用整数形式的player_id来构造base_id
                base_id = f"{int(self.client.player_id)}_base"
                if base_id in self.client.game_state['buildings']:
                    input_data = {
                        'type': 'produce_unit',
                        'building_id': base_id,
                        'unit_type': 'tank'
                    }
                    self.client.input_buffer.append(input_data)
    
    def get_selection_rect(self):
        """
        获取选择矩形的坐标 (left, top, right, bottom)
        如果没有拖拽选择，则返回 None
        """
        if self.dragging and ((self.drag_start[0] - self.drag_end[0])**2 + (self.drag_start[1] - self.drag_end[1])**2)**0.5 >= self.drag_threshold:
            left = min(self.drag_start[0], self.drag_end[0])
            right = max(self.drag_start[0], self.drag_end[0])
            top = min(self.drag_start[1], self.drag_end[1])
            bottom = max(self.drag_start[1], self.drag_end[1])
            return (left, top, right, bottom)
        return None
    
    def draw_selection_rectangle(self):
        # 这个方法已废弃，绘制逻辑已移到 GameRenderer.draw_ui 中
        pass

def main():
    pygame.init()
    
    client = FrameSyncClient()
    renderer = GameRenderer(client)
    input_handler = InputHandler(client, renderer)
    
    # 将input_handler添加到client中，以便renderer可以访问
    client.input_handler = input_handler
    
    # 获取初始房间列表
    client.get_room_list()
    
    running = True
    while running:
        running = input_handler.handle_events()
        client.run_frame()
        renderer.render()
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()