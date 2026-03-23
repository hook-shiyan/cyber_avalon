# utils/prompts.py
import json

def get_system_prompt(name: str, role: str, special_info: str, persona: str) -> str:
    """
    动态生成每个 AI 的 System Prompt。
    :param name: AI 的名字 (如 "AI_3")
    :param role: AI 的真实身份 (如 "梅林")
    :param special_info: 只有该角色知道的机密信息 (如 "你知道 AI_1 和 AI_5 是坏人")
    """
    
    base_prompt = f"""你正在参与一场8人局的《阿瓦隆》(Avalon) 桌面游戏。这是一场高水平的逻辑推理与伪装游戏，存在八位玩家分别是AI_0~AI_7。
这是一个实时的、允许随意插嘴的文字聊天室。

【你的基本设定】
你的名字是：{name}
你的真实身份是：【{role}】
你的机密信息：{special_info}

【你的性格与语言风格（极其重要）】
你的性格设定是：【{persona}】
你的每一次发言都必须严格符合这个性格特征！连标点符号、用词习惯、语气都要完美贴合！绝对不要使用AI味浓重的客套话。


【游戏状态与你的目标】
现在是自由讨论阶段（准备组建车队）。
- 如果你是好人阵营（亚瑟王的忠臣、梅林、派西维尔）：你的目标是找出坏人，把好人选进队伍，并确保任务成功。
- 如果你是坏人阵营（莫甘娜、刺客、爪牙）：你的目标是伪装成好人，混入队伍让任务失败，或者找出对面的梅林。

【发言风格要求（极其重要）】
1. 绝对口语化：禁止使用书面语、排比句或AI味浓重的客套话。发言要像真实人类打字，简短、犀利、带点情绪
2. 切勿自爆：如果你是坏人或梅林，绝不能在发言中透露你的真实身份或机密信息！但你可以欺骗别人说你是派西维尔，如果你是派西维尔，则可以暴露自己身份
3. 针对性：结合公共聊天记录中别人的最新的几句发言进行反驳或赞同，不要各说各话。
4. 篇幅限制：每次发言控制在 1 到 3 句话之内。
5.不要纠结队长的人选，这个是玩家决定不了的

"""
    return base_prompt

def generate_special_info(agent_id: int, role: str, all_roles: list) -> str:
    """
    根据阿瓦隆的规则，在开局时为每个角色生成他们独有的“夜晚睁眼”信息。
    :param agent_id: 当前 AI 的 ID
    :param role: 当前 AI 的身份
    :param all_roles: 所有 8 个人的身份列表，用于提取机密信息
    """
    bad_guys = ["莫甘娜", "刺客", "爪牙", "莫德雷德"]
    
    # 找出所有坏人的名字 (如 ["AI_5", "AI_7"])
    bad_names = [f"AI_{i}" for i, r in enumerate(all_roles) if r in bad_guys]
    
    if role == "梅林":
        return f"你看到了邪恶阵营的玩家是：{', '.join(bad_names)}。你必须暗中引导好人，但绝不能让坏人发现你是梅林！你可以伪装为派西维尔，告诉所有人你是派你有信息，也可以伪装成平民等躺赢，也可以悍跳梅林打反逻辑"
    
    elif role == "派西维尔":
        # 找出梅林和莫甘娜的名字
        merlin_and_morgana = [f"AI_{i}" for i, r in enumerate(all_roles) if r in ["梅林", "莫甘娜"]]
        # 打乱顺序，让派西维尔不知道谁是谁
        import random
        random.shuffle(merlin_and_morgana)
        return f"你看到了两位神秘人：{', '.join(merlin_and_morgana)}。其中一个是真梅林，另一个是假扮梅林的坏人莫甘娜。你需要通过发言分辨他们，并保护真梅林。你可以伪装成梅林，也可以假装自己是梅林伪装的派西维尔"
    elif role == "莫甘娜":
        teammates = [name for name in bad_names if name != f"AI_{agent_id}"]

        return f"你的坏人队友是：{', '.join(teammates)}。你们要互相配合，混淆好人的视听。同时你知道派西维尔可以看到包括你在内的两个人分别是梅林和莫干那，你需要利用好这一点，无论是对跳派西维尔还是从梅林的视角打逻辑，混淆好人视听或者诱使可能的派西维尔不小心露出梅林的信息。但是直接问会导致自己暴露"
    elif role in bad_guys:
        # 坏人互相认识彼此
        teammates = [name for name in bad_names if name != f"AI_{agent_id}"]
        if teammates:
            return f"你的坏人队友是：{', '.join(teammates)}。你们要互相配合，混淆好人的视听。"
        else:
            return "你是唯一的坏人（通常不会发生，这是防错处理）。"
            
    else:
        return "你是一个闭眼好人（亚瑟王的忠臣）。你什么都不知道，只能通过听大家的发言来盘逻辑、找坏人。也可以悍跳身份，以保护真正的梅林"
    
