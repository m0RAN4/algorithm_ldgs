"""HTTP 服务器：既发页面也提供 JSON 接口。

用的是标准库的 http.server，没装 Flask 之类的框架。
"""
from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config

from .api import dispatch, load_api_modules

_STATIC_LOCK = threading.Lock()
_MAX_BODY = 2 * 1024 * 1024 #请求体最大 2MB，超了直接拒掉
_LOG_ENABLED = True

#Windows 上 mimetypes 会去查注册表，.js 有时被认成 text/plain，
#浏览器加载 ES Module 时对类型要求很严，认错了就直接不执行，所以这里写死
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "AlgorithmLDGS/1.0"
    protocol_version = "HTTP/1.1"

    #一些公共的小工具

    def log_message(self, fmt, *args): # noqa: A003
        #默认的日志格式不好看，改成简单的
        if _LOG_ENABLED:
            print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _send(self, status: int, body: bytes, content_type: str,
              extra_headers=None):
        """发一个响应出去，头和数据一起写。"""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        #开发阶段别让浏览器缓存，改完刷新就是最新的
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD": #HEAD 请求只要头，不发正文
            self.wfile.write(body)

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False,
                          default=str).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _read_body(self):
        """把请求体读出来，JSON 和表单两种都认。"""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0:
            return None #没有请求体
        if length > _MAX_BODY:
            return {"__error__": "请求体过大"}
        raw = self.rfile.read(length)
        content_type = (self.headers.get("Content-Type") or "").lower()
        text = raw.decode("utf-8", "replace")
        #按类型判断，看不出来就靠内容开头是不是 { 或 [ 猜一下
        if "application/json" in content_type or text.lstrip().startswith(("{", "[")):
            try:
                return json.loads(text)
            except ValueError:
                return {"__error__": "JSON 解析失败"}
        #不是 JSON 就按表单解析
        return {k: v[0] for k, v in urllib.parse.parse_qs(text).items()}

    #请求分发

    def _handle(self, method: str):
        """所有请求都先到这里，再分给 API 或者静态文件。"""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path) #路径里的中文要解码
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/"):
            body = self._read_body()
            if isinstance(body, dict) and "__error__" in body:
                self._send_json(400, {"ok": False, "error": body["__error__"]})
                return
            try:
                status, payload = dispatch(method, path, query, body)
            except Exception as exc:
                #最后的兜底，保证出什么错都能给前端一个 JSON 回复
                status = 500
                payload = {"ok": False,
                           "error": "%s: %s" % (type(exc).__name__, exc)}
            self._send_json(status, payload)
            return

        self._serve_static(path) #不是接口就走静态文件

    def do_GET(self):        self._handle("GET")
    def do_HEAD(self):       self._handle("GET")
    def do_POST(self):       self._handle("POST")
    def do_PUT(self):        self._handle("PUT")
    def do_DELETE(self):     self._handle("DELETE")

    #静态文件

    def _serve_static(self, path: str):
        """把 frontend 目录下的文件发出去。"""
        if path in ("/", ""):
            path = "/index.html" #根路径默认给首页

        #只允许访问 frontend 里面的文件。不检查的话，
        #请求 /../../C:/Windows/xxx 就能把系统文件读走
        relative = posixpath.normpath(path).lstrip("/")
        if relative.startswith("..") or os.path.isabs(relative):
            self._send(403, b"403 Forbidden", "text/plain; charset=utf-8")
            return

        #再确认一次：拼出来的真实路径必须还在 frontend 目录里
        root = os.path.abspath(config.FRONTEND_DIR)
        target = os.path.abspath(os.path.join(root, relative))
        if not target.startswith(root + os.sep) and target != root:
            self._send(403, b"403 Forbidden", "text/plain; charset=utf-8")
            return
        if not os.path.isfile(target):
            self._send(404, "404 Not Found".encode("utf-8"),
                       "text/plain; charset=utf-8")
            return

        #先查写死的类型表，查不到再问 mimetypes
        extension = os.path.splitext(target)[1].lower()
        content_type = _MIME.get(extension)
        if content_type is None:
            content_type, _encoding = mimetypes.guess_type(target)
        if content_type is None:
            content_type = "application/octet-stream" #实在认不出就当二进制
        if content_type.startswith("text/") and "charset" not in content_type:
            content_type += "; charset=utf-8"

        with _STATIC_LOCK:
            with open(target, "rb") as handle:
                body = handle.read()
        self._send(200, body, content_type)


def create_server(host: str = None, port: int = None) -> ThreadingHTTPServer:
    """建好服务器对象，还没开始监听。"""
    load_api_modules() #这一刻才把各个接口注册进来
    host = host or config.SERVER_HOST
    port = port or config.SERVER_PORT
    #用多线程版，一个请求卡住不影响别的
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True #主线程退出时工作线程跟着退
    return server
