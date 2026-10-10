"""服务层：把知识库和推理机装到一起。

这里是整个系统唯一的组装点。推理机和知识库互相不认识，由这个模块把
知识库当参数传给推理机。好处是换知识库（MySQL 换文件）只动这里一行，
推理机里没有任何一行需要知道规则存在哪。
"""
from __future__ import annotations

import time
from typing import Dict, List

import config

from ..inference.engine import ForwardInferenceEngine
from ..inference.models import Fact
from ..knowledge import file_repository, repository, seed_data


def get_repository():
    """看配置返回哪个知识库实现。"""
    if config.KNOWLEDGE_SOURCE == "file":
        return file_repository.FileKnowledgeRepository()
    return repository.MySqlKnowledgeRepository()


def _fact_map(facts: List[Fact]) -> Dict[str, Fact]:
    """做成 编码 -> Fact 的字典，查起来快。"""
    return {fact.code: fact for fact in facts}


def _topic_map() -> Dict[str, dict]:
    """取算法主题详情，推荐结论后面的难度、路径、典型题都在这儿。"""
    if config.KNOWLEDGE_SOURCE == "file":
        #文件模式直接从种子数据里拿，字段名对齐数据库那边
        return {
            code: {"topic_code": code, "topic_name": name, "difficulty": level,
                   "estimated_hours": hours, "core_points": points,
                   "learning_path": path, "typical_problems": problems}
            for code, name, level, hours, points, path, problems
            in seed_data.TOPICS
        }
    return repository.topic_map()


def _describe_fact(code: str, facts: Dict[str, Fact]) -> dict:
    """把一个事实编码变成前端好用的字典。

    推理机返回的都是编码，中文名和说明是知识库这边补上的。
    """
    fact = facts.get(code)
    return {
        "code": code,
        "name": fact.name if fact else code, #查不到就退回编码
        "category_code": fact.category_code if fact else "",
        "category_name": fact.category_name if fact else "",
        "description": fact.description if fact else "",
        "fact_type": fact.fact_type if fact else "",
    }


#事实目录


def fact_catalog() -> dict:
    """给前端的事实清单，按类别分好组。

    只把 input 类的事实放进 input_categories，因为界面上只让用户勾
    "自己的情况"，推导出来的结论不能让他自己勾。
    """
    repo = get_repository()
    facts = repo.fetch_facts()

    #类别从哪儿取，看用的是哪个知识库
    if config.KNOWLEDGE_SOURCE == "file":
        categories = list(seed_data.CATEGORIES)
    else:
        categories = [(c["category_code"], c["category_name"], c["sort_order"])
                      for c in repository.list_categories()]

    #先按类别建好空桶
    grouped: Dict[str, dict] = {}
    for code, name, order in categories:
        grouped[code] = {"category_code": code, "category_name": name,
                         "sort_order": order, "facts": []}
    #再把事实一个个丢进对应的桶里
    for fact in facts:
        bucket = grouped.setdefault(fact.category_code, {
            "category_code": fact.category_code,
            "category_name": fact.category_name or fact.category_code,
            "sort_order": 999, "facts": []}) #类别没登记过就新开一个
        bucket["facts"].append({
            "code": fact.code, "name": fact.name,
            "description": fact.description, "fact_type": fact.fact_type,
        })

    ordered = sorted(grouped.values(), key=lambda g: (g["sort_order"],
                                                      g["category_code"]))
    return {
        "input_categories": [g for g in ordered
                             if g["facts"] and g["facts"][0]["fact_type"] == "input"],
        "derived_categories": [g for g in ordered
                               if g["facts"] and g["facts"][0]["fact_type"] != "input"],
    }


#推理主流程


def run_consultation(input_codes: List[str], persist: bool = True) -> dict:
    """跑一次咨询：推理、拼结果、存库。"""
    started = time.time()

    #选知识库，注入给推理机
    repo = get_repository()
    engine = ForwardInferenceEngine(repo, max_rounds=config.MAX_INFERENCE_ROUNDS)

    #这一步是真正的推理，返回的事实编码
    result = engine.infer(input_codes)

    #取元数据，等下把编码翻译成中文
    facts = _fact_map(repo.fetch_facts())
    topics = _topic_map()

    #记一下每个结论是第几轮推出来的
    derived_round: Dict[str, int] = {}
    for step in result.steps:
        for code in step.derived_facts:
            derived_round.setdefault(code, step.round_no) #只记第一次

    conclusions = []
    for code in result.derived_facts:
        item = _describe_fact(code, facts)
        item["round"] = derived_round.get(code) #第几轮推出的
        item["topic"] = topics.get(code) #挂上主题详情，没有就是 None
        conclusions.append(item)

    #把每一轮的轨迹整理成前端要的样子
    traces = []
    for step in result.steps:
        traces.append({
            "round_no": step.round_no,
            "rule_code": step.rule.rule_code,
            "rule_name": step.rule.rule_name,
            "rule_description": step.rule.description,
            "priority": step.rule.priority,
            "strategy": step.strategy, #哪一级策略起的作用
            "resolution": step.resolution, #中文说明
            "matched_facts": [_describe_fact(c, facts) for c in step.matched_facts],
            "derived_facts": [_describe_fact(c, facts) for c in step.derived_facts],
            "candidate_count": len(step.candidates), #冲突集有几条
            "candidates": [{"rule_code": r.rule_code, "rule_name": r.rule_name,
                            "priority": r.priority,
                            "condition_count": r.condition_count}
                           for r in step.candidates],
            "rejected": [{"rule_code": r.rule.rule_code,
                          "rule_name": r.rule.rule_name,
                          "priority": r.rule.priority,
                          "condition_count": r.rule.condition_count,
                          "lost_by": r.lost_by, "detail": r.detail}
                         for r in step.rejected],
        })

    duration_ms = int((time.time() - started) * 1000)

    def pick(category: str):
        #按类别把结论挑出来，界面上分块显示
        return [c for c in conclusions if c["category_code"] == category]

    payload = {
        "ok": True,
        "message": result.message,
        "rounds": result.rounds,
        "rules_loaded": result.rules_loaded,
        "halted": result.halted,
        "duration_ms": duration_ms,
        "input_facts": [_describe_fact(c, facts) for c in result.initial_facts],
        "conclusions": conclusions,
        "routes": pick("route"),
        "recommendations": pick("rec"),
        "advices": pick("advice"),
        "stages": pick("stage"),
        "traces": traces,
    }

    #存库。只有连数据库的模式才存，文件模式没有地方存
    if persist and config.KNOWLEDGE_SOURCE == "db":
        try:
            record_id = repository.save_consult(
                {"round_count": result.rounds, "duration_ms": duration_ms,
                 "halted": result.halted, "rules_loaded": result.rules_loaded},
                result.initial_facts, result.derived_facts, traces)
            payload["record_id"] = record_id
        except Exception as exc:
            #存不上不影响这次推理，用户照样能看到结果，只是历史里少一条
            payload["save_error"] = str(exc)

    return payload
