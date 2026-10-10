"""
AI写的检查工具，目的是核对用户建表对不对，和设定一不一样
静态检查：把后端代码里所有SQL用到的表和字段，跟建表脚本对一遍
不连数据库也不建库，纯粹是文本比对。好处是在还没建表的时候就能发现
"代码里查了一个表里没有的字段"这种问题，不用等到跑起来才报错。
"""
from __future__ import annotations

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#让 Windows 控制台能正常显示中文
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

#从建表脚本里解析出表结构

def parse_schema(path):
    """把 01_schema.sql 解析成 {表名: {字段名, ...}}。"""
    text = open(path, encoding="utf-8").read()
    #先把 SQL 注释去掉，免得注释里的内容干扰匹配
    text = re.sub(r"--[^\n]*", "", text)
    tables = {}
    #一条 CREATE TABLE 从 "CREATE TABLE `x` (" 到 "\n) ENGINE" 结束
    for match in re.finditer(
            r"CREATE TABLE `(\w+)`\s*\((.*?)\n\)\s*ENGINE", text, re.S):
        name, body = match.group(1), match.group(2)
        columns = set()
        for line in body.split("\n"):
            line = line.strip().rstrip(",") #去掉行尾的逗号
            #字段定义是 `字段名` 类型 的形式。索引和约束行不以反引号开头，
            #所以匹配不上，正好跳过
            col = re.match(r"`(\w+)`\s+(?:INT|VARCHAR|DATETIME|TINYINT|ENUM|JSON|TEXT|BIGINT|DATE|TIMESTAMP)",
                           line, re.I)
            if col:
                columns.add(col.group(1))
        tables[name] = columns
    return tables

#把后端代码里的 SQL 抠出来

#匹配 query_all(...) / execute(...) 这类调用，后面跟的是一串字符串拼接
SQL_CALL = re.compile(
    r'(?:query_all|query_one|execute|conn\.query)\(\s*'
    r'((?:"[^"]*"\s*)+)', re.S)


def strip_python_concat(chunk):
    """把多行字符串拼起来的那段还原成一条完整 SQL。"""
    parts = re.findall(r'"([^"]*)"', chunk)
    return "".join(parts)


def collect_sql_files(root):
    """遍历目录下所有 .py 文件。"""
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def check():
    tables = parse_schema(os.path.join(BASE, "sql", "01_schema.sql"))
    if not tables:
        print("!! 没有从 01_schema.sql 解析到任何表")
        return 1

    #先把解析出来的表结构列一遍，方便肉眼扫一下
    print("Schema 共 %d 张表：" % len(tables))
    for name in sorted(tables):
        print("  %-20s %2d 列  %s" % (name, len(tables[name]),
                                      ", ".join(sorted(tables[name]))))
    print()

    problems = []
    checked = 0

    for path in collect_sql_files(os.path.join(BASE, "backend")):
        text = open(path, encoding="utf-8").read()
        for match in SQL_CALL.finditer(text):
            sql = strip_python_concat(match.group(1))
            if not sql.strip():
                continue
            checked += 1
            rel = os.path.relpath(path, BASE)
            #算一下这条 SQL 在源文件里的行号，报错时好定位
            line = text[:match.start()].count("\n") + 1

            #检查一：INSERT INTO 表 (字段...) 里的字段
            for ins in re.finditer(r"INSERT INTO\s+(\w+)\s*\(([^)]*)\)", sql, re.I):
                table, cols = ins.group(1), ins.group(2)
                if table not in tables:
                    problems.append("%s:%d INSERT 到未知表 %s" % (rel, line, table))
                    continue
                for col in [c.strip().strip("`") for c in cols.split(",")]:
                    if col and col not in tables[table]:
                        problems.append("%s:%d INSERT %s 表无字段 %s"
                                        % (rel, line, table, col))

            #检查二：FROM / JOIN 后面跟的表名存不存在
            for ref in re.finditer(r"(?:FROM|JOIN)\s+(\w+)", sql, re.I):
                table = ref.group(1)
                if table not in tables:
                    problems.append("%s:%d 引用未知表 %s" % (rel, line, table))

            #检查三：别名.字段 这种写法。先收集这一句里有哪些别名
            aliases = {}
            for alias_match in re.finditer(
                    r"(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?", sql, re.I):
                table, alias = alias_match.group(1), alias_match.group(2)
                #下面这些词是 SQL 关键字，跟在表名后面的可能是它们而不是别名
                if table in tables and alias and alias.lower() not in (
                        "where", "order", "group", "on", "left", "inner", "join",
                        "having", "limit", "and", "or", "set"):
                    aliases[alias] = table
            #表名本身也能当别名用，比如 fact.fact_code 这种写法
            aliases.update({t: t for t in tables})
            for use in re.finditer(r"\b(\w+)\.(\w+)\b", sql):
                alias, col = use.group(1), use.group(2)
                if alias in aliases and col not in aliases[alias]:
                    problems.append("%s:%d %s.%s 不存在（表 %s）"
                                    % (rel, line, alias, col, aliases[alias]))

            #检查四：UPDATE 表 SET 字段 = ... 里的字段
            for upd in re.finditer(r"UPDATE\s+(\w+)\s+SET\s+(.*?)(?:WHERE|$)",
                                   sql, re.I | re.S):
                table, body = upd.group(1), upd.group(2)
                if table not in tables:
                    problems.append("%s:%d UPDATE 未知表 %s" % (rel, line, table))
                    continue
                for col in re.finditer(r"(\w+)\s*=", body):
                    name = col.group(1)
                    if name.lower() in ("where", "and", "or"):
                        continue #这几个是关键字，不是字段
                    if name not in tables[table]:
                        problems.append("%s:%d UPDATE %s 表无字段 %s"
                                        % (rel, line, table, name))

    print("共检查 %d 条 SQL 语句。" % checked)
    if problems:
        print("\n发现 %d 处问题：" % len(problems))
        for item in sorted(set(problems)): #去重后排序，报错好看一点
            print("  ✗", item)
        return 1
    print("未发现表名/字段名不一致。")
    return 0


if __name__ == "__main__":
    sys.exit(check())
