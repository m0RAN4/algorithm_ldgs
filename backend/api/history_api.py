"""咨询记录和统计的接口。"""
from __future__ import annotations

from ..service import knowledge_service
from . import ApiError, Request, route


def _record_id(request: Request) -> int:
    """从路径里取记录 id。"""
    raw = request.params.get("record_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ApiError("记录 ID 不合法：%s" % raw)


@route("GET", "/api/consults")
def list_consults(request: Request):
    """历史记录列表。limit 限制在 1 到 500 之间，防止一次拉太多。"""
    limit = request.arg("limit", "50")
    try:
        limit = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        limit = 50 #传了不是数字的东西就用默认值
    return {"records": knowledge_service.list_consults(limit)}


@route("GET", "/api/consults/{record_id}")
def get_consult(request: Request):
    """一条记录的详情，带完整推理轨迹。"""
    return knowledge_service.get_consult(_record_id(request))


@route("DELETE", "/api/consults/{record_id}")
def delete_consult(request: Request):
    knowledge_service.delete_consult(_record_id(request))
    return {"deleted": True}


@route("GET", "/api/stats")
def stats(_request: Request):
    return knowledge_service.statistics()
