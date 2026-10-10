"""知识库管理：规则的增删改查和校验。

对应实验要求第 5 条（可选）——不改推理机程序也能往知识库里加、删、改规则。
这个模块只管数据库里的数据。推理机每次推理前都会重新取一遍规则，
所以改完立刻生效，不用重启服务，更不用动推理机。
"""
from __future__ import annotations

import config
import re
from typing import Dict, List

from ..knowledge import file_repository, repository, seed_data
from ..knowledge.connection import DatabaseError

#规则编号和事实编码都用这个格式：字母开头，后面字母数字下划线
RULE_CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")

READONLY_MESSAGE = ("当前使用内置文件知识库（只读演示模式），无法修改规则。"
                    "配好数据库后用 python app.py 启动即可在界面上增删改规则。")


class ValidationError(Exception):
    """规则或事实的数据不合法，消息会直接显示给用户。"""


def _is_file_mode() -> bool:
    #知识源不是 db 就是文件模式
    return config.KNOWLEDGE_SOURCE != "db"


def _require_writable():
    """写操作之前先过一下，文件模式直接拒绝。"""
    if _is_file_mode():
        raise ValidationError(READONLY_MESSAGE)


def _fact_codes() -> Dict[str, str]:
    #做成 编码 -> 中文名，很多地方要用
    return {row["fact_code"]: row["fact_name"] for row in list_facts()}


def validate_rule(payload: dict) -> dict:
    """校验一条规则的数据，顺便整理成规范格式。

    前端提交上来的东西不能直接信，这里把该查的都查一遍，
    错误信息写成中文，直接显示给用户看。
    """
    if not isinstance(payload, dict):
        raise ValidationError("提交的数据格式不正确")

    code = str(payload.get("rule_code") or "").strip()
    name = str(payload.get("rule_name") or "").strip()
    description = str(payload.get("description") or "").strip()

    #编号允许留空：新增时自动生成一个（见返回值），修改时保持原编号。
    #填了就要符合格式
    if code and not RULE_CODE_PATTERN.match(code):
        raise ValidationError("规则编号只能由字母、数字、下划线组成，且以字母开头")
    if not name:
        raise ValidationError("规则名称不能为空")
    if len(name) > 64:
        raise ValidationError("规则名称不能超过 64 个字符")

    #优先级
    try:
        priority = int(payload.get("priority", 0))
    except (TypeError, ValueError):
        raise ValidationError("优先级必须是整数")
    if not 0 <= priority <= 9999:
        raise ValidationError("优先级取值范围是 0 ~ 9999")

    #前件。一条规则至少得有一个条件
    raw_conditions = payload.get("conditions") or []
    if not isinstance(raw_conditions, list) or not raw_conditions:
        raise ValidationError("规则至少要有一个前件条件")

    conditions = []
    seen = set() #用来查重
    for item in raw_conditions:
        #前端传的是字典，也兼容直接传字符串的情况
        if isinstance(item, dict):
            fact_code = str(item.get("fact_code") or "").strip()
            is_negate = bool(item.get("is_negate"))
        else:
            fact_code, is_negate = str(item).strip(), False
        if not fact_code:
            continue #空的跳过
        if fact_code in seen:
            raise ValidationError("前件中存在重复的条件事实：%s" % fact_code)
        seen.add(fact_code)
        conditions.append({"fact_code": fact_code, "is_negate": is_negate})

    #后件。只传了一个字符串的话先包成列表
    raw_conclusions = payload.get("conclusions") or []
    if isinstance(raw_conclusions, str):
        raw_conclusions = [raw_conclusions]
    conclusions = []
    seen_conclusions = set()
    for item in raw_conclusions:
        fact_code = str(item.get("fact_code") if isinstance(item, dict)
                        else item).strip()
        if not fact_code or fact_code in seen_conclusions:
            continue #空的和重复的都丢掉
        seen_conclusions.add(fact_code)
        conclusions.append(fact_code)

    if not conditions:
        raise ValidationError("规则至少要有一个有效的前件条件")
    if not conclusions:
        raise ValidationError("规则至少要有一个结论")

    #引用的每一个事实都必须已经在事实字典里存在
    known = _fact_codes()
    unknown = [c for c in list(seen) + conclusions if c not in known]
    if unknown:
        raise ValidationError("以下事实不存在，请先在事实字典中定义：%s"
                              % "、".join(sorted(set(unknown))))

    return {
        "rule_code": code or repository.next_rule_code(), #没填就自动生成一个
        "rule_name": name,
        "priority": priority,
        "description": description,
        "is_enabled": bool(payload.get("is_enabled", True)),
        "conditions": conditions,
        "conclusions": conclusions,
    }


#规则


def _file_repo() -> file_repository.FileKnowledgeRepository:
    return file_repository.FileKnowledgeRepository()


def _file_rule_rows() -> List[dict]:
    """把文件知识库的规则转成和数据库行一样的字典，这样界面处理方式统一。"""
    rows = []
    for rule in _file_repo().fetch_rules():
        rows.append({
            "rule_id": rule.rule_id,
            "rule_code": rule.rule_code,
            "rule_name": rule.rule_name,
            "priority": rule.priority,
            "description": rule.description,
            "is_enabled": rule.is_enabled,
            "created_at": None, #文件里没有这两个时间，给 None
            "updated_at": None,
            "conditions": [{"fact_code": c.fact_code, "is_negate": c.is_negate}
                           for c in rule.conditions],
            "conclusions": list(rule.conclusions),
        })
    return rows


def _file_fact_rows() -> List[dict]:
    """文件知识库的事实也转成一样的字典。"""
    category_names = {code: name for code, name, _o in seed_data.CATEGORIES}
    rows = []
    for index, fact in enumerate(_file_repo().fetch_facts(), start=1):
        rows.append({
            "fact_id": index, #文件模式没有真主键，用顺序号顶替
            "fact_code": fact.code,
            "fact_name": fact.name,
            "category_code": fact.category_code,
            "category_name": category_names.get(fact.category_code, ""),
            "fact_type": fact.fact_type,
            "description": fact.description,
            "sort_order": index * 10,
            "is_enabled": 1,
        })
    return rows


def list_rules(keyword: str = "", only_enabled: bool = False) -> List[dict]:
    """取规则列表。文件模式下没有数据库，就在内存里过滤和排序。"""
    if _is_file_mode():
        rows = _file_rule_rows()
        if only_enabled:
            rows = [r for r in rows if r["is_enabled"]]
        if keyword:
            key = keyword.lower()
            rows = [r for r in rows
                    if key in r["rule_code"].lower()
                    or key in r["rule_name"].lower()]
        #优先级高的排前面，和数据库那边的排序保持一致
        rows.sort(key=lambda r: (-r["priority"], r["rule_id"]))
    else:
        rows = repository.list_rules(keyword, only_enabled)
    return [decorate_rule(row) for row in rows]


def get_rule(rule_id: int) -> dict:
    """按 id 取一条规则。"""
    if _is_file_mode():
        for row in _file_rule_rows():
            if row["rule_id"] == rule_id:
                return decorate_rule(row)
        raise ValidationError("规则不存在或已被删除")
    row = repository.get_rule(rule_id)
    if not row:
        raise ValidationError("规则不存在或已被删除")
    return decorate_rule(row)


def next_rule_code() -> str:
    """猜一个能用的规则编号，给新增界面预填。"""
    if _is_file_mode():
        return "R%03d" % (len(_file_rule_rows()) + 1)
    return repository.next_rule_code()


def decorate_rule(row: dict) -> dict:
    """给规则补上几段现成的可读文本，界面上直接用。

    数据库里前件存的是编码，这里翻译成中文拼成一句话，
    比如 ["stage_foundation","base_programming"] 变成
    "处于基础夯实阶段 ∧ 有编程基础"。
    """
    known = _fact_codes()
    #前件拼成一句话，∧ 就是逻辑与
    row["condition_text"] = " ∧ ".join(
        ("非 " if c["is_negate"] else "") + known.get(c["fact_code"], c["fact_code"])
        for c in row["conditions"]) or "（无前件）"
    #后件也一样
    row["conclusion_text"] = " ∧ ".join(
        known.get(c, c) for c in row["conclusions"]) or "（无结论）"
    #再给一份带编码的明细，编辑规则的时候要回填
    row["conditions_detail"] = [
        {"fact_code": c["fact_code"], "fact_name": known.get(c["fact_code"], ""),
         "is_negate": c["is_negate"]} for c in row["conditions"]]
    row["conclusions_detail"] = [
        {"fact_code": c, "fact_name": known.get(c, "")} for c in row["conclusions"]]
    return row


def create_rule(payload: dict) -> dict:
    """新增一条规则。编号没填就自动生成一个，前端不用先查。"""
    _require_writable()
    data = validate_rule(payload)
    try:
        repository.create_rule(data)
    except DatabaseError as exc:
        #数据库的英文报错翻译成中文再抛出去
        raise ValidationError(_friendly_db_error(exc, data["rule_code"]))
    return {"rule_code": data["rule_code"]}


def update_rule(rule_id: int, payload: dict) -> dict:
    """改一条规则。"""
    _require_writable()
    if not repository.get_rule(rule_id):
        raise ValidationError("规则不存在或已被删除")
    data = validate_rule(payload)
    #编号允许不改，留空就用原来的
    data["rule_code"] = (str(payload.get("rule_code") or "").strip()
                         or repository.get_rule(rule_id)["rule_code"])
    try:
        repository.update_rule(rule_id, data)
    except DatabaseError as exc:
        raise ValidationError(_friendly_db_error(exc, data["rule_code"]))
    return {"rule_code": data["rule_code"]}


def delete_rule(rule_id: int) -> None:
    """删一条规则。影响行数是 0 说明压根没这条。"""
    _require_writable()
    if not repository.delete_rule(rule_id):
        raise ValidationError("规则不存在或已被删除")


