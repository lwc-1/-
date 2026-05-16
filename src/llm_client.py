"""LLM 客户端 - 基于 OpenAI-compatible API 的统一调用接口"""

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class OpenAICompatibleClient:
    """支持任何 OpenAI-compatible API 的客户端"""

    def __init__(self, api_key: str, base_url: str, model: str,
                 temperature: float = 0.2, max_tokens: int = 1500):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def chat(self, messages: list[dict], temperature: float | None = None,
             max_tokens: int | None = None) -> str:
        """
        调用 LLM 进行对话。

        Args:
            messages: OpenAI 格式的消息列表，如 [{"role": "user", "content": "..."}]
            temperature: 温度参数（可选，覆盖默认值）
            max_tokens: 最大 token 数（可选，覆盖默认值）

        Returns:
            模型回复的纯文本内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as e:
            error_msg = str(e)
            # 不要在错误信息中暴露 API Key
            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
                raise RuntimeError(f"API 认证失败，请检查 API Key 配置。错误类型: {type(e).__name__}")
            raise RuntimeError(f"LLM 调用失败: {type(e).__name__} - {error_msg}")


class MockLLMClient:
    """Mock 客户端，用于无 API Key 时的演示运行"""

    def __init__(self, role: str = "candidate"):
        self.role = role  # "candidate" 或 "judge"

    def chat(self, messages: list[dict], **kwargs) -> str:
        """生成模拟回复"""
        if self.role == "candidate":
            return self._mock_candidate_response(messages)
        else:
            return self._mock_judge_response(messages)

    def _mock_candidate_response(self, messages: list[dict]) -> str:
        """模拟被测模型的回答"""
        user_msg = messages[-1]["content"] if messages else ""

        # 根据用例类型生成不同格式的 mock 回答
        if "JSON" in user_msg or "json" in user_msg:
            return '''[
  {
    "task": "完成首页提测",
    "owner": "张三",
    "deadline": "5月15日"
  },
  {
    "task": "接口文档更新",
    "owner": "李四",
    "deadline": "5月12日"
  },
  {
    "task": "修复服务器配置",
    "owner": "赵六",
    "deadline": "5月11日"
  }
]'''
        elif "Markdown" in user_msg or "表格" in user_msg:
            return '''| 阶段 | 负责人 | 开始时间 | 结束时间 | 交付物 |
|------|--------|----------|----------|--------|
| 需求分析 | 张琳 | 5月1日 | 5月15日 | PRD |
| 设计 | 李明 | 5月16日 | 5月31日 | 设计稿 |
| 开发 | 王强 | 6月1日 | 7月15日 | 可测试版本 |'''
        elif "摘要" in user_msg or "压缩" in user_msg or "精简" in user_msg:
            return "本次会议决定MVP版本延期至8月15日发布，7月1日前完成技术方案评审。Q3优先级：AI助手>性能优化>国际化。计划紧急招聘2名AI工程师，6月底前到岗。"
        elif "邮件" in user_msg:
            return """主题：关于技术分享活动通知

各位同事：

兹定于下周三（5月15日）下午2:00-4:00在3楼大会议室举办技术分享活动，主题为"微服务架构实践"。

请技术部全体同事准时参加，并提前准备好笔记本电脑。

如有疑问请联系我。

此致
敬礼"""
        else:
            return "根据您提供的文档内容，我整理了以下关键信息：\n\n1. 核心要点已提取完成\n2. 数据分析结果如上所述\n3. 建议后续关注重点领域的优化\n\n如需进一步细化，请告知具体方向。"

    def _mock_judge_response(self, messages: list[dict]) -> str:
        """模拟评判模型的评分输出"""
        import random
        scores = {
            "instruction_following": random.randint(3, 5),
            "content_accuracy": random.randint(3, 5),
            "format_compliance": random.randint(3, 5),
            "completeness": random.randint(3, 5),
            "consistency": random.randint(4, 5),
        }
        overall = round(sum(scores.values()) / len(scores), 1)
        import json
        result = {
            "case_id": "MOCK",
            "scores": scores,
            "overall_score": overall,
            "pass": overall >= 4.0,
            "rationale": "Mock评分：模型回答基本完成了指令要求，格式基本符合预期。",
            "bad_case_tags": ["minor_format_issue"] if overall < 4.0 else [],
            "improvement_suggestions": ["建议增强格式约束"] if overall < 4.5 else []
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
