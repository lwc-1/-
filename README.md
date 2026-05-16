# 面向办公文档场景的大模型自动化评测系统

## 项目背景

本项目模拟 AI 模型评测岗位的真实工作流程，针对办公文档处理场景（信息抽取、文档摘要、格式转换、多轮上下文），构建端到端的自动化评测系统。

## 评测流程

```
测试用例集 → 被测模型回答 → 规则校验 → LLM-as-Judge 评分 → 数据分析 → 测试报告
```

## 项目功能

1. **测试用例管理**：30 条中文办公文档处理测试用例，支持单轮/多轮对话
2. **自动化评测**：调用被测模型 API 获取回答，自动执行规则校验和 LLM-as-Judge 评分
3. **分层评测框架**：L1-L3 三级评测框架，覆盖 4 类办公文档处理能力
4. **Bad Case 分析**：自动识别低分用例，归因问题类型，提供优化建议
5. **测试报告生成**：自动生成 Markdown 格式测试报告和结构化统计数据
6. **人工抽检支持**：生成人工复核模板，支持机评与人评对比

## 评测框架

```
L1：办公文档处理能力
├── L2：信息抽取
│   ├── L3：会议纪要待办抽取
│   ├── L3：合同/通知关键信息抽取
│   └── L3：表格字段抽取
├── L2：文档摘要
│   ├── L3：会议纪要摘要
│   ├── L3：产品需求文档摘要
│   └── L3：用户反馈摘要
├── L2：格式转换
│   ├── L3：文本转 JSON
│   ├── L3：文本转 Markdown 表格
│   └── L3：非结构化内容转结构化清单
└── L2：多轮上下文
    ├── L3：基于前文生成邮件
    ├── L3：根据追加要求修改输出
    └── L3：压缩内容但保留关键信息
```

## 安装方式

```bash
cd llm-office-eval
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 配置方式

复制 `.env.example` 为 `.env`，填入 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
CANDIDATE_API_KEY=你的DeepSeek Key
CANDIDATE_BASE_URL=https://api.deepseek.com
CANDIDATE_MODEL=deepseek-chat

JUDGE_API_KEY=你的DeepSeek Key
JUDGE_BASE_URL=https://api.deepseek.com
JUDGE_MODEL=deepseek-chat

TEMPERATURE=0.2
MAX_TOKENS=1500
```

## 运行方式

### Mock 模式（无需 API Key）

```bash
python scripts/run_eval.py --cases data/cases_seed.jsonl --max-cases 3 --mock
```

### 真实 API 模式

```bash
# 先跑 5 条测试
python scripts/run_eval.py --cases data/cases_seed.jsonl --max-cases 5

# 跑完整 30 条
python scripts/run_eval.py --cases data/cases_seed.jsonl
```

### 生成人工抽检模板

```bash
python scripts/make_human_review.py --results outputs/你的输出目录/results.csv
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--cases` | 测试用例文件路径 |
| `--max-cases` | 最大运行用例数 |
| `--output-dir` | 输出目录（默认自动生成时间戳目录） |
| `--mock` | Mock 模式，无需 API Key |

## 输出文件说明

每次运行会在 `outputs/` 下生成一个时间戳目录：

```
outputs/20240516_143000/
├── results.jsonl      # 逐条评测结果（JSON Lines）
├── results.csv        # 评测结果表格
├── report.md          # Markdown 测试报告
└── summary.json       # 结构化统计数据
```

## 如何扩展到其他模型

本项目使用 OpenAI-compatible API，只需修改 `.env` 即可切换模型：

**GPT-4：**
```env
CANDIDATE_BASE_URL=https://api.openai.com/v1
CANDIDATE_MODEL=gpt-4
```

**硅基流动：**
```env
CANDIDATE_BASE_URL=https://api.siliconflow.cn/v1
CANDIDATE_MODEL=deepseek-ai/DeepSeek-V2-Chat
```

**Claude（通过兼容接口）：**
```env
CANDIDATE_BASE_URL=你的兼容接口地址
CANDIDATE_MODEL=claude-3-sonnet
```

## 技术栈

- Python 3.10+
- openai SDK（OpenAI-compatible API 调用）
- python-dotenv（环境变量管理）
- pandas（数据处理）
- tqdm（进度条）
- tenacity（重试机制）
