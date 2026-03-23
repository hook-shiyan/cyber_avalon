# test.py
import asyncio
from core.message_bus import MessageBus
from agents.avalon_agent import AvalonAgent

async def main():
    print("=== 赛博阿瓦隆：并发能量架构测试启动 ===")
    
    # 1. 初始化公共水池 (8人局)
    bus = MessageBus(total_agents=8)
    
    # 2. 赋予身份并初始化 8 个 Agent
    roles = ["梅林", "派西维尔", "忠臣", "忠臣", "忠臣", "莫甘娜", "刺客", "爪牙"]
    agents = []
    for i in range(8):
        agent = AvalonAgent(agent_id=i, name=f"AI_{i}", role=roles[i], bus=bus)
        agents.append(agent)
        
    # 3. 将 Agent 的运行逻辑加入事件循环
    tasks = [asyncio.create_task(agent.listen_and_speak()) for agent in agents]
    
    # 4. 关键：等待一小会儿，确保所有 AI 都已经进入了 wait() 挂机监听状态
    await asyncio.sleep(1)
    
    # 5. 主持人抛出第一句话，激活全场！
    await bus.publish(
        sender_name="系统主持人",
        content="天亮了。本轮任务需要 3 人上车，AI_0 是队长。大家请自由讨论！",
        agent_id=None, # 系统主持人没有 agent_id
        want_to_vote=False
    )
    
    # 6. 监控运行状态：等待自然结束或强制超时
    try:
        # 挂起主线程，死死盯着 bus.discussion_ended 信号
        # 如果 AI 们成功有 5 个人投了赞成票，这个信号就会被激活
        await asyncio.wait_for(bus.discussion_ended.wait(), timeout=20.0)
        print("\n✅ 测试成功退出：Agent 们通过投票共识，触发了结束机制！")
    except asyncio.TimeoutError:
        # 如果 20 秒都没吵出个结果，主线程强制介入
        print("\n⏱️ 测试超时退出：达到 20 秒最大时长，系统强制收回麦克风。")
        bus.discussion_ended.set() # 手动激活全局结束信号，通知所有 AI 下班
        
    # 7. 优雅地等待所有 Agent 任务清理内存并退出
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\n=== 对局日志盘点 ===")
    for msg in bus.get_all_messages():
        print(msg)
    print("=== 赛博圆桌已安全关闭 ===")

if __name__ == "__main__":
    asyncio.run(main())