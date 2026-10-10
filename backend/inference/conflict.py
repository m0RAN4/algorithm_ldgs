"""
冲突消解：从冲突集里挑一条规则出来执行
好几条规则的条件同时被满足就叫冲突。这里用分级比较的办法，一级比不出胜负
才比下一级：
第1级优先级规则自己的 priority，数值大的优先
第2级专一性前件条件多的优先，条件多说明规则写得更具体
第3级最近性命中的事实里最新的那个，越新越优先
第4级规则编号rule_id 小的优先，保证同样的输入结果每次都一样
前三级要用的数据（优先级、前件、事实加入顺序）都是知识库提供的，策略本身
写在推理机里，两边不互相依赖
"""
from __future__ import annotations

from typing import List, Tuple

from .models import (STRATEGY_ORDER, STRATEGY_PRIORITY, STRATEGY_RECENCY,
                     STRATEGY_SPECIFICITY, MatchResult, RejectedRule,
                     WorkingMemory)


def resolve_conflict(candidates: List[MatchResult], memory: WorkingMemory
                     ) -> Tuple[MatchResult, List[RejectedRule], str, str]:
    """
    从冲突集里选一条规则
    返回四样东西：选中的那个匹配结果、被淘汰的规则列表、一段中文说明、
    还有起决定作用的是哪一级策略
    """
    if not candidates:
        raise ValueError("冲突集为空，无法消解")
    #只有一条就不用比了
    if len(candidates) == 1:
        only = candidates[0]
        return only, [], "冲突集中只有一条规则，直接执行", "single"

    rejected: List[RejectedRule] = []
    remaining = list(candidates)

    #1比优先级，数值大的赢
    best = max(m.rule.priority for m in remaining)
    winners = [m for m in remaining if m.rule.priority == best]
    if len(winners) < len(remaining):
        #优先级不够高的淘汰掉，记下原因
        losers = [m for m in remaining if m.rule.priority != best]
        for m in losers:
            rejected.append(RejectedRule(
                m.rule, STRATEGY_PRIORITY,
                "优先级 %d 低于 %d" % (m.rule.priority, best)))
        #只剩一个就直接返回
        if len(winners) == 1:
            return (winners[0], rejected,
                    "优先级更高（%d > %d）" % (best, max(l.rule.priority
                                                        for l in losers)),
                    STRATEGY_PRIORITY)
        #还有并列的，带进下一级继续比
        remaining = winners

    #2比前件条件的个数，更具体的赢
    best = max(m.rule.condition_count for m in remaining)
    winners = [m for m in remaining if m.rule.condition_count == best]
    if len(winners) < len(remaining):
        losers = [m for m in remaining if m.rule.condition_count != best]
        for m in losers:
            rejected.append(RejectedRule(
                m.rule, STRATEGY_SPECIFICITY,
                "前件条件数 %d 少于 %d，规则更笼统"
                % (m.rule.condition_count, best)))
        if len(winners) == 1:
            return (winners[0], rejected,
                    "优先级相同，按专一性取前件更具体的规则（条件数 %d）" % best,
                    STRATEGY_SPECIFICITY)
        remaining = winners

    #3比命中事实的新旧，用到更新事实的赢
    best = max(m.recency for m in remaining)
    winners = [m for m in remaining if m.recency == best]
    if len(winners) < len(remaining):
        losers = [m for m in remaining if m.recency != best]
        for m in losers:
            rejected.append(RejectedRule(
                m.rule, STRATEGY_RECENCY,
                "命中事实的最新位置 %d 早于 %d" % (m.recency, best)))
        if len(winners) == 1:
            return (winners[0], rejected,
                    "优先级与专一性相同，取命中了更新事实的规则（事实位置 %d）" % best,
                    STRATEGY_RECENCY)
        remaining = winners

    #4比规则编号，小的赢，为了让结果确定
    remaining.sort(key=lambda m: m.rule.rule_id)
    chosen = remaining[0]
    for m in remaining[1:]:
        rejected.append(RejectedRule(
            m.rule, STRATEGY_ORDER,
            "各策略均相同，规则编号 %d 大于 %d"
            % (m.rule.rule_id, chosen.rule.rule_id)))
    return (chosen, rejected,
            "各策略均无法区分，按规则库编号顺序取 %s" % chosen.rule.rule_code,
            STRATEGY_ORDER)
