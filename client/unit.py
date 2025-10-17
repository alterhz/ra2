import math


class Unit:
    def __init__(self, unit_id, player_id, unit_type, x, y, target_x=None, target_y=None, health=100, speed=2.0):
        self.id = unit_id
        self.player_id = player_id
        self.type = unit_type
        self.x = x
        self.y = y
        self.target_x = target_x if target_x is not None else x
        self.target_y = target_y if target_y is not None else y
        self.health = health
        self.speed = speed
        # 添加格子坐标属性
        self.grid_x = int(x // 20)
        self.grid_y = int(y // 20)
        self.is_moving = False

    def move_to(self, target_x, target_y):
        """
        设置单位的移动目标位置
        """
        # 移动开始时，解绑格子
        self.is_moving = True
        self.target_x = target_x
        self.target_y = target_y

    def update_position(self):
        """
        更新单位的位置，朝目标位置移动
        """
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 2:
            self.x += (dx / distance) * min(self.speed, distance)
            self.y += (dy / distance) * min(self.speed, distance)
        else:
            # 移动停止时，绑定格子
            self.is_moving = False
            self.x = self.target_x
            self.y = self.target_y

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
            'speed': self.speed
        }

    @classmethod
    def from_dict(cls, data):
        """
        从字典数据创建单位对象
        """
        return cls(
            unit_id=data['id'],
            player_id=data['player_id'],
            unit_type=data['type'],
            x=data['x'],
            y=data['y'],
            target_x=data.get('target_x', data['x']),
            target_y=data.get('target_y', data['y']),
            health=data.get('health', 100),
            speed=data.get('speed', 2.0)
        )

    def update_grid_position(self):
        """
        更新单位所在的格子位置
        """
        self.grid_x = int(self.x // 20)
        self.grid_y = int(self.y // 20)