# core/game_engine.py
import random
import json
import os

class GameEngine:
    """阿瓦隆游戏状态机与规则引擎"""
    
    def __init__(self, agent_names: list, roles_setup: list, state_file: str = "game_state.json"):
        self.agent_names = agent_names
        self.roles_setup = roles_setup
        self.state_file = state_file
        
        # 8人局的发车人数标准配置
        self.quest_team_sizes = [3, 4, 4, 5, 5]
        
        # 游戏核心状态字典 (会实时同步到 JSON 文件)
        self.state = {
            "current_round": 1,              # 当前轮次 (1-5)
            "current_leader": None,          # 当前队长
            "leader_index": 0,               # 队长在列表中的索引
            "failed_team_votes": 0,          # 连续否决的组队次数 (达到5次坏人直接获胜)
            "quest_results": [],             # 任务结果记录 ["Success", "Fail", ...]
            "lady_of_the_lake_owner": None,  # 湖中仙女当前持有者
            "lady_history": [],              # 仙女验人记录 [{"source": "AI_1", "target": "AI_3", "is_bad": True}]
            "round_history": {}  ,            # 记录每一轮的详细票型与任务数据
            "assassination_target": None,    # 刺客最终选择刀的人
            "assassination_hit_merlin": None # 是否刀中梅林
        }
        
        # 角色分配字典 { "AI_0": "梅林", "AI_1": "忠臣", ... }
        self.role_mapping = {}

    # ==========================================
    # 1. 游戏初始化接口
    # ==========================================
    def initialize_game(self) -> dict:
        """
        初始化游戏：随机分发身份，随机决定首位队长，初始化轮次历史。
        返回 role_mapping 供 main.py 实例化 Agent 使用。
        """
        # 1. 打乱身份池并分配
        shuffled_roles = self.roles_setup.copy()
        random.shuffle(shuffled_roles)
        for i, name in enumerate(self.agent_names):
            self.role_mapping[name] = shuffled_roles[i]
            
        # 2. 随机指定首位队长
        self.state["leader_index"] = random.randint(0, len(self.agent_names) - 1)
        self.state["current_leader"] = self.agent_names[self.state["leader_index"]]
        
        # 3. 湖中仙女初始默认给最后一位玩家 (可选规则)
        self.state["lady_of_the_lake_owner"] = self.agent_names[-1]
        
        # 4. 初始化第一轮的数据结构
        self._init_round_state(1)
        
        # 5. 持久化到 JSON
        self._flush_state_to_json()
        
        return self.role_mapping

    def _init_round_state(self, round_num: int):
        """内部方法：为新的一轮准备数据结构"""
        self.state["round_history"][f"round_{round_num}"] = {
            "required_team_size": self.quest_team_sizes[round_num - 1],
            "proposed_team": [],      # 队长提名的队伍
            "team_votes": {},         # 组队公开投票 { "AI_0": "Approve", "AI_1": "Reject" }
            "quest_votes": {}         # 任务秘密投票 { "AI_0": "Success", "AI_2": "Fail" } (打乱顺序)
        }

    # ==========================================
    # 2. 流程与投票接口 (供外部主控循环调用)
    # ==========================================
    def enter_voting_phase(self, proposed_team: list):
        """队长选好人后，进入组队投票环节"""
        current_round = self.state["current_round"]
        self.state["round_history"][f"round_{current_round}"]["proposed_team"] = proposed_team
        self._flush_state_to_json()

    def resolve_team_vote(self, votes: dict) -> bool:
        """
        结算【组队公开投票】。
        :param votes: 字典，包含所有人的投票结果，如 {"AI_0": "Approve", "AI_1": "Reject", ...}
        :return: 布尔值，组队是否成功 (赞成票 > 一半)
        """
        current_round = self.state["current_round"]
        self.state["round_history"][f"round_{current_round}"]["team_votes"] = votes
        
        approve_count = list(votes.values()).count("Approve")
        is_approved = approve_count > (len(self.agent_names) / 2)
        
        if is_approved:
            self.state["failed_team_votes"] = 0 # 发车成功，重置死亡发车线计数
        else:
            self.state["failed_team_votes"] += 1
            self._pass_leader() # 发车失败，队长顺延
            
        self._flush_state_to_json()
        return is_approved

    def resolve_quest_vote(self, quest_votes: list) -> str:
        """
        结算【任务秘密投票】（上车的人发起的任务成功/失败）。
        :param quest_votes: 列表，例如 ["Success", "Success", "Fail"]
        :return: 字符串，"Success" 或 "Fail"
        """
        current_round = self.state["current_round"]
        
        # ⚠️ 第四轮的特殊规则：需要出现两张 Fail 任务才会失败
        requires_two_fails = (current_round == 4)
        fail_count = quest_votes.count("Fail")
        
        if requires_two_fails:
            quest_result = "Fail" if fail_count >= 2 else "Success"
        else:
            quest_result = "Fail" if fail_count >= 1 else "Success"
            
        # 记录结果并打乱秘密投票 (保护隐私)
        random.shuffle(quest_votes)
        self.state["round_history"][f"round_{current_round}"]["quest_votes"] = quest_votes
        self.state["quest_results"].append(quest_result)
        
        # 准备进入下一轮
        if current_round < 5:
            self.state["current_round"] += 1
            self._pass_leader()
            self._init_round_state(self.state["current_round"])
            
        self._flush_state_to_json()
        return quest_result

    def _pass_leader(self):
        """内部方法：队长标志顺延"""
        self.state["leader_index"] = (self.state["leader_index"] + 1) % len(self.agent_names)
        self.state["current_leader"] = self.agent_names[self.state["leader_index"]]

    # ==========================================
    # 3. 湖中仙女接口
    # ==========================================
    def trigger_lady_of_the_lake(self, source_agent: str, target_agent: str) -> bool:
        """
        启用湖中仙女接口进行验人。
        :return: 布尔值，True 代表目标是坏人阵营，False 代表好人阵营
        """
        if self.state["lady_of_the_lake_owner"] != source_agent:
            raise ValueError(f"{source_agent} 目前不持有湖中仙女！")
            
        target_role = self.role_mapping[target_agent]
        is_bad_guy = target_role in ["莫甘娜", "刺客", "爪牙", "莫德雷德"]
        
        # 记录历史，并将仙女移交给被验的人
        self.state["lady_history"].append({
            "source": source_agent,
            "target": target_agent,
            "is_bad": is_bad_guy
        })
        self.state["lady_of_the_lake_owner"] = target_agent
        
        self._flush_state_to_json()
        return is_bad_guy

    # ==========================================
    # 4. 状态持久化
    # ==========================================
    def _flush_state_to_json(self):
        """将当前游戏引擎的状态字典覆盖写入本地 JSON 文件"""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=4)
    
    # ==========================================
    # 5. 胜负判定与刺杀接口
    # ==========================================
    def check_game_over(self) -> str:
        """
        检查游戏是否触发结束条件。由 main.py 在每次投票或任务结束后调用。
        返回:
        - "Evil_Wins_By_Fails": 坏人通过 3 次任务失败获胜
        - "Evil_Wins_By_Votes": 坏人通过连续 5 次流局（发车失败）获胜
        - "Assassination_Phase": 好人完成 3 次任务，游戏挂起，进入刺客查杀环节
        - "Continue": 未满足任何结束条件，游戏继续
        """
        if self.state["failed_team_votes"] >= 5:
            return "Evil_Wins_By_Votes"
            
        fail_count = self.state["quest_results"].count("Fail")
        success_count = self.state["quest_results"].count("Success")
        
        if fail_count >= 3:
            return "Evil_Wins_By_Fails"
        elif success_count >= 3:
            return "Assassination_Phase"
        else:
            return "Continue"

    def execute_assassination(self, target_agent: str) -> bool:
        """
        执行刺客最后的刺杀动作。
        :param target_agent: 刺客决定要刀的 AI 名字 (如 "AI_3")
        :return: True 代表刀中梅林（坏人绝地翻盘），False 代表刀错人（好人最终获胜）
        """
        if target_agent not in self.role_mapping:
            raise ValueError(f"刺杀目标 {target_agent} 不存在于游戏中！")
            
        target_role = self.role_mapping[target_agent]
        is_hit = (target_role == "梅林")
        
        # 记录刺杀结果到状态字典并持久化
        self.state["assassination_target"] = target_agent
        self.state["assassination_hit_merlin"] = is_hit
        self._flush_state_to_json()
        
        return is_hit