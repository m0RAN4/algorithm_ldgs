"""
匹配器
判断一条规则的前件是不是被当前工作记忆满足了
规则前件是几个条件的合取（AND），条件可以带"非"，就是要求那个事实不存在
否定条件只在输入事实上用。因为推理开始前会把用户勾的事实一次性全装进
"""
from __future__ import annotations

from typing import List

from .models import MatchResult, Rule, WorkingMemory


def match_rule(rule: Rule, memory: WorkingMemory,
               fired_rule_ids=None) -> MatchResult:
    """
    拿一条规则和工作记忆比对。
    要同时满足三件事才算匹配上：
    1. 规则是启用状态；
    2. 前件里每个条件都成立（肯定条件要求事实在，否定条件要求不在）；
    3. 后件里至少有一条结论还没有。最后这条是防止同一条规则反复触发
    """
    #停用的规则直接跳过
    if not rule.is_enabled:
        return MatchResult(rule=rule, matched=False, reason="规则已停用")

    #这次推理里已经触发过了，跳过
    if fired_rule_ids is not None and rule.rule_id in fired_rule_ids:
        return MatchResult(rule=rule, matched=False, reason="本轮推理中已触发过")

    #没写前件的规则不算数
    if not rule.conditions:
        return MatchResult(rule=rule, matched=False, reason="规则没有前件")

    matched_facts: List[str] = []
    latest = -1
    #把前件里的条件一个一个查过去
    for condition in rule.conditions:
        exists = memory.contains(condition.fact_code)
        if condition.is_negate:
            #否定条件：要求这个事实不在，在的话就不成立
            if exists:
                return MatchResult(
                    rule=rule, matched=False,
                    reason="否定条件「非 %s」不成立" % condition.fact_code)
        else:
            #肯定条件：要求这个事实在，不在就直接返回
            if not exists:
                return MatchResult(
                    rule=rule, matched=False,
                    reason="缺少条件事实 %s" % condition.fact_code)
            matched_facts.append(condition.fact_code)
            #记下命中的事实里最新的那个，冲突消解第3级要用
            latest = max(latest, memory.order_of(condition.fact_code))

    #后件里已经存在的结论去掉，剩下的才是这轮真正能推出来的
    new_conclusions = [c for c in rule.conclusions if not memory.contains(c)]
    if not new_conclusions:
        return MatchResult(rule=rule, matched=False, reason="结论事实已全部存在")

    return MatchResult(
        rule=rule,
        matched=True,
        matched_facts=matched_facts,
        new_conclusions=new_conclusions,
        recency=latest,
    )


def match_all(rules, memory: WorkingMemory, fired_rule_ids=None) -> List[MatchResult]:
    """把所有规则都比一遍，返回匹配上的那些，也就是冲突集"""
    results = []
    for rule in rules:
        result = match_rule(rule, memory, fired_rule_ids)
        if result.matched:
            results.append(result)
    return results
