"""离线路径的单元测试(不依赖网络 / API key)。运行:python -m unittest discover tests"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moneyagent import agent, llm, mock, tools
from moneyagent import db as dbmod


class TestDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = dbmod.Database(os.path.join(self.tmp, "t.db"))

    def tearDown(self):
        self.db.close()

    def test_add_and_list(self):
        tid = self.db.add_transaction("expense", 25, "餐饮", "面馆", "", "2026-11-24")
        self.assertGreater(tid, 0)
        rows = self.db.list_transactions()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 25)
        self.assertEqual(rows[0]["category"], "餐饮")

    def test_summary_and_breakdown(self):
        self.db.add_transaction("expense", 10, "餐饮", "", "", "2026-11-01")
        self.db.add_transaction("expense", 20, "交通", "", "", "2026-11-02")
        self.db.add_transaction("income", 100, "工资", "", "", "2026-11-01")
        s = self.db.summary("2026-11-01", "2026-11-30")
        self.assertEqual(s["total_expense"], 30)
        self.assertEqual(s["total_income"], 100)
        self.assertEqual(s["balance"], 70)
        bd = self.db.category_breakdown("2026-11-01", "2026-11-30")
        cats = {x["category"]: x["total"] for x in bd}
        self.assertEqual(cats["餐饮"], 10)

    def test_budget(self):
        self.db.set_budget("餐饮", 500)
        self.assertEqual(self.db.get_budget("餐饮"), 500)
        self.assertEqual(self.db.get_budgets(), {"餐饮": 500})

    def test_delete(self):
        tid = self.db.add_transaction("expense", 9, "其他", "", "", "2026-11-01")
        self.assertTrue(self.db.delete_transaction(tid))
        self.assertFalse(self.db.delete_transaction(tid))


class TestTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = dbmod.Database(os.path.join(self.tmp, "t.db"))

    def tearDown(self):
        self.db.close()

    def test_record_and_summary(self):
        r = tools.execute_tool("record_transaction",
                               {"type": "expense", "amount": 15, "category": "餐饮", "merchant": "面馆"}, self.db)
        self.assertIn("id", r)
        s = tools.execute_tool("get_summary", {"start": "2026-11-01", "end": "2026-11-30"}, self.db)
        self.assertEqual(s["total_expense"], 15)

    def test_unknown_tool(self):
        r = tools.execute_tool("nope", {}, self.db)
        self.assertIn("error", r)


class TestMock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = dbmod.Database(os.path.join(self.tmp, "t.db"))

    def tearDown(self):
        self.db.close()

    def test_mock_record(self):
        r = mock.run("午饭花了25块", self.db)
        self.assertIn("已记", r["answer"])
        self.assertTrue(r["steps"])
        rows = self.db.list_transactions()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount"], 25)
        self.assertEqual(rows[0]["category"], "餐饮")

    def test_mock_budget(self):
        r = mock.run("餐饮预算 500", self.db)
        self.assertIn("500", r["answer"])
        self.assertEqual(self.db.get_budget("餐饮"), 500)

    def test_agent_falls_back_to_mock_without_key(self):
        r = agent.run("午饭花了25块", db=self.db, config={"api_key": ""})
        self.assertTrue(r["steps"])


class TestLLM(unittest.TestCase):
    def test_extract_json_plain(self):
        self.assertEqual(llm.extract_json('{"a": 1}'), {"a": 1})

    def test_extract_json_fenced(self):
        self.assertEqual(llm.extract_json('```json\n{"tool": "x"}\n```'), {"tool": "x"})


if __name__ == "__main__":
    unittest.main()
