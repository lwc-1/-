"""
人工复核模板生成脚本

从评测结果中抽取 30% 的用例，生成人工复核表格模板。
用于对比机评和人评结果，提高评测可信度。

使用方式：
    python scripts/make_human_review.py --results outputs/20240516_143000/results.csv

    # 指定抽样比例
    python scripts/make_human_review.py --results outputs/20240516_143000/results.csv --ratio 0.5
"""

import sys
import argparse
from pathlib import Path

import pandas as pd

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="人工复核模板生成工具"
    )
    parser.add_argument(
        "--results",
        type=str,
        required=True,
        help="评测结果 CSV 文件路径",
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=0.3,
        help="抽样比例（默认 0.3，即 30%%）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出文件路径（默认保存在 results.csv 同目录下）",
    )

    args = parser.parse_args()

    # 读取结果文件
    results_path = Path(args.results)
    if not results_path.exists():
        results_path = project_root / args.results
        if not results_path.exists():
            print(f"❌ 结果文件不存在: {args.results}")
            sys.exit(1)

    print(f"📂 读取评测结果: {results_path}")
    df = pd.read_csv(results_path)
    total = len(df)

    # 抽样
    sample_size = max(1, int(total * args.ratio))
    sample_df = df.sample(n=sample_size, random_state=42)

    print(f"📊 总用例数: {total}")
    print(f"📊 抽样比例: {args.ratio*100:.0f}%")
    print(f"📊 抽样数量: {sample_size}")

    # 构建人工复核模板
    review_records = []
    for _, row in sample_df.iterrows():
        record = {
            "case_id": row["case_id"],
            "l2": row["l2"],
            "l3": row["l3"],
            "final_answer": row.get("final_answer", ""),
            "judge_overall_score": row.get("overall_score", ""),
            "judge_instruction_following": row.get("instruction_following", ""),
            "judge_content_accuracy": row.get("content_accuracy", ""),
            "judge_format_compliance": row.get("format_compliance", ""),
            "judge_completeness": row.get("completeness", ""),
            "judge_consistency": row.get("consistency", ""),
            # 以下字段留空，由人工填写
            "human_instruction_following": "",
            "human_content_accuracy": "",
            "human_format_compliance": "",
            "human_completeness": "",
            "human_consistency": "",
            "human_overall_score": "",
            "human_notes": "",
        }
        review_records.append(record)

    review_df = pd.DataFrame(review_records)

    # 保存
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = results_path.parent / "human_review_sample.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    review_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"\n✅ 人工复核模板已生成: {output_path}")
    print(f"\n📝 使用说明:")
    print(f"  1. 打开 {output_path}")
    print(f"  2. 查看 final_answer 列（模型回答）")
    print(f"  3. 对照原始测试用例，为每条填写 human_* 列的评分（1-5分）")
    print(f"  4. 在 human_notes 列记录评分理由或观察")
    print(f"  5. 对比 judge_* 和 human_* 评分差异，分析机评准确性")

    # 如果有 judge 分数，输出快速统计
    if "overall_score" in sample_df.columns:
        judge_scores = pd.to_numeric(sample_df["overall_score"], errors="coerce")
        valid_scores = judge_scores.dropna()
        if len(valid_scores) > 0:
            print(f"\n📊 抽样用例机评统计:")
            print(f"  平均分: {valid_scores.mean():.2f}")
            print(f"  最高分: {valid_scores.max():.1f}")
            print(f"  最低分: {valid_scores.min():.1f}")


if __name__ == "__main__":
    main()
