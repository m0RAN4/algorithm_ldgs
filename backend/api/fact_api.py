"""事实字典管理接口。"""
from __future__ import annotations

from ..service import knowledge_service
from . import ApiError, Request, route


def _fact_id(request: Request) -> int:
    """从路径里取事实 id。"""
    raw = request.params.get("fact_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ApiError("事实 ID 不合法：%s" % raw)


@route("GET", "/api/facts")
def list_facts(request: Request):
    """事实列表，可以按 input/derived 筛。"""
    fact_type = request.arg("fact_type")
    rows = knowledge_service.list_facts()
    if fact_type:
        rows = [r for r in rows if r["fact_type"] == fact_type]
    return {
        "total": len(rows),
        "facts": rows,
        "categories": knowledge_service.list_categories(), #编辑事实时选类别用
    }


@route("POST", "/api/facts")
def create_fact(request: Request):
    return {"fact_id": knowledge_service.create_fact(request.body)}


@route("PUT", "/api/facts/{fact_id}")
def update_fact(request: Request):
    knowledge_service.update_fact(_fact_id(request), request.body)
    return {"updated": True}


@route("DELETE", "/api/facts/{fact_id}")
def delete_fact(request: Request):
    knowledge_service.delete_fact(_fact_id(request))
    return {"deleted": True}


@route("GET", "/api/topics")
def list_topics(_request: Request):
    return {"topics": knowledge_service.list_topics()}
