"""
用来证明分离的快速启动检验
文件知识库，也就是知识库的另一种实现。
这个文件本身就是"知识库和推理机分离"的证据：它实现了和 MySQL 仓储一模一样的
KnowledgeProvider 接口。启动时把知识源切成 file，同一套推理机代码就改从文件读
规则了，推理机一行都不用改

主要用来做演示和离线自检，没有数据库也能把推理跑通
"""
from __future__ import annotations

import json
import os
from typing import List

from ..inference.models import Condition, Fact, Rule
from ..inference.provider import KnowledgeProvider
from . import seed_data

DEFAULT_STORE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "data", "rule_store.json")


class FileKnowledgeRepository(KnowledgeProvider):
    """从 JSON 文件或内置的种子数据里读知识。"""

    def __init__(self, store_path: str = None):
        self.store_path = os.path.abspath(store_path or DEFAULT_STORE)

    def _load(self) -> dict:
        """有 JSON 文件就读文件，没有就把 seed_data 转成同样的结构。"""
        if os.path.exists(self.store_path):
            with open(self.store_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        #元组的字段顺序：编码、名称、类别、类型、说明
        return {
            "facts": [
                {"fact_code": c, "fact_name": n, "category_code": cat,
                 "fact_type": t, "description": d}
                for c, n, cat, t, d in seed_data.FACTS],
            "rules": [
                {"rule_id": i, "rule_code": c, "rule_name": n, "priority": p,
                 "conditions": [{"fact_code": fc, "is_negate": ng}
                                for fc, ng in cond],
                 "conclusions": concl, "description": desc, "is_enabled": True}
                for i, (c, n, p, cond, concl, desc)
                in enumerate(seed_data.RULES, start=1)],
        }

    def fetch_facts(self) -> List[Fact]:
        """接口方法，返回全部事实。"""
        #先把 类别编码 -> 类别中文名 的对应关系做出来
        category_names = {code: name for code, name, _o in seed_data.CATEGORIES}
        return [
            Fact(code=item["fact_code"], name=item["fact_name"],
                 category_code=item["category_code"],
                 category_name=category_names.get(item["category_code"], ""),
                 fact_type=item.get("fact_type", "input"),
                 description=item.get("description", ""))
            for item in self._load()["facts"]
        ]

    def fetch_rules(self) -> List[Rule]:
        """接口方法，返回全部规则。"""
        rules = []
        for item in self._load()["rules"]:
            rules.append(Rule(
                rule_id=item["rule_id"],
                rule_code=item["rule_code"],
                rule_name=item["rule_name"],
                priority=int(item.get("priority", 0)),
                conditions=[Condition(fact_code=c["fact_code"],
                                      is_negate=c.get("is_negate", False))
                            for c in item.get("conditions", [])],
                conclusions=list(item.get("conclusions", [])),
                description=item.get("description", ""),
                is_enabled=item.get("is_enabled", True),
            ))
        return rules

    def dump_seed(self) -> None:
        """把内置的种子数据写成 JSON 文件，方便离线演示。"""
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        payload = {
            "facts": [
                {"fact_code": c, "fact_name": n, "category_code": cat,
                 "fact_type": t, "description": d}
                for c, n, cat, t, d in seed_data.FACTS],
            "rules": [
                {"rule_id": i, "rule_code": c, "rule_name": n, "priority": p,
                 "conditions": [{"fact_code": fc, "is_negate": ng}
                                for fc, ng in cond],
                 "conclusions": concl, "description": desc, "is_enabled": True}
                for i, (c, n, p, cond, concl, desc)
                in enumerate(seed_data.RULES, start=1)],
        }
        with open(self.store_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
