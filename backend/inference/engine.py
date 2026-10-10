"""
正向推理机
跑起来就是产生式系统的"识别-行动"循环，具体顺序看下面这个：
1. 匹配   把所有规则和工作记忆比一遍，得到冲突集
2. 消解   用分级策略从冲突集里选一条出来
3. 执行   把这条规则的结论加进工作记忆，记一笔轨迹
只要冲突集不为空就一直循环。因为每条规则在一次推理里最多触发一次，所以
循环一定会停，max_rounds只是个保险，预估根本用不到
这个文件不导入backend.knowledge里的任何东西，也没有SQL和文件读写
规则是从构造函数传进来的provider拿的，所以换知识库不影响推理机
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from .conflict import resolve_conflict
from .matcher import match_all
from .models import (InferenceResult, InferenceStep, WorkingMemory)

DEFAULT_MAX_ROUNDS = 200


class ForwardInferenceEngine:
    """
    基于产生式规则的正向推理机
    """
    def __init__(self, rule_provider, max_rounds: int = DEFAULT_MAX_ROUNDS):
        self.rule_provider = rule_provider
        self.max_rounds = max_rounds

    def infer(self, initial_fact_codes: Sequence[str]) -> InferenceResult:
        """从给的初始事实开始做正向推理。"""
        #每次推理都重新取一遍规则，这样知识库改了立刻生效，不用重启
        rules = [r for r in self.rule_provider.fetch_rules() if r.is_enabled]

        #建工作记忆，把用户勾的事实一次性全部装进去
        memory = WorkingMemory()
        initial = []
        for code in initial_fact_codes:
            code = (code or "").strip()
            if not code:
                continue
            if memory.add_code(code):
                initial.append(code) #去重之后才记进 initial

        steps: List[InferenceStep] = []
        derived: List[str] = []
        fired_rule_ids = set() #这次推理里已经触发过的规则
        halted = False

        #主循环匹配、冲突消解、执行
        while len(steps) < self.max_rounds:
            candidates = match_all(rules, memory, fired_rule_ids)
            if not candidates:
                break #冲突集空了，没有新东西可推

            chosen, rejected, resolution, strategy = resolve_conflict(
                candidates, memory)

            #执行把结论并进工作记忆
            newly = [c for c in chosen.new_conclusions if memory.add_code(c)]
            derived.extend(newly)
            fired_rule_ids.add(chosen.rule.rule_id)

            #这一轮的轨迹记下来，界面上要展示
            steps.append(InferenceStep(
                round_no=len(steps) + 1,
                rule=chosen.rule,
                matched_facts=list(chosen.matched_facts),
                derived_facts=newly,
                candidates=[m.rule for m in candidates],
                rejected=rejected,
                resolution=resolution,
                strategy=strategy,
            ))
        else:
            #while的条件不成立才退出来的，说明到轮次上限了
            halted = True

        message = "推理完成，共触发 %d 条规则" % len(steps)
        if halted:
            message = "达到最大推理轮次 %d，推理中止" % self.max_rounds
        elif not steps:
            message = "没有规则被触发，请检查所选条件是否充分"

        return InferenceResult(
            initial_facts=initial,
            derived_facts=derived,
            all_facts=memory.codes(),
            steps=steps,
            rules_loaded=len(rules),
            rounds=len(steps),
            halted=halted,
            message=message,
        )

    def explain(self, initial_fact_codes: Sequence[str]) -> str:
        """把一次推理的过程转成纯文本，命令行里看用"""
        result = self.infer(initial_fact_codes)
        lines = ["初始事实： " + ", ".join(result.initial_facts), ""]
        for step in result.steps:
            lines.append("第 %d 轮" % step.round_no)
            lines.append("  冲突集共 %d 条规则" % len(step.candidates))
            lines.append("  选中规则： %s" % step.rule) #这里会用到 Rule.__str__
            lines.append("  消解依据： %s" % step.resolution)
            lines.append("  推导结论： %s" % ", ".join(step.derived_facts))
            lines.append("")
        lines.append(result.message)
        return "\n".join(lines)