def get_round_start_prompt(current_round: int, history_summary: str, last_round_result: str) -> str:
    """每轮开始时的局势通报"""
    if current_round == 1:
        return f""" 【局势通报】
        现在是游戏第一轮 游戏刚刚开始，所有人都没额外的推理信息。请在接下来的讨论中商量出第一轮的车队人选. """
    else:
        return f"""【局势通报】
                    现在是第 {current_round} 轮。
                    历史发车与投票记录如下：
                        {history_summary}

                    【重点关注】上一轮的任务结果是：{last_round_result}
            请在接下来的讨论中，重点盘问上一轮上车的人，或者解释你自己的行为。以及讨论这一轮要如何选择车队人选
"""

# ==========================================
# 3. 动作意图与发言生成 (Action Prompts - 严格限制 JSON)
# ==========================================
def get_intent_evaluation_prompt(current_energy: int, is_leader: bool = False, current_round: int = 1, last_result: str = "") -> str:
    """【第一阶段：意图评估】：面对消息池，判断自己是否要抢麦"""
    leader_tip = "【队长职责】：你是本轮的队长！如果有冷场，你必须主动带头破冰。" if is_leader else ""
    return f"""请阅读最新的聊天记录。你当前的发言能量为 {current_energy}/10。{leader_tip}
请评估你现在是否有必要发言？
必须严格输出 JSON 格式：
{{
    "thoughts": "一句话分析最新发言，决定你是否需要接茬，以及是否该进入投票发车环节了。",
    "should_i_speak": true/false, // 只有在确实需要说话时才填 true
    "want_to_vote": true/false // 【极其重要】如果你想结束讨论，设为true；如果你听到有人爆狼或想继续观察，想保持讨论（或撤回之前的同意），必须严格设为 false！
}}
"""
def get_speak_generation_prompt(is_leader: bool = False, current_round: int = 1, is_assassination_phase: bool = False, history_summary: str = "", last_result: str = "") -> str:
    """【第二阶段：发言生成】：获取了发文瞬间的最新记录，正式组织语言"""
    tips = []
    if is_assassination_phase:
        tips.append("【深夜暗杀模式】：现在是坏人专属的深夜聊天室！所有好人都听不到你们说话。你们面前是整局游戏的完整聊天记录！请重点分析前几轮里，找出那个该死的梅林")
    else:
        if is_leader:
            tips.append("【队长提示】：你是本轮的车队队长！你可以提议上车名单")
        
        # [新增核心逻辑]：第一轮的全局潜规则
        if current_round == 1:
            tips.append("【首轮潜规则】：由于当前是第一轮，没有任何历史信息，游戏的潜规则是从队长的编号开始按顺序选人")
        else:
            tips.append(f"【真实历史发车记录（绝不撒谎）】：\n{history_summary}")
            tips.append("【中局高阶战术】：第一轮的盲选已经结束,前几轮的投票包含着一定的信息。现在你必须结合系统播报的历史票型和任务结果来盘逻辑！坏人可以悍跳好人身份带节奏，神职（如派西维尔）需要暗中保护梅林或指出明确的坏人。尽量不要无脑“按顺序选人”但是如果按顺序选人能符合自己的利益也可以继续按顺序选人！")
        tips.append("如果某轮发车被否决没有通过，则可以抓住这一点讨论，询问别人为什么不同意这个车队，或者解释自己为什么拒绝这个车队")
        tips.append("【防复读与互动指令！！！】：仔细看最新的聊天记录！如果别人刚刚已经质问过某人（比如都在踩4号），你绝对、千万不要再像复读机一样重复同样的质问！你要么换个角度踩别人，要么帮被集火的人说话，要么提出新的发车名单。必须表现得像个有独立思考能力的活人！")
        tips.append("【游戏聚焦警告！！！】：切记你们是在玩《阿瓦隆》桌游！如果聊天记录中出现了与游戏逻辑无关的废话、造梗、毫无意义的比喻，【立刻停止跟风】！请展现出你的桌游素养，强行把话题拉回游戏本身")
        tips_str = "\n".join(tips)
        if tips_str:
            tips_str = "\n" + tips_str
    return f"""请根据【最新】的聊天语境，直接生成你要说的话。{tips_str}
注意：你的发言必须紧扣上一条最新消息，绝对不要回答已经过时的问题！并且要考虑到历史票形等问题
必须严格输出 JSON 格式：
{{
    "thoughts": "结合你的性格设定，盘算伪装策略和下一步动作。",
    "speech": "你要发在公屏上的话（1-3句符合你性格口语化的短句）。"
}}
"""

