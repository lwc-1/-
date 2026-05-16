"""配置模块 - 从 .env 文件读取所有配置"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Config:
    """评测系统配置"""

    # 被测模型配置
    candidate_api_key: str = os.getenv("CANDIDATE_API_KEY", "")
    candidate_base_url: str = os.getenv("CANDIDATE_BASE_URL", "https://api.deepseek.com")
    candidate_model: str = os.getenv("CANDIDATE_MODEL", "deepseek-chat")

    # 评判模型配置
    judge_api_key: str = os.getenv("JUDGE_API_KEY", "")
    judge_base_url: str = os.getenv("JUDGE_BASE_URL", "https://api.deepseek.com")
    judge_model: str = os.getenv("JUDGE_MODEL", "deepseek-chat")

    # 生成参数
    temperature: float = float(os.getenv("TEMPERATURE", "0.2"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "1500"))

    @classmethod
    def is_mock_mode(cls) -> bool:
        """判断是否需要进入 mock 模式（缺少 API Key 时）"""
        return not cls.candidate_api_key or not cls.judge_api_key

    @classmethod
    def print_config(cls, hide_keys: bool = True):
        """打印当前配置（隐藏 API Key）"""
        print("=" * 50)
        print("当前配置:")
        print(f"  被测模型: {cls.candidate_model}")
        print(f"  被测模型 Base URL: {cls.candidate_base_url}")
        print(f"  被测模型 API Key: {'***已配置***' if cls.candidate_api_key else '未配置'}")
        print(f"  评判模型: {cls.judge_model}")
        print(f"  评判模型 Base URL: {cls.judge_base_url}")
        print(f"  评判模型 API Key: {'***已配置***' if cls.judge_api_key else '未配置'}")
        print(f"  Temperature: {cls.temperature}")
        print(f"  Max Tokens: {cls.max_tokens}")
        print("=" * 50)
