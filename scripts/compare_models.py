"""
多模型对比报告生成脚本

对比两次评测运行的结果，生成 Markdown 格式对比报告。

使用方式：
    python scripts/compare_models.py --run1 outputs/deepseek_xxx --run2 outputs/qwen_xxx

    # 指定模型名称标签
    python scripts/compare_models.py --run1 outputs/deepseek_xxx --run2 outputs/qwen_xxx --name1 "DeepSeek-V4" --name2 "Qwen2.5-7B"
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def load_results(run_dir: Path) -> list[dict]:
    """加载某次运行的结果"""
    jsonl_path = run_dir / "results.jsonl"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"结果文件不存在: {jsonl_path}")

    results = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def generate_comparison(results1, results2, name1, name2, output_path):
    """生成对比报告"""

    # 基础统计
    def stats(results):
        scores = [r["overall_score"] for r in results if r["overall_score"] is not None]
        passed = sum(1 for r in results if r.get("pass"))
        total = len(results)
        return {
            "total": total,
            "avg": round(sum(scores) / len(scores), 2) if scores else 0,
            "max": max(scores) if scores else 0,
            "min": min(scores) if scores else 0,
            "passed": passed,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
        }

    s1 = stats(results1)
    s2 = stats(results2)

    # 维度对比
    dimensions = ["instruction_following", "content_accuracy", "format_compliance",
                  "completeness", "consistency"]

    def dim_avg(results, dim):
        vals = []
        for r in results:
            s = r.get("judge_result", {}).get("scores", {}).get(dim)
            if s is not None:
                vals.append(s)
        return round(sum(vals) / len(vals), 2) if vals else 0

    # L2 维度对比
    def l2_stats(results):
        groups = {}
        for r in results:
            l2 = r["l2"]
            if l2 not in groups:
                groups[l2] = []
            groups[l2].append(r)

        stats_dict = {}
        for l2, group in groups.items():
            scores = [r["overall_score"] for r in group if r["overall_score"] is not None]
            passed = sum(1 for r in group if r.get("pass"))
            stats_dict[l2] = {
                "avg": round(sum(scores) / len(scores), 2) if scores else 0,
                "pass_rate": round(passed / len(group) * 100, 1) if group else 0,
            }
        return stats_dict

    l2_s1 = l2_stats(results1)
    l2_s2 = l2_stats(results2)

    # 逐条对比 - 找出差异最大的用例
    case_diffs = []
    r1_map = {r["case_id"]: r for r in results1}
    r2_map = {r["case_id"]: r for r in results2}

    common_cases = set(r1_map.keys()) & set(r2_map.keys())
    for cid in common_cases:
        s1_score = r1_map[cid].get("overall_score") or 0
        s2_score = r2_map[cid].get("overall_score") or 0
        diff = s1_score - s2_score
        case_diffs.append({
            "case_id": cid,
            "l2": r1_map[cid]["l2"],
            "l3": r1_map[cid]["l3"],
            "score1": s1_score,
            "score2": s2_score,
            "diff": round(diff, 1),
        })

    case_diffs.sort(key=lambda x: abs(x["diff"]), reverse=True)

    # 生成报告
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""# 多模型对比评测报告

## 生成时间
{now}

## 1. 对比概览

| 指标 | {name1} | {name2} | 差异 |
|------|---------|---------|------|
| 测试用例数 | {s1['total']} | {s2['total']} | - |
| **平均分** | **{s1['avg']}** | **{s2['avg']}** | **{s1['avg'] - s2['avg']:+.2f}** |
| 最高分 | {s1['max']} | {s2['max']} | {s1['max'] - s2['max']:+.1f} |
| 最低分 | {s1['min']} | {s2['min']} | {s1['min'] - s2['min']:+.1f} |
| 通过数 | {s1['passed']}/{s1['total']} | {s2['passed']}/{s2['total']} | - |
| **通过率** | **{s1['pass_rate']}%** | **{s2['pass_rate']}%** | **{s1['pass_rate'] - s2['pass_rate']:+.1f}%** |

## 2. 五维度评分对比

| 评分维度 | {name1} | {name2} | 差异 |
|----------|---------|---------|------|
"""
    for dim in dimensions:
        d1 = dim_avg(results1, dim)
        d2 = dim_avg(results2, dim)
        diff = d1 - d2
        dim_cn = {
            "instruction_following": "指令完成度",
            "content_accuracy": "内容准确性",
            "format_compliance": "格式正确性",
            "completeness": "完整性",
            "consistency": "上下文一致性",
        }[dim]
        report += f"| {dim_cn} | {d1} | {d2} | {diff:+.2f} |\n"

    report += f"""
## 3. 按 L2 维度对比

| L2 维度 | {name1} 平均分 | {name2} 平均分 | {name1} 通过率 | {name2} 通过率 |
|---------|---------------|---------------|---------------|---------------|
"""
    all_l2 = sorted(set(list(l2_s1.keys()) + list(l2_s2.keys())))
    for l2 in all_l2:
        a1 = l2_s1.get(l2, {}).get("avg", "-")
        a2 = l2_s2.get(l2, {}).get("avg", "-")
        p1 = l2_s1.get(l2, {}).get("pass_rate", "-")
        p2 = l2_s2.get(l2, {}).get("pass_rate", "-")
        report += f"| {l2} | {a1} | {a2} | {p1}% | {p2}% |\n"

    report += f"""
## 4. 差异最大的用例 TOP10

以下用例在两个模型上得分差异最大：

| Case ID | L2 | L3 | {name1} | {name2} | 差异 |
|---------|----|----|---------|---------|------|
"""
    for item in case_diffs[:10]:
        report += f"| {item['case_id']} | {item['l2']} | {item['l3']} | {item['score1']} | {item['score2']} | {item['diff']:+.1f} |\n"

    # Bad cases unique to each
    bad1 = set(r["case_id"] for r in results1 if not r.get("pass"))
    bad2 = set(r["case_id"] for r in results2 if not r.get("pass"))
    only_bad_in_1 = bad1 - bad2
    only_bad_in_2 = bad2 - bad1
    both_bad = bad1 & bad2

    report += f"""
## 5. Bad Case 对比分析

| 类别 | 数量 | Case IDs |
|------|------|----------|
| 仅 {name1} 失败 | {len(only_bad_in_1)} | {', '.join(sorted(only_bad_in_1)) or '无'} |
| 仅 {name2} 失败 | {len(only_bad_in_2)} | {', '.join(sorted(only_bad_in_2)) or '无'} |
| 两者都失败 | {len(both_bad)} | {', '.join(sorted(both_bad)) or '无'} |

## 6. 结论

"""
    if s1['avg'] > s2['avg']:
        winner = name1
        loser = name2
        diff_score = s1['avg'] - s2['avg']
    else:
        winner = name2
        loser = name1
        diff_score = s2['avg'] - s1['avg']

    report += f"""- **{winner}** 综合表现优于 **{loser}**，平均分高出 {diff_score:.2f} 分。
- {name1} 通过率 {s1['pass_rate']}%，{name2} 通过率 {s2['pass_rate']}%。
- 差异主要体现在：得分差异最大的 L2 维度可作为后续重点优化方向。
- 建议：对两者都失败的用例进行深入 Bad Case 分析，可能反映出测试用例本身的设计问题或该场景的普遍挑战。
"""

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    # 同时保存结构化对比数据
    comparison_data = {
        "generated_at": now,
        "model1": {"name": name1, "stats": s1},
        "model2": {"name": name2, "stats": s2},
        "dimension_comparison": {
            dim: {"model1": dim_avg(results1, dim), "model2": dim_avg(results2, dim)}
            for dim in dimensions
        },
        "top_diffs": case_diffs[:10],
        "bad_case_analysis": {
            "only_model1_fail": list(only_bad_in_1),
            "only_model2_fail": list(only_bad_in_2),
            "both_fail": list(both_bad),
        }
    }
    json_path = output_path.parent / "comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 对比报告已生成: {output_path}")
    print(f"✅ 对比数据已生成: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="多模型对比报告生成")
    parser.add_argument("--run1", type=str, required=True, help="第一次运行的输出目录")
    parser.add_argument("--run2", type=str, required=True, help="第二次运行的输出目录")
    parser.add_argument("--name1", type=str, default="Model A", help="第一个模型的显示名称")
    parser.add_argument("--name2", type=str, default="Model B", help="第二个模型的显示名称")
    parser.add_argument("--output", type=str, default=None, help="对比报告输出路径")

    args = parser.parse_args()

    run1_dir = Path(args.run1)
    run2_dir = Path(args.run2)

    if not run1_dir.exists():
        run1_dir = project_root / args.run1
    if not run2_dir.exists():
        run2_dir = project_root / args.run2

    print(f"📊 对比: {args.name1} vs {args.name2}")
    print(f"  Run 1: {run1_dir}")
    print(f"  Run 2: {run2_dir}")

    results1 = load_results(run1_dir)
    results2 = load_results(run2_dir)

    print(f"  Run 1 用例数: {len(results1)}")
    print(f"  Run 2 用例数: {len(results2)}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = project_root / "outputs" / "comparison_report.md"

    generate_comparison(results1, results2, args.name1, args.name2, output_path)


if __name__ == "__main__":
    main()
