# agents/avalon_agent.py
import asyncio
import random
import json
import time
import config
from agents.base_agent import BaseAgent
from utils.prompts import get_system_prompt,get_speak_generation_prompt,get_intent_evaluation_prompt

class AvalonAgent(BaseAgent):
    def __init__(self, agent_id: int, name: str, role: str, bus,logger,  system_prompt: str = ""):
        super().__init__(agent_id, name, bus)
        self.role = role       # 身份（如：梅林、派西维尔、忠臣、刺客等）
        self.energy = config.MAX_ENERGY
        self.system_prompt = system_prompt
        self.logger = logger
        # 新增机制：记录上一次发言是否因为手速慢被刷屏打断了
        self.was_interrupted = False
        

    async def listen_and_speak(self):
        """Agent 的并发主循环：空闲监听 -> 能量评估 -> 思考生成 -> 校验发送 -> 冷却"""
        last_read_index = 0
        
        # 只要总线没有发出“讨论结束”的全局信号，就一直保持运行
        while not self.bus.discussion_ended.is_set():
            try:
                # ==========================================
                # 状态 1：【空闲/监听状态】 (Idle & Listen)
                # ==========================================
                async with self.bus.condition:
                    while len(self.bus.messages) <= last_read_index and not self.bus.discussion_ended.is_set():
                        try:
                            # 引入动态超时机制（3-6秒），防止群体死寂（冷场救场）
                            timeout = random.uniform(config.TIMEOUT_MIN, config.TIMEOUT_MAX)
                            await asyncio.wait_for(self.bus.condition.wait(), timeout=timeout)
                        except asyncio.TimeoutError:
                            # 超时后直接打破等待，带着当前的能量去评估是否要主动找话题
                            break
                
                # 如果在休眠期间收到结束信号，立刻安全退出
                if self.bus.discussion_ended.is_set():
                    print(f"  🛑 [{self.name}] 收到全局结束信号，清理内存，安全退出。")
                    break

                # 获取新消息
                current_msg_count = len(self.bus.messages) #消息数量
                new_messages = self.bus.messages[last_read_index:current_msg_count]
                last_read_index = current_msg_count

                # ==========================================
                # 状态 2：【能量结算阶段】 (Energy Update)
                # ==========================================
                for msg in new_messages:
                    # 忽略自己发出的消息
                    if msg.startswith(f"[{self.name}]"):
                        continue
                        
                    # 能量法则：被 Cue 到 +3，普通吃瓜 +1
                    if self.name in msg:
                        self.energy = min(self.energy + config.CUE_REWARD, config.MAX_ENERGY)
                    else:
                        self.energy = min(self.energy + config.NORMAL_REWARD, config.MAX_ENERGY)

                # ==========================================
                # 状态 3：【第一重网关：本地能量判定】
                # ==========================================
                # 能量不足 5 点，处于疲劳状态，无权调用大模型，继续退回监听
                if self.energy < config.SPEAK_THRESHOLD:
                    continue
                    
                # ==========================================
                # 状态 4：【生成状态】 (Generating / 调用大模型)
                # ==========================================
                # 记录开始思考时的水池状态
                chat_history = "\n".join(self.bus.messages)
                is_currently_leader = f"本轮队长是：{self.name}" in chat_history
                
                # 错开起步时间：队长反应快，其他人稍等，避免开局撞车
                if is_currently_leader:
                    await asyncio.sleep(random.uniform(0.1, 0.2))
                else:
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    

                current_round = getattr(self.bus, 'current_round', 1)
                last_result = getattr(self.bus, 'last_result', '无')
                history_summary = getattr(self.bus, 'history_summary', '{}')

                intent_prompt = get_intent_evaluation_prompt(self.energy, is_currently_leader, current_round, last_result)
                intent_context = f"【当前聊天记录】\n{chat_history}\n\n{intent_prompt}"
                
                
                


                # 第 1 次极速调用 API：只问大模型“你想不想说话？”
                intent_res = await self.generate_response(self.system_prompt, intent_context)
                
                if self.bus.discussion_ended.is_set():
                    break
                should_speak = intent_res.get("should_i_speak", False)
                want_to_vote = intent_res.get("want_to_vote", False)

                current_vote_status = self.bus.voting_status[self.agent_id]
                # 如果大模型觉得没必要说话，扣除 1 点内耗，直接回退监听
                if not should_speak:
                    self.energy -= config.THINK_COST
                    # [关键修复]：只有当自己之前没有投过赞成票时，才发送默默同意，防止无限刷屏死锁！
                    if want_to_vote and not self.bus.voting_status[self.agent_id]:
                        if not self.bus.discussion_ended.is_set():
                            await self.bus.publish(
                                sender_name=self.name,
                                content="（默默同意发车）",
                                agent_id=self.agent_id,
                                want_to_vote=True
                            )
                        elif not want_to_vote and current_vote_status:
                            if not self.bus.discussion_ended.is_set():
                                await self.bus.publish(
                                    sender_name=self.name,
                                    content="（觉得局势有变，撤回了发车同意）",
                                    agent_id=self.agent_id,
                                    want_to_vote=False)
                    
                    continue
               
                # ==========================================
                # 状态 5：【第二阶段：获取最新语境并生成发言】 (Speech Generation)
                # ==========================================
                # 既然决定要说话了，我们在落笔的前一秒，再抓取一次绝对最新的聊天记录！
                pool_size_before_speech = len(self.bus.messages)
                latest_chat_history = "\n".join(self.bus.messages)
                
                current_round = getattr(self.bus, 'current_round', 1)
                last_result = getattr(self.bus, 'last_result', '无')
                history_summary = getattr(self.bus, 'history_summary', '{}')
                is_assassination = getattr(self.bus, 'is_assassination_phase', False)
                
                action_prompt = get_speak_generation_prompt(
                    is_leader=is_currently_leader, 
                    current_round=current_round,
                    is_assassination_phase=is_assassination,
                    history_summary=history_summary,
                    last_result=last_result
                )
                
                latest_context = f"【最新聊天记录】\n{latest_chat_history}\n\n{action_prompt}"
                # if current_round == 2 and not getattr(self, "has_printed_debug", False):
                #     print(f"\n{'='*20} 🐞 [DEBUG: 喂给 {self.name} 的终极 Prompt] {'='*20}")
                #     print(f"👉 [原始历史记录 (history_summary)]:\n{history_summary}\n")
                #     print(f"👉 [上一轮真实结果 (last_result)]: {last_result}\n")
                #     print(f"👉 [完整合并后的最新语境 (latest_context)]:\n{latest_context}")
                #     print("="*70 + "\n")
                #     # 设置全局标记，确保 8 个 AI 只有第一个执行到这里的会打印，防止控制台刷屏
                #     self.has_printed_debug = True 
                #     # 也可以给 bus 加上这个标记，确保全场只打印一次
                #     self.bus.has_printed_debug = True
                speech_res = await self.generate_response(self.system_prompt, latest_context)
                
                if self.bus.discussion_ended.is_set():
                    break

                # ==========================================
                # 状态 6：【提交校验：终极物理防刷屏拦截】 (Commit Check)
                # ==========================================
                # 检查在写小作文的这 1-2 秒内，有没有人又狂刷了屏幕
                pool_size_after_speech = len(self.bus.messages)
                messages_added_during_think = pool_size_after_speech - pool_size_before_speech
                
                if messages_added_during_think > config.PATIENT:
                    continue
                    
                self.energy -= config.SPEAK_COST
                
                # [核心修复]：提取发言时的真实 Thoughts，并静默写入日志！
                speech_thoughts = speech_res.get("thoughts", "未提取到构思过程")
                self.logger.log_thought(
                    self.name, self.role, self.energy, 
                    f"[发言构思] -> {speech_thoughts}"
                )
                
                speech_text = speech_res.get("speech", "")
                
                if speech_text:
                    await self.bus.publish(
                        sender_name=self.name,
                        content=speech_text,
                        agent_id=self.agent_id,
                        want_to_vote=want_to_vote 
                    )

            except Exception as e:
                self.logger.log_system(f"❌ [{self.name}] 运行异常: {e}")
                break

    