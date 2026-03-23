import os
import json
from datetime import datetime

class GameLogger:
    """游戏日志记录器：负责将公屏聊天和 AI 的内心 OS 持久化到本地"""
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # 以当前时间作为本次对局的日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_dir, f"avalon_game_{timestamp}.txt")
        
        self._write_to_file(f"=== 赛博阿瓦隆 对局日志 [{timestamp}] ===\n")

    def _write_to_file(self, content: str):
        """底层的写入方法"""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def log_speech(self, sender: str, content: str):
        """记录公屏上的可见发言"""
        log_line = f"📢 [公屏] {sender}: {content}"
        self._write_to_file(log_line)
        print(log_line) # 同步在控制台打印

    def log_thought(self, agent_name: str, role: str, energy: int, thought: str):
        """记录 AI 极其关键的内心 OS (只有上帝视角的日志里能看到)"""
        log_line = f"  🧠 [内心OS | {agent_name} ({role}) | 能量:{energy}] -> {thought}"
        self._write_to_file(log_line)

    def log_system(self, content: str):
        """记录系统级的事件 (比如开始投票、任务成败)"""
        log_line = f"\n⚙️ [系统] {content}\n"
        self._write_to_file(log_line)
        print(log_line)