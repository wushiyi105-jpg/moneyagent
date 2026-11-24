"""离线演示模式:无 API key 时的确定性规则引擎。

仅用于:让项目在没有 key 时也能端到端跑通、以及单元测试。
配置 LLM_API_KEY 后,真正的理解/判断/生成全部由大模型的多步工具调用完成。
"""

from __future__ import annotations

import re
from datetime import date

from . import db as dbmod

# 关键词 → 分类
_CATEGORY_KEYWORDS = [
    ("餐饮", ["吃", "饭", "餐", "面", "外卖", "咖啡", "奶茶", "早餐", "午餐", "晚餐", "宵夜", "麦当劳", "肯德基", "火锅", "烧烤"]),
    ("交通", ["打车", "滴滴", "地铁", "公交", "高铁", "火车", "机票", "加油", "停车", "出租", "网约车"]),
    ("购物", ["买", "淘宝", "京东", "拼多多", "超市", "商场", "衣服", "鞋", "手机", "电器", "零食", "日用品"]),
    ("居住", ["房租", "物业", "水电", "燃气", "宽带", "房贷", "维修"]),
    ("娱乐", ["电影", "游戏", "KTV", "会员", "视频", "旅游", "门票", "演出"]),
    ("医疗", ["药", "医院", "挂号", "体检", "看病", "牙科"]),
    ("教育", ["书", "课程", "培训", "学费", "考试", "网课"]),
    ("其他", []),
]

_INCOME_KEYWORDS = ["工资", "薪水", "收入", "赚", "奖金", "报销", "理财收益", "利息", "红包", "进账", "稿费", "兼职"]


def _extract_amount(text: str) -> float | None:
    # 支持:15块 / 15元 / ¥15 / 15.5 / 一万二
    m = re.search(r"(\d+(?:\.\d+)?)\s*[块元]|¥\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*元", text)
    if m:
        val = next((g for g in m.groups() if g), None)
        if val:
            return round(float(val), 2)
    m2 = re.search(r"([一二两三四五六七八九十百千万]+)\s*[块元]", text)
    if m2:
        return _cn_num(m2.group(1))
    return None


def _cn_num(s: str) -> float:
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0.0
    cur = 0.0
    for ch in s:
        if ch in digits:
            cur = digits[ch]
        elif ch in units:
            cur = (cur or 1) * units[ch]
            if ch == "万":
                total = (total + cur) * 1
            else:
                total += cur
                cur = 0
    return total + cur


def _classify(text: str) -> str:
    for cat, kws in _CATEGORY_KEYWORDS:
        if any(k in text for k in kws):
            return cat
    return "其他"


def _is_income(text: str) -> bool:
    return any(k in text for k in _INCOME_KEYWORDS)


def _month_bounds(ref: str = "") -> tuple[str, str]:
    import calendar
    today = date.today()
    last = calendar.monthrange(today.year, today.month)[1]
    return f"{today.year:04d}-{today.month:02d}-01", f"{today.year:04d}-{today.month:02d}-{last:02d}"


def run(text: str, db: dbmod.Database) -> dict:
    """离线规则版:简单记账 / 查询 / 预算,返回 {answer, steps}。"""
    steps: list[dict] = []
    today = dbmod.today()

    amount = _extract_amount(text)

    # 设置预算:例如「餐饮预算 500」
    m_budget = re.search(r"(.{0,4}?)预算\s*[设为是]?\s*(\d+(?:\.\d+)?)", text)
    if m_budget:
        cat = _classify(m_budget.group(1)) if m_budget.group(1).strip() else "餐饮"
        amt = float(m_budget.group(2))
        db.set_budget(cat, amt)
        return {"answer": f"已设置 {cat} 月预算 {amt} 元。", "steps": [{"tool": "set_budget", "arguments": {"category": cat, "amount": amt}, "result": f"预算已设置"}]}

    # 记账
    if amount is not None and ("记" in text or "花" in text or "买" in text or "收" in text or "赚" in text or "吃" in text or "用了" in text or _is_income(text)):
        typ = "income" if _is_income(text) else "expense"
        cat = "其他收入" if typ == "income" else _classify(text)
        merchant = ""
        m = re.search(r"[在去](.+?)(?:买|吃|花)", text)
        if m:
            merchant = m.group(1).strip()[:20]
        tid = db.add_transaction(typ, amount, cat, merchant, "", today)
        steps.append({"tool": "record_transaction", "arguments": {"type": typ, "amount": amount, "category": cat, "merchant": merchant}, "result": {"id": tid}})
        # 本月汇总 + 预算核对
        s, e = _month_bounds()
        summ = db.summary(s, e)
        steps.append({"tool": "get_summary", "arguments": {"start": s, "end": e}, "result": summ})
        label = "收入" if typ == "income" else "支出"
        ans = f"已记一笔{label}:{amount:g} 元({cat}"
        if merchant:
            ans += f",{merchant}"
        ans += ")。本月累计支出 {:.2f} 元、收入 {:.2f} 元。".format(summ["total_expense"], summ["total_income"])
        if typ == "expense" and cat in db.get_budgets():
            b = db.get_budget(cat)
            spent = next((x["total"] for x in db.category_breakdown(s, e) if x["category"] == cat), 0.0)
            if spent > b:
                ans += f"⚠️ {cat} 已超预算({spent:.2f}/{b:.2f})。"
            else:
                ans += f"{cat} 预算还剩 {b - spent:.2f} 元。"
        return {"answer": ans, "steps": steps}

    # 查询 / 报表
    if any(k in text for k in ["查", "看看", "花了", "多少", "账单", "流水", "报表", "报告", "汇总", "这个月", "本月", "消费"]):
        s, e = _month_bounds()
        summ = db.summary(s, e)
        steps.append({"tool": "get_summary", "arguments": {"start": s, "end": e}, "result": summ})
        parts = [f"本月支出 {summ['total_expense']:.2f} 元、收入 {summ['total_income']:.2f} 元、结余 {summ['balance']:.2f} 元(共 {summ['count']} 笔)。"]
        bd = db.category_breakdown(s, e)
        if bd:
            parts.append("分类明细:" + "、".join(f"{x['category']} {x['total']:.2f}" for x in bd[:5]))
        return {"answer": "\n".join(parts), "steps": steps}

    return {"answer": "我没太看懂。你可以说「午饭花了25块」「这个月花了多少」「餐饮预算设500」。", "steps": steps}
