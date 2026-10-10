#配置：数据库、端口、最大轮次、知识源
#
#所有可调项都能用环境变量覆盖，名字统一以 LDGS_ 开头。
#推荐做法：把项目根目录的 .env.example 复制成 .env 再填写。
#.env 已被 .gitignore 排除，密码不会被提交到仓库。
from __future__ import annotations
import os

#路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str) -> None:
    """把 .env 里的 KEY=VALUE 读进环境变量。

    启动时读一次就够了。已经存在的环境变量不会被文件覆盖，所以命令行里
    临时指定的值依然管用。只用标准库实现，不装 python-dotenv 之类的包。
    """
    if not os.path.isfile(path):
        return #没有 .env 就全部走默认值，很正常
    try:
        #用 utf-8-sig，这样用记事本另存为带 BOM 的文件也能正确解析
        with open(path, "r", encoding="utf-8-sig") as handle:
            lines = handle.readlines()
    except OSError:
        return #读不了就当没有这个文件，不要因为一个配置文件让程序起不来

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue #空行和注释行跳过
        if line.lower().startswith("export "):
            line = line[7:].lstrip() #顺手兼容 shell 写法：export KEY=VALUE

        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not key:
            continue

        if value[:1] in ("'", '"'):
            #加了引号：引号里的内容整个都是值，里面的 # 不算注释
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            #没加引号：# 后面的当注释丢掉
            value = value.split("#", 1)[0].strip()

        if key not in os.environ: #已有的环境变量优先，不覆盖
            os.environ[key] = value


_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _env_int(name: str, default: str) -> int:
    """读整数配置。写错了给一句能看懂的中文提示，而不是抛 ValueError。"""
    raw = os.environ.get(name, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise SystemExit("配置项 %s 需要是整数，当前值是 %r，"
                         "请检查 .env 或系统环境变量。" % (name, raw))


def _env_float(name: str, default: str) -> float:
    """读浮点配置，同上。"""
    raw = os.environ.get(name, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise SystemExit("配置项 %s 需要是数字，当前值是 %r，"
                         "请检查 .env 或系统环境变量。" % (name, raw))


#数据库
DB_CONFIG = {
    "host": os.environ.get("LDGS_DB_HOST", "127.0.0.1"),
    "port": _env_int("LDGS_DB_PORT", "3306"),
    "user": os.environ.get("LDGS_DB_USER", "root"),
    #密码故意不给默认值。填在 .env（已忽略）或系统环境变量里，
    #免得真实密码跟着代码一起提交出去
    "password": os.environ.get("LDGS_DB_PASSWORD", ""),
    "database": os.environ.get("LDGS_DB_NAME", "algorithm_ldgs"),
    "charset": "utf8mb4",
    # 连接超时（秒）
    "timeout": _env_float("LDGS_DB_TIMEOUT", "8"),
}

#HTTP服务
SERVER_HOST = os.environ.get("LDGS_HOST", "127.0.0.1")
SERVER_PORT = _env_int("LDGS_PORT", "8000")

#推理机
#单次推理的最大轮次
MAX_INFERENCE_ROUNDS = _env_int("LDGS_MAX_ROUNDS", "200")

#知识来源：db = 从数据库读取（默认）；file = 从内置知识文件读取。
#两种实现提供完全相同的接口，推理机代码不需要任何改动。
KNOWLEDGE_SOURCE = os.environ.get("LDGS_KNOWLEDGE_SOURCE", "db")

#路径
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
SQL_DIR = os.path.join(BASE_DIR, "sql")
