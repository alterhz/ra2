class GridManager:
    """
    网格管理器，用于处理单位在网格中的位置，防止单位重叠
    每个20x20像素的格子只能存在一个单位
    """
    
    # 顺时针查找顺序的偏移量，按照题目中提供的顺序：
    # 21,22,23,24,25,
    # 20, 7, 8, 9,10,
    # 19, 6, 1, 2,11,
    # 18, 5, 4, 3,12,
    # 17,16,15,14,13,
    #
    # 对应坐标（以中心点1为原点）：
    SEARCH_OFFSETS = [
        (0, 0),   # 1 - 当前位置
        (0, -1),  # 2 - 上
        (1, -1),  # 3 - 右上
        (1, 0),   # 4 - 右
        (1, 1),   # 5 - 右下
        (0, 1),   # 6 - 下
        (-1, 1),  # 7 - 左下
        (-1, 0),  # 8 - 左
        (-1, -1), # 9 - 左上
        (0, -2),  # 10 - 上2格
        (1, -2),  # 11 - 右上2格
        (2, -2),  # 12 - 右2上2格
        (2, -1),  # 13 - 右2上1格
        (2, 0),   # 14 - 右2格
        (2, 1),   # 15 - 右2下1格
        (2, 2),   # 16 - 右2下2格
        (1, 2),   # 17 - 下2格右1格
        (0, 2),   # 18 - 下2格
        (-1, 2),  # 19 - 下2格左1格
        (-2, 2),  # 20 - 下2格左2格
        (-2, 1),  # 21 - 下1格左2格
        (-2, 0),  # 22 - 左2格
        (-2, -1), # 23 - 上1格左2格
        (-2, -2), # 24 - 上2格左2格
        (-1, -2), # 25 - 上2格左1格
    ]

    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        # 初始化网格，每个格子存储占用该格子的单位ID
        self.grid = {}
        # 存储单位到格子的映射
        self.unit_to_grid = {}

    def get_grid_position(self, x, y):
        """
        获取坐标对应的网格位置
        """
        grid_x = int(x // 20)
        grid_y = int(y // 20)
        return grid_x, grid_y

    def is_position_valid(self, grid_x, grid_y):
        """
        检查网格位置是否有效
        """
        return 0 <= grid_x < self.width and 0 <= grid_y < self.height

    def is_grid_occupied(self, grid_x, grid_y):
        """
        检查网格是否被占用
        """
        return (grid_x, grid_y) in self.grid

    def bind_unit_to_grid(self, unit):
        """
        将单位绑定到网格位置
        """
        # 更新单位的网格坐标
        unit.update_grid_position()
        
        # 自己已经绑定目标格子，则直接返回
        if unit.id in self.unit_to_grid:
            current_grid = self.unit_to_grid[unit.id]
            if current_grid[0] == unit.grid_x and current_grid[1] == unit.grid_y:
                print(f"{unit.id} is already at ({unit.x}, {unit.y}), from grid ({unit.grid_x}, {unit.grid_y})")
                return
        
        # 检查当前位置是否被占用
        if self.is_grid_occupied(unit.grid_x, unit.grid_y):
            # 如果被占用，查找附近空闲位置
            new_grid_x, new_grid_y = self.find_free_position(unit.grid_x, unit.grid_y)
            old_x = unit.x
            old_y = unit.y
            old_grid_x = unit.grid_x
            old_grid_y = unit.grid_y
            # 更新单位的实际坐标
            to_x = new_grid_x * 20 + 10  # 格子中心
            to_y = new_grid_y * 20 + 10
            unit.move_to(to_x, to_y)
            unit.grid_x = new_grid_x
            unit.grid_y = new_grid_y
            print(f"{unit.id} moved from ({old_x}, {old_y}) to ({unit.x}, {unit.y}), from grid ({old_grid_x}, {old_grid_y}) to ({new_grid_x}, {new_grid_y})")

        
        # 绑定单位到网格
        self.grid[(unit.grid_x, unit.grid_y)] = unit.id
        self.unit_to_grid[unit.id] = (unit.grid_x, unit.grid_y)

    def unbind_unit_from_grid(self, unit):
        """
        将单位从网格解绑（开始移动时）
        """
        if unit.id in self.unit_to_grid:
            grid_pos = self.unit_to_grid[unit.id]
            if grid_pos in self.grid:
                del self.grid[grid_pos]
            del self.unit_to_grid[unit.id]

    def find_free_position(self, center_x, center_y):
        """
        查找中心位置附近空闲的网格位置
        按照顺时针方向查找
        """
        for dx, dy in self.SEARCH_OFFSETS:
            new_x = center_x + dx
            new_y = center_y + dy
            
            # 检查位置是否有效且未被占用
            if self.is_position_valid(new_x, new_y) and not self.is_grid_occupied(new_x, new_y):
                return new_x, new_y
        
        # 如果找不到空位置，返回原始位置（这种情况应该很少发生）
        return center_x, center_y

    def update_unit_position(self, unit):
        """
        更新单位位置并处理网格绑定/解绑
        """
        if unit.is_moving:
            # 如果单位正在移动，解绑网格
            self.unbind_unit_from_grid(unit)
        else:
            # 如果单位停止移动，绑定网格
            self.bind_unit_to_grid(unit)