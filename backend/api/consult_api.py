"""推理咨询相关的接口。"""
from __future__ import annotations

import config

from ..service import consult_service
from . import ApiError, Request, route


@route("POST", "/api/consult")
def run_consult(request: Request):
    """跑一次推理。

    请求体是这样的：{"fact_codes": ["level_beginner", "goal_interview"]}
    """
    codes = request.get("fact_codes")
    #参数先检查一遍，别把乱七八糟的东西丢给推理机
    if codes is None:
        raise ApiError("请求体缺少 fact_codes 字段")
    if not isinstance(codes, list):
        raise ApiError("fact_codes 必须是数组")
    #去掉空白和空字符串
    codes = [str(c).strip() for c in codes if str(c).strip()]
    if not codes:
        raise ApiError("请至少选择一项条件")
    if len(codes) > 100:
        raise ApiError("一次最多选择 100 项条件")

    #自检的时候不想往库里写记录，就传 persist=false
    persist = bool(request.get("persist", True))
    return consult_service.run_consultation(codes, persist=persist)


@route("GET", "/api/catalog")
def catalog(_request: Request):
    """事实目录，按类别分好组给前端渲染勾选框用。"""
    data = consult_service.fact_catalog()
    data["knowledge_source"] = config.KNOWLEDGE_SOURCE #前端要显示当前是哪种模式
    return data
