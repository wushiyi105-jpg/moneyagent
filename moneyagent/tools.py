"""工具层:定义模型可调用的工具,并负责执行。

工具调用协议:模型输出 {"tool": "<名称>", "arguments": {<参数>}},
本模块的 execute_tool 执行并返回结果,喂回模型。
"""

from __future__ import annotations

from datetime import date

from . import db as dbmod


def tools_description() -> str:
    """生成喂给模型的工具清单(中文说明)。"""
    lines = [
        "1. record_transaction —— 记一笔收支。参数: type('expense'或'income')、amount(金额,元)、"
        "category(分类)、merchant(商家/来源,可选)、note(备注,可选)、date(日期YYYY-MM-DD,可选,默认今天)",
        "2. query_transactions —— 查询流水。参数: start(开始日期,可选)、end(结束日期,可选)、"
        "category(分类,可选)、type('expense'或'income',可选)",
        "3. get_summary —— 查询某时间段的收支汇总(总收入/总支出/结余/笔数)。参数: start、end(必填,YYYY-MM-DD)",
        "4. get_budget —— 查询预算。参数: category(分类,可选;不传则返回全部预算)",
        "5. set_budget —— 设置某分类的月预算。参数: category、amount(金额,元)",
        "6. delete_transaction —— 删除一笔流水。参数: id(流水ID,整数)",
    ]
    return "\n".join(lines)


def _month_bounds(ref: str) -> tuple[str, str]:
    """由 'YYYY-MM' 或 'YYYY-MM-DD' 求当月第一天与最后一天。"""
    if len(ref) == 7:  # YYYY-MM
        y, m = int(ref[:4]), int(ref[5:7])
    else:
        y, m = int(ref[:4]), int(ref[5:7])
    first = f"{y:04d}-{m:02d}-01"
    if m == 12:
        last = f"{y + 1:04d}-01-31"
    else:
        last = f"{y:04d}-{m + 1:02d}-01"
    # 简化:用 31 号作为月末上界(数据库按 <= 过滤,实际当月天数由 date 判断)
    import calendar
    last_day = calendar.monthrange(y, m)[1]
    return first, f"{y:04d}-{m:02d}-{last_day:02d}"


def execute_tool(name: str, args: dict, db: dbmod.Database) -> dict:
    """执行单个工具,返回 JSON 可序列化的结果。"""
    args = args or {}

    if name == "record_transaction":
        typ = args.get("type", "expense")
        amount = float(args.get("amount", 0))
        category = str(args.get("category", "")).strip()
        merchant = str(args.get("merchant", "")).strip()
        note = str(args.get("note", "")).strip()
        d = str(args.get("date", "")).strip() or dbmod.today()
        tid = db.add_transaction(typ, amount, category, merchant, note, d)
        label = "支出" if typ == "expense" else "收入"
        return {"id": tid, "recorded": f"{label} {amount} 元 [{category}] {merchant} {note}".strip(),
                "date": d}

    if name == "query_transactions":
        rows = db.list_transactions(
            start=str(args.get("start", "")).strip(),
            end=str(args.get("end", "")).strip(),
            category=str(args.get("category", "")).strip(),
            type=str(args.get("type", "")).strip(),
            limit=int(args.get("limit", 50)),
        )
        return {"count": len(rows), "transactions": rows}

    if name == "get_summary":
        start = str(args.get("start", "")).strip()
        end = str(args.get("end", "")).strip()
        if not start and not end:
            start, end = _month_bounds(date.today().strftime("%Y-%m"))
        elif not end:
            end = start
        s = db.summary(start, end)
        s["start"], s["end"] = start, end
        return s

    if name == "get_budget":
        cat = str(args.get("category", "")).strip()
        if cat:
            b = db.get_budget(cat)
            return {"category": cat, "amount": b if b is not None else None}
        return {"budgets": db.get_budgets()}

    if name == "set_budget":
        cat = str(args.get("category", "")).strip()
        amount = float(args.get("amount", 0))
        db.set_budget(cat, amount)
        return {"category": cat, "amount": amount}

    if name == "delete_transaction":
        tid = int(args.get("id", 0))
        ok = db.delete_transaction(tid)
        return {"id": tid, "deleted": ok}

    return {"error": f"未知工具: {name}"}


def is_valid_tool(name: str) -> bool:
    return name in {
        "record_transaction", "query_transactions", "get_summary",
        "get_budget", "set_budget", "delete_transaction",
    }
