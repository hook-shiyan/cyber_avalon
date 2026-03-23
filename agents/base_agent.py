# agents/base_agent.py
import asyncio
import json
import random
import openai  # 真实接入大模型时需要 pip install openai
import config
class BaseAgent:
    """所有 AI 玩家的底层基类，负责处理网络请求、JSON 解析和异常重试"""
    
    def __init__(self, agent_id: int, name: str, bus):
        self.agent_id = agent_id
        self.name = name
        self.bus = bus
        
        # 真实的 DeepSeek 异步客户端初始化 (读取 config 中的配置)
        self.client = openai.AsyncOpenAI(
            api_key=config.LLM_API_KEY, 
            base_url=config.LLM_BASE_URL,
            timeout=15.0
        )

    async def generate_response(self, system_prompt: str, current_context: str) -> dict:
        """
        核心通信方法：向大模型发送包含历史记录的请求，并强制要求返回特定的 JSON 格式。
        """
        # 设置最大重试次数，防止 8 并发导致偶发的限流报错直接挂掉程序
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=config.LLM_MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": current_context}
                    ],
                    # 强制模型输出 JSON 格式 (DeepSeek 完全兼容此参数)
                    response_format={"type": "json_object"}, 
                    temperature=0.7
                )
                
                raw_content = response.choices[0].message.content.strip()
                
                # 容错清洗：如果大模型带了 Markdown 的代码块标记，将其剥离
                if raw_content.startswith("```json"):
                    raw_content = raw_content[7:]
                if raw_content.endswith("```"):
                    raw_content = raw_content[:-3]
                    
                return json.loads(raw_content.strip())
                
            except json.JSONDecodeError:
                print(f"⚠️ [{self.name}] 第 {attempt + 1} 次尝试：大模型返回的 JSON 格式损坏。")
            except Exception as e:
                print(f"❌ [{self.name}] 第 {attempt + 1} 次尝试：API 调用失败: {e}")
            
            # 如果报错了，休眠 2 秒后重试，给接口喘息的时间
            if attempt < max_retries - 1:
                await asyncio.sleep(2.0)
            
        # 如果重试了 3 次依然失败，返回兜底的静默操作，保证游戏流程不卡死
        print(f"💀 [{self.name}] API 彻底调用失败，执行兜底静默逻辑。")
        return {"should_i_speak": False, "speech": "", "want_to_vote": False}