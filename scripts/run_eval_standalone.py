"""
独立运行验证脚本 - 使用纯标准库验证项目逻辑（无需安装第三方依赖）

用途：在没有安装 openai/pandas/tqdm/tenacity 的环境中验证核心逻辑可运行。
实际使用时请安装 requirements.txt 中的依赖后使用 run_eval.py。

使用方式：
    python scripts/run_eval_standalone.py
"""

import sys
import json
import os
import re
import random
from pathlib import Path
from datetime import datetime

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ===== 内联的核心逻辑（不依赖第三方包） =====

def load_cases(path: str) -> list:
    """加载测试用例"""
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
                cases.append(case)
            except json.JSONDecodeError as e:
                print(f"  警告: 第 {i} 行 JSON 解析失败 - {e}")
    return cases


def mock_candidate_response(messages: list) -> str:
    """模拟被测模型回答"""
    user_msg = messages[-1]["content"] if messages else ""

    if "JSON" in user_msg or "json" in user_msg:
        return '''[
  {"task": "完成首页提测", "owner": "张三", "deadline": "5月15日"},
  {"task": "接口文档更新", "owner": "李四", "deadline": "5月12日"},
  {"task": "修复服务器配置", "owner": "赵六", "deadline": "5月11日"},
  {"task": "用户反馈模块开发", "owner": "张三和李四", "deadline": "5月20日"}
]'''
    elif "Markdown" in user_msg or "表格" in user_msg:
        return '''| 阶段 | 负责人 | 开始时间 | 结束时间 | 交付物 |
|------|--------|----------|----------|--------|
| 需求分析 | 张琳 | 5月1日 | 5月15日 | PRD |
| 设计 | 李明 | 5月16日 | 5月31日 | 设计稿 |
| 开发 | 王强 | 6月1日 | 7月15日 | 可测试版本 |
| 测试 | 赵芳 | 7月16日 | 7月31日 | 测试报告 |
| 上线部署 | 钱进 | 8月1日 | 8月5日 | 上线checklist |'''
    elif "摘要" in user_msg or "压缩" in user_msg or "精简" in user_msg:
        return "本次会议决定MVP版本延期至8月15日发布，7月1日前完成技术方案评审。Q3优先级：AI助手>性能优化>国际化。计划紧急招聘2名AI工程师，6月底前到岗。"
    elif "邮件" in user_msg:
        return """主题：关于技术分享活动通知

各位技术部同事：

兹定于下周三下午2:00-4:00在3楼大会议室举办技术分享活动，主题为"微服务架构实践"。

请全体同事准时参加，并请提前准备好笔记本电脑。

如有疑问请联系我。

此致"""
    else:
        return "根据您提供的文档内容，我已完成信息整理。核心要点如下：\n1. 已完成关键信息提取\n2. 数据准确性已确认\n3. 建议持续关注优先级最高的事项"


def mock_judge_response(case_id: str) -> dict:
    """模拟 Judge 评分"""
    scores = {
        "instruction_following": random.randint(3, 5),
        "content_accuracy": random.randint(3, 5),
        "format_compliance": random.randint(3, 5),
        "completeness": random.randint(3, 5),
        "consistency": random.randint(4, 5),
    }
    overall = round(sum(scores.values()) / len(scores), 1)
    return {
        "case_id": case_id,
        "scores": scores,
        "overall_score": overall,
        "pass": overall >= 4.0,
        "rationale": "Mock评分：模型回答基本完成指令要求。" if overall >= 4.0 else "Mock评分：部分维度存在不足。",
        "bad_case_tags": [] if overall >= 4.0 else ["minor_issue"],
        "improvement_suggestions": [] if overall >= 4.5 else ["建议加强格式约束"],
    }


