TOTAL_AGENTS = 8
ENABLE_LADY_OF_THE_LAKE = False

ROLES_SETUP = [
    "梅林", 
    "派西维尔", 
    "忠臣", 
    "忠臣", 
    "忠臣", 
    "莫甘娜", 
    "刺客", 
    "爪牙" # 替换了普通的"爪牙"
]

VOTES_TO_END_DISCUSSION = 5

MAX_ENERGY = 10         # 能量槽上限，允许高能玩家连续爆发
SPEAK_THRESHOLD = 5     # 抢麦及格线：能量低于此值陷入疲劳禁言
SPEAK_COST = 5          # 成功发出一句话扣除的能量
THINK_COST = 1          # 意愿达到但大模型决定潜水，扣除的精神内耗
CUE_REWARD = 3          # 被别人直接点名 (Cue) 时回复的能量
NORMAL_REWARD = 1       # 别人普通发言时吃瓜回复的能量
PATIENT = 3
# 动态休眠防死寂机制的超时时间范围 (秒)
TIMEOUT_MIN = 3.0
TIMEOUT_MAX = 6.0

LLM_BASE_URL = "https://api.deepseek.com"
LLM_API_KEY = "sk-c7773e4b153c42e3928e9fdf3bacaaa6"
LLM_MODEL_NAME = "deepseek-chat"