# core/message_bus.py
import asyncio

class MessageBus:
    """全局消息总线：负责记录聊天历史、广播事件以及管理全局投票状态"""
    def __init__(self, logger, total_agents: int = 8):
        # 记录所有的聊天历史
        self.messages = []
        self.global_history = []
        self.logger = logger
        # 使用 Condition 实现并发广播的条件锁
        self.condition = asyncio.Condition()
        
        # 全局投票列表，记录每个 Agent 的投票状态 (严格对应索引 0-7)
        self.total_agents = total_agents
        self.voting_status = [False] * total_agents  #是否转阶段的列表
        
        # 讨论结束的全局信号，方便外部引擎监控或让 Agent 随时安全退出
        self.discussion_ended = asyncio.Event()
        self.vote_threshold = 5
    async def publish(self, sender_name: str, content: str, agent_id: int = None, want_to_vote: bool = False):
        """
        发布新消息并唤醒所有正在等待的 AI。
        
        :param sender_name: 发言者名称 (如 "系统主持人" 或 "AI_1")
        :param content: 发言的具体内容
        :param agent_id: 发言者的数字 ID (0-7)，系统发言留空即可
        :param want_to_vote: 该发言者是否想要结束讨论进入组队投票
        """
        # 1. 记录消息入池
        vote_tag = " [🙋提议结束讨论]" if want_to_vote else ""
        msg = f"[{sender_name}]: {content}{vote_tag}"
        self.messages.append(msg)
        self.global_history.append(msg)
        self.logger.log_speech(sender_name, f"{content}{vote_tag}")

        # 2. 更新投票状态池 (仅处理合法 Agent 的投票，防止系统发言报错)
        if agent_id is not None and 0 <= agent_id < self.total_agents:
            self.voting_status[agent_id] = want_to_vote
            
            # 统计同意结束的人数
            votes_to_end = self.voting_status.count(True)
            # print(f"  📊 [系统水池监控] 当前同意结束讨论的人数: {votes_to_end}/5 (达标即结束)")

            # 3. 核心机制触发：达到阈值 5 人
            if votes_to_end > self.vote_threshold and not self.discussion_ended.is_set():
                sys_msg = "[系统主持人]: 超过5人同意，本轮自由讨论强制结束，立刻进入组队投票环节！"
                self.messages.append(sys_msg)
                print(f"\n🚨 触发机制 -> {sys_msg}")
                
                # 激活全局结束信号
                self.discussion_ended.set()

        # 4. 获取异步锁，并唤醒所有阻塞在 condition.wait() 的 Agent
        async with self.condition:
            self.condition.notify_all()
            
    def get_all_messages(self) -> list:
        """获取全量消息列表，供 Agent 调用大模型时构建上下文"""
        return self.messages