def run_rule_checks(answer: str, case: dict) -> dict:
    """规则校验"""
    result = {"format_valid": True, "missing_keywords": [], "length_valid": True, "rule_score_hint": 5, "notes": []}

    expected_format = case.get("expected_format", "")
    constraints = case.get("constraints", {})

    # JSON 格式检查
    if expected_format == "json":
        try:
            # 提取 JSON
            text = answer
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
            if match:
                text = match.group(1)
            else:
                for i, ch in enumerate(text):
                    if ch in ('[', '{'):
                        text = text[i:]
                        break
            json.loads(text)
        except (json.JSONDecodeError, TypeError):
            result["format_valid"] = False
            result["notes"].append("JSON格式不合法")

    # Markdown 表格检查
    elif expected_format == "markdown_table":
        if "|" not in answer or "---" not in answer:
            result["format_valid"] = False
            result["notes"].append("缺少Markdown表格特征")

    # 关键词检查
    must_include = constraints.get("must_include", [])
    for kw in must_include:
        if kw not in answer:
            result["missing_keywords"].append(kw)

    # 长度检查
    max_words = constraints.get("max_words")
    if max_words:
        content_len = len(re.sub(r'\s+', '', answer))
        if content_len > max_words * 1.2:
            result["length_valid"] = False
            result["notes"].append(f"内容过长: {content_len}字符 (限制{max_words})")

    # 计算 rule_score_hint
    score = 5
    if not result["format_valid"]:
        score -= 2
    if len(result["missing_keywords"]) >= 3:
        score -= 2
    elif len(result["missing_keywords"]) >= 1:
        score -= 1
    if not result["length_valid"]:
        score -= 1
    result["rule_score_hint"] = max(1, score)

    return result


def evaluate_case(case: dict) -> dict:
    """评测单条用例"""
    case_id = case["case_id"]
    turns = case["turns"]

    # 调用被测模型 (mock)
    if case["case_type"] == "single_turn":
        messages = [{"role": "user", "content": turns[0]["content"]}]
        final_answer = mock_candidate_response(messages)
    else:
        messages = []
        final_answer = ""
        for turn in turns:
            messages.append({"role": "user", "content": turn["content"]})
            final_answer = mock_candidate_response(messages)
            messages.append({"role": "assistant", "content": final_answer})

    # 规则校验
    rule_result = run_rule_checks(final_answer, case)

    # Judge 评分 (mock)
    judge_result = mock_judge_response(case_id)

    return {
        "case_id": case_id,
        "l1": case["l1"],
        "l2": case["l2"],
        "l3": case["l3"],
        "case_type": case["case_type"],
        "final_answer": final_answer,
        "rule_check_result": rule_result,
        "judge_result": judge_result,
        "overall_score": judge_result["overall_score"],
        "pass": judge_result["pass"],
        "bad_case_tags": judge_result["bad_case_tags"],
        "improvement_suggestions": judge_result["improvement_suggestions"],
    }


def generate_csv(results: list, output_path: Path):
    """生成 CSV（纯标准库实现）"""
    import csv
    fields = ["case_id", "l1", "l2", "l3", "case_type", "overall_score", "pass",
              "format_valid", "rule_score_hint",
              "instruction_following", "content_accuracy", "format_compliance",
              "completeness", "consistency", "bad_case_tags", "final_answer"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            row = {
                "case_id": r["case_id"],
                "l1": r["l1"],
                "l2": r["l2"],
                "l3": r["l3"],
                "case_type": r["case_type"],
                "overall_score": r["overall_score"],
                "pass": r["pass"],
                "format_valid": r["rule_check_result"]["format_valid"],
                "rule_score_hint": r["rule_check_result"]["rule_score_hint"],
                "bad_case_tags": "; ".join(r.get("bad_case_tags", [])),
                "final_answer": r["final_answer"][:200],
            }
            scores = r.get("judge_result", {}).get("scores", {})
            for dim in ["instruction_following", "content_accuracy", "format_compliance",
                        "completeness", "consistency"]:
                row[dim] = scores.get(dim, "")
            writer.writerow(row)


def generate_report(results: list, output_path: Path):
    """生成 Markdown 报告"""
    total = len(results)
    scores = [r["overall_score"] for r in results if r["overall_score"] is not None]
    passed = sum(1 for r in results if r.get("pass"))
    avg_score = sum(scores) / len(scores) if scores else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # L2 统计
    l2_stats = {}
    for r in results:
        l2 = r["l2"]
        if l2 not in l2_stats:
            l2_stats[l2] = {"scores": [], "passed": 0, "total": 0}
        l2_stats[l2]["total"] += 1
        if r["overall_score"] is not None:
            l2_stats[l2]["scores"].append(r["overall_score"])
        if r.get("pass"):
            l2_stats[l2]["passed"] += 1

    report = f"""# 大模型办公文档处理能力评测报告

## 1. 评测配置

| 配置项 | 值 |
|--------|-----|
| 运行模式 | Mock 模拟模式 |
| 生成时间 | {now} |
| 测试用例数 | {total} |

## 2. 整体评测结果

| 指标 | 数值 |
|------|------|
| 总用例数 | {total} |
| 平均分 | {avg_score:.2f} / 5.0 |
| 通过数 | {passed} |
| 通过率 | {passed/total*100:.1f}% |
| 最高分 | {max(scores):.1f} |
| 最低分 | {min(scores):.1f} |

## 3. 按 L2 维度评分

| L2 维度 | 用例数 | 平均分 | 通过率 |
|---------|--------|--------|--------|
"""
    for l2, stat in l2_stats.items():
        avg = sum(stat["scores"]) / len(stat["scores"]) if stat["scores"] else 0
        rate = stat["passed"] / stat["total"] * 100 if stat["total"] > 0 else 0
        report += f"| {l2} | {stat['total']} | {avg:.2f} | {rate:.1f}% |\n"

    report += f"""
## 4. Bad Case 列表

"""
    bad_cases = [r for r in results if not r.get("pass")]
    if bad_cases:
        for bc in sorted(bad_cases, key=lambda x: x.get("overall_score", 0))[:5]:
            report += f"- **{bc['case_id']}** (L2: {bc['l2']}) - 得分: {bc['overall_score']}\n"
    else:
        report += "无 Bad Case，所有用例均通过。\n"

    report += f"""
## 5. 优化建议

1. 对于格式要求严格的用例，建议在 prompt 中添加格式示例
2. 对于信息抽取类用例，建议增加"不遗漏"的显式约束
3. 多轮对话场景建议优化上下文管理策略

---
*报告生成时间: {now}*
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)


def main():
    print("=" * 60)
    print("  面向办公文档场景的大模型自动化评测系统")
    print("  [Mock 模式 - 独立验证脚本]")
    print("=" * 60)
    print()

    # 加载用例
    cases_path = ROOT / "data" / "cases_seed.jsonl"
    print(f"📂 加载测试用例: {cases_path}")
    cases = load_cases(str(cases_path))
    print(f"✅ 成功加载 {len(cases)} 条用例")

    # 限制运行数量（验证用）
    max_cases = 5
    cases = cases[:max_cases]
    print(f"📋 本次验证运行 {len(cases)} 条用例")
    print()

    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ROOT / "outputs" / f"mock_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 执行评测
    results = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] 评测 {case['case_id']} ({case['l2']} - {case['l3']})")
        result = evaluate_case(case)
        results.append(result)
        status = "✅ PASS" if result["pass"] else "❌ FAIL"
        print(f"         {status} (得分: {result['overall_score']})")

    print()

    # 保存结果
    # JSONL
    jsonl_path = output_dir / "results.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # CSV
    csv_path = output_dir / "results.csv"
    generate_csv(results, csv_path)

    # Report
    report_path = output_dir / "report.md"
    generate_report(results, report_path)

    # Summary JSON
    total = len(results)
    scores = [r["overall_score"] for r in results]
    passed = sum(1 for r in results if r["pass"])
    summary = {
        "generated_at": datetime.now().isoformat(),
        "mode": "mock",
        "total_cases": total,
        "avg_score": round(sum(scores) / len(scores), 2),
        "pass_count": passed,
        "pass_rate": round(passed / total * 100, 1),
    }
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 打印总结
    print(f"{'='*50}")
    print(f"📊 评测总结")
    print(f"{'='*50}")
    print(f"  总用例数: {total}")
    print(f"  平均分: {summary['avg_score']}")
    print(f"  通过率: {passed}/{total} ({summary['pass_rate']}%)")
    print(f"{'='*50}")
    print()
    print(f"📄 输出文件:")
    print(f"  - {jsonl_path}")
    print(f"  - {csv_path}")
    print(f"  - {report_path}")
    print(f"  - {summary_path}")
    print()
    print("✅ Mock 模式验证完成！")


if __name__ == "__main__":
    main()
