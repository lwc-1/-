"""测试用例加载模块"""

import json
from pathlib import Path

# 每条用例必须包含的字段
REQUIRED_FIELDS = ["case_id", "l1", "l2", "l3", "case_type", "turns"]


def load_cases(path: str) -> list[dict]:
    """
    加载 JSONL 格式的测试用例集。

    Args:
        path: JSONL 文件路径

    Returns:
        测试用例列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 格式错误
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"测试用例文件不存在: {path}")

    cases = []
    errors = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            # 解析 JSON
            try:
                case = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"第 {line_num} 行: JSON 解析失败 - {e}")
                continue

            # 校验必要字段
            missing = [field for field in REQUIRED_FIELDS if field not in case]
            if missing:
                errors.append(f"第 {line_num} 行 (case_id={case.get('case_id', '未知')}): 缺少字段 {missing}")
                continue

            # 校验 turns 非空
            if not case["turns"] or not isinstance(case["turns"], list):
                errors.append(f"第 {line_num} 行 (case_id={case['case_id']}): turns 必须是非空数组")
                continue

            # 校验 case_type
            if case["case_type"] not in ("single_turn", "multi_turn"):
                errors.append(f"第 {line_num} 行 (case_id={case['case_id']}): case_type 必须是 single_turn 或 multi_turn")
                continue

            cases.append(case)

    # 如果有错误，打印警告但不中断
    if errors:
        print(f"\n⚠️  用例加载警告 ({len(errors)} 个问题):")
        for err in errors:
            print(f"  - {err}")
        print()

    if not cases:
        raise ValueError(f"未能从 {path} 加载任何有效用例")

    print(f"✅ 成功加载 {len(cases)} 条测试用例")
    return cases


def get_case_distribution(cases: list[dict]) -> dict:
    """统计用例在各 L2 维度的分布"""
    dist = {}
    for case in cases:
        l2 = case.get("l2", "未知")
        dist[l2] = dist.get(l2, 0) + 1
    return dist
