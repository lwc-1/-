"""Judge 模块 - LLM-as-Judge 自动评分"""

import json
import re

JUDGE_SYSTEM_PROMPT = """你是一个专业的AI模型评测专家。你需要根据给定的评分维度和标准，对被测模型的回答进行评分。

评分维度（每项1-5分）：
1. instruction_following（指令完成度）：模型是否完成了用户的全部要求
   - 5分：完全满足所有指令要求
   - 4分：基本满足，仅有轻微遗漏
   - 3分：完成核心要求，但存在明显遗漏
   - 2分：只完成少量要求，关键要求缺失
   - 1分：基本未完成或答非所问

2. content_accuracy（内容准确性）：回答内容是否与原文事实一致，有无幻觉
   - 5分：所有信息准确无误
   - 4分：核心信息准确，仅有细枝末节偏差
   - 3分：大部分准确，但有1-2处明显错误
   - 2分：多处事实错误或存在明显幻觉
   - 1分：大量错误，严重偏离原文

3. format_compliance（格式正确性）：输出格式是否符合要求（JSON/Markdown/邮件等）
   - 5分：格式完全符合要求
   - 4分：格式基本正确，有微小瑕疵
   - 3分：有格式但不完全符合要求
   - 2分：格式大部分不符合
   - 1分：完全不符合格式要求

4. completeness（完整性）：是否遗漏关键字段或关键约束
   - 5分：所有关键信息和约束都已覆盖
   - 4分：覆盖95%以上的关键信息
   - 3分：覆盖核心信息但遗漏部分重要内容
   - 2分：遗漏多项关键信息
   - 1分：信息严重不完整

5. consistency（上下文一致性）：多轮任务中是否前后矛盾或丢失上下文
   - 5分：完全一致，无矛盾
   - 4分：基本一致，偶有轻微不一致
   - 3分：存在可察觉的不一致
   - 2分：明显矛盾或丢失重要上下文
   - 1分：严重矛盾或完全忽略上下文

你必须严格以JSON格式输出评分结果，不要输出任何其他解释文字。"""


def build_judge_prompt(case: dict, transcript: list[dict], final_answer: str,
                       rule_check_result: dict) -> list[dict]:
    """
    构建 Judge 评分的完整 prompt。

    Args:
        case: 测试用例
        transcript: 完整对话记录
        final_answer: 被测模型最终回答
        rule_check_result: 规则校验结果

    Returns:
        Judge 模型的 messages 列表
    """
    user_prompt = f"""请对以下被测模型的回答进行评分。

## 测试用例信息
- Case ID: {case['case_id']}
- L1: {case['l1']}
- L2: {case['l2']}
- L3: {case['l3']}
- 用例类型: {case['case_type']}

## 用户测试输入
{_format_turns(case['turns'])}

## 参考要点
{json.dumps(case.get('reference_points', []), ensure_ascii=False)}

## 期望输出格式
{case.get('expected_format', '无特定要求')}

## 约束条件
{json.dumps(case.get('constraints', {}), ensure_ascii=False)}

## 评分注意事项
{case.get('judge_notes', '无特殊说明')}

## 被测模型完整对话记录
{_format_transcript(transcript)}

## 被测模型最终回答
{final_answer}

## 规则校验结果
{json.dumps(rule_check_result, ensure_ascii=False, indent=2)}

---

请严格按以下JSON格式输出评分（不要输出其他任何内容）：
{{
  "case_id": "{case['case_id']}",
  "scores": {{
    "instruction_following": <1-5>,
    "content_accuracy": <1-5>,
    "format_compliance": <1-5>,
    "completeness": <1-5>,
    "consistency": <1-5>
  }},
  "overall_score": <五项平均，保留1位小数>,
  "pass": <overall_score >= 4.0 为 true，否则 false>,
  "rationale": "<简短说明主要扣分点>",
  "bad_case_tags": ["<问题标签1>", "<问题标签2>"],
  "improvement_suggestions": ["<优化建议1>", "<优化建议2>"]
}}"""

    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def parse_judge_response(response: str, case_id: str) -> dict:
    """
    解析 Judge 模型的输出。

    Args:
        response: Judge 模型原始输出
        case_id: 用例 ID（用于 fallback）

    Returns:
        解析后的评分结果字典
    """
    # 尝试提取 JSON
    json_str = _extract_json_from_response(response)

    try:
        result = json.loads(json_str)
        # 补充 case_id
        result["case_id"] = case_id
        # 确保 overall_score 存在
        if "overall_score" not in result and "scores" in result:
            scores = result["scores"]
            result["overall_score"] = round(sum(scores.values()) / len(scores), 1)
        # 确保 pass 字段存在
        if "pass" not in result:
            result["pass"] = result.get("overall_score", 0) >= 4.0
        return result
    except (json.JSONDecodeError, TypeError, KeyError):
        # 解析失败，返回 fallback 结果
        return {
            "case_id": case_id,
            "scores": {
                "instruction_following": None,
                "content_accuracy": None,
                "format_compliance": None,
                "completeness": None,
                "consistency": None,
            },
            "overall_score": None,
            "pass": None,
            "rationale": f"Judge 输出解析失败，原始输出已保存",
            "bad_case_tags": ["judge_parse_error"],
            "improvement_suggestions": ["需要人工复核"],
            "raw_judge_output": response[:2000],  # 保留前2000字符用于调试
        }


def _format_turns(turns: list[dict]) -> str:
    """格式化用例的输入轮次"""
    lines = []
    for i, turn in enumerate(turns, 1):
        lines.append(f"[第{i}轮 - {turn['role']}]: {turn['content']}")
    return "\n\n".join(lines)


def _format_transcript(transcript: list[dict]) -> str:
    """格式化完整对话记录"""
    lines = []
    for msg in transcript:
        role_label = "用户" if msg["role"] == "user" else "模型"
        content = msg["content"][:500]  # 截断过长内容
        lines.append(f"[{role_label}]: {content}")
    return "\n\n".join(lines)


def _extract_json_from_response(text: str) -> str:
    """从 Judge 输出中提取 JSON（处理 ```json 包裹等情况）"""
    # 1. 尝试匹配 ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 2. 尝试找到 { 开始的 JSON 对象
    brace_start = text.find("{")
    if brace_start >= 0:
        # 找到最后一个 }
        brace_end = text.rfind("}")
        if brace_end > brace_start:
            return text[brace_start:brace_end + 1]

    # 3. 直接返回原文尝试解析
    return text.strip()
