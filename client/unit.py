import math
import pygame


class Unit:
    def __init__(self, unit_id, player_id, unit_type, x, y, target_x=None, target_y=None, health=100, speed=2):
        self.id = unit_id
        self.player_id = player_id
        self.type = unit_type
        self.x = x
        self.y = y
        self.target_x = target_x if target_x is not None else x
        self.target_y = target_y if target_y is not None else y
        self.health = health
        # 使用定点数表示速度，实际速度 = speed / 1000
        self.speed = speed
        # 添加格子坐标属性
        self.grid_x = x // 32
        self.grid_y = y // 32
        self.is_moving = False
        """
        添加方向属性，0-7表示8个方向，
        0=(-157.5,157.5), 
        1=(-157.7, -112.5), 
        2=(-112.5, -67.5), 
        3=(-67.5, -22.5), 
        4=(-22.5, 22.5), 
        5=(22.5, 67.5), 
        6=(67.5, 112.5), 
        7=(112.5, 157.5)
        """
        self.direction = 0
        # 添加透明度属性，用于实现单位死亡时的淡出效果
        self.alpha = 255
        # 添加自动攻击相关属性
        self.last_attack_time = 0  # 上次攻击时间
        # 使用定点数表示攻击间隔，实际间隔 = attack_interval / 1000 秒
        self.attack_interval = 1000  # 攻击间隔（毫秒）
        self.attack_range = 100  # 攻击范围（像素）
    
    def move_to(self, target_x, target_y):
        """
        设置单位的移动目标位置
        """
        # 移动开始时，解绑格子
        self.is_moving = True
        self.target_x = target_x
        self.target_y = target_y
        
        # 计算移动方向, 将角度转换为8个方向之一 (0-7)
        self.direction = self.cal_direction(self.x, self.y, target_x, target_y)
            
    def update_position(self):
        """
        更新单位的位置，朝目标位置移动
        """
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        # 使用定点数运算计算距离
        distance_sq = dx * dx + dy * dy
        # 为了避免浮点运算，使用近似方法计算平方根
        distance = int(math.sqrt(distance_sq))

        if distance > 2:
            # 使用定点数运算进行移动
            move_distance = min(self.speed, distance)
            if distance > 0:
                self.x += (dx * move_distance) // distance
                self.y += (dy * move_distance) // distance
        else:
            # 移动停止时，绑定格子
            self.is_moving = False
            self.x = self.target_x
            self.y = self.target_y
            
        # 如果单位血量为0，逐渐降低透明度实现淡出效果
        if self.health <= 0:
            self.alpha = max(0, self.alpha - 5)  # 每次减少5点透明度，直到完全透明

    def to_dict(self):
        """
        将单位对象转换为字典格式，用于网络传输和存储
        """
        return {
            'id': self.id,
            'player_id': self.player_id,
            'type': self.type,
            'x': self.x,
            'y': self.y,
            'target_x': self.target_x,
            'target_y': self.target_y,
            'health': self.health,
            'speed': self.speed,
            'direction': self.direction
        }

    @classmethod
    def from_dict(cls, data):
        """
        从字典数据创建单位对象
        """
        unit = cls(
            unit_id=data['id'],
            player_id=data['player_id'],
            unit_type=data['type'],
            x=data['x'],
            y=data['y'],
            target_x=data.get('target_x', data['x']),
            target_y=data.get('target_y', data['y']),
            health=data.get('health', 100),
            speed=data.get('speed', 2)
        )
        unit.direction = data.get('direction', 0)
        return unit

    def update_grid_position(self):
        """
        更新单位所在的格子位置
        """
        self.grid_x = self.x // 32
        self.grid_y = self.y // 32

    def direction_to_sprite_index(self, direction):
        """
        将方向转换为索引
        0 -> 4
        1 -> 3
        2 -> 2
        3 -> 1
        4 -> 0
        5 -> 7
        6 -> 6
        7 -> 5
        """
        return (direction + 4) % 8
    
    def cal_direction(self, x, y, target_x, target_y):
        """
        计算两点之间的方向
        """
        dx = target_x - x
        dy = target_y - y
        # 为了避免浮点运算，直接使用 atan2 然后转换
        angle = math.atan2(dy, dx)
        direction = int(((angle + math.pi) / (2 * math.pi)) * 8) % 8
        return direction

    # tostring
    def __str__(self):
        return f"Unit(id={self.id}, player_id={self.player_id}, type={self.type}, x={self.x}, y={self.y}, target_x={self.target_x}, target_y={self.target_y}, health={self.health}, speed={self.speed}, direction={self.direction})"