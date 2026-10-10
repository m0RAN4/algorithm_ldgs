"""
数据库连接管理。
HTTP 服务是多线程的，一条 MySQL 连接不能同时给几个线程用，包序号会乱。
所以这里每次操作都新建一条连接，用完就关，简单也不会出问题，
本地数据库建连接的开销可以忽略。
"""
from __future__ import annotations

import contextlib

import config

from .mysql_driver import MySQLConnection, MySQLError


class DatabaseError(Exception):
    """把底层驱动的异常包一层，上层就不用管具体是哪个驱动了。"""


def connect(database: str = None) -> MySQLConnection:
    """建一条新连接。database 传 None 表示不指定库。"""
    cfg = dict(config.DB_CONFIG)
    if database is not None:
        cfg["database"] = database
    try:
        return MySQLConnection(
            host=cfg["host"], port=cfg["port"], user=cfg["user"],
            password=cfg["password"], database=cfg["database"],
            charset=cfg["charset"], timeout=cfg["timeout"])
    except MySQLError as exc:
        raise DatabaseError(str(exc)) from exc


@contextlib.contextmanager
def connection(database: str = None):
    """配合 with 用，出了代码块自动关连接。"""
    conn = connect(database)
    try:
        yield conn
    finally:
        conn.close()


def query_all(sql: str, params=None):
    """查一批数据回来，返回字典列表，键是列名。"""
    with connection() as conn:
        try:
            columns, rows = conn.query(sql, params)
        except MySQLError as exc:
            raise DatabaseError(str(exc)) from exc
    #把列名和每一行配起来，变成字典
    return [dict(zip(columns, row)) for row in rows]


def query_one(sql: str, params=None):
    """只取第一行，没有就返回 None。"""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params=None):
    """执行增删改，返回 (影响了几行, 自增主键)。"""
    with connection() as conn:
        try:
            conn.query(sql, params)
            #这两个函数得在同一条连接上查才有效
            _cols, rows = conn.query("SELECT ROW_COUNT(), LAST_INSERT_ID()")
        except MySQLError as exc:
            raise DatabaseError(str(exc)) from exc
    affected, last_id = rows[0]
    return int(affected), int(last_id)


def execute_many(statements):
    """在同一个事务里按顺序执行多条语句。

    中间任何一步出错就整体回滚，不会留下半条数据。写规则和写咨询记录都用它，
    免得出现"规则写进去了但条件没写进去"这种情况。
    """
    with connection() as conn:
        try:
            conn.query("START TRANSACTION")
            try:
                for sql, params in statements:
                    conn.query(sql, params)
            except Exception:
                conn.query("ROLLBACK") #出错了先回滚
                raise
            conn.query("COMMIT") #全部成功才提交
        except MySQLError as exc:
            raise DatabaseError(str(exc)) from exc


def ping() -> tuple:
    """自检用，返回 (通不通, 说明文字)。"""
    try:
        with connection() as conn:
            _cols, rows = conn.query("SELECT VERSION(), DATABASE()")
        version, dbname = rows[0]
        return True, "已连接 MySQL %s，当前数据库 %s" % (version, dbname)
    except (MySQLError, DatabaseError) as exc:
        return False, str(exc)