def toggle_rule(rule_id: int, enabled: bool) -> None:
    """启用或停用。停用不删数据，只是不参与推理。"""
    _require_writable()
    if not repository.toggle_rule(rule_id, enabled):
        raise ValidationError("规则不存在或已被删除")


def _friendly_db_error(exc: Exception, code: str) -> str:
    """把数据库的英文报错换成用户看得懂的中文。"""
    text = str(exc)
    if "Duplicate entry" in text or "1062" in text:
        return "规则编号 %s 已存在，请换一个" % code #1062 是唯一键冲突
    if "foreign key" in text.lower():
        return "前件或结论引用了不存在的事实"
    return "保存规则失败：%s" % text


#事实


def list_facts() -> List[dict]:
    if _is_file_mode():
        return _file_fact_rows()
    return repository.list_facts()


def create_fact(payload: dict) -> int:
    """新增一条事实。"""
    _require_writable()
    code = str(payload.get("fact_code") or "").strip()
    name = str(payload.get("fact_name") or "").strip()
    if not code or not RULE_CODE_PATTERN.match(code):
        raise ValidationError("事实编码只能由字母、数字、下划线组成，且以字母开头")
    if not name:
        raise ValidationError("事实名称不能为空")
    fact_type = payload.get("fact_type", "input")
    if fact_type not in ("input", "derived"):
        raise ValidationError("事实类型只能是 input 或 derived")
    try:
        return repository.create_fact({
            "fact_code": code, "fact_name": name,
            "category_code": payload.get("category_code", "base"),
            "fact_type": fact_type,
            "description": str(payload.get("description") or ""),
            "sort_order": payload.get("sort_order", 0),
        })
    except DatabaseError as exc:
        text = str(exc)
        if "Duplicate entry" in text or "1062" in text:
            raise ValidationError("事实编码 %s 已存在" % code)
        raise ValidationError("新增事实失败：%s" % text)


def update_fact(fact_id: int, payload: dict) -> None:
    """改一条事实。编码不给改，因为规则正引用着它。"""
    _require_writable()
    if not repository.get_fact(fact_id):
        raise ValidationError("事实不存在")
    name = str(payload.get("fact_name") or "").strip()
    if not name:
        raise ValidationError("事实名称不能为空")
    repository.update_fact(fact_id, {
        "fact_name": name,
        "category_code": payload.get("category_code", "base"),
        "fact_type": payload.get("fact_type", "input"),
        "description": str(payload.get("description") or ""),
        "sort_order": payload.get("sort_order", 0),
    })


def delete_fact(fact_id: int) -> None:
    """删事实之前先看看还有没有规则在用它，有就不让删。"""
    _require_writable()
    row = repository.get_fact(fact_id)
    if not row:
        raise ValidationError("事实不存在")
    used = repository.fact_reference_count(row["fact_code"])
    if used:
        raise ValidationError(
            "事实「%s」仍被 %d 处规则引用，请先调整相关规则"
            % (row["fact_name"], used))
    repository.delete_fact(fact_id)


def list_categories() -> List[dict]:
    """取事实类别。"""
    if _is_file_mode():
        return [{"category_code": code, "category_name": name,
                 "sort_order": order}
                for code, name, order in seed_data.CATEGORIES]
    return repository.list_categories()


#历史和统计


def list_consults(limit: int = 50) -> List[dict]:
    """文件模式不存历史，直接给空列表。"""
    if _is_file_mode():
        return []
    return repository.list_consults(limit)


def get_consult(record_id: int) -> dict:
    if _is_file_mode():
        raise ValidationError("文件知识源模式下不保存历史记录")
    record = repository.get_consult(record_id)
    if not record:
        raise ValidationError("记录不存在")
    return record


def delete_consult(record_id: int) -> None:
    _require_writable()
    if not repository.delete_consult(record_id):
        raise ValidationError("记录不存在")


def statistics() -> dict:
    """概览页的数据。文件模式没有数据库，自己数一遍。"""
    if _is_file_mode():
        return {
            "fact_count": len(_file_fact_rows()),
            "input_fact_count": sum(1 for r in _file_fact_rows()
                                    if r["fact_type"] == "input"),
            "rule_count": len(_file_rule_rows()),
            "enabled_rule_count": len(_file_rule_rows()),
            "topic_count": len(seed_data.TOPICS),
            "consult_count": 0,
            "last_consult_at": None,
            "hot_facts": [], "hot_rules": [],
            "readonly": True, #界面上要显示"只读模式"
        }
    data = repository.overview()
    data["hot_facts"] = repository.hot_facts()
    data["hot_rules"] = repository.hot_rules()
    data["readonly"] = False
    return data


def list_topics() -> List[dict]:
    """取算法主题。"""
    if _is_file_mode():
        return [{"topic_code": c, "topic_name": n, "difficulty": d,
                 "estimated_hours": h, "core_points": cp,
                 "learning_path": lp, "typical_problems": tp,
                 "sort_order": i * 10}
                for i, (c, n, d, h, cp, lp, tp)
                in enumerate(seed_data.TOPICS, start=1)]
    return repository.list_topics()
