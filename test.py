


import math

dx = -10
dy = -4

angle = math.atan2(dy, dx)
# 将角度转换为8个方向之一 (0-7)
direction = int(((angle + 9 / 8 * math.pi) / (2 * math.pi)) * 8) % 8
print(direction)