"""
知识库的接口定义
推理机不直接依赖任何具体的存储实现，只依赖这里声明的接口。MySQL 仓储和
文件仓储都实现这个接口，所以知识库可以整体换掉，推理机一行都不用改
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import Fact, Rule


class KnowledgeProvider(ABC):
    """知识库对外提供的只读接口。"""

    @abstractmethod
    def fetch_rules(self) -> List[Rule]:
        """取全部规则，前件和后件都要带上。"""

    @abstractmethod
    def fetch_facts(self) -> List[Fact]:
        """取全部事实的定义，用来展示和校验。"""


class RuleProvider(ABC):
    """最小接口，推理机只需要规则。"""

    @abstractmethod
    def fetch_rules(self) -> List[Rule]:
        """取全部规则。"""
