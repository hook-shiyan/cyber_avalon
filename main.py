import asyncio
import config
import random
import json
from core.message_bus import MessageBus
from core.game_engine import GameEngine
from agents.avalon_agent import AvalonAgent
from utils.logger import GameLogger
from utils.prompts import (
    get_system_prompt, 
    generate_special_info,
    get_round_start_prompt,
    get_team_proposal_prompt,
    get_team_vote_prompt,
    get_quest_vote_prompt,
    get_assassination_prompt
)

async def main():
    logger = GameLogger()
    logger.log_system("=== 赛博阿瓦隆 游戏初始化开始 ===")

    # 1. 实例化核心组件
    bus = MessageBus(logger=logger, total_agents=config.TOTAL_AGENTS)
    agent_names = [f"AI_{i}" for i in range(config.TOTAL_AGENTS)]
    engine = GameEngine(agent_names=agent_names, roles_setup=config.ROLES_SETUP)
    
    # 身份分发与记录
    role_mapping = engine.initialize_game()
    logger.log_system(f"真实身份映射 (仅上帝可见): {role_mapping}")
    PERSONAS = [
        "暴躁老哥：脾气火爆，毫无耐心。说话极度简短，满嘴火药味，喜欢直接怒怼别人，常使用感叹号！",
        "理中客：冷静且做作。喜欢长篇大论盘逻辑，习惯用‘第一’、‘第二’、‘从逻辑上来说’，像个侦探。",
        "阴阳人：尖酸刻薄，冷嘲热讽。说话带刺，极度喜欢使用反问句（比如‘不会吧不会吧’），看谁都不爽。",
        "萌新小白：极度不自信，喜欢跟风。语气犹豫，经常使用‘吧’、‘呢’、‘是不是’，喜欢附和强势的人。",
        "老油条：桌游老手，满嘴黑话。说话圆滑，喜欢挑拨离间，被质问时极擅长转移话题，绝不正面回答。",
        "神经刀：脑回路清奇。关注点极其奇怪，经常提出反常理的猜测，发言跳脱，让别人摸不着头脑。",
        "和事佬：极其害怕冲突。看到别人吵架就想打圆场，致力于让大家别吵了赶紧发车，口头禅是‘别急别急’。",
        "疑心病：极度缺乏安全感。觉得所有人都在骗自己，各种被迫害妄想，谁赞成发车他就觉得谁是坏人。"
    ]
    random.shuffle(PERSONAS)
    # 2. 实例化 8 位 AI 并喂给系统提示词
    agents = []
    for i, name in enumerate(agent_names):
        role = role_mapping[name]
        # 生成专属的机密信息
        special_info = generate_special_info(i, role, list(role_mapping.values()))
        agent_persona = PERSONAS[i]
        # 生成并绑定常驻的 System Prompt
        sys_prompt = get_system_prompt(name, role, special_info, agent_persona)
        
        agent = AvalonAgent(agent_id=i, name=name, role=role, bus=bus, logger=logger)
        agent.system_prompt = sys_prompt
        agents.append(agent)
        
        logger.log_thought(name, role, agent.energy, f"已获取初始剧本。机密信息：{special_info}")

    logger.log_system("所有 AI 玩家已就绪。游戏正式开始！")

    # 3. 游戏主循环 (最多 5 轮)
    game_active = True
    while game_active:
        current_round = engine.state["current_round"]
        leader_name = engine.state["current_leader"]
        req_team_size = engine.quest_team_sizes[current_round - 1]
        failed_votes = engine.state["failed_team_votes"]
        
        # 同步轮次给所有 Agent
        bus.current_round = current_round
        
        # ===================================================================
        # [核心修复]：自然语言战报生成器 (彻底抛弃原始 JSON)
        # ===================================================================
        history_text_lines = []
        for r in range(1, current_round):
            round_key = f"round_{r}"
            if round_key in engine.state.get("round_history", {}):
                r_data = engine.state["round_history"][round_key]
                team_members = ", ".join(r_data.get("proposed_team", []))
                
                # 安全匹配这一轮的最终任务结果
                if (r - 1) < len(engine.state.get("quest_results", [])):
                    q_res = engine.state["quest_results"][r - 1]
                    res_cn = "🟢 成功 (全票好人)" if q_res == "Success" else "🔴 失败 (车上有坏人投了破坏票)"
                else:
                    res_cn = "未知"
                    
                history_text_lines.append(f"- 第 {r} 轮发车：车上成员是 [{team_members}]，任务结果：{res_cn}。")

        bus.history_summary = "\n".join(history_text_lines) if history_text_lines else "暂无历史发车记录。"
        
        # 提取上一轮的单纯结果供提示词短句使用
        if engine.state["quest_results"]:
            last_q_res = engine.state["quest_results"][-1]
            bus.last_result = "Success" if last_q_res == "Success" else "Fail"
            result_cn = "🟢 成功 (好人得分)" if last_q_res == "Success" else "🔴 失败 (有坏人搞破坏)"
        else:
            bus.last_result = "无"
            result_cn = "无"
        # ===================================================================
        
        # 组装干净的播报，杜绝让 AI 产生“失败”幻觉
        round_summary = f"第 {current_round} 轮开始！【上一轮任务结果：{result_cn}】\n" \
                        f"当前连续组队遭拒次数(流局): {failed_votes}/5。\n" \
                        f"本轮需要 {req_team_size} 人上车。本轮队长是：{leader_name}。"

        # --- 阶段 A：自由讨论环节 ---
        logger.log_system(">>> 进入自由讨论阶段 <<<")
        
        # 清理上一轮的结束信号和投票池
        bus.discussion_ended.clear()
        bus.voting_status = [False] * config.TOTAL_AGENTS
        
        
        # 给全局历史加一个书签，方便最后深夜看
        if current_round > 1:
            bus.global_history.append(f"\n========== 以上为第 {current_round-1} 轮发言 ==========\n")
            
        

        # 先唤醒所有 Agent 进入监听挂机状态
        divider = f"========== 以上为历史发言，现在进入 第 {current_round} 轮 - 第 {failed_votes + 1} 次组队讨论 =========="
        await bus.publish("系统主持人", divider)
        tasks = [asyncio.create_task(agent.listen_and_speak()) for agent in agents]
        
        # 让出控制权 1 秒，确保 8 个人都躺好等枪响
        await asyncio.sleep(1.0)
        async def discussion_timer(bus_obj, duration=180, interval=10):
            for remaining in range(duration, 0, -interval):
                if bus_obj.discussion_ended.is_set():
                    break # 已经被玩家投票结束了，时钟安静退出
                
                await bus_obj.publish("系统主持人", f"⏳ 讨论倒计时：剩余 {remaining} 秒！倒计时结束将强制进入发车")
                
                try:
                    # 挂起等待 interval 秒，如果中途凑够了 5 票，直接打断睡眠
                    await asyncio.wait_for(bus_obj.discussion_ended.wait(), timeout=interval)
                    break
                except asyncio.TimeoutError:
                    continue # 时间到了还没结束，进入下一轮循环播报
            
            # 60 秒走完，如果还没结束，法官强制砸锤！
            if not bus_obj.discussion_ended.is_set():
                await bus_obj.publish("系统主持人", "⏰ 60秒时间到！自由讨论强制结束，立刻进入队长定票环节！")
                bus_obj.discussion_ended.set()
        timer_task = asyncio.create_task(discussion_timer(bus))
        # 打响发令枪
        await bus.publish("系统主持人", round_summary)
        
        # 主程序挂起，等待水池发出 discussion_ended 信号
        await bus.discussion_ended.wait()
        timer_task.cancel()
        # 强制取消所有 Agent 的监听死循环
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.log_system(">>> 自由讨论阶段结束 <<<")

        # --- 阶段 B：队长选人环节 ---
        leader_agent = next(a for a in agents if a.name == leader_name)
        logger.log_system(f"等待队长 {leader_name} 提交出战名单...")
        
        proposal_prompt = get_team_proposal_prompt(req_team_size, agent_names, current_round)
        proposal_res = await leader_agent.generate_response(leader_agent.system_prompt, proposal_prompt)
        proposed_team = proposal_res.get("proposed_team", [])
        
        if not isinstance(proposed_team, list) or len(proposed_team) != req_team_size:
            proposed_team = random.sample(agent_names, req_team_size)
            logger.log_system(f"队长输出格式错误，系统强制代为选人：{proposed_team}")
            
        engine.enter_voting_phase(proposed_team)
        await bus.publish("系统主持人", f"队长 {leader_name} 提名的出战队伍是：{proposed_team}。请大家进行组队投票！")

        # --- 阶段 C：组队公开投票环节 ---
        logger.log_system(">>> 进入组队投票环节 <<<")
        votes = {}
        vote_tasks = []
        for agent in agents:
            v_prompt = get_team_vote_prompt(proposed_team)
            vote_tasks.append(agent.generate_response(agent.system_prompt, v_prompt))
            
        vote_results = await asyncio.gather(*vote_tasks)
        
        for agent, res in zip(agents, vote_results):
            vote_decision = res.get("vote", "Reject")
            votes[agent.name] = vote_decision
            logger.log_thought(agent.name, agent.role, agent.energy, f"投票OS: {res.get('thoughts', '')} -> 决定: {vote_decision}")
            
        is_approved = engine.resolve_team_vote(votes)

        approves = [agent for agent, v in votes.items() if v == "Approve"]
        rejects = [agent for agent, v in votes.items() if v == "Reject"]
        vote_detail = f"【赞成票】: {', '.join(approves) if approves else '无'} | 【反对票】: {', '.join(rejects) if rejects else '无'}"
        await bus.publish("系统主持人", f"组队投票结果公布！\n{vote_detail}\n最终结果：发车{'🟢 成功' if is_approved else '🔴 被否决'}！")



        status = engine.check_game_over()
        if status == "Evil_Wins_By_Votes":
            await bus.publish("系统主持人", "连续 5 次组队投票被否决，好人阵营分崩离析，【坏人阵营直接获胜】！")
            break

        if not is_approved:
            # 没过半，回到循环开头换下一个队长
            continue

        # --- 阶段 D：任务秘密投票环节 ---
        logger.log_system(">>> 进入任务执行环节 <<<")
        await bus.publish("系统主持人", f"队伍 {proposed_team} 已上车，正在执行任务，请等待结果...")
        
        quest_votes = []
        for agent_name in proposed_team:
            agent = next(a for a in agents if a.name == agent_name)
            if agent.role in ["梅林", "派西维尔", "忠臣"]:
                quest_votes.append("Success")
            else:
                q_prompt = get_quest_vote_prompt()
                res = await agent.generate_response(agent.system_prompt, q_prompt)
                decision = res.get("quest_card", "Success")
                quest_votes.append(decision)
                logger.log_thought(agent.name, agent.role, agent.energy, f"任务OS: {res.get('thoughts', '')} -> 出牌: {decision}")

        quest_result = engine.resolve_quest_vote(quest_votes)
        fail_count = quest_votes.count('Fail')
        
        # 在公屏清楚地打印任务成功还是失败
        final_quest_word = "🟢 成功" if quest_result == "Success" else "🔴 失败"
        await bus.publish("系统主持人", f"第 {current_round} 轮任务结果：【{final_quest_word}】！(其中包含了 {fail_count} 张失败卡)")

        # --- 阶段 E：胜负判定与刺杀 ---
        status = engine.check_game_over()
        
        if status == "Evil_Wins_By_Fails":
            await bus.publish("系统主持人", "任务累计失败 3 次，【坏人阵营获胜】！")
            break
            
        elif status == "Assassination_Phase":
            await bus.publish("系统主持人", "好人阵营成功完成 3 次任务！游戏进入黑夜。")
            logger.log_system(">>> 进入坏人私密讨论与刺杀环节 <<<")
            
            bad_roles = ["莫甘娜", "刺客", "爪牙", "莫德雷德"]
            evil_agents = [a for a in agents if a.role in bad_roles]
            
            # 为深夜聊天室准备环境
            bus.is_assassination_phase = True
            bus.messages = bus.global_history.copy() # 全局记忆拿出来倒进池子
            bus.vote_threshold = (len(evil_agents) // 2) + 1
            bus.discussion_ended.clear()
            bus.voting_status = [False] * config.TOTAL_AGENTS
            
            # 打响深夜的发令枪
            await bus.publish("系统主持人", "【深夜专属频道】请邪恶阵营睁眼！你们有一次私下讨论的机会。回顾上面整局的票型和发言，找出那个开了天眼的梅林！讨论充分后请附带投票结束。")
            
            # 只启动坏人
            evil_tasks = [asyncio.create_task(agent.listen_and_speak()) for agent in evil_agents]
            
            await bus.discussion_ended.wait()
            
            for t in evil_tasks:
                t.cancel()
            await asyncio.gather(*evil_tasks, return_exceptions=True)
            logger.log_system(">>> 坏人讨论结束，等待刺客落刀 <<<")
            
            assassin = next(a for a in evil_agents if a.role == "刺客")
            a_prompt = get_assassination_prompt()
            res = await assassin.generate_response(assassin.system_prompt, a_prompt)
            target = res.get("target", "AI_0")
            
            logger.log_thought(assassin.name, assassin.role, assassin.energy, f"刺杀OS: {res.get('thoughts', '')} -> 决定刀: {target}")
            await bus.publish("系统主持人", f"刺客 {assassin.name} 决定刺杀：{target}！")
            
            hit_merlin = engine.execute_assassination(target)
            if hit_merlin:
                await bus.publish("系统主持人", "刺客精准刀中梅林！【坏人阵营绝地翻盘获胜】！")
            else:
                await bus.publish("系统主持人", f"刺杀失败！{target} 不是梅林！【好人阵营最终获胜】！")
            break
            
        elif status == "Continue":
            pass

    logger.log_system("=== 赛博阿瓦隆 游戏彻底结束 ===")

if __name__ == "__main__":
    asyncio.run(main())