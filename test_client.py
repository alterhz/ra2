import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.main import start_client

if __name__ == "__main__":
    start_client("127.0.0.1", 8888)