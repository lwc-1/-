"""评测执行器 - 端到端自动化评测流程"""

import json
import time
from pathlib import Path
from datetime import datetime

from tqdm import tqdm

from .config import Config
from .case_loader import load_cases
from .llm_client import OpenAICompatibleClient, MockLLMClient
from .rule_checks import run_rule_checks
from .judge import build_judge_prompt, parse_judge_response
from .report import generate_report, generate_summary


class EvaluationRunner:
    """评测执行器"""

    def __init__(self, cases_path: str, output_dir: str | None = None,
                 max_cases: int | None = None, mock: bool = False):
        """
        初始化评测执行器。

        Args:
            cases_path: 测试用例文件路径
            output_dir: 输出目录（为空则自动生成时间戳目录）
            max_cases: 最大运行用例数
            mock: 是否使用 Mock 模式
        """
        self.cases_path = cases_path
        self.max_cases = max_cases
        self.mock = mock or Config.is_mock_mode()

        # 设置输出目录
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = Path("outputs") / timestamp
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化客户端
        self._init_clients()

    def _init_clients(self):
        """初始化 LLM 客户端"""
        if self.mock:
            print("🔧 运行模式: Mock（模拟模式，不调用真实 API）")
            self.candidate_client = MockLLMClient(role="candidate")
            self.judge_client = MockLLMClient(role="judge")
        else:
            print("🚀 运行模式: 真实 API")
            Config.print_config()
            self.candidate_client = OpenAICompatibleClient(
                api_key=Config.candidate_api_key,
                base_url=Config.candidate_base_url,
                model=Config.candidate_model,
                temperature=Config.temperature,
                max_tokens=Config.max_tokens,
            )
            self.judge_client = OpenAICompatibleClient(
                api_key=Config.judge_api_key,
                base_url=Config.judge_base_url,
                model=Config.judge_model,
                temperature=0.1,  # Judge 用更低温度保证稳定性
                max_tokens=2000,
            )

    def run(self) -> list[dict]:
        """
        执行完整评测流程。

        Returns:
            所有评测结果列表
        """
        # 1. 加载用例
        cases = load_cases(self.cases_path)
        if self.max_cases:
            cases = cases[:self.max_cases]
            print(f"📋 本次运行 {len(cases)} 条用例（限制 max_cases={self.max_cases}）")
        else:
            print(f"📋 本次运行全部 {len(cases)} 条用例")

        print(f"📁 输出目录: {self.output_dir}")
        print()

        # 2. 逐条执行评测
        results = []
        results_file = self.output_dir / "results.jsonl"

        for case in tqdm(cases, desc="评测进度"):
            result = self._evaluate_single_case(case)
            results.append(result)

            # 每跑完一条就落盘
            with open(results_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

        # 3. 生成输出文件
        self._save_results(results)

        # 4. 打印总结
        self._print_summary(results)

        return results

    def _evaluate_single_case(self, case: dict) -> dict:
        """执行单条用例的评测"""
        case_id = case["case_id"]
        case_type = case["case_type"]
        turns = case["turns"]

        # Step 1: 调用被测模型
        transcript = []
        final_answer = ""

        if case_type == "single_turn":
            # 单轮对话
            messages = [{"role": "user", "content": turns[0]["content"]}]
            final_answer = self.candidate_client.chat(messages)
            transcript = messages + [{"role": "assistant", "content": final_answer}]

        elif case_type == "multi_turn":
            # 多轮对话：逐轮调用，保持上下文
            messages = []
            for turn in turns:
                messages.append({"role": "user", "content": turn["content"]})
                response = self.candidate_client.chat(messages)
                messages.append({"role": "assistant", "content": response})
                final_answer = response
            transcript = messages

        # Step 2: 规则校验
        rule_check_result = run_rule_checks(final_answer, case)

        # Step 3: LLM-as-Judge 评分
        judge_messages = build_judge_prompt(case, transcript, final_answer, rule_check_result)
        judge_response = self.judge_client.chat(judge_messages)
        judge_result = parse_judge_response(judge_response, case_id)

        # Step 4: 组装结果
        result = {
            "case_id": case_id,
            "l1": case["l1"],
            "l2": case["l2"],
            "l3": case["l3"],
            "case_type": case_type,
            "final_answer": final_answer,
            "rule_check_result": rule_check_result,
            "judge_result": judge_result,
            "overall_score": judge_result.get("overall_score"),
            "pass": judge_result.get("pass"),
            "bad_case_tags": judge_result.get("bad_case_tags", []),
            "improvement_suggestions": judge_result.get("improvement_suggestions", []),
        }

        return result

    def _save_results(self, results: list[dict]):
        """保存所有评测结果"""
        import pandas as pd

        # 保存 CSV
        csv_path = self.output_dir / "results.csv"
        flat_results = []
        for r in results:
            flat = {
                "case_id": r["case_id"],
                "l1": r["l1"],
                "l2": r["l2"],
                "l3": r["l3"],
                "case_type": r["case_type"],
                "overall_score": r["overall_score"],
                "pass": r["pass"],
                "format_valid": r["rule_check_result"].get("format_valid"),
                "rule_score_hint": r["rule_check_result"].get("rule_score_hint"),
                "bad_case_tags": "; ".join(r.get("bad_case_tags", [])),
                "final_answer": r["final_answer"][:200],  # 截断
            }
            # 展开 judge scores
            scores = r.get("judge_result", {}).get("scores", {})
            for dim, score in scores.items():
                flat[dim] = score
            flat_results.append(flat)

        df = pd.DataFrame(flat_results)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        # 生成 Markdown 报告
        report_path = self.output_dir / "report.md"
        report_content = generate_report(results, self.mock)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        # 生成 summary.json
        summary_path = self.output_dir / "summary.json"
        summary = generate_summary(results)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n📄 结果文件已生成:")
        print(f"  - {csv_path}")
        print(f"  - {report_path}")
        print(f"  - {summary_path}")
        print(f"  - {self.output_dir / 'results.jsonl'}")

    def _print_summary(self, results: list[dict]):
        """打印评测总结"""
        total = len(results)
        scores = [r["overall_score"] for r in results if r["overall_score"] is not None]
        passed = sum(1 for r in results if r.get("pass") is True)

        print(f"\n{'='*50}")
        print(f"📊 评测总结")
        print(f"{'='*50}")
        print(f"  总用例数: {total}")
        if scores:
            print(f"  平均分: {sum(scores)/len(scores):.2f}")
            print(f"  通过数: {passed}/{total} (通过率 {passed/total*100:.1f}%)")
            print(f"  最高分: {max(scores):.1f}")
            print(f"  最低分: {min(scores):.1f}")
        print(f"{'='*50}")
