# 帧同步服务器和客户端核心逻辑

## 1. 服务器帧同步核心逻辑

### 1.1 服务器接收帧

服务器通过 `_handle_player_input` 方法接收客户端发送的帧输入数据：

```
def _handle_player_input(self, addr: tuple, data: dict):
    # 检查玩家是否已连接
    if addr not in self.player_rooms:
        return
    
    room_id = self.player_rooms[addr]
    room = self.rooms[room_id]
    
    if addr not in room.players:
        return
    
    player = room.players[addr]
    frame = data['frame']
    inputs = data['inputs']
    
    # 检查帧是否在有效范围（current_frame-3 到 current_frame+3）
    if frame < room.current_frame - 3 or frame > room.current_frame + 3:
        print(f"忽略超出范围的输入: 来自 {addr} 的帧 {frame}，有效范围 [{room.current_frame-3}, {room.current_frame+3}]")
        return
    
    # 检查是否已经处理过（存在于history_frames中）
    if frame in room.history_frames:
        print(f"忽略已处理的输入: 来自 {addr} 的帧 {frame}, data:{data}")
        return
    
    # 存储输入
    if frame not in room.frame_inputs:
        room.frame_inputs[frame] = {}
    room.frame_inputs[frame][player['id']] = inputs

    if len(inputs) > 0:
        print(f"收到来自 {addr} 的输入数据: {data}, 当前帧: {room.current_frame}, player_id: {player['id']}")
    
    # 记录最后输入帧
    player['last_input_frame'] = frame
    
    # 发送输入确认
    ack_data = {
        'type': 'input_ack',
        'frame': frame,
        'server_frame': room.current_frame,
        'player_id': player['id']
    }
    self.udp.send_reliable(ack_data, addr)
```

1. **帧范围检查**：服务器只接受当前帧前后3帧范围内的输入（[current_frame-3, current_frame+3]）
2. **重复帧检查**：如果帧已存在于 history_frames 中，则忽略该输入
3. **存储输入**：将输入存储在 frame_inputs 中，按帧号和玩家ID索引
4. **发送确认**：向客户端发送 input_ack 确认消息

### 1.2 服务器广播帧

服务器通过 `run_frame` 方法处理并广播帧：

```
def run_frame(self):
    """运行所有房间的一帧"""
    for room_id, room in list(self.rooms.items()):
        if not room.game_started:
            continue
        
        current_time = time.time()
        if current_time - room.last_frame_time < room.frame_interval:
            continue
        
        room.last_frame_time += room.frame_interval
        
        # 按顺序处理延迟帧：current_frame-3, current_frame-2, current_frame-1
        for offset in [3, 2, 1]:
            target_frame = room.current_frame - offset
            if target_frame < 0:
                continue  # 跳过负帧
            
            # 检查该帧是否已处理
            if target_frame in room.history_frames:
                continue
            
            # 确保target_frame在frame_inputs中
            if target_frame not in room.frame_inputs:
                room.frame_inputs[target_frame] = {}

            # 处理current_frame-3帧，补空帧
            if offset == 3:
                for addr, player in list(room.players.items()):
                    if player['id'] not in room.frame_inputs[target_frame]:
                        room.frame_inputs[target_frame][player['id']] = []
            
            # 检查是否所有玩家都提交了该帧的输入
            num_players = len(room.players)
            if len(room.frame_inputs[target_frame]) == num_players:
                # 存储该帧输入到history_frames
                room.history_frames[target_frame] = dict(room.frame_inputs[target_frame])
                # 同步该帧到客户端
                self._sync_delay_frame_to_client(room, target_frame)
            else:
                # 如果当前offset的帧未集齐，停止处理后续offset的帧
                break

        # 清理旧帧
        old_frames = [f for f in room.frame_inputs if f < room.current_frame - 60]
        for f in old_frames:
            del room.frame_inputs[f]

        room.current_frame += 1
```

服务器通过 `_sync_delay_frame_to_client` 方法将帧输入广播给房间内所有客户端：

```
def _sync_delay_frame_to_client(self, room: GameRoom, frame: int):
    """同步指定帧到客户端"""
    # 使用history_frames中存储的已确认输入
    if frame not in room.history_frames:
        return
    
    frame_data = {
        'type': 'frame_inputs',
        'frame': frame,
        'inputs': room.history_frames[frame]
    }

    for addr in room.players:
        self.udp.send_reliable(frame_data, addr)

    # 检查非空帧
    not_empty_frame = False
    for player_id, player_inputs in frame_data['inputs'].items():
        if len(player_inputs) > 0:
            not_empty_frame = True
    
    if not_empty_frame:
        print(f"房间 {room.room_id} 广播非空帧: {frame_data}")
```

1. **帧率控制**：按照设定的帧率（20 FPS）推进游戏逻辑
2. **延迟帧处理**：优先处理当前帧之前的帧（current_frame-3, current_frame-2, current_frame-1）
3. **帧完整性检查**：确保所有玩家都提交了指定帧的输入后才进行广播
4. **帧广播**：将帧输入广播给房间内所有客户端
5. **历史帧存储**：将已广播的帧存储在 history_frames 中，用于后续可能的同步请求

## 2. 客户端帧同步核心逻辑

### 2.1 客户端接收帧

客户端通过 `_handle_frame_inputs` 方法接收服务器广播的帧数据：

