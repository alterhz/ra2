import pygame; pygame.init(); 
fonts = pygame.font.get_fonts(); 
chinese_fonts = [f for f in fonts if any(c in f for c in ['song', 'ming', 'kai', 'hei', 'fang', 'yahei', 'sim'])]; 
print('支持中文字体:', chinese_fonts[:10])