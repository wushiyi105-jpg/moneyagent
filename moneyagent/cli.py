"""命令行入口:python -m moneyagent [自然语言] 或 python -m moneyagent <子命令>。"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, agent, db as dbmod, llm
from .llm import LLMError

MOCK_BANNER = (
    "⚠️  当前为离线演示模式(未配置 LLM_API_KEY),结果由内置规则生成。\n"
    "   在 .env 填入 LLM_API_KEY 后,将由大模型多步工具调用完成理解/判断/生成。\n"
)


def _get_db(args) -> dbmod.Database:
    return dbmod.Database(args.db if getattr(args, "db", None) else None)


def _render_steps(steps: list[dict]) -> str:
    if not steps:
        return ""
    lines = ["", "📋 执行步骤:"]
    for i, s in enumerate(steps, 1):
        args = json.dumps(s.get("arguments", {}), ensure_ascii=False)
        lines.append(f"  {i}. {s['tool']}({args})")
        res = s.get("result", {})
        if isinstance(res, dict) and "error" in res:
            lines.append(f"     ❌ {res['error']}")
    return "\n".join(lines)


def _emit(r: dict, args):
    if getattr(args, "json", False):
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("🤖 " + r["answer"].replace("\n", "\n   "))
        print(_render_steps(r["steps"]))


def cmd_chat(args):
    db = _get_db(args)
    cfg = llm.config_from_args(args)
    text = " ".join(args.text)
    r = agent.run(text, db=db, config=cfg, force_mock=args.mock)
    _emit(r, args)


def cmd_budget(args):
    db = _get_db(args)
    if args.action == "set":
        if not args.category or args.amount is None:
            print("用法: moneyagent budget set <分类> <金额>", file=sys.stderr)
            sys.exit(2)
        db.set_budget(args.category, args.amount)
        print(f"✅ 已设置 {args.category} 月预算 {args.amount:.2f} 元")
    else:  # show
        budgets = db.get_budgets()
        if not budgets:
            print("还没有设置任何预算。用 `moneyagent budget set 餐饮 500` 设置。")
            return
        today = dbmod.today()
        s, e = f"{today[:7]}-01", today
        print("💰 预算一览(本月):")
        for cat, amt in sorted(budgets.items()):
            spent = next((x["total"] for x in db.category_breakdown(s, e) if x["category"] == cat), 0.0)
            flag = "⚠️ 超支" if spent > amt else "✅"
            print(f"  · {cat}:已花 {spent:.2f} / 预算 {amt:.2f}  {flag}")


def cmd_ledger(args):
    db = _get_db(args)
    rows = db.recent(args.n)
    if not rows:
        print("还没有任何流水。试试 `python -m moneyagent 午饭花了25块`")
        return
    print(f"🧾 最近 {len(rows)} 笔:")
    for r in rows:
        sign = "-" if r["type"] == "expense" else "+"
        cat = r["category"] or "未分类"
        extra = f"  {r['merchant']}" if r["merchant"] else ""
        note = f"  ({r['note']})" if r["note"] else ""
        print(f"  [{r['id']}] {r['date']} {sign}{r['amount']:.2f}  {cat}{extra}{note}")


def cmd_report(args):
    db = _get_db(args)
    cfg = llm.config_from_args(args)
    prompt = "请给我出这个月的消费报告:总支出、总收入、结余、分类占比、预算执行情况,并给出1-2条省钱建议。"
    r = agent.run(prompt, db=db, config=cfg, force_mock=args.mock)
    _emit(r, args)


def cmd_web(args):
    from . import web
    web.serve(host=args.host, port=args.port, db_path=args.db if getattr(args, "db", None) else None,
              force_mock=args.mock)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="moneyagent",
        description="钱袋 · 智能记账财务管家:自然语言记账 / 查账 / 管预算 / 出报告。",
    )
    p.add_argument("--version", action="version", version=f"moneyagent {__version__}")
    p.add_argument("--mock", action="store_true", help="强制离线演示模式(不调用模型)")
    p.add_argument("--json", action="store_true", help="以 JSON 输出原始结果")
    p.add_argument("--model", help="覆盖 LLM_MODEL")
    p.add_argument("--base-url", help="覆盖 LLM_BASE_URL")
    p.add_argument("--api-key", help="覆盖 LLM_API_KEY")
    p.add_argument("--db", help="SQLite 数据库路径")

    sub = p.add_subparsers(dest="command")

    cp = sub.add_parser("chat", help="自然语言对话(记账/查账/报告)")
    cp.add_argument("text", nargs="+")
    cp.set_defaults(func=cmd_chat)

    bp = sub.add_parser("budget", help="管理分类月预算")
    bp.add_argument("action", choices=["set", "show"])
    bp.add_argument("category", nargs="?")
    bp.add_argument("amount", nargs="?", type=float)
    bp.set_defaults(func=cmd_budget)

    lp = sub.add_parser("ledger", help="查看最近流水")
    lp.add_argument("n", nargs="?", type=int, default=20)
    lp.set_defaults(func=cmd_ledger)

    rp = sub.add_parser("report", help="生成月度消费报告")
    rp.set_defaults(func=cmd_report)

    wp = sub.add_parser("web", help="启动 Web 界面")
    wp.add_argument("--host", default="127.0.0.1")
    wp.add_argument("--port", type=int, default=8000)
    wp.set_defaults(func=cmd_web)

    return p


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    known = {"chat", "budget", "ledger", "report", "web"}
    value_flags = {"--model", "--base-url", "--api-key", "--db"}
    # 找第一个位置参数(跳过 flag 及其取值)
    i = 0
    while i < len(raw):
        tok = raw[i]
        if tok in value_flags:
            i += 2
        elif tok.startswith("-"):
            i += 1
        else:
            break
    # 第一个位置参数不是已知子命令时,插入 chat 作为默认子命令
    if i < len(raw) and raw[i] not in known:
        raw.insert(i, "chat")
    args = build_parser().parse_args(raw)
    if args.command is None:
        build_parser().print_help()
        sys.exit(0)

    if not args.mock and args.command in (None, "chat", "report"):
        if not llm.config_from_args(args).get("api_key"):
            print(MOCK_BANNER, file=sys.stderr)

    try:
        args.func(args)
    except LLMError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
