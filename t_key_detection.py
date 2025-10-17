import pygame
import sys

# 初始化 Pygame
pygame.init()

# 设置显示窗口
screen = pygame.display.set_mode((400, 300))
pygame.display.set_caption("T键检测示例")

# 设置字体
font = pygame.font.Font(None, 36)

# 主循环
running = True
t_pressed = False

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_t:
                t_pressed = True
                print("T键被按下!")
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_t:
                t_pressed = False
    
    # 填充背景色
    screen.fill((0, 0, 0))
    
    # 显示文本
    if t_pressed:
        text = font.render("T键按下", True, (0, 255, 0))
    else:
        text = font.render("按T键", True, (255, 255, 255))
    
    screen.blit(text, (150, 120))
    
    # 更新显示
    pygame.display.flip()

# 退出 Pygame
pygame.quit()
sys.exit()