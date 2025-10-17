import pygame
from .frame_sync_client import same_player_id


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
        
        # x, y 都要是20的整数倍
        fixed_pos = (pos[0] // 20 * 20 + 10, pos[1] // 20 * 20 + 10)
        
        input_data = {
            'type': 'move_units',
            'unit_ids': self.client.selected_units,
            'x': fixed_pos[0],
            'y': fixed_pos[1]
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
            # 检查unit是Unit对象还是字典
            if hasattr(unit, 'player_id'):
                # Unit对象
                unit_player_id = unit.player_id
                unit_x, unit_y = unit.x, unit.y
                unit_id = unit.id
            else:
                # 字典格式
                unit_player_id = unit['player_id']
                unit_x, unit_y = unit['x'], unit['y']
                unit_id = unit['id']
                
            if same_player_id(unit_player_id, self.client.player_id):
                distance = ((unit_x - pos[0])**2 + (unit_y - pos[1])**2)**0.5
                if distance <= click_radius and distance < closest_distance:
                    closest_unit = unit
                    closest_distance = distance
        
        # 如果找到单位，则选中它
        if closest_unit:
            # 获取单位ID
            if hasattr(closest_unit, 'id'):
                unit_id = closest_unit.id
            else:
                unit_id = closest_unit['id']
            self.client.selected_units.append(unit_id)
    
    def handle_box_selection(self, pos):
        """处理框选单位"""
        self.drag_end = pos
        
        left = min(self.drag_start[0], self.drag_end[0])
        right = max(self.drag_start[0], self.drag_end[0])
        top = min(self.drag_start[1], self.drag_end[1])
        bottom = max(self.drag_start[1], self.drag_end[1])
        
        self.client.selected_units.clear()
        for unit in self.client.game_state['units'].values():
            # 检查unit是Unit对象还是字典
            if hasattr(unit, 'player_id'):
                # Unit对象
                unit_player_id = unit.player_id
                unit_x, unit_y = unit.x, unit.y
            else:
                # 字典格式
                unit_player_id = unit['player_id']
                unit_x, unit_y = unit['x'], unit['y']
                
            if same_player_id(unit_player_id, self.client.player_id) and left <= unit_x <= right and top <= unit_y <= bottom:
                # 获取单位ID
                if hasattr(unit, 'id'):
                    unit_id = unit.id
                else:
                    unit_id = unit['id']
                self.client.selected_units.append(unit_id)
    
    def handle_keydown(self, key):
        if key == pygame.K_a:
            self.client.selected_units = []
            for unit in self.client.game_state['units'].values():
                # 检查unit是Unit对象还是字典
                if hasattr(unit, 'player_id'):
                    # Unit对象
                    unit_player_id = unit.player_id
                    unit_id = unit.id
                else:
                    # 字典格式
                    unit_player_id = unit['player_id']
                    unit_id = unit['id']
                    
                if same_player_id(unit_player_id, self.client.player_id):
                    self.client.selected_units.append(unit_id)
        
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