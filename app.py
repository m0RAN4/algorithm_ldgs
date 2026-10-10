"""
算法学习方向指导系统

markdown的README.md让我给删了，毕竟也没啥配置需求要说了，基础配置
如果后续上传github也许会添加，算了已经打算上传了，现在能这看到说明上传了，AI生成一份README.md了
当作基础说明
普通使用者特别是小白注意，你要是去当什么需要提交的东西就注意一下，令令令申申申申申，先配好数据库以及py环境再来运行，数据库是mysql，建表语句已经AI打包了
有文件的，别没搞配置说我乱给代码啊
————moRAN 2026.10.10
看完记得删

启动入口，vscode等编辑器配置好后可以直接运行app.py就行，直接能用完整版
下面是为了体现分块的，不用也没啥影响
python app.py                启动 Web 服务（知识源 = MySQL）
python app.py --source file  用内置文件知识库启动（无需数据库）
python app.py --check        只做自检，不启动服务
python app.py --port 8080    指定端口
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser

#把项目根目录加进搜索路径，这样下面才能import backend里的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

def _setup_console() -> None:
    """让 Windows 控制台能正常显示中文"""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

_setup_console()

BANNER = r"""
算法学习方向指导系统
Algorithm Learning Direction Guidance System
基于产生式规则的小型专家系统
"""

def check_database(verbose: bool = True) -> bool:
    """检查数据库是否可用，并给出可操作的中文提示"""
    #这两个import放在函数里面，是因为它们会把整个backend连带加载进来，
    #放模块顶层的话连--help都会变慢
    from backend.knowledge import connection
    from backend.knowledge.connection import DatabaseError

    try:
        ok, message = connection.ping()
    except DatabaseError as exc:
        ok, message = False, str(exc) #连不上的原因记下来

    if ok:
        if verbose:
            print("  [数据库] %s" % message)
        return True

    #连不上对应给用户的反馈
    if verbose:
        print("  [数据库] 连接失败：%s" % message)
        print()
        if not config.DB_CONFIG["password"]:
            print("  提示：当前数据库密码是空的，请先在 .env 里设置 LDGS_DB_PASSWORD")
            print()
        print("  请先完成建表，步骤：")
        print("    1. 把项目根目录的 .env.example 复制一份改名为 .env，")
        print("       填上 MySQL 的地址、用户名和密码")
        print("    2. 用 Navicat 等工具连接本机 MySQL（%s:%s，用户 %s）"
              % (config.DB_CONFIG["host"], config.DB_CONFIG["port"],
                 config.DB_CONFIG["user"]))
        print("    3. 先后执行项目 sql 目录下的两个脚本：")
        print("       01_schema.sql    建库建表（会清空同名旧表）")
        print("       02_init_data.sql 写入初始知识")
        print("    4. 确认数据库名称为 %s" % config.DB_CONFIG["database"])
        print()
        print("  如果暂时不想配数据库，可以先用内置知识库体验：")
        print("    python app.py --source file")
    return False

def run_self_check() -> int:
    """不启动服务，只验证知识库与推理机是否正常"""
    print(BANNER)
    print("自检模式")
    print("-" * 60)

    from backend.service import consult_service

    ok = True
    if config.KNOWLEDGE_SOURCE == "db":
        ok = check_database()
        if not ok:
            return 1 #数据库都不通，后面没法测
    else:
        print("  [数据库] 已跳过（知识源 = file）")

    #先看事实库有多少条
    catalog = consult_service.fact_catalog()
    inputs = sum(len(g["facts"]) for g in catalog["input_categories"])
    derived = sum(len(g["facts"]) for g in catalog["derived_categories"])
    print("  [事实库] 输入事实 %d 条，结论事实 %d 条" % (inputs, derived))

    #再看规则库
    repo = consult_service.get_repository()
    rules = repo.fetch_rules()
    print("  [规则库] 共 %d 条规则（启用 %d 条）"
          % (len(rules), sum(1 for r in rules if r.is_enabled)))

    #最后拿一组固定条件跑一遍推理，能出结果就说明整条链路是通的
    sample = ["level_intermediate", "base_programming", "ds_basic",
              "ds_tree_graph", "goal_interview", "math_strong", "time_plenty",
              "habit_practice"]
    result = consult_service.run_consultation(sample, persist=False)
    print("  [推理机] 示例推理触发 %d 轮，用时 %d ms"
          % (result["rounds"], result["duration_ms"]))
    print("  [推理结果]")
    for item in result["recommendations"]:
        print("      · %s" % item["name"])
    print("-" * 60)
    print("自检通过。" if ok else "自检未通过。")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(
        description="算法学习方向指导系统（产生式系统实验）")
    parser.add_argument("--source", choices=["db", "file"], default=None,
                        help="知识源：db=MySQL（默认） file=内置文件")
    parser.add_argument("--host", default=None, help="监听地址")
    parser.add_argument("--port", type=int, default=None, help="监听端口")
    parser.add_argument("--check", action="store_true", help="只自检不启动")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    #命令行里传了的就以命令行为准，覆盖配置里的默认值
    if args.source:
        config.KNOWLEDGE_SOURCE = args.source
    if args.host:
        config.SERVER_HOST = args.host
    if args.port:
        config.SERVER_PORT = args.port

    if args.check:
        return run_self_check()

    print(BANNER)
    print("启动前检查：")
    if config.KNOWLEDGE_SOURCE == "db":
        if not check_database():
            #数据库连不上就别硬启动，启动了用户打开页面也是一堆报错
            print()
            print("已中止启动。请先建表，或改用 --source file 体验。")
            return 1
    else:
        print("  [知识源] 内置文件知识库（不含数据库，规则仅可读）")

    from backend.server import create_server

    try:
        server = create_server()
    except OSError as exc:
        #最常见的原因是端口被上一个没关干净的进程占着
        print("  [服务] 启动失败：%s" % exc)
        print("  端口可能被占用，试试：python app.py --port 8080")
        return 1

    host, port = server.server_address[0], server.server_address[1]
    url = "http://%s:%d/" % (host, port)
    print()
    print("-" * 60)
    print("  服务已启动： %s" % url)
    print("  知识源：    %s" % config.KNOWLEDGE_SOURCE)
    print("  按 Ctrl+C 停止服务")
    print("-" * 60)

    if not args.no_browser:
        #等0.8秒再开浏览器，给服务留点启动时间。
        #用Timer不卡住主线程
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever() #一直跑着不返回，直到按下 Ctrl+C
    except KeyboardInterrupt:
        print("\n正在停止服务 ...")
    finally:
        #不管是怎么退出的，都得把端口还回去
        server.shutdown()
        server.server_close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
