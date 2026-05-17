"""
评测全流程自动化 Agent

输入产品功能描述 → 自动生成测试用例 → 执行评测 → 输出报告

使用方式：
    # 交互模式（手动输入产品描述）
    python scripts/run_agent.py

    # 指定产品描述文件
    python scripts/run_agent.py --input docs/product_desc.txt

    # 指定生成用例数量
    python scripts/run_agent.py --input docs/product_desc.txt --num-cases 10

    # Mock 模式（不调用 API）
    python scripts/run_agent.py --mock
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config import Config
from src.llm_client import OpenAICompatibleClient, MockLLMClient
from src.evaluator import EvaluationRunner


CASE_GENERATION_PROMPT = """你是一个专业的AI模型评测工程师。请根据以下产品功能描述，自动生成测试用例。

要求：
1. 每条测试用例为一个JSON对象，字段包括：case_id, l1, l2, l3, case_type, turns, reference_points, expected_format, constraints, judge_notes
2. l1 固定为"办公文档处理能力"
3. l2 从以下选择：信息抽取、文档摘要、格式转换、多轮上下文
4. case_type 为 single_turn 或 multi_turn
5. turns 为数组，每条包含 role 和 content
6. 用例要贴合产品实际使用场景，有明确的评判标准
7. 包含至少2条边界条件用例（如格式强约束、信息缺失处理等）
8. 输出严格为JSON数组，不要输出任何其他文字

请生成 {num_cases} 条测试用例。

产品功能描述：
{product_description}
"""


def generate_cases_with_llm(product_desc: str, num_cases: int, client) -> list[dict]:
    """调用LLM自动生成测试用例"""
    prompt = CASE_GENERATION_PROMPT.format(
        product_description=product_desc,
        num_cases=num_cases
    )

    print("🤖 Agent Step 1/3: 正在根据产品描述自动生成测试用例...")
    response = client.chat([
        {"role": "system", "content": "你是一个专业的AI评测工程师，严格按JSON格式输出。"},
        {"role": "user", "content": prompt}
    ], max_tokens=4000)

    # 解析JSON
    try:
        # 处理可能的```json包裹
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", response, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # 找第一个[开始
            start = response.find("[")
            end = response.rfind("]")
            if start >= 0 and end > start:
                json_str = response[start:end+1]
            else:
                json_str = response

        cases = json.loads(json_str)
        if isinstance(cases, list):
            print(f"   ✅ 成功生成 {len(cases)} 条测试用例")
            return cases
        else:
            print("   ⚠️ LLM输出格式异常，使用默认用例")
            return []
    except (json.JSONDecodeError, TypeError) as e:
        print(f"   ⚠️ 用例解析失败: {e}")
        print(f"   原始输出前200字: {response[:200]}")
        return []


def save_generated_cases(cases: list[dict], output_path: Path):
    """保存生成的用例到JSONL文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(f"   📄 用例已保存: {output_path}")


def run_agent(product_desc: str, num_cases: int = 8, mock: bool = False):
    """
    Agent 主流程：
    1. 根据产品描述生成测试用例
    2. 执行自动化评测
    3. 生成测试报告
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = project_root / "outputs" / f"agent_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  评测全流程自动化 Agent")
    print("=" * 60)
    print(f"\n📝 产品描述: {product_desc[:100]}...")
    print(f"📋 计划生成: {num_cases} 条测试用例")
    print(f"📁 输出目录: {output_dir}")
    print()

    # Step 1: 生成测试用例
    if mock:
        print("🔧 运行模式: Mock")
        client = MockLLMClient(role="candidate")
        # Mock模式使用预设用例
        cases = [
            {
                "case_id": f"AGENT-{i:03d}",
                "l1": "办公文档处理能力",
                "l2": ["信息抽取", "文档摘要", "格式转换", "多轮上下文"][i % 4],
                "l3": "自动生成用例",
                "case_type": "single_turn",
                "turns": [{"role": "user", "content": f"请根据以下内容提取关键信息：{product_desc[:50]}"}],
                "reference_points": ["关键信息完整提取"],
                "expected_format": "json",
                "constraints": {"must_include": [], "max_words": None},
                "judge_notes": "检查信息提取是否完整准确"
            }
            for i in range(num_cases)
        ]
        print(f"   ✅ Mock模式生成 {len(cases)} 条用例")
    else:
        if Config.is_mock_mode():
            print("❌ 未配置API Key，请先配置.env文件")
            sys.exit(1)

        client = OpenAICompatibleClient(
            api_key=Config.candidate_api_key,
            base_url=Config.candidate_base_url,
            model=Config.candidate_model,
            temperature=0.7,  # 生成用例用较高温度保证多样性
            max_tokens=4000,
        )
        cases = generate_cases_with_llm(product_desc, num_cases, client)

        if not cases:
            print("❌ 用例生成失败，退出")
            sys.exit(1)

    # 保存生成的用例
    cases_path = output_dir / "generated_cases.jsonl"
    save_generated_cases(cases, cases_path)

    # Step 2: 执行评测
    print(f"\n🤖 Agent Step 2/3: 正在执行自动化评测...")
    runner = EvaluationRunner(
        cases_path=str(cases_path),
        output_dir=str(output_dir),
        max_cases=None,
        mock=mock,
    )
    results = runner.run()

    # Step 3: 输出总结
    print(f"\n🤖 Agent Step 3/3: 评测报告已生成")
    print()
    print("=" * 60)
    print("  Agent 执行完成")
    print("=" * 60)
    print(f"  输入: 产品功能描述 ({len(product_desc)} 字)")
    print(f"  生成: {len(cases)} 条测试用例")
    print(f"  评测: 已完成")
    print(f"  报告: {output_dir / 'report.md'}")
    print("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(description="评测全流程自动化Agent")
    parser.add_argument("--input", type=str, default=None, help="产品描述文件路径")
    parser.add_argument("--num-cases", type=int, default=8, help="生成测试用例数量（默认8条）")
    parser.add_argument("--mock", action="store_true", help="Mock模式运行")

    args = parser.parse_args()

    # 获取产品描述
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            input_path = project_root / args.input
        if not input_path.exists():
            print(f"❌ 文件不存在: {args.input}")
            sys.exit(1)
        product_desc = input_path.read_text(encoding="utf-8").strip()
    else:
        # 交互模式
        print("请输入产品功能描述（输入完毕后按两次回车）：")
        lines = []
        empty_count = 0
        while True:
            try:
                line = input()
                if line == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                    lines.append(line)
            except EOFError:
                break
        product_desc = "\n".join(lines)

    if not product_desc:
        print("❌ 产品描述为空")
        sys.exit(1)

    run_agent(product_desc, num_cases=args.num_cases, mock=args.mock)


if __name__ == "__main__":
    main()
