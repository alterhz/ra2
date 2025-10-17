class GridManager:
    """
    网格管理器，用于处理单位在网格中的位置，防止单位重叠
    每个20x20像素的格子只能存在一个单位
    """
    
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

    def bind_unit_to_grid(self, unit, teleport=False):
        """
        将单位绑定到网格位置
        :param unit: 要绑定的单位对象
        :param teleport: 是否瞬移，如果为True，则单位会立即移动到目标位置
        """
        # 更新单位的网格坐标
        unit.update_grid_position()
        
        # 自己已经绑定目标格子，则直接返回
        if unit.id in self.unit_to_grid:
            current_grid = self.unit_to_grid[unit.id]
            if current_grid[0] == unit.grid_x and current_grid[1] == unit.grid_y:
                # print(f"{unit.id} is already at ({unit.x}, {unit.y}), from grid ({unit.grid_x}, {unit.grid_y})")
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
            
            if teleport:
                # 瞬移模式：直接设置单位位置
                unit.x = to_x
                unit.y = to_y
                unit.target_x = to_x
                unit.target_y = to_y
                unit.is_moving = False
            else:
                # 正常模式：使用移动方法
                unit.move_to(to_x, to_y)
                
            unit.grid_x = new_grid_x
            unit.grid_y = new_grid_y
            # print(f"{unit.id} moved from ({old_x}, {old_y}) to ({unit.x}, {unit.y}), from grid ({old_grid_x}, {old_grid_y}) to ({new_grid_x}, {new_grid_y})")

        
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

    def generate_search_offsets(self, max_radius):
        """
        动态生成搜索偏移量
        按照顺时针螺旋方式生成坐标偏移
        """
        offsets = [(0, 0)]  # 首先是中心点
        
        # 按照半径逐层生成偏移量
        for radius in range(1, max_radius + 1):
            # 从上边开始，顺时针生成
            # 上边：从左到右
            for x in range(-radius, radius + 1):
                offsets.append((x, -radius))
            
            # 右边：从上到下（排除顶点）
            for y in range(-radius + 1, radius):
                offsets.append((radius, y))
            
            # 下边：从右到左
            for x in range(radius, -radius - 1, -1):
                offsets.append((x, radius))
            
            # 左边：从下到上（排除顶点）
            for y in range(radius - 1, -radius, -1):
                offsets.append((-radius, y))
        
        return offsets

    def find_free_position(self, center_x, center_y, max_radius=3):
        """
        查找中心位置附近空闲的网格位置
        按照顺时针螺旋方向查找
        """
        search_offsets = self.generate_search_offsets(max_radius)
        
        for dx, dy in search_offsets:
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