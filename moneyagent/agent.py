"""核心 Agent:多步工具调用循环(ReAct 风格)+ 离线回退。

用户一句自然语言 → 模型自己决定调用哪个工具(记一笔 / 查流水 / 查预算 /
出汇总),拿到结果再决定下一步,循环直到给出最终回答。账本跨会话保存。
"""

from __future__ import annotations

import json
from datetime import date

from . import llm, mock, tools
from .db import Database
from .llm import LLMError

MAX_STEPS = 8

_SYSTEM = """你是「钱袋」,一个智能记账财务管家。你用自然语言帮用户记账、查账、管预算、出消费报告。

你只能通过调用工具来完成操作。每次回复必须是下面两种之一(只输出 JSON,不要任何解释):

1) 调用工具:
{"tool":"工具名","arguments":{参数}}

2) 最终回答(任务完成时):
{"answer":"给用户看的回答"}

规则:
- 金额单位是元,保留两位小数。
- 分类从「餐饮、交通、购物、居住、娱乐、医疗、教育、其他、工资、奖金、理财、其他收入」中选;收入用后四类。
- 今天是 {today}。
- 一步一步来:每次只调用一个工具,拿到结果后再决定下一步,不要臆测结果。
- 记账前先判断是否可能是重复(同一天、金额与商家相近),拿不准就先查账再记。
- 回答要简洁友好,金额用中文语境(如「15 元」),必要时分行。

可用工具:
{tools}"""


def _use_model(config: dict | None, force_mock: bool) -> bool:
    if force_mock:
        return False
    cfg = {**llm.default_config(), **(config or {})}
    return bool(cfg.get("api_key"))


def _cfg(config: dict | None) -> dict:
    return {**llm.default_config(), **(config or {})}


def run(user_input: str, db: Database, config: dict | None = None,
        force_mock: bool = False) -> dict:
    """执行一次记账任务,返回 {"answer": str, "steps": [...]}。"""
    if not _use_model(config, force_mock):
        return mock.run(user_input, db)

    cfg = _cfg(config)
    system = _SYSTEM.replace("{today}", date.today().isoformat()).replace("{tools}", tools.tools_description())
    history: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_input},
    ]
    steps: list[dict] = []

    for _ in range(MAX_STEPS):
        raw = llm.chat(history, config=cfg, temperature=0.2, max_tokens=2048)
        try:
            data = llm.extract_json(raw)
        except LLMError:
            history.append({"role": "assistant", "content": raw})
            history.append({"role": "user", "content": '输出格式不对,请严格按 JSON 输出:调用工具用 {"tool":"...","arguments":{...}},结束用 {"answer":"..."}。'})
            continue

        if not isinstance(data, dict):
            history.append({"role": "assistant", "content": raw})
            history.append({"role": "user", "content": "请输出一个 JSON 对象。"})
            continue

        if "answer" in data:
            return {"answer": str(data["answer"]), "steps": steps}

        if "tool" in data and tools.is_valid_tool(str(data["tool"])):
            args = data.get("arguments") or {}
            if not isinstance(args, dict):
                args = {}
            try:
                result = tools.execute_tool(str(data["tool"]), args, db)
            except Exception as e:  # noqa: BLE001
                result = {"error": str(e)}
            steps.append({"tool": str(data["tool"]), "arguments": args, "result": result})
            history.append({"role": "assistant", "content": raw})
            history.append({"role": "user", "content": "工具执行结果:" + json.dumps(result, ensure_ascii=False, default=str)})
            continue

        # 无法识别:要求模型纠正
        history.append({"role": "assistant", "content": raw})
        history.append({"role": "user", "content": '无法识别。请输出 {"tool":"工具名","arguments":{...}} 或 {"answer":"..."}。'})

    return {"answer": "达到最大步骤数仍未完成,请换个说法再试。", "steps": steps}
