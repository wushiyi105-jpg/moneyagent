"""SQLite 持久层:流水账本 + 分类预算。纯标准库 sqlite3,线程安全。"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import date

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "moneyagent.db")

# 支出 / 收入分类(模型与离线规则共用)
EXPENSE_CATEGORIES = ["餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "其他"]
INCOME_CATEGORIES = ["工资", "奖金", "理财", "其他收入"]


def today() -> str:
    return date.today().isoformat()


class Database:
    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("MONEYAGENT_DB") or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT,
                    merchant TEXT,
                    note TEXT,
                    date TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS budgets (
                    category TEXT PRIMARY KEY,
                    amount REAL NOT NULL
                )
                """
            )
            self.conn.commit()

    # ---------- 流水 ----------
    def add_transaction(self, type: str, amount: float, category: str = "",
                        merchant: str = "", note: str = "", date: str = "") -> int:
        if type not in ("expense", "income"):
            raise ValueError(f"非法类型: {type}")
        amount = round(float(amount), 2)
        date = date or today()
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO transactions (type, amount, category, merchant, note, date) VALUES (?,?,?,?,?,?)",
                (type, amount, category, merchant, note, date),
            )
            self.conn.commit()
            return cur.lastrowid

    def get_transaction(self, tid: int) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM transactions WHERE id = ?", (tid,)).fetchone()
        return dict(row) if row else None

    def list_transactions(self, start: str = "", end: str = "", category: str = "",
                          type: str = "", limit: int = 200) -> list[dict]:
        sql = "SELECT * FROM transactions WHERE 1=1"
        args: list = []
        if start:
            sql += " AND date >= ?"; args.append(start)
        if end:
            sql += " AND date <= ?"; args.append(end)
        if category:
            sql += " AND category = ?"; args.append(category)
        if type:
            sql += " AND type = ?"; args.append(type)
        sql += " ORDER BY date DESC, id DESC LIMIT ?"; args.append(limit)
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def delete_transaction(self, tid: int) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM transactions WHERE id = ?", (tid,))
            self.conn.commit()
            return cur.rowcount > 0

    # ---------- 预算 ----------
    def set_budget(self, category: str, amount: float):
        amount = round(float(amount), 2)
        with self._lock:
            self.conn.execute(
                "INSERT INTO budgets (category, amount) VALUES (?,?) "
                "ON CONFLICT(category) DO UPDATE SET amount=excluded.amount",
                (category, amount),
            )
            self.conn.commit()

    def get_budgets(self) -> dict[str, float]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM budgets").fetchall()
        return {r["category"]: r["amount"] for r in rows}

    def get_budget(self, category: str) -> float | None:
        return self.get_budgets().get(category)

    # ---------- 统计 ----------
    def summary(self, start: str, end: str) -> dict:
        """返回 {total_expense, total_income, balance, count}。"""
        with self._lock:
            rows = self.conn.execute(
                "SELECT type, SUM(amount) AS s, COUNT(*) AS c FROM transactions "
                "WHERE date >= ? AND date <= ? GROUP BY type",
                (start, end),
            ).fetchall()
        total_expense = total_income = count = 0.0
        n = 0
        for r in rows:
            n += r["c"]
            if r["type"] == "expense":
                total_expense = r["s"]
            else:
                total_income = r["s"]
        return {
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
            "balance": round(total_income - total_expense, 2),
            "count": n,
        }

    def category_breakdown(self, start: str, end: str, type: str = "expense") -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT category, SUM(amount) AS total, COUNT(*) AS count FROM transactions "
                "WHERE date >= ? AND date <= ? AND type = ? GROUP BY category ORDER BY total DESC",
                (start, end, type),
            ).fetchall()
        return [{"category": r["category"] or "未分类", "total": round(r["total"], 2), "count": r["count"]} for r in rows]

    def recent(self, n: int = 10) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
