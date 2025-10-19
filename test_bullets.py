#!/usr/bin/env python3
"""
子弹功能测试脚本
测试单位每秒发射一颗子弹到鼠标位置的功能
"""

import pygame
import sys
import math
import time
from client.frame_sync_client import FrameSyncClient
from client.game_renderer import GameRenderer
from client.input_handler import InputHandler
from client.bullet import Bullet


def test_bullets():
    """
    测试子弹功能
    """
    pygame.init()
    
    # 创建客户端
    client = FrameSyncClient()
    renderer = GameRenderer(client)
    input_handler = InputHandler(client, renderer)
    
    # 将input_handler添加到client中
    client.input_handler = input_handler
    
    # 模拟选中单位
    client.selected_units = ["1_0"]  # 假设这是玩家1的第一个单位
    
    # 创建一个测试单位
    from client.unit import Unit
    test_unit = Unit(
        unit_id="1_0",
        player_id=1,
        unit_type='tank',
        x=400,
        y=300
    )
    client.game_state['units']["1_0"] = test_unit
    
    print("开始子弹测试...")
    print("按ESC键退出测试")
    print("移动鼠标到屏幕上的不同位置，观察单位是否每秒发射子弹")
    
    # 主循环
    clock = pygame.time.Clock()
    running = True
    
    while running:
        # 处理事件
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
        
        # 更新游戏状态
        client.update_game_state()
        
        # 渲染
        renderer.screen.fill((0, 0, 0))  # 黑色背景
        
        # 绘制单位
        renderer.draw_unit(test_unit)
        
        # 绘制所有子弹
        for bullet in client.bullets.values():
            bullet.draw(renderer.screen)
        
        # 显示说明文字
        try:
            font = pygame.font.SysFont(None, 24)
            text = font.render("移动鼠标测试子弹发射功能，按ESC退出", True, (255, 255, 255))
            renderer.screen.blit(text, (10, 10))
            
            # 显示子弹数量
            bullet_count_text = font.render(f"活动子弹数量: {len(client.bullets)}", True, (255, 255, 255))
            renderer.screen.blit(bullet_count_text, (10, 40))
        except Exception as e:
            print(f"渲染文本时出错: {e}")
        
        pygame.display.flip()
        clock.tick(60)  # 60 FPS
    
    pygame.quit()
    print("子弹测试完成")


if __name__ == "__main__":
    test_bullets()