import pygame
import os
import math


class Bullet:
    def __init__(self, bullet_id, start_x, start_y, target_x, target_y, speed=5.0):
        self.id = bullet_id
        self.start_x = start_x
        self.start_y = start_y
        self.x = start_x
        self.y = start_y
        self.target_x = target_x
        self.target_y = target_y
        self.speed = speed
        self.is_active = True  # 子弹是否还在飞行中
        self.is_exploding = False  # 是否正在爆炸
        self.explosion_frame = 0  # 爆炸动画帧
        self.max_explosion_frames = 15  # 总共16帧爆炸动画(2行8列，去掉第一帧飞行)
        
        # 计算移动方向
        dx = target_x - start_x
        dy = target_y - start_y
        distance = max(math.sqrt(dx * dx + dy * dy), 0.001)  # 防止除零
        
        # 单位向量
        self.dx = dx / distance
        self.dy = dy / distance
        
        # 加载爆炸效果精灵表
        self.explosion_sprites = None
        self.load_sprites()
    
    def load_sprites(self):
        """加载爆炸效果精灵表"""
        try:
            explosion_path = os.path.join("resources", "effects", "bullet.png")
            if os.path.exists(explosion_path):
                self.explosion_sprites = pygame.image.load(explosion_path).convert_alpha()
                print(f"成功加载子弹爆炸效果: {explosion_path}")
            else:
                print(f"子弹爆炸效果图片不存在: {explosion_path}")
        except Exception as e:
            print(f"加载子弹爆炸效果失败: {e}")
            self.explosion_sprites = None
    
    def update(self):
        """更新子弹状态"""
        if not self.is_active:
            return
            
        if not self.is_exploding:
            # 飞行状态
            # 计算到目标点的距离
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            distance = math.sqrt(dx * dx + dy * dy)
            
            # 如果接近目标点，开始爆炸
            if distance <= self.speed:
                self.x = self.target_x
                self.y = self.target_y
                self.is_exploding = True
            else:
                # 继续飞行
                self.x += self.dx * self.speed
                self.y += self.dy * self.speed
        else:
            # 爆炸状态
            self.explosion_frame += 1
            if self.explosion_frame >= self.max_explosion_frames:
                self.is_active = False  # 爆炸结束，子弹消失
    
    def draw(self, screen):
        """绘制子弹"""
        if not self.is_active:
            return
            
        if not self.is_exploding:
            # 飞行状态，绘制简单圆形或使用第一帧图片
            if self.explosion_sprites:
                # 使用第一张图片作为飞行状态的子弹
                sprite_rect = pygame.Rect(0, 0, 128, 96)  # 第一帧 (1024*192, 2行8列)
                sprite = self.explosion_sprites.subsurface(sprite_rect)
                scaled_sprite = pygame.transform.scale(sprite, (20, 20))
                screen.blit(scaled_sprite, (self.x - 10, self.y - 10))
            else:
                # 回退到简单圆形
                pygame.draw.circle(screen, (255, 255, 0), (int(self.x), int(self.y)), 5)
        else:
            # 爆炸状态，按顺序播放动画
            if self.explosion_sprites and self.explosion_frame < self.max_explosion_frames:
                # 计算当前应该显示哪一帧
                # 总共16帧(2行8列)，跳过第一帧(飞行帧)，所以从第二帧开始
                frame_index = self.explosion_frame
                
                # 计算行列位置 (每行8帧)
                row = (frame_index + 1) // 8  # +1是因为跳过了第一帧
                col = (frame_index + 1) % 8
                
                # 修正行列位置
                sprite_x = col * 128
                sprite_y = row * 96
                
                sprite_rect = pygame.Rect(sprite_x, sprite_y, 128, 96)
                
                # 确保不会越界
                if (sprite_y + 96 <= self.explosion_sprites.get_height() and 
                    sprite_x + 128 <= self.explosion_sprites.get_width()):
                    try:
                        sprite = self.explosion_sprites.subsurface(sprite_rect)
                        scaled_sprite = pygame.transform.scale(sprite, (60, 60))
                        screen.blit(scaled_sprite, (self.x - 30, self.y - 30))
                    except ValueError:
                        # 如果裁剪出错，绘制简单圆形
                        pygame.draw.circle(screen, (255, 100, 0), (int(self.x), int(self.y)), 15)
                else:
                    pygame.draw.circle(screen, (255, 100, 0), (int(self.x), int(self.y)), 15)
            else:
                pygame.draw.circle(screen, (255, 100, 0), (int(self.x), int(self.y)), 15)
    
    def to_dict(self):
        """将子弹对象转换为字典格式，用于网络传输和存储"""
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'start_x': self.start_x,
            'start_y': self.start_y,
            'target_x': self.target_x,
            'target_y': self.target_y,
            'speed': self.speed,
            'is_active': self.is_active,
            'is_exploding': self.is_exploding,
            'explosion_frame': self.explosion_frame
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典数据创建子弹对象"""
        bullet = cls(
            bullet_id=data['id'],
            start_x=data['start_x'],
            start_y=data['start_y'],
            target_x=data['target_x'],
            target_y=data['target_y'],
            speed=data.get('speed', 5.0)
        )
        bullet.x = data['x']
        bullet.y = data['y']
        bullet.is_active = data.get('is_active', True)
        bullet.is_exploding = data.get('is_exploding', False)
        bullet.explosion_frame = data.get('explosion_frame', 0)
        return bullet