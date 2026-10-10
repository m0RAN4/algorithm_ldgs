"""
MySQL知识库仓储
干的活是把数据库里的行装配成推理机认识的 Fact / Rule 对象，另外提供
规则的增删改查。这个类实现了 KnowledgeProvider 接口，但对推理机来说
它只是"某个 provider"，推理机并不知道背后是 MySQL。
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from ..inference.models import (FACT_TYPE_DERIVED, FACT_TYPE_INPUT, Condition,
                                Fact, Rule)
from ..inference.provider import KnowledgeProvider
from . import connection
from .connection import DatabaseError

#事实


def list_categories() -> List[dict]:
    """取全部事实类别，按展示顺序排。"""
    return connection.query_all(
        "SELECT category_code, category_name, sort_order "
        "FROM fact_category ORDER BY sort_order, category_code")


def list_facts(only_enabled: bool = False, fact_type: str = None) -> List[dict]:
    """取事实列表，连类别中文名一起查出来。"""
    sql = ("SELECT f.fact_id, f.fact_code, f.fact_name, f.category_code, "
           "       c.category_name, f.fact_type, f.description, f.sort_order, "
           "       f.is_enabled "
           "FROM fact f LEFT JOIN fact_category c "
           "  ON c.category_code = f.category_code ")
    #条件是一点点拼上去的，用到了哪个才加哪个
    where = []
    params = []
    if only_enabled:
        where.append("f.is_enabled = 1")
    if fact_type:
        where.append("f.fact_type = %s")
        params.append(fact_type)
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "ORDER BY c.sort_order, f.sort_order, f.fact_id"
    return connection.query_all(sql, params or None)


def get_fact(fact_id: int) -> Optional[dict]:
    """按主键查一条事实。"""
    return connection.query_one(
        "SELECT fact_id, fact_code, fact_name, category_code, fact_type, "
        "       description, sort_order, is_enabled FROM fact WHERE fact_id = %s",
        [fact_id])


def create_fact(data: dict) -> int:
    """新增一条事实，返回新的主键。"""
    _affected, new_id = connection.execute(
        "INSERT INTO fact (fact_code, fact_name, category_code, fact_type, "
        "                  description, sort_order, is_enabled) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        [data["fact_code"], data["fact_name"], data["category_code"],
         data.get("fact_type", FACT_TYPE_INPUT), data.get("description", ""),
         int(data.get("sort_order", 0)), 1 if data.get("is_enabled", True) else 0])
    return new_id


def update_fact(fact_id: int, data: dict) -> int:
    """改一条事实。注意 fact_code 是不给改的，它被规则引用着。"""
    affected, _ = connection.execute(
        "UPDATE fact SET fact_name = %s, category_code = %s, fact_type = %s, "
        "  description = %s, sort_order = %s, is_enabled = %s "
        "WHERE fact_id = %s",
        [data["fact_name"], data["category_code"],
         data.get("fact_type", FACT_TYPE_INPUT), data.get("description", ""),
         int(data.get("sort_order", 0)),
         1 if data.get("is_enabled", True) else 0, fact_id])
    return affected


def delete_fact(fact_id: int) -> int:
    """删一条事实。前件后件表上有外键，关联的记录会被一起删掉。"""
    affected, _ = connection.execute("DELETE FROM fact WHERE fact_id = %s", [fact_id])
    return affected


def fact_reference_count(fact_code: str) -> int:
    """数一下这个事实被多少条规则引用了，删除之前先提示用。"""
    row = connection.query_one(
        "SELECT (SELECT COUNT(*) FROM rule_condition WHERE fact_code = %s) + "
        "       (SELECT COUNT(*) FROM rule_conclusion WHERE fact_code = %s) AS n",
        [fact_code, fact_code])
    return int(row["n"]) if row else 0


#规则


def fetch_facts() -> List[Fact]:
    """接口方法：取全部启用的事实，装配成 Fact 对象。"""
    #先做出 类别编码 -> 类别中文名 的对应关系
    category_names = {c["category_code"]: c["category_name"]
                      for c in list_categories()}
    return [
        Fact(code=row["fact_code"], name=row["fact_name"],
             category_code=row["category_code"],
             category_name=category_names.get(row["category_code"], ""),
             fact_type=row["fact_type"], description=row["description"] or "")
        for row in list_facts(only_enabled=True)
    ]


def fetch_rules() -> List[Rule]:
    """接口方法：取全部规则，装配成 Rule 对象。

    这里固定用三条 SELECT 查完（规则、前件、后件），再在 Python 里按
    rule_id 分好组装起来。要是每条规则各查一次条件和结论，50 条规则
    就要查 101 次，太亏了。
    """
    rule_rows = connection.query_all(
        "SELECT rule_id, rule_code, rule_name, priority, description, is_enabled "
        "FROM rule ORDER BY rule_id")
    if not rule_rows:
        return []

    cond_rows = connection.query_all(
        "SELECT rule_id, fact_code, is_negate FROM rule_condition "
        "ORDER BY rule_id, sort_order, condition_id")
    concl_rows = connection.query_all(
        "SELECT rule_id, fact_code FROM rule_conclusion "
        "ORDER BY rule_id, sort_order, conclusion_id")

    #前件按 rule_id 分组
    conditions: Dict[int, List[Condition]] = {}
    for row in cond_rows:
        conditions.setdefault(row["rule_id"], []).append(
            Condition(fact_code=row["fact_code"],
                      is_negate=bool(row["is_negate"])))
    #后件也按 rule_id 分组
    conclusions: Dict[int, List[str]] = {}
    for row in concl_rows:
        conclusions.setdefault(row["rule_id"], []).append(row["fact_code"])

    return [
        Rule(
            rule_id=row["rule_id"],
            rule_code=row["rule_code"],
            rule_name=row["rule_name"],
            priority=int(row["priority"]),
            conditions=conditions.get(row["rule_id"], []),
            conclusions=conclusions.get(row["rule_id"], []),
            description=row["description"] or "",
            is_enabled=bool(row["is_enabled"]),
        )
        for row in rule_rows
    ]


def list_rules(keyword: str = "", only_enabled: bool = False) -> List[dict]:
    """取规则列表给界面用，支持按编号或名称搜索。"""
    sql = ("SELECT rule_id, rule_code, rule_name, priority, description, "
           "       is_enabled, created_at, updated_at FROM rule ")
    where, params = [], []
    if only_enabled:
        where.append("is_enabled = 1")
    if keyword:
        #编号和名称都搜一下
        where.append("(rule_code LIKE %s OR rule_name LIKE %s)")
        params.extend(["%" + keyword + "%", "%" + keyword + "%"])
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "ORDER BY priority DESC, rule_id"
    rows = connection.query_all(sql, params or None)

    if not rows:
        return []
    return _attach_conditions_and_conclusions(rows)


def get_rule(rule_id: int) -> Optional[dict]:
    """查一条规则的完整信息，带前件后件。"""
    row = connection.query_one(
        "SELECT rule_id, rule_code, rule_name, priority, description, "
        "       is_enabled, created_at, updated_at FROM rule WHERE rule_id = %s",
        [rule_id])
    if not row:
        return None
    return _attach_conditions_and_conclusions([row])[0]


def _attach_conditions_and_conclusions(rows: List[dict]) -> List[dict]:
    """给一批规则补上前件和后件。

    先把这批规则的 id 拼成 IN (...) 一次查回来，再按 rule_id 分发下去，
    免得每条规则都去查一次。
    """
    index = {row["rule_id"]: row for row in rows}
    for row in rows:
        row["conditions"] = []
        row["conclusions"] = []

    #id 都是数据库里的整数，直接拼进 IN 里没有注入风险
    ids = ", ".join(str(int(r["rule_id"])) for r in rows)
    for row in connection.query_all(
            "SELECT rule_id, fact_code, is_negate, sort_order FROM rule_condition "
            "WHERE rule_id IN (%s) ORDER BY sort_order, condition_id" % ids):
        if row["rule_id"] in index:
            index[row["rule_id"]]["conditions"].append({
                "fact_code": row["fact_code"],
                "is_negate": bool(row["is_negate"]),
            })
    for row in connection.query_all(
            "SELECT rule_id, fact_code FROM rule_conclusion "
            "WHERE rule_id IN (%s) ORDER BY sort_order, conclusion_id" % ids):
        if row["rule_id"] in index:
            index[row["rule_id"]]["conclusions"].append(row["fact_code"])

    #顺手把字段类型规整一下，界面上好直接用
    for row in rows:
        row["is_enabled"] = bool(row["is_enabled"])
        row["priority"] = int(row["priority"])
        row["description"] = row["description"] or ""
    return rows


def _rule_statements(data: dict, rule_id: Optional[int] = None):
    """拼出新增或修改一条规则要执行的全部语句，交给事务去跑。

    rule_id 传 None 是新增，传了值就是修改。返回值是一串
    (SQL, 参数) 的元组，不是直接执行。
    """
    conditions = data.get("conditions") or []
    conclusions = data.get("conclusions") or []
    if not conditions:
        raise DatabaseError("规则至少要有一个前件条件")
    if not conclusions:
        raise DatabaseError("规则至少要有一个结论")

    statements = []
    if rule_id is None:
        #新增：先插主表
        statements.append((
            "INSERT INTO rule (rule_code, rule_name, priority, description, "
            "                  is_enabled) VALUES (%s, %s, %s, %s, %s)",
            [data["rule_code"], data["rule_name"], int(data.get("priority", 0)),
             data.get("description", ""),
             1 if data.get("is_enabled", True) else 0]))
    else:
        #修改：先改主表，再把旧的前件后件全删掉
        statements.append((
            "UPDATE rule SET rule_code = %s, rule_name = %s, priority = %s, "
            "  description = %s, is_enabled = %s WHERE rule_id = %s",
            [data["rule_code"], data["rule_name"], int(data.get("priority", 0)),
             data.get("description", ""),
             1 if data.get("is_enabled", True) else 0, rule_id]))
        statements.append((
            "DELETE FROM rule_condition WHERE rule_id = %s", [rule_id]))
        statements.append((
            "DELETE FROM rule_conclusion WHERE rule_id = %s", [rule_id]))

    #子表引用父表主键：新增时用子查询按编号回查，修改时直接用传进来的 id。
    #这里不能用 LAST_INSERT_ID()——它只对"紧随父表插入的那一条"有效，
    #后面每条子表插入都会把自己的自增主键顶上去，第二条开始就指错了
    if rule_id is None:
        rule_ref = "(SELECT rule_id FROM rule WHERE rule_code = %s)"
        ref_params = [data["rule_code"]]
    else:
        rule_ref = "%s"
        ref_params = [rule_id]
    #前件一行一个条件，sort_order 按 10 递增留点余地
    for order, item in enumerate(conditions):
        code = item["fact_code"] if isinstance(item, dict) else item
        negate = item.get("is_negate", False) if isinstance(item, dict) else False
        statements.append((
            "INSERT INTO rule_condition (rule_id, fact_code, is_negate, sort_order) "
            "VALUES (" + rule_ref + ", %s, %s, %s)",
            ref_params + [code, 1 if negate else 0, (order + 1) * 10]))
    #后件也是一行一个结论
    for order, code in enumerate(conclusions):
        statements.append((
            "INSERT INTO rule_conclusion (rule_id, fact_code, sort_order) "
            "VALUES (" + rule_ref + ", %s, %s)",
            ref_params + [code, (order + 1) * 10]))
    return statements


def create_rule(data: dict) -> None:
    """新增一条规则，主表、前件、后件在同一个事务里写完。"""
    connection.execute_many(_rule_statements(data))


def update_rule(rule_id: int, data: dict) -> None:
    """修改一条规则，同样是事务。"""
    connection.execute_many(_rule_statements(data, rule_id))


def delete_rule(rule_id: int) -> int:
    """删规则。前件和后件靠外键的级联删除自动清掉。"""
    affected, _ = connection.execute("DELETE FROM rule WHERE rule_id = %s", [rule_id])
    return affected


def toggle_rule(rule_id: int, enabled: bool) -> int:
    """启用或停用一条规则。停用不动数据，只是不参与匹配。"""
    affected, _ = connection.execute(
        "UPDATE rule SET is_enabled = %s WHERE rule_id = %s",
        [1 if enabled else 0, rule_id])
    return affected


def next_rule_code() -> str:
    """猜一个没用过的规则编号，给新增界面和自动生成用。

    取现有 R 编号里最大的数字加一。不数行数、也不看主键：
    删过规则、事务回滚过的话主键会跳号，但用户看到的编号空间
    （R001、R002……）才是顺序的依据。
    """
    row = connection.query_one(
        "SELECT MAX(CAST(SUBSTRING(rule_code, 2) AS UNSIGNED)) AS n "
        "FROM rule WHERE rule_code REGEXP '^R[0-9]+$'")
    n = int(row["n"]) if row and row["n"] is not None else 0
    return "R%03d" % (n + 1)


#算法主题


def list_topics() -> List[dict]:
    """取全部算法主题。"""
    return connection.query_all(
        "SELECT topic_id, topic_code, topic_name, difficulty, estimated_hours, "
        "       core_points, learning_path, typical_problems, sort_order "
        "FROM algorithm_topic ORDER BY sort_order, topic_id")


def topic_map() -> Dict[str, dict]:
    """做成 主题编码 -> 主题内容 的字典，方便按编码取。"""
    return {row["topic_code"]: row for row in list_topics()}


#咨询记录


def save_consult(summary: dict, input_codes: List[str], derived_codes: List[str],
                 traces: List[dict]) -> int:
    """保存一次推理：主记录、事实明细、逐轮轨迹。

    会话编号没有用"先数一下有几条再加一"，那样两个请求同时进来会撞唯一键。
    这里是先插一条编号为空的记录拿到自增主键，再用主键回填 LDGS-0001。
    """
    _affected, record_id = connection.execute(
        "INSERT INTO consult_record (session_no, input_count, conclusion_count, "
        "  round_count, duration_ms, is_halted, rules_loaded) "
        "VALUES (NULL, %s, %s, %s, %s, %s, %s)",
        [len(input_codes), len(derived_codes),
         summary["round_count"], summary["duration_ms"],
         1 if summary.get("halted") else 0, summary.get("rules_loaded", 0)])
    connection.execute(
        "UPDATE consult_record "
        "SET session_no = CONCAT('LDGS-', LPAD(record_id, 4, '0')) "
        "WHERE record_id = %s", [record_id])

    #事实的名字先查出来，等下写明细的时候直接取，不用一条条查
    fact_rows = {f["fact_code"]: f for f in list_facts()}

    statements = []
    #输入的事实
    for order, code in enumerate(input_codes, start=1):
        info = fact_rows.get(code)
        statements.append((
            "INSERT INTO consult_record_fact (record_id, fact_code, fact_name, "
            "  category_code, fact_role, result_order) VALUES (%s, %s, %s, %s, %s, %s)",
            [record_id, code, info["fact_name"] if info else code,
             info["category_code"] if info else "", "input", order]))
    #推出的结论，result_order 记下推导顺序
    for order, code in enumerate(derived_codes, start=1):
        info = fact_rows.get(code)
        statements.append((
            "INSERT INTO consult_record_fact (record_id, fact_code, fact_name, "
            "  category_code, fact_role, result_order) VALUES (%s, %s, %s, %s, %s, %s)",
            [record_id, code, info["fact_name"] if info else code,
             info["category_code"] if info else "", "derived", order]))
    #每一轮的轨迹，几个列表用 JSON 存
    for trace in traces:
        statements.append((
            "INSERT INTO consult_trace (record_id, round_no, rule_code, rule_name, "
            "  priority, strategy, resolution, matched_facts, derived_facts, "
            "  candidate_count, rejected) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [record_id, trace["round_no"], trace["rule_code"], trace["rule_name"],
             trace["priority"], trace["strategy"], trace["resolution"],
             json.dumps(trace["matched_facts"], ensure_ascii=False),
             json.dumps(trace["derived_facts"], ensure_ascii=False),
             trace["candidate_count"],
             json.dumps(trace["rejected"], ensure_ascii=False)]))
    connection.execute_many(statements)
    return record_id


def list_consults(limit: int = 50) -> List[dict]:
    """查咨询记录列表，新的排前面。"""
    return connection.query_all(
        "SELECT record_id, session_no, input_count, conclusion_count, round_count, "
        "       duration_ms, is_halted, rules_loaded, created_at "
        "FROM consult_record ORDER BY record_id DESC LIMIT %s", [int(limit)])


def get_consult(record_id: int) -> Optional[dict]:
    """查一条记录的详情，事实明细和推理轨迹都带上。"""
    record = connection.query_one(
        "SELECT record_id, session_no, input_count, conclusion_count, round_count, "
        "       duration_ms, is_halted, rules_loaded, created_at "
        "FROM consult_record WHERE record_id = %s", [record_id])
    if not record:
        return None
    #这次咨询勾了哪些、推出了哪些
    record["facts"] = connection.query_all(
        "SELECT fact_code, fact_name, category_code, fact_role, result_order "
        "FROM consult_record_fact WHERE record_id = %s "
        "ORDER BY fact_role, result_order", [record_id])
    #逐轮轨迹
    traces = connection.query_all(
        "SELECT round_no, rule_code, rule_name, priority, strategy, resolution, "
        "       matched_facts, derived_facts, candidate_count, rejected "
        "FROM consult_trace WHERE record_id = %s ORDER BY round_no", [record_id])
    #三个字段在库里是 JSON 文本，取出来要转回列表
    for trace in traces:
        for key in ("matched_facts", "derived_facts", "rejected"):
            try:
                trace[key] = json.loads(trace[key]) if trace[key] else []
            except (ValueError, TypeError):
                trace[key] = []
    record["traces"] = traces
    return record


def delete_consult(record_id: int) -> int:
    """删一条记录，明细和轨迹靠级联删除一起清掉。"""
    affected, _ = connection.execute(
        "DELETE FROM consult_record WHERE record_id = %s", [record_id])
    return affected


#统计


def overview() -> dict:
    """概览页要的几个总数。"""
    def scalar(sql):
        #只取一个数字的查询用这个包一下
        row = connection.query_one(sql)
        return int(list(row.values())[0]) if row else 0

    return {
        "fact_count": scalar("SELECT COUNT(*) FROM fact"),
        "input_fact_count": scalar(
            "SELECT COUNT(*) FROM fact WHERE fact_type = 'input'"),
        "rule_count": scalar("SELECT COUNT(*) FROM rule"),
        "enabled_rule_count": scalar(
            "SELECT COUNT(*) FROM rule WHERE is_enabled = 1"),
        "topic_count": scalar("SELECT COUNT(*) FROM algorithm_topic"),
        "consult_count": scalar("SELECT COUNT(*) FROM consult_record"),
        "last_consult_at": (connection.query_one(
            "SELECT MAX(created_at) AS t FROM consult_record") or {}).get("t"),
    }


def hot_facts(limit: int = 8) -> List[dict]:
    """最常被勾选的事实。能这么简单地分组统计，是因为输入事实是一行一条存的。"""
    return connection.query_all(
        "SELECT fact_code, fact_name, COUNT(*) AS times "
        "FROM consult_record_fact WHERE fact_role = 'input' "
        "GROUP BY fact_code, fact_name ORDER BY times DESC, fact_code "
        "LIMIT %s", [int(limit)])


def hot_rules(limit: int = 8) -> List[dict]:
    """触发次数最多的规则。"""
    return connection.query_all(
        "SELECT rule_code, rule_name, COUNT(*) AS times "
        "FROM consult_trace GROUP BY rule_code, rule_name "
        "ORDER BY times DESC, rule_code LIMIT %s", [int(limit)])


class MySqlKnowledgeRepository(KnowledgeProvider):
    """把上面这些函数包成一个对象，好在服务层注入给推理机。"""

    def fetch_rules(self) -> List[Rule]:
        return fetch_rules()

    def fetch_facts(self) -> List[Fact]:
        return fetch_facts()
