import pygame
import sys
from .frame_sync_client import FrameSyncClient
from .game_renderer import GameRenderer
from .input_handler import InputHandler


def start_client(ip, port):
    pygame.init()
    
    client = FrameSyncClient(ip, port)
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
