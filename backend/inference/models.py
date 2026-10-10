"""
推理机用到的数据结构
这里只有数据的定义，没有数据库也没有文件操作。知识库负责把存储里的数据
装配成这些对象，推理机只认识这些对象，两边就靠这个文件对接。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

#事实的两种来源
FACT_TYPE_INPUT = "input" # 用户勾选的
FACT_TYPE_DERIVED = "derived" # 推理推出来的

#冲突消解是第几级策略起的作用，会写进推理轨迹用来说明原因
STRATEGY_PRIORITY = "priority"
STRATEGY_SPECIFICITY = "specificity"
STRATEGY_RECENCY = "recency"
STRATEGY_ORDER = "order"


@dataclass(frozen=True)
class Fact:
    """一条事实。frozen 表示建好之后不允许再改"""
    code: str # 编码，程序内部拿它做比对
    name: str = "" # 中文名，界面上显示用
    category_code: str = "" # 所属类别的编码
    category_name: str = "" # 所属类别的中文名
    fact_type: str = FACT_TYPE_INPUT # 是input还是derived
    description: str = "" # 说明文字

    def __str__(self) -> str:
        #打印对象的时候优先显示中文名，没有就退回编码
        return self.name or self.code


@dataclass(frozen=True)
class Condition:
    """规则前件里的一个条件项"""
    fact_code: str #要求哪个事实
    is_negate: bool = False #True表示要求这个事实不存在

    def __str__(self) -> str:
        #打印的时候带上前面的"非"，方便看
        return ("非 " if self.is_negate else "") + self.fact_code


@dataclass
class Rule:
    """一条产生式规则，IF 前件 THEN 后件"""

    rule_id: int # 主键，冲突消解第4级比的就是它
    rule_code: str # 编号，比如 R001
    rule_name: str # 名称
    priority: int = 0 # 优先级，越大越优先
    conditions: List[Condition] = field(default_factory=list) # 前件
    conclusions: List[str] = field(default_factory=list) # 后件，存的是事实编码
    description: str = "" # 说明
    is_enabled: bool = True # 停用的规则不参与匹配

    @property
    def condition_count(self) -> int:
        #条件个数，冲突消解第2级（专一性）用它
        return len(self.conditions)

    def __str__(self) -> str:
        return "[%s] %s" % (self.rule_code, self.rule_name)


@dataclass
class MatchResult:
    """一条规则和工作记忆匹配之后的结果"""

    rule: Rule
    matched: bool # 匹配上了没有
    matched_facts: List[str] = field(default_factory=list) # 满足了哪些条件事实
    new_conclusions: List[str] = field(default_factory=list) # 后件里还没出现过的结论
    recency: int = -1 # 命中的事实里最新那个的加入序号，第3级策略用
    reason: str = "" # 没匹配上时说明原因，调试用


@dataclass
class RejectedRule:
    """冲突消解里被淘汰掉的候选规则。"""

    rule: Rule
    lost_by: str # 被哪一级策略淘汰的
    detail: str = "" # 具体说明，比如"优先级 95 低于 98"


@dataclass
class InferenceStep:
    """推理过程中的一轮：匹配、冲突消解、执行。"""

    round_no: int # 第几轮
    rule: Rule # 这一轮选中执行的规则
    matched_facts: List[str] # 命中的事实
    derived_facts: List[str] # 这一轮新推出来的结论
    candidates: List[Rule] = field(default_factory=list) # 这一轮的冲突集
    rejected: List[RejectedRule] = field(default_factory=list) # 被淘汰的那些
    resolution: str = "" # 消解说明，比如"优先级更高（98 > 95）"
    strategy: str = "" # 起决定作用的是哪一级


@dataclass
class InferenceResult:
    """一次推理跑完之后的结果。"""

    initial_facts: List[str] = field(default_factory=list) # 输入的初始事实
    derived_facts: List[str] = field(default_factory=list) # 推出来的结论，按推导顺序
    all_facts: List[str] = field(default_factory=list) # 结束时工作记忆里的全部事实
    steps: List[InferenceStep] = field(default_factory=list) # 每一轮的轨迹
    rules_loaded: int = 0 # 这次载入了多少条规则
    rounds: int = 0 # 一共推了几轮
    halted: bool = False # 是不是因为到了最大轮次被中止
    message: str = "" # 给用户看的一句话

    @property
    def conclusions(self) -> List[str]:
        #结论列表，后面的排后面
        return list(self.derived_facts)


@dataclass
class WorkingMemory:
    """综合数据库，存当前已知的所有事实

    除了事实本身，还记了每个事实是第几个加进来的，这个顺序就是冲突消解
    第3级"最近性"的依据。
    """

    _facts: Dict[str, Fact] = field(default_factory=dict) # 编码事实
    _order: Dict[str, int] = field(default_factory=dict) # 编码加入序号
    _counter: int = 0 # 加入计数器，每加一条加1

    def add(self, fact: Fact) -> bool:
        """加一条事实，返回是不是新加的"""
        if fact.code in self._facts:
            return False #已经在了，不算新增
        self._facts[fact.code] = fact
        self._order[fact.code] = self._counter #记下它是第几个进来的
        self._counter += 1
        return True

    def add_code(self, code: str) -> bool:
        #只给编码的时候用这个，内部包一个 Fact
        return self.add(Fact(code=code))

    def extend(self, facts) -> None:
        #批量加
        for fact in facts:
            self.add(fact)

    def contains(self, code: str) -> bool:
        #这个事实在不在
        return code in self._facts

    def order_of(self, code: str) -> int:
        #取加入序号，不在的话返回 -1
        return self._order.get(code, -1)

    def codes(self) -> List[str]:
        return list(self._facts.keys())

    def facts(self) -> List[Fact]:
        return list(self._facts.values())

    def __len__(self) -> int:
        return len(self._facts)

    def __contains__(self, code: str) -> bool:
        #有了它就能写 if code in memory
        return code in self._facts
