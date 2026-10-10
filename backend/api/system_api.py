"""系统自检和架构说明的接口。"""
from __future__ import annotations

import config

from ..knowledge import connection
from . import Request, route

#概览页要展示的代码结构说明，直接写死在这里
ARCHITECTURE = {
    "inference_engine": {
        "package": "backend/inference",
        "files": ["engine.py 正向推理机", "matcher.py 匹配",
                  "conflict.py 冲突消解", "models.py 数据结构",
                  "provider.py 知识库接口"],
        "depends_on": "只依赖 backend/inference 内部的接口与数据结构",
        "forbidden": "不 import backend.knowledge，不写 SQL，不读文件",
    },
    "knowledge_base": {
        "package": "backend/knowledge",
        "files": ["repository.py MySQL 仓储", "file_repository.py 文件仓储",
                  "seed_data.py 知识内容", "mysql_driver.py 数据库驱动",
                  "connection.py 连接管理"],
        "depends_on": "只依赖 backend/inference/models 里的数据结构定义",
    },
    "composition_root": {
        "package": "backend/service",
        "files": ["consult_service.py 组装推理机与知识库",
                  "knowledge_service.py 知识库管理"],
        "depends_on": "同时依赖推理机与知识库，是唯一的组装点",
    },
}


@route("GET", "/api/health")
def health(_request: Request):
    """探活接口，页面右上角那个状态灯就是调它。"""
    if config.KNOWLEDGE_SOURCE == "file":
        #文件模式压根没连数据库，不用去 ping
        db_ok, db_message = False, "当前知识源为 file（文件），未连接数据库"
    else:
        db_ok, db_message = connection.ping()
    return {
        "server": "ok",
        "database": {"ok": db_ok, "message": db_message},
        "knowledge_source": config.KNOWLEDGE_SOURCE,
        "max_inference_rounds": config.MAX_INFERENCE_ROUNDS,
    }


@route("GET", "/api/architecture")
def architecture(_request: Request):
    return ARCHITECTURE