```
def _handle_frame_inputs(self, data: dict):
    """处理帧输入"""
    frame = data['frame']
    inputs = data['inputs']

    # inputs数组中的元素的数组大于0，则说明有输入
    hasInput = False
    for player_id, player_inputs in inputs.items():
        for input_data in player_inputs:
            if len(input_data) > 0:
                hasInput = True
                break
        

    if hasInput:
        print(f"收到帧输入: {data}, current_frame: {self.current_frame}")
    
    # 存储输入
    self.received_inputs[frame] = inputs
    # print(f"保存帧输入: {frame}, inputs: {inputs}")
    
    # 更新server_frame
    if frame > self.server_frame:
        self.server_frame = frame
```

1. **存储帧数据**：将接收到的帧数据存储在 received_inputs 中
2. **更新服务器帧号**：更新 server_frame 为接收到的最大帧号
3. **日志记录**：对非空输入帧进行日志输出

### 2.2 客户端处理帧

客户端通过 `run_frame` 和 `run_one_frame` 方法处理游戏帧：

```
def run_frame(self):
    """运行客户端帧逻辑"""
    current_time = time.time()
    
    if not self.connected:
        return False
    
    if not self.game_started:
        # 即使游戏未开始也发送ping
        self.send_ping()
        return False
    
    # 锁帧
    if self.current_frame >= self.server_frame:
        return False
    
    # 服务器帧与当前帧的差
    gap = self.server_frame - self.current_frame

    if gap >= 10:
        # 多处理30帧
        run_frames = min(gap - 1, 30)
        print(f"服务器帧与当前帧的差过大: {gap}，多处理{run_frames}帧，当前帧： {self.current_frame}")
        for i in range(run_frames):
            self.run_one_frame()
        should_process_frame = True
    elif gap >= 2:
        # 多处理一帧
        if gap > 3:
            print(f"服务器帧与当前帧的差超过2帧，每帧多处理一帧: {gap}，当前帧： {self.current_frame}")
        self.run_one_frame()
        should_process_frame = True
    else:
        # 限制帧率
        elapsed_time = current_time - self.last_frame_time
        if elapsed_time >= self.frame_interval:
            self.last_frame_time = current_time
            should_process_frame = True
        else:
            should_process_frame = False

    if not should_process_frame:
        self.send_ping()
        return False
    
    # 每帧都上报输入，包括空输入
    self.send_inputs()
    
    self.run_one_frame()

    return True
```

```
def run_one_frame(self):
    if self.current_frame in self.received_inputs:
        self.apply_inputs(self.current_frame)
    else:
        print(f"2没有输入帧: {self.current_frame}")
    
    # 更新游戏状态
    self.update_game_state()
    
    old_pending = [f for f in self.pending_inputs if f < self.current_frame - 20]
    for frame in old_pending:
        del self.pending_inputs[frame]
    
    self.current_frame += 1
    # 只有当真正处理了一个游戏逻辑帧后，才增加逻辑帧计数
    self.logic_frame_count += 1
```

1. **锁帧机制**：当 current_frame >= server_frame 时暂停处理，等待服务器推进
2. **追帧机制**：
   - 当服务器帧与当前帧差距>=10帧时，一次处理最多30帧
   - 当差距>=2帧时，一次多处理一帧
   - 正常情况下按20 FPS速率处理
3. **应用输入**：通过 apply_inputs 方法应用存储在 received_inputs 中的帧输入
4. **更新游戏状态**：通过 update_game_state 方法更新单位位置等游戏状态

### 2.3 客户端发送帧

客户端通过 `send_inputs` 方法发送输入到服务器：

```
def send_inputs(self):
    """发送输入到服务器"""
    if not self.connected or not self.game_started:
        return
    
    predicted_frame = self.server_frame + 2

    # 判断pending_inputs是否存在预测帧
    if predicted_frame in self.pending_inputs:
        print(f"预测帧已存在: {predicted_frame}")
        return
        
    input_data = {
        'type': 'player_input',
        'frame': predicted_frame,
        'inputs': self.input_buffer.copy()
    }

    # 非空帧打印日志
    if len(input_data['inputs']) > 0:
        print(f"发送非空输入: {input_data}, 当前帧: {self.current_frame}")
    
    # 使用可靠传输发送
    self.udp.send_reliable(input_data, self.server_addr)
    
    # 添加到等待确认列表
    self.pending_inputs[predicted_frame] = self.input_buffer.copy()
    
    # 清空输入缓冲区
    self.input_buffer.clear()
```

1. **预测帧号**：发送目标帧号为 server_frame + 2
2. **避免重复发送**：检查 pending_inputs 中是否已存在该帧
3. **发送输入**：将 input_buffer 中的输入发送给服务器
4. **等待确认**：将发送的帧添加到 pending_inputs 中，等待服务器确认

## 3. 帧同步机制总结

### 3.1 核心同步机制

1. **服务器权威性**：服务器负责收集所有客户端输入并广播给所有客户端
2. **延迟补偿**：服务器优先处理延迟帧（current_frame-3等），确保输入完整性
3. **锁帧机制**：客户端在未收到服务器新帧时暂停游戏逻辑
4. **追帧机制**：当客户端落后较多时，通过批量处理帧来追赶

### 3.2 数据结构

- **服务器端**：
  - frame_inputs：存储当前待处理的帧输入
  - history_frames：存储已处理并广播的帧输入历史

- **客户端端**：
  - received_inputs：存储从服务器接收到的帧输入
  - pending_inputs：存储已发送但未确认的帧输入
  - input_buffer：存储本地用户输入缓冲区

### 3.3 关键帧概念

1. **current_frame**：当前正在处理的游戏逻辑帧
2. **server_frame**：客户端已知的服务器最新帧
3. **预测帧**：客户端预测的下一个输入帧号（server_frame + 2）