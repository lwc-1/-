"""
评测运行脚本 - 端到端执行大模型办公文档处理能力评测

使用方式：
    # Mock 模式（无需 API Key）
    python scripts/run_eval.py --cases data/cases_seed.jsonl --max-cases 3 --mock

    # 真实 API 模式（跑5条）
    python scripts/run_eval.py --cases data/cases_seed.jsonl --max-cases 5

    # 完整运行
    python scripts/run_eval.py --cases data/cases_seed.jsonl

    # 指定输出目录
    python scripts/run_eval.py --cases data/cases_seed.jsonl --output-dir outputs/test_run
"""

import sys
import argparse
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.evaluator import EvaluationRunner


def main():
    parser = argparse.ArgumentParser(
        description="面向办公文档场景的大模型自动化评测系统"
    )
    parser.add_argument(
        "--cases",
        type=str,
        required=True,
        help="测试用例文件路径（JSONL 格式）",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="最大运行用例数（不指定则运行全部）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="输出目录（不指定则自动生成时间戳目录）",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用 Mock 模式运行（不调用真实 API）",
    )
    parser.add_argument(
        "--candidate-model",
        type=str,
        default=None,
        help="覆盖被测模型名称（如 deepseek-chat, Qwen/Qwen2.5-7B-Instruct）",
    )
    parser.add_argument(
        "--candidate-base-url",
        type=str,
        default=None,
        help="覆盖被测模型 Base URL",
    )
    parser.add_argument(
        "--candidate-api-key",
        type=str,
        default=None,
        help="覆盖被测模型 API Key",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="本次运行的标签名（用于区分不同模型的结果）",
    )

    args = parser.parse_args()

    # 验证用例文件存在
    cases_path = Path(args.cases)
    if not cases_path.exists():
        # 尝试从项目根目录查找
        cases_path = project_root / args.cases
        if not cases_path.exists():
            print(f"❌ 测试用例文件不存在: {args.cases}")
            sys.exit(1)

    print("=" * 60)
    print("  面向办公文档场景的大模型自动化评测系统")
    print("=" * 60)
    print()

    # 应用命令行覆盖配置
    from src.config import Config
    if args.candidate_model:
        Config.candidate_model = args.candidate_model
    if args.candidate_base_url:
        Config.candidate_base_url = args.candidate_base_url
    if args.candidate_api_key:
        Config.candidate_api_key = args.candidate_api_key

    # 确定输出目录
    output_dir = args.output_dir
    if not output_dir and args.run_name:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/{args.run_name}_{timestamp}"

    # 创建并运行评测
    runner = EvaluationRunner(
        cases_path=str(cases_path),
        output_dir=output_dir,
        max_cases=args.max_cases,
        mock=args.mock,
    )

    try:
        results = runner.run()
        print("\n✅ 评测完成！")
    except KeyboardInterrupt:
        print("\n\n⚠️  评测被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 评测过程出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