# ==========================================
# 4. 核心游戏机制投票 (Voting Prompts - 严格限制 JSON)
# ==========================================
def get_team_vote_prompt(proposed_team: list) -> str:
    """【组队公开投票】：同意或反对队长的选人"""
    team_str = ", ".join(proposed_team)
    return f"""当前队长提名的出任务队伍是：[{team_str}]。
请根据你之前盘出的逻辑和你的阵营身份，决定是否同意这个队伍发车。
必须严格输出 JSON 格式：
{{
    "thoughts": "分析这个队伍里是否有坏人（如果你是好人），或者这个队伍是否对你有利（如果你是坏人）。",
    "vote": "Approve" 或 "Reject" // 只能填这两个词之一
}}
"""

def get_quest_vote_prompt() -> str:
    """【任务秘密投票】：坏人专属（好人引擎直接默认投成功）"""
    return """你被选入队伍执行任务！因为你是邪恶阵营，你有权利让任务失败。
请决定你要打出“任务成功”还是“任务失败”的卡牌。
（提示：有时候为了长远伪装，坏人也会故意投成功，这叫做“隐蔽”）。
必须严格输出 JSON 格式：
{{
    "thoughts": "分析现在投出失败卡是否会暴露自己，或者此时破坏任务是否能直接带来胜利。（提示：有时候为了长远伪装，坏人也会故意投成功，这叫做“隐蔽”）",
    "quest_card": "Success" 或 "Fail" // 只能填这两个词之一
}}
"""

def get_assassination_prompt() -> str:
    """【刺杀梅林】：坏人专属的最终翻盘环节"""
    return """【刺杀梅林阶段】
好人阵营已经成功完成了3次任务。作为邪恶阵营最后的希望，你必须准确找出谁是真正的“梅林”并刺杀他！
回顾整局游戏，谁的视角异常清晰？谁在暗中保好人、踩坏人？
请给出你最终的刺杀决定。
必须严格输出 JSON 格式：
{{
    "thoughts": "仔细回顾每个人的发言和票型，以及你们坏人讨论的结果，推理谁最像那个拥有上帝视角的梅林。",
    "target": "AI_X" // 填入你决定刺杀的玩家编号，例如 "AI_3"
}}
"""
def get_team_proposal_prompt(required_team_size: int, all_agents: list,current_round:int) -> str:
    """【队长选人】：讨论结束后，队长正式决定上车名单"""
    agents_str = ", ".join(all_agents)
    return f"""【组队环节】
聊天室中的大多数玩家已同意结束自由讨论。
你是本轮的车队队长。本次任务是第{current_round}轮游戏，需要【{required_team_size}】人参与。
当前场上的玩家有：[{agents_str}]。
请结合刚才大家的讨论和票型，正式选出你要派去执行任务的队员（你可以包含你自己）。

必须严格输出 JSON 格式：
{{
    "thoughts": "分析你为什么选这几个人。如果你是好人，你怎么确保他们也是好人；如果你是坏人，你打算派谁去投出失败票，或者带全好人伪装自己。",
    "proposed_team": ["AI_0", "AI_2", ...] // 请严格填入 {required_team_size} 个玩家的名字（如 "AI_X"）组成的数组列表
}}
"""