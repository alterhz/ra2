import pygame
import time
import os


class GameRenderer:
    def __init__(self, client):
        self.window_width = 1024
        self.window_height = 768
        self.client = client
        self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
        pygame.display.set_caption("红警 - 可靠帧同步")
        self.clock = pygame.time.Clock()
        
        # 加载房间背景图片
        self.room_background = None
        self.lobby_background = None
        try:
            # 加载大厅背景图片
            lobby_background_path = os.path.join("resources", "loading.jpg")
            if os.path.exists(lobby_background_path):
                self.lobby_background = pygame.image.load(lobby_background_path)
                print(f"成功加载大厅背景图片: {lobby_background_path}")
            else:
                print(f"大厅背景图片不存在: {lobby_background_path}")
                
            # 加载房间背景图片
            background_path = os.path.join("resources", "background_room.jpg")
            if os.path.exists(background_path):
                self.room_background = pygame.image.load(background_path)
                print(f"成功加载房间背景图片: {background_path}")
            else:
                print(f"房间背景图片不存在: {background_path}")
        except Exception as e:
            print(f"加载背景图片失败: {e}")
        
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
        self.start_button_rect = pygame.Rect(650, 300, 140, 40)
        self.start_button_color = (0, 200, 0)  # 绿色
        self.start_button_hover_color = (0, 255, 0)  # 亮绿色
        self.start_button_text_color = (255, 255, 255)  # 白色
        
        # 断线重连按钮
        self.reconnect_button_rect = pygame.Rect(700, 20, 140, 40)

        # 大厅界面按钮
        self.create_room_button_rect = pygame.Rect(860, 20, 140, 40)
        self.join_room_button_rect = pygame.Rect(860, 80, 140, 40)
        self.refresh_room_button_rect = pygame.Rect(860, 140, 140, 40)
        

        
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
        # 绘制大厅背景图片（如果存在）
        if self.lobby_background:
            # 缩放背景图片以适应窗口大小
            scaled_background = pygame.transform.scale(self.lobby_background, (self.window_width, self.window_height))
            self.screen.blit(scaled_background, (0, 0))
        else:
            # 如果没有背景图片，则使用纯色背景
            self.screen.fill(self.colors['background'])
            
        # 绘制房间列表标题
        try:
            title_text = self.font.render("房间列表", True, self.colors['ui_text'])
            self.screen.blit(title_text, (10, 200))
            
            # 绘制房间列表
            y_offset = 250
            for i, room in enumerate(self.client.room_list):
                room_text = self.font.render(f"{room['room_id']} ({room['player_count']} 玩家)", True, self.colors['ui_text'])
                room_rect = pygame.Rect(10, y_offset, 350, 45)
                
                # 检查是否被选中
                if self.client.selected_room_id == room['room_id']:
                    pygame.draw.rect(self.screen, (50, 50, 50), room_rect)
                else:
                    pygame.draw.rect(self.screen, (0, 50, 50), room_rect)
                
                self.screen.blit(room_text, (15, y_offset + 5))
                y_offset += 50
            
            # 绘制按钮
            self.draw_button(self.create_room_button_rect, "创建房间")
            self.draw_button(self.join_room_button_rect, "加入房间")
            self.draw_button(self.refresh_room_button_rect, "刷新列表")
            # self.draw_button(self.reconnect_button_rect, "断线重连")
            
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
        # 绘制背景图片（如果存在）
        if self.room_background:
            # 缩放背景图片以适应窗口大小
            scaled_background = pygame.transform.scale(self.room_background, (self.window_width, self.window_height))
            self.screen.blit(scaled_background, (0, 0))
        else:
            # 如果没有背景图片，则使用纯色背景
            self.screen.fill(self.colors['background'])
        
        try:
            # 显示房间信息
            room_text = self.font.render(f"房间ID: {self.client.room_id}", True, self.colors['ui_text'])
            self.screen.blit(room_text, (10, 10))
            
            player_text = self.font.render(f"玩家ID: {self.client.player_id}", True, self.colors['ui_text'])
            self.screen.blit(player_text, (10, 50))
            
            # 显示房间内的所有玩家
            y_offset = 100
            players_title = self.font.render("房间内玩家:", True, self.colors['ui_text'])
            self.screen.blit(players_title, (10, y_offset))
            y_offset += 30
            
            # 显示玩家列表
            for player_id, player_info in self.client.players.items():
                # 标记房主
                host_marker = " [房主]" if player_info.get('is_host', False) else ""
                player_name = f"{player_info.get('name', 'Player' + str(player_id))}{host_marker}"
                player_color = player_info.get('color', [255, 255, 255])
                
                # 创建带颜色的玩家文本
                player_text = self.font.render(player_name, True, player_color)
                self.screen.blit(player_text, (20, y_offset))
                y_offset += 25
            
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
        # 检查unit是Unit对象还是字典
        if hasattr(unit, 'player_id'):
            # Unit对象
            player_id = unit.player_id
            unit_type = unit.type
            x, y = unit.x, unit.y
            health = unit.health
        else:
            # 字典格式（为了兼容性）
            player_id = unit["player_id"]
            unit_type = unit["type"]
            x, y = unit["x"], unit["y"]
            health = unit["health"]
            
        player_color_key = f'player{player_id}'
        player_color = self.colors.get(player_color_key, (128, 128, 128))  # 默认灰色
        
        # 绘制单位形状
        if unit_type == 'miner':
            pygame.draw.circle(self.screen, player_color, (x, y), 10)
        elif unit_type == 'tank':
            pygame.draw.polygon(self.screen, player_color, [
                (x, y-12),
                (x-10, y+8),
                (x+10, y+8)
            ])
        else:
            pygame.draw.circle(self.screen, player_color, (x, y), 8)
        
        # 绘制血条
        health_width = 30
        health_ratio = health / 100
        pygame.draw.rect(self.screen, (255, 0, 0), (x-15, y-20, health_width, 4))
        pygame.draw.rect(self.screen, (0, 255, 0), (x-15, y-20, health_width * health_ratio, 4))
        
        # 检查是否选中
        if hasattr(unit, 'id'):
            unit_id = unit.id
        else:
            unit_id = unit['id']
            
        if unit_id in self.client.selected_units:
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