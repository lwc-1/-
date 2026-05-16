"""报告生成模块 - 生成 Markdown 测试报告和结构化统计"""

from datetime import datetime
from collections import Counter


def generate_report(results: list[dict], is_mock: bool = False) -> str:
    """
    生成 Markdown 格式的测试报告。

    Args:
        results: 评测结果列表
        is_mock: 是否为 mock 模式

    Returns:
        Markdown 格式的报告内容
    """
    total = len(results)
    scores = [r["overall_score"] for r in results if r["overall_score"] is not None]
    passed = sum(1 for r in results if r.get("pass") is True)
    avg_score = sum(scores) / len(scores) if scores else 0

    # 各维度平均分
    dimensions = ["instruction_following", "content_accuracy", "format_compliance",
                  "completeness", "consistency"]
    dim_scores = {}
    for dim in dimensions:
        dim_vals = []
        for r in results:
            s = r.get("judge_result", {}).get("scores", {}).get(dim)
            if s is not None:
                dim_vals.append(s)
        dim_scores[dim] = sum(dim_vals) / len(dim_vals) if dim_vals else 0

    # 按 L2 维度统计
    l2_stats = _get_l2_stats(results)

    # Bad case 分析
    bad_cases = [r for r in results if r.get("pass") is False]
    bad_cases_sorted = sorted(bad_cases, key=lambda x: x.get("overall_score") or 0)

    # 问题标签统计
    all_tags = []
    for r in results:
        all_tags.extend(r.get("bad_case_tags", []))
    tag_counter = Counter(all_tags)

    # 构建报告
    mode_label = "Mock 模拟模式" if is_mock else "真实 API 模式"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"""# 大模型办公文档处理能力评测报告

## 1. 项目简介

本报告为面向办公文档处理场景的大模型自动化评测结果，评测覆盖信息抽取、文档摘要、格式转换、多轮上下文等核心能力。

## 2. 评测配置

| 配置项 | 值 |
|--------|-----|
| 运行模式 | {mode_label} |
| 生成时间 | {now} |
| 测试用例数 | {total} |

## 3. 评测框架

```
L1：办公文档处理能力
├── L2：信息抽取（会议纪要待办抽取、合同/通知关键信息、表格字段抽取）
├── L2：文档摘要（会议纪要摘要、产品需求文档摘要、用户反馈摘要）
├── L2：格式转换（文本转JSON、文本转Markdown表格、非结构化转结构化清单）
└── L2：多轮上下文（基于前文生成邮件、追加要求修改输出、压缩内容保留关键信息）
```

## 4. 整体评测结果

| 指标 | 数值 |
|------|------|
| 总用例数 | {total} |
| 平均分 | {avg_score:.2f} / 5.0 |
| 通过数 | {passed} |
| 通过率 | {passed/total*100:.1f}% |
| 最高分 | {max(scores):.1f} |
| 最低分 | {min(scores):.1f} |

## 5. 五维度评分详情

| 评分维度 | 平均分 | 说明 |
|----------|--------|------|
| 指令完成度 (instruction_following) | {dim_scores['instruction_following']:.2f} | 是否完成用户全部要求 |
| 内容准确性 (content_accuracy) | {dim_scores['content_accuracy']:.2f} | 是否与原文事实一致 |
| 格式正确性 (format_compliance) | {dim_scores['format_compliance']:.2f} | 输出格式是否符合要求 |
| 完整性 (completeness) | {dim_scores['completeness']:.2f} | 是否遗漏关键信息 |
| 上下文一致性 (consistency) | {dim_scores['consistency']:.2f} | 多轮中是否前后矛盾 |

## 6. 按 L2 维度评分

| L2 维度 | 用例数 | 平均分 | 通过率 |
|---------|--------|--------|--------|
"""

    for l2, stats in l2_stats.items():
        report += f"| {l2} | {stats['count']} | {stats['avg_score']:.2f} | {stats['pass_rate']:.1f}% |\n"

    report += f"""
## 7. Bad Case 分析

### 7.1 低分用例 TOP5

"""
    for i, bc in enumerate(bad_cases_sorted[:5], 1):
        score = bc.get("overall_score", "N/A")
        tags = ", ".join(bc.get("bad_case_tags", [])) or "无标签"
        rationale = bc.get("judge_result", {}).get("rationale", "无说明")
        report += f"**{i}. {bc['case_id']}** (L2: {bc['l2']}, L3: {bc['l3']})\n"
        report += f"- 得分: {score}\n"
        report += f"- 问题标签: {tags}\n"
        report += f"- 扣分原因: {rationale}\n\n"

    if not bad_cases_sorted:
        report += "无 Bad Case，所有用例均通过。\n\n"

    report += """### 7.2 问题归因统计

| 问题标签 | 出现次数 |
|----------|----------|
"""
    for tag, count in tag_counter.most_common(10):
        report += f"| {tag} | {count} |\n"

    if not tag_counter:
        report += "| 无问题标签 | 0 |\n"

    report += f"""
## 8. 优化建议

基于本次评测结果，提出以下优化建议：

1. **格式约束增强**：对于要求输出 JSON 的用例，建议在 system prompt 中明确要求合法 JSON 格式
2. **信息完整性**：对信息抽取类任务，建议增加"请勿遗漏任何条目"的显式约束
3. **多轮上下文保持**：对多轮对话任务，建议优化上下文窗口管理策略
4. **字数控制**：对有字数限制的摘要任务，建议增加字数自检步骤
5. **低分 L2 领域专项优化**：针对平均分最低的 L2 领域增加专项回归测试用例

## 9. 附录

- 评测时间: {now}
- 报告自动生成，如需人工复核请使用 `make_human_review.py` 生成抽检模板
"""

    return report


def generate_summary(results: list[dict]) -> dict:
    """
    生成结构化统计数据。

    Args:
        results: 评测结果列表

    Returns:
        统计摘要字典
    """
    total = len(results)
    scores = [r["overall_score"] for r in results if r["overall_score"] is not None]
    passed = sum(1 for r in results if r.get("pass") is True)

    # 各维度统计
    dimensions = ["instruction_following", "content_accuracy", "format_compliance",
                  "completeness", "consistency"]
    dim_stats = {}
    for dim in dimensions:
        vals = []
        for r in results:
            s = r.get("judge_result", {}).get("scores", {}).get(dim)
            if s is not None:
                vals.append(s)
        dim_stats[dim] = {
            "avg": round(sum(vals) / len(vals), 2) if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        }

    # L2 统计
    l2_stats = _get_l2_stats(results)

    # 问题标签
    all_tags = []
    for r in results:
        all_tags.extend(r.get("bad_case_tags", []))

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_cases": total,
        "overall": {
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "max_score": max(scores) if scores else None,
            "min_score": min(scores) if scores else None,
            "pass_count": passed,
            "fail_count": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        },
        "dimension_scores": dim_stats,
        "l2_breakdown": l2_stats,
        "bad_case_tags": dict(Counter(all_tags).most_common(20)),
        "bad_case_ids": [r["case_id"] for r in results if r.get("pass") is False],
    }

    return summary


def _get_l2_stats(results: list[dict]) -> dict:
    """按 L2 维度统计"""
    l2_groups = {}
    for r in results:
        l2 = r["l2"]
        if l2 not in l2_groups:
            l2_groups[l2] = []
        l2_groups[l2].append(r)

    l2_stats = {}
    for l2, group in l2_groups.items():
        group_scores = [r["overall_score"] for r in group if r["overall_score"] is not None]
        group_passed = sum(1 for r in group if r.get("pass") is True)
        l2_stats[l2] = {
            "count": len(group),
            "avg_score": round(sum(group_scores) / len(group_scores), 2) if group_scores else 0,
            "pass_count": group_passed,
            "pass_rate": round(group_passed / len(group) * 100, 1) if group else 0,
        }

    return l2_stats
