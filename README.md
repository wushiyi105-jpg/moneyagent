# 钱袋 QianDai · 智能记账财务管家 Agent

[![test](https://github.com/wushiyi105-jpg/moneyagent/actions/workflows/test.yml/badge.svg)](https://github.com/wushiyi105-jpg/moneyagent/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![零第三方依赖](https://img.shields.io/badge/dependencies-零-2ea44f)]()

> 像聊天一样记账、查账、管预算、出报告——它会自己一步步调工具完成,你看着就行。

一个**财务/生活方向**的智能体:自然语言记一笔账,由大模型通过**多步工具调用循环**完成任务——
模型自己决定调用「记一笔 / 查流水 / 查预算 / 出汇总」中的哪个工具,拿到结果再决定下一步,
直到给出最终回答。账本用 SQLite **跨会话长期保存**。

- 🧠 **多步工具调用(ReAct 风格)**:不是单次问答,模型自主规划「调哪个工具、调几次」
- 💾 **跨会话记忆**:流水与预算持久化,下次打开还在
- 🐍 零第三方依赖,Python 3.10+ 标准库即可运行
- 🖥 双入口:CLI + Web(Web 里可视化展示每一步工具调用)
- 🔌 兼容任意 OpenAI 风格接口:DeepSeek / OpenAI / 本地 Ollama 等

---

## 判定标准对照(是否算 Agent)

| 判定标准 | 满足? | 依据 |
|---|---|---|
| **模型参与** | ✅ | 运行时由大模型完成理解(口语金额/分类)、判断(重复记账/预算超支)、生成(报告与省钱建议),并通过**工具调用**执行多步任务。规则引擎仅用于无 key 时的离线演示/单测。 |
| **独立运行** | ✅ | 零第三方依赖,CLI + Web 双入口,`python -m moneyagent 午饭花了25块` 即可接收任务→执行→返回结果。 |
| **结论** | **是 Agent** | 两条均满足 |

关键边界对照:它比「单次 LLM 调用」更进一步——**模型自主决定调用哪个工具、调用几次**,
这是典型的 Agent 行为(ReAct 循环);不是「裸 prompt」、不是「仅 MCP 文件 I/O」。

> ✅ **已实测**:用 DeepSeek `deepseek-flash` 实际跑通多步工具调用
> (查重 → 记账 → 查汇总 → 查预算 → 合成回答),CLI 与 Web 均返回正确结果;11 个单元测试通过。

---

## 快速开始

```bash
cd moneyagent
cp .env.example .env      # 填入 LLM_API_KEY(或直接 export)
python -m moneyagent "今天中午吃了碗面15块,帮我记一下"
```

默认对接 DeepSeek(最便宜的 `deepseek-flash`)。首次运行自动建库。

## 命令参考

```bash
# 💬 自然语言对话(记账/查账/报告)—— 默认入口
python -m moneyagent "午饭花了25块,记一下"
python -m moneyagent "打车28块,再看看这个月餐饮超没超预算"

# 💰 预算
python -m moneyagent budget set 餐饮 500
python -m moneyagent budget show

# 🧾 流水
python -m moneyagent ledger

# 📊 月度消费报告
python -m moneyagent report

# 🌐 Web 界面(浏览器打开 http://127.0.0.1:8000)
python -m moneyagent web --port 8000

# 全局选项
python -m moneyagent --mock "午饭25块"         # 强制离线演示(不调用模型)
python -m moneyagent --json "这个月花了多少"    # 输出原始 JSON
```

## 它怎么工作(多步工具调用)

一句「打车 28 块,再看看这个月餐饮超没超预算」,模型会自主执行:

```
① query_transactions  → 先查今天是否已记过(判断重复记账)
② record_transaction  → 记下:交通 28 元
③ get_summary         → 查本月总支出/收入/结余
④ get_budget          → 查餐饮预算
→ 合成回答:已记账 + 本月汇总 + 预算还剩多少
```

可调用的 6 个工具:`record_transaction`、`query_transactions`、`get_summary`、`get_budget`、`set_budget`、`delete_transaction`。

## 目录结构

```
moneyagent/
├── moneyagent/
│   ├── agent.py    # 多步工具调用循环(ReAct)+ 离线回退
│   ├── tools.py    # 工具定义与执行器
│   ├── db.py       # SQLite 账本 + 预算(线程安全,跨会话)
│   ├── llm.py      # LLM 客户端(OpenAI 风格接口 + .env 加载 + 空响应重试)
│   ├── mock.py     # 离线规则引擎(仅演示/测试)
│   ├── cli.py      # 命令行入口
│   ├── web.py      # Web 界面(可视化每一步工具调用)
│   └── __main__.py
├── tests/test_moneyagent.py   # 离线路径单元测试(11 个)
├── .github/workflows/test.yml # CI:每次 push/PR 自动跑单测
├── .env.example
└── README.md
```

## 测试

本地:

```bash
python -m unittest discover tests -v
```

CI:每次 push / PR,由 GitHub Actions 在 Python 3.10 / 3.11 / 3.12 上自动跑同一组测试,
结果见仓库顶部的 `test` 徽章。

## 作者

- 邮箱:[wushiyi105@gmail.com](mailto:wushiyi105@gmail.com)
- 电话:18384198104
- GitHub:[@wushiyi105-jpg](https://github.com/wushiyi105-jpg)

## License

[MIT](./LICENSE)
