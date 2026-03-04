"""vLLM客户端封装"""
import yaml
from openai import OpenAI


class LLMClient:
    def __init__(self, config_path: str = "./config/model_config.yaml"):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)["model"]
        self.client = OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])
        self.model = cfg["name"]
        self.default_temperature = cfg.get("temperature", 0.1)
        self.default_max_tokens = cfg.get("max_tokens", 2048)

    def chat(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens or self.default_max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as e:
            raise ConnectionError(
                f"LLM调用失败: {e}\n"
                f"请确认 vLLM 服务是否已启动（默认 http://localhost:8000）"
            ) from e

    def chat_json(self, system_prompt: str, user_input: str) -> str:
        """带JSON格式约束的调用"""
        system_prompt += "\n\n你必须只返回合法JSON，不要返回任何其他文字或markdown。"
        return self.chat(system_prompt, user_input)
