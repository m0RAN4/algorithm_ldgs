"""规则库管理接口，对应实验要求第 5 条：不改推理机也能增删改规则。"""
from __future__ import annotations

from ..service import knowledge_service
from . import ApiError, Request, route


def _rule_id(request: Request) -> int:
    """从路径里取规则 id，顺手转成整数。"""
    raw = request.params.get("rule_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ApiError("规则 ID 不合法：%s" % raw)


@route("GET", "/api/rules")
def list_rules(request: Request):
    """规则列表，可以带关键词搜。"""
    return knowledge_service.list_rules(
        keyword=(request.arg("keyword") or "").strip(),
        only_enabled=request.arg("only_enabled") in ("1", "true", "True"))


@route("GET", "/api/rules/next-code")
def next_code(_request: Request):
    """给新增界面一个建议的编号。

    这条必须注册在 /api/rules/{rule_id} 前面，不然 next-code 会被
    当成 rule_id 匹配走。
    """
    return {"rule_code": knowledge_service.next_rule_code()}


@route("POST", "/api/rules")
def create_rule(request: Request):
    return knowledge_service.create_rule(request.body)


@route("GET", "/api/rules/{rule_id}")
def get_rule(request: Request):
    return knowledge_service.get_rule(_rule_id(request))


@route("PUT", "/api/rules/{rule_id}")
def update_rule(request: Request):
    return knowledge_service.update_rule(_rule_id(request), request.body)


@route("DELETE", "/api/rules/{rule_id}")
def delete_rule(request: Request):
    knowledge_service.delete_rule(_rule_id(request))
    return {"deleted": True}


@route("POST", "/api/rules/{rule_id}/toggle")
def toggle_rule(request: Request):
    """启用或停用规则，不用打开编辑窗口。"""
    enabled = request.get("is_enabled", True)
    knowledge_service.toggle_rule(_rule_id(request), bool(enabled))
    return {"is_enabled": bool(enabled)}
