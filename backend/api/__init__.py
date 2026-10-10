"""很简单的路由框架，只用标准库。

各个 api 模块用 @route 装饰器把函数注册成接口，server.py 收到请求后
交给 dispatch 分发。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ..service.knowledge_service import ValidationError


class ApiError(Exception):
    """能直接返回给前端的业务错误，消息会原样显示。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


class Request:
    """一次请求的封装，把参数都整理好方便取。"""

    def __init__(self, method: str, path: str, query: Dict[str, List[str]],
                 body: Any, params: Dict[str, str]):
        self.method = method
        self.path = path
        self.query = query
        self.body = body if isinstance(body, dict) else {}
        self.raw_body = body
        self.params = params #从路径里提出来的参数，比如 {rule_id: "3"}

    def arg(self, name: str, default=None):
        """取地址栏上的查询参数。"""
        values = self.query.get(name)
        return values[0] if values else default #同一个参数传了多次只取第一个

    def get(self, name: str, default=None):
        """先看请求体里有没有，没有再去查询参数里找。"""
        if name in self.body:
            return self.body[name]
        return self.arg(name, default)

    def required(self, name: str):
        """必填参数，缺了就报错。"""
        value = self.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ApiError("缺少必填参数：%s" % name)
        return value


#所有注册进来的路由，元素是 (方法, 路径模板, 处理函数)
_ROUTES: List[tuple] = []
#编译好的正则缓存，同一个模板不用反复编译
_PATTERN_CACHE: Dict[str, re.Pattern] = {}


def route(method: str, pattern: str):
    """装饰器，把一个函数注册成接口。

    pattern 里的 {名字} 表示路径参数，比如 /api/rules/{rule_id}。
    """

    def decorator(func):
        _ROUTES.append((method.upper(), pattern, func))
        return func

    return decorator


def _compile(pattern: str) -> re.Pattern:
    """把 /api/rules/{rule_id} 这种模板编译成正则。"""
    if pattern not in _PATTERN_CACHE:
        #把 {rule_id} 换成(?P<rule_id>[^/]+)，也就是"斜杠以外的任意字符"
        regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern)
        _PATTERN_CACHE[pattern] = re.compile("^" + regex + "$")
    return _PATTERN_CACHE[pattern]


def _resolve(method: str, path: str):
    """找到匹配的处理函数，顺便把路径参数取出来。"""
    for route_method, pattern, func in _ROUTES:
        if route_method != method:
            continue
        match = _compile(pattern).match(path)
        if match:
            return func, match.groupdict()
    return None, None


def dispatch(method: str, path: str, query: Dict[str, List[str]], body: Any):
    """执行请求，返回 (HTTP 状态码, 响应体字典)。"""
    func, params = _resolve(method, path)
    if func is None:
        return 404, {"ok": False, "error": "接口不存在：%s %s" % (method, path)}

    request = Request(method, path, query, body, params)
    try:
        result = func(request)
    except ValidationError as exc:
        #校验不通过，是用户填错了，400
        return 400, {"ok": False, "error": str(exc)}
    except ApiError as exc:
        return exc.status, {"ok": False, "error": exc.message}
    except Exception as exc:
        #兜底。不接住的话异常会冒到 server 那边，连接可能直接被掐断，
        #前端就只能看到"网络错误"，看不出真正的原因
        return 500, {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    #处理函数可以自己返回 (状态码, 内容)，不然就按 200 处理
    if isinstance(result, tuple):
        status, payload = result
        return status, payload
    return 200, {"ok": True, "data": result}


def load_api_modules() -> None:
    """把各个 api 模块导进来，导入的时候装饰器就完成注册了。"""
    from . import (consult_api, fact_api, history_api, # noqa: F401
                   rule_api, system_api)
