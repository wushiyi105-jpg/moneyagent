# 钱袋 QianDai · 智能记账财务管家

[![test](https://github.com/wushiyi105-jpg/moneyagent/workflows/test/badge.svg)](https://github.com/wushiyi105-jpg/moneyagent/actions) [![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)]() [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE) [![codecov](https://codecov.io/gh/wushiyi105-jpg/moneyagent/branch/main/graph/badge.svg)](https://codecov.io/gh/wushiyi105-jpg/moneyagent)

![demo](assets/demo.gif)

> 像聊天一样记账、查账、管预算、出报告——它会自己一步步调工具完成,你看着就行。

一个自然语言记账的智能体应用:大模型通过**多步工具调用**完成任务——自己决定
调用「记一笔 / 查流水 / 查预算 / 出汇总」中的哪个工具,拿到结果再决定下一步,
直到给出最终回答。账本用 SQLite **跨会话长期保存**。

**CLI + Web 双入口,零第三方依赖,开箱即用。**

## ✨ 特性

- 🧠 **多步工具调用** —— 不是单次问答,模型自主规划「调哪个工具、调几次」
- 💬 **自然语言记账** —— 「今天中午吃了碗面15块」一句话,自动提取金额、分类、商家、时间
- 🔍 **查重判断** —— 记账前先查是否重复,避免记两遍
- 💰 **预算管理** —— 设分类月预算,超支自动提醒
- 📊 **消费报告** —— 一句话出月度报告:总收支、分类占比、预算执行、省钱建议
- 💾 **跨会话记忆** —— 流水与预算持久化,下次打开还在
- 🖥 **双入口** —— 命令行 + 网页界面(网页里可视化每一步工具调用)
- ⚡ **零依赖** —— 纯 Python 标准库,Python 3.10+ 即可运行

## 🚀 快速开始

```bash
git clone https://github.com/wushiyi105-jpg/moneyagent.git
cd moneyagent

# 配置模型 key
cp .env.example .env       # 填入 LLM_API_KEY
#   或 export LLM_API_KEY=你的key

# 直接开用
python -m moneyagent "今天中午吃了碗面15块,帮我记一下"
```

默认对接 DeepSeek(最便宜的 `deepseek-flash`)。
> **⚠️ 项目不自带任何 API key,请填入你自己的 key**(`.env` 已 gitignore,不会提交)。
未配置 key 时自动进入离线模式。

## 📖 命令参考

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
python -m moneyagent --json "这个月花了多少"    # 输出原始 JSON
python -m moneyagent --mock "午饭25块"          # 强制离线模式
```

## 🧠 工作原理(多步工具调用)

一句「打车 28 块,再看看这个月餐饮超没超预算」,模型会自主执行:

```
① query_transactions  → 先查今天是否已记过(判断重复记账)
② record_transaction  → 记下:交通 28 元
③ get_summary         → 查本月总支出/收入/结余
④ get_budget          → 查餐饮预算
→ 合成回答:已记账 + 本月汇总 + 预算还剩多少
```

可调用的 6 个工具:`record_transaction`、`query_transactions`、`get_summary`、`get_budget`、`set_budget`、`delete_transaction`。

### 数据流

一条数据在这几个模块之间怎么走：

```mermaid
flowchart LR
    A[一句话记账或提问] --> B[agent.py<br/>ReAct 循环]
    B --> C[llm.py<br/>决定调哪个工具]
    C --> D[tools.py<br/>execute_tool]
    D --> E[db.py<br/>写流水 · 查预算 · 汇总]
    E --> F[agent.py<br/>工具结果回填]
    F -->|还要再调一次| C
    F -->|说完了| G[cli.py / web.py]
    F -->|没有 key| H[mock.py<br/>规则回退] --> G
```

## 🔌 模型接入

兼容任意 **OpenAI 风格 `/chat/completions`** 接口,**使用你自己的 API key**,改三个环境变量即可:

| 平台 | `LLM_BASE_URL` | `LLM_MODEL` |
|---|---|---|
| DeepSeek(默认) | `https://api.deepseek.com` | `deepseek-flash` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5` |

> `LLM_API_KEY` 必填;`LLM_BASE_URL`、`LLM_MODEL` 选填。

## 🗂 目录结构

```
moneyagent/
├── moneyagent/
│   ├── agent.py    # 多步工具调用循环(ReAct)+ 离线回退
│   ├── tools.py    # 工具定义与执行器
│   ├── db.py       # SQLite 账本 + 预算(线程安全,跨会话)
│   ├── llm.py      # LLM 客户端(OpenAI 风格接口 + .env 加载 + 空响应重试)
│   ├── mock.py     # 离线规则引擎(兜底/测试)
│   ├── cli.py      # 命令行入口
│   ├── web.py      # Web 界面(可视化每一步工具调用)
│   └── __main__.py
├── assets/demo.gif             # 演示动图
├── tests/test_moneyagent.py    # 离线路径单元测试
├── .github/workflows/test.yml  # CI
├── .env.example
└── README.md
```

## ✅ 测试

本地:

```bash
python -m unittest discover tests -v
```

每次 push / PR 由 GitHub Actions 在 Python 3.10 / 3.11 / 3.12 上自动跑同一组测试,结果见顶部 `test` 徽章。

## 👤 作者

- 署名：shiyi
- 邮箱:[wushiyi105@gmail.com](mailto:wushiyi105@gmail.com)
- 电话:18384198104
- GitHub:[@wushiyi105-jpg](https://github.com/wushiyi105-jpg)

## 📄 License

[MIT](./LICENSE)
