"""规则校验模块 - 对模型回答进行自动化规则检查"""

import json
import re


def run_rule_checks(answer: str, case: dict) -> dict:
    """
    对模型回答进行规则校验。

    Args:
        answer: 模型的回答文本
        case: 对应的测试用例

    Returns:
        规则校验结果字典
    """
    result = {
        "format_valid": True,
        "missing_keywords": [],
        "length_valid": True,
        "rule_score_hint": 5,
        "notes": [],
    }

    expected_format = case.get("expected_format", "")
    constraints = case.get("constraints", {})

    # 1. 格式校验
    if expected_format == "json":
        result["format_valid"] = _check_json_format(answer, result)
    elif expected_format == "markdown_table":
        result["format_valid"] = _check_markdown_table(answer, result)

    # 2. 关键词检查
    must_include = constraints.get("must_include", [])
    if must_include:
        result["missing_keywords"] = _check_keywords(answer, must_include)
        if result["missing_keywords"]:
            result["notes"].append(f"缺少关键词: {result['missing_keywords']}")

    # 3. 长度检查（中文按字符数近似）
    max_words = constraints.get("max_words")
    if max_words:
        result["length_valid"] = _check_length(answer, max_words, result)

    # 4. 计算规则评分提示
    result["rule_score_hint"] = _calculate_rule_score(result)

    return result


def _check_json_format(answer: str, result: dict) -> bool:
    """检查回答是否是合法 JSON"""
    # 尝试提取 JSON 内容（可能被包裹在 ```json ``` 中）
    json_content = _extract_json(answer)

    try:
        json.loads(json_content)
        return True
    except (json.JSONDecodeError, TypeError):
        result["notes"].append("JSON 格式不合法，无法解析")
        return False


def _check_markdown_table(answer: str, result: dict) -> bool:
    """检查回答是否包含 Markdown 表格特征"""
    has_pipe = "|" in answer
    has_separator = bool(re.search(r"\|[-:]+\|", answer) or re.search(r"---", answer))

    if not has_pipe:
        result["notes"].append("未检测到 Markdown 表格分隔符 |")
        return False
    if not has_separator:
        result["notes"].append("未检测到 Markdown 表格分隔行 (---)")
        return False
    return True


def _check_keywords(answer: str, must_include: list[str]) -> list[str]:
    """检查回答中是否包含必需的关键词"""
    missing = []
    for keyword in must_include:
        if keyword not in answer:
            missing.append(keyword)
    return missing


def _check_length(answer: str, max_words: int, result: dict) -> bool:
    """检查回答长度（中文按字符数近似处理）"""
    # 去除空白字符后计算
    content = re.sub(r'\s+', '', answer)
    actual_len = len(content)

    # 允许 20% 的容差
    threshold = int(max_words * 1.2)

    if actual_len > threshold:
        result["notes"].append(f"内容过长: {actual_len} 字符（限制 {max_words}，容差阈值 {threshold}）")
        return False
    return True


def _calculate_rule_score(result: dict) -> int:
    """根据规则校验结果计算一个评分提示（1-5）"""
    score = 5

    if not result["format_valid"]:
        score -= 2

    missing_count = len(result["missing_keywords"])
    if missing_count >= 3:
        score -= 2
    elif missing_count >= 1:
        score -= 1

    if not result["length_valid"]:
        score -= 1

    return max(1, score)


def _extract_json(text: str) -> str:
    """从文本中提取 JSON 内容（处理 ```json 代码块包裹的情况）"""
    # 尝试匹配 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 尝试找到第一个 [ 或 { 开始的 JSON
    for i, ch in enumerate(text):
        if ch in ('[', '{'):
            return text[i:]

    return text
