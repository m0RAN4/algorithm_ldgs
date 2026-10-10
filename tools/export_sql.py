"""
由 backend/knowledge/seed_data.py 生成建表和初始化的 SQL。

运行：python tools/export_sql.py

生成两个文件：
    sql/01_schema.sql        建库建表（会自动覆盖，重复执行会清空旧表）
    sql/02_init_data.sql     初始知识（事实、规则、算法主题）

这么做是因为知识内容得存两份：一份进数据库，一份给文件知识库用。
各写一遍太容易漏，所以让 seed_data.py 当唯一来源，SQL 由它生成。
"""
from __future__ import annotations

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def _setup_console():
    """让 Windows 控制台能正常显示中文。"""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_setup_console()

from backend.knowledge import seed_data # noqa: E402
from backend.knowledge.mysql_driver import escape # noqa: E402

DB_NAME = "algorithm_ldgs"
COLLATION = "utf8mb4_0900_ai_ci"

HEADER = """-- ============================================================================
--  {title}
--  项目：算法学习方向指导系统（Algorithm Learning Direction Guidance System）
--  数据库：{db}      字符集：utf8mb4      排序规则：{collation}
--  说明：本文件由 tools/export_sql.py 自动生成，请勿手工修改。
-- ============================================================================
"""

SCHEMA = """
CREATE DATABASE IF NOT EXISTS `algorithm_ldgs`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `algorithm_ldgs`;

-- 先关闭外键检查，便于重复执行本脚本
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `consult_trace`;
DROP TABLE IF EXISTS `consult_record_fact`;
DROP TABLE IF EXISTS `consult_record`;
DROP TABLE IF EXISTS `algorithm_topic`;
DROP TABLE IF EXISTS `rule_conclusion`;
DROP TABLE IF EXISTS `rule_condition`;
DROP TABLE IF EXISTS `rule`;
DROP TABLE IF EXISTS `fact`;
DROP TABLE IF EXISTS `fact_category`;

-- ---------------------------------------------------------------- 1. 事实类别
CREATE TABLE `fact_category` (
    `category_code` VARCHAR(32)  NOT NULL                COMMENT '类别编码',
    `category_name` VARCHAR(64)  NOT NULL                COMMENT '类别中文名称',
    `sort_order`    INT          NOT NULL DEFAULT 0      COMMENT '界面展示顺序',
    PRIMARY KEY (`category_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='事实类别字典表：给事实分类，界面按类别分组展示';

-- ---------------------------------------------------------------- 2. 事实字典
CREATE TABLE `fact` (
    `fact_id`       INT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT '事实主键',
    `fact_code`     VARCHAR(64)  NOT NULL                 COMMENT '事实编码，推理机内部使用的唯一标识',
    `fact_name`     VARCHAR(64)  NOT NULL                 COMMENT '事实中文名称',
    `category_code` VARCHAR(32)  NOT NULL                 COMMENT '所属类别，关联 fact_category',
    `fact_type`     ENUM('input','derived') NOT NULL DEFAULT 'input'
                                                          COMMENT 'input=用户勾选的输入事实；derived=推理推出的结论',
    `description`   VARCHAR(255) NOT NULL DEFAULT ''      COMMENT '事实说明',
    `sort_order`    INT          NOT NULL DEFAULT 0       COMMENT '同类别内展示顺序',
    `is_enabled`    TINYINT(1)   NOT NULL DEFAULT 1       COMMENT '1=启用；0=停用',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP        COMMENT '更新时间',
    PRIMARY KEY (`fact_id`),
    UNIQUE KEY `uk_fact_code` (`fact_code`),
    KEY `idx_fact_category` (`category_code`),
    KEY `idx_fact_type` (`fact_type`),
    CONSTRAINT `fk_fact_category` FOREIGN KEY (`category_code`)
        REFERENCES `fact_category` (`category_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='事实字典表：定义产生式系统综合数据库里允许出现的全部原子命题';

-- ---------------------------------------------------------------- 3. 规则主表
CREATE TABLE `rule` (
    `rule_id`     INT UNSIGNED NOT NULL AUTO_INCREMENT   COMMENT '规则主键',
    `rule_code`   VARCHAR(32)  NOT NULL                  COMMENT '规则编号，如 R001',
    `rule_name`   VARCHAR(64)  NOT NULL                  COMMENT '规则名称',
    `priority`    INT          NOT NULL DEFAULT 0        COMMENT '静态优先级，数值越大越优先（冲突消解第 1 级）',
    `description` VARCHAR(255) NOT NULL DEFAULT ''       COMMENT '规则说明',
    `is_enabled`  TINYINT(1)   NOT NULL DEFAULT 1        COMMENT '1=启用；0=停用（停用后不参与匹配）',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP        COMMENT '更新时间',
    PRIMARY KEY (`rule_id`),
    UNIQUE KEY `uk_rule_code` (`rule_code`),
    KEY `idx_rule_priority` (`priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='规则主表：一条产生式规则 IF <前件> THEN <后件>';

-- ---------------------------------------------------------------- 4. 规则前件
CREATE TABLE `rule_condition` (
    `condition_id` INT UNSIGNED NOT NULL AUTO_INCREMENT   COMMENT '前件主键',
    `rule_id`      INT UNSIGNED NOT NULL                  COMMENT '所属规则',
    `fact_code`    VARCHAR(64)  NOT NULL                  COMMENT '条件事实编码',
    `is_negate`    TINYINT(1)   NOT NULL DEFAULT 0        COMMENT '1=该条件取反（要求事实不存在）',
    `sort_order`   INT          NOT NULL DEFAULT 0        COMMENT '条件顺序',
    PRIMARY KEY (`condition_id`),
    UNIQUE KEY `uk_rule_condition` (`rule_id`, `fact_code`),
    KEY `idx_condition_fact` (`fact_code`),
    CONSTRAINT `fk_condition_rule` FOREIGN KEY (`rule_id`)
        REFERENCES `rule` (`rule_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_condition_fact` FOREIGN KEY (`fact_code`)
        REFERENCES `fact` (`fact_code`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='规则前件表：前件内多个条件之间是「合取」(AND) 关系';

-- ---------------------------------------------------------------- 5. 规则后件
CREATE TABLE `rule_conclusion` (
    `conclusion_id` INT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT '后件主键',
    `rule_id`       INT UNSIGNED NOT NULL                 COMMENT '所属规则',
    `fact_code`     VARCHAR(64)  NOT NULL                 COMMENT '结论事实编码',
    `sort_order`    INT          NOT NULL DEFAULT 0       COMMENT '结论顺序',
    PRIMARY KEY (`conclusion_id`),
    UNIQUE KEY `uk_rule_conclusion` (`rule_id`, `fact_code`),
    KEY `idx_conclusion_fact` (`fact_code`),
    CONSTRAINT `fk_conclusion_rule` FOREIGN KEY (`rule_id`)
        REFERENCES `rule` (`rule_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_conclusion_fact` FOREIGN KEY (`fact_code`)
        REFERENCES `fact` (`fact_code`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='规则后件表：后件内多个结论同时成立，都会加入综合数据库';

-- ---------------------------------------------------------------- 6. 算法主题
CREATE TABLE `algorithm_topic` (
    `topic_id`         INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主题主键',
    `topic_code`       VARCHAR(64)  NOT NULL                COMMENT '主题编码，与推荐类事实编码同名',
    `topic_name`       VARCHAR(64)  NOT NULL                COMMENT '主题名称',
    `difficulty`       VARCHAR(16)  NOT NULL DEFAULT ''     COMMENT '难度：入门/进阶/高级',
    `estimated_hours`  INT          NOT NULL DEFAULT 0      COMMENT '建议学时',
    `core_points`      VARCHAR(500) NOT NULL DEFAULT ''     COMMENT '核心考点',
    `learning_path`    VARCHAR(500) NOT NULL DEFAULT ''     COMMENT '学习路径建议',
    `typical_problems` VARCHAR(500) NOT NULL DEFAULT ''     COMMENT '典型题目',
    `sort_order`       INT          NOT NULL DEFAULT 0      COMMENT '展示顺序',
    PRIMARY KEY (`topic_id`),
    UNIQUE KEY `uk_topic_code` (`topic_code`),
    CONSTRAINT `fk_topic_fact` FOREIGN KEY (`topic_code`)
        REFERENCES `fact` (`fact_code`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='算法主题知识表：为「推荐学习」类结论补充难度、路径与典型题';

-- ---------------------------------------------------------------- 7. 咨询记录
CREATE TABLE `consult_record` (
    `record_id`        INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '记录主键',
    `session_no`       VARCHAR(32)  NULL                    COMMENT '会话编号，如 LDGS-0001，插入后由主键回填',
    `input_count`      INT          NOT NULL DEFAULT 0      COMMENT '输入事实条数',
    `conclusion_count` INT          NOT NULL DEFAULT 0      COMMENT '推出结论条数',
    `round_count`      INT          NOT NULL DEFAULT 0      COMMENT '推理轮次',
    `duration_ms`      INT          NOT NULL DEFAULT 0      COMMENT '推理耗时（毫秒）',
    `is_halted`        TINYINT(1)   NOT NULL DEFAULT 0      COMMENT '1=达到最大轮次被中止',
    `rules_loaded`     INT          NOT NULL DEFAULT 0      COMMENT '本次载入的规则条数',
    `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '咨询时间',
    PRIMARY KEY (`record_id`),
    UNIQUE KEY `uk_session_no` (`session_no`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='咨询记录主表：一次推理会话的汇总信息';

-- ---------------------------------------------------------------- 8. 记录事实明细
CREATE TABLE `consult_record_fact` (
    `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT   COMMENT '明细主键',
    `record_id`     INT UNSIGNED NOT NULL                  COMMENT '所属咨询记录',
    `fact_code`     VARCHAR(64)  NOT NULL                  COMMENT '事实编码',
    `fact_name`     VARCHAR(64)  NOT NULL                  COMMENT '事实名称快照',
    `category_code` VARCHAR(32)  NOT NULL DEFAULT ''       COMMENT '事实类别快照',
    `fact_role`     ENUM('input','derived') NOT NULL       COMMENT 'input=用户所选；derived=推理推出',
    `result_order`  INT          NOT NULL DEFAULT 0        COMMENT '结论的推导先后顺序（1 为最早推出）',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_record_fact` (`record_id`, `fact_code`, `fact_role`),
    KEY `idx_record_fact_code` (`fact_code`),
    CONSTRAINT `fk_record_fact_record` FOREIGN KEY (`record_id`)
        REFERENCES `consult_record` (`record_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='咨询记录事实明细表：归一化保存每次咨询的输入与结论，便于统计';

-- ---------------------------------------------------------------- 9. 推理轨迹
CREATE TABLE `consult_trace` (
    `trace_id`        INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '轨迹主键',
    `record_id`       INT UNSIGNED NOT NULL                COMMENT '所属咨询记录',
    `round_no`        INT          NOT NULL                COMMENT '第几轮推理',
    `rule_code`       VARCHAR(32)  NOT NULL                COMMENT '本轮选中执行的规则编号',
    `rule_name`       VARCHAR(64)  NOT NULL                COMMENT '规则名称快照',
    `priority`        INT          NOT NULL DEFAULT 0      COMMENT '执行时的优先级快照',
    `strategy`        VARCHAR(16)  NOT NULL DEFAULT ''     COMMENT '起决定作用的冲突消解策略',
    `resolution`      VARCHAR(255) NOT NULL DEFAULT ''     COMMENT '冲突消解说明',
    `matched_facts`   JSON         NULL                    COMMENT '被满足的前件事实编码',
    `derived_facts`   JSON         NULL                    COMMENT '本轮推出的结论事实编码',
    `candidate_count` INT          NOT NULL DEFAULT 0      COMMENT '本轮冲突集中的规则条数',
    `rejected`        JSON         NULL                    COMMENT '被淘汰的候选规则及原因',
    PRIMARY KEY (`trace_id`),
    UNIQUE KEY `uk_record_round` (`record_id`, `round_no`),
    CONSTRAINT `fk_trace_record` FOREIGN KEY (`record_id`)
        REFERENCES `consult_record` (`record_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='推理过程明细表：保存每一轮「匹配-冲突消解-执行」的结果，可完整还原推理链';

SET FOREIGN_KEY_CHECKS = 1;
"""


def build_init_data() -> str:
    """拼出初始知识那一段 SQL。

    每张表的 INSERT 都写成一条多值语句，比一行一条 INSERT 短很多。
    """
    lines = [
        "USE `algorithm_ldgs`;",
        "",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "",
        #先清空，这样脚本可以重复执行
        "TRUNCATE TABLE `consult_trace`;",
        "TRUNCATE TABLE `consult_record_fact`;",
        "TRUNCATE TABLE `consult_record`;",
        "TRUNCATE TABLE `algorithm_topic`;",
        "TRUNCATE TABLE `rule_conclusion`;",
        "TRUNCATE TABLE `rule_condition`;",
        "TRUNCATE TABLE `rule`;",
        "TRUNCATE TABLE `fact`;",
        "TRUNCATE TABLE `fact_category`;",
        "SET FOREIGN_KEY_CHECKS = 1;",
        "",
    ]

    #1 事实类别
    lines.append("-- ---------------------------------------------------------------- 1. 事实类别")
    rows = []
    for code, name, order in seed_data.CATEGORIES:
        rows.append("(%s, %s, %d)" % (escape(code), escape(name), order))
    lines.append("INSERT INTO `fact_category` (`category_code`, `category_name`, `sort_order`) VALUES")
    lines.append(",\n".join(rows) + ";")
    lines.append("")

    #2 事实字典
    lines.append("-- ---------------------------------------------------------------- 2. 事实字典")
    order_in_category = {} #同一类别里按出现顺序编排序号
    rows = []
    for code, name, category, fact_type, description in seed_data.FACTS:
        order_in_category[category] = order_in_category.get(category, 0) + 10
        rows.append("(%s, %s, %s, %s, %s, %d, 1)" % (
            escape(code), escape(name), escape(category), escape(fact_type),
            escape(description), order_in_category[category]))
    lines.append("INSERT INTO `fact` (`fact_code`, `fact_name`, `category_code`, "
                 "`fact_type`, `description`, `sort_order`, `is_enabled`) VALUES")
    lines.append(",\n".join(rows) + ";")
    lines.append("")

    #3 规则主表。rule_id 用列表下标，和 build_rules() 里保持一致
    lines.append("-- ---------------------------------------------------------------- 3. 规则主表")
    rows = []
    for index, (code, name, priority, _c, _k, desc) in enumerate(seed_data.RULES, start=1):
        rows.append("(%d, %s, %s, %d, %s, 1)" % (
            index, escape(code), escape(name), priority, escape(desc)))
    lines.append("INSERT INTO `rule` (`rule_id`, `rule_code`, `rule_name`, "
                 "`priority`, `description`, `is_enabled`) VALUES")
    lines.append(",\n".join(rows) + ";")
    lines.append("")

    #4 规则前件。一条规则有几个条件就出几行
    lines.append("-- ---------------------------------------------------------------- 4. 规则前件（IF 部分）")
    rows = []
    for index, (_code, _name, _p, conditions, _k, _d) in enumerate(seed_data.RULES, start=1):
        for order, (fact_code, negate) in enumerate(conditions, start=1):
            #negate 是 Python 的 True/False，插库要转成 1/0
            rows.append("(%d, %s, %d, %d)" % (
                index, escape(fact_code), 1 if negate else 0, order * 10))
    lines.append("INSERT INTO `rule_condition` (`rule_id`, `fact_code`, "
                 "`is_negate`, `sort_order`) VALUES")
    lines.append(",\n".join(rows) + ";")
    lines.append("")

    #5 规则后件
    lines.append("-- ---------------------------------------------------------------- 5. 规则后件（THEN 部分）")
    rows = []
    for index, (_code, _name, _p, _c, conclusions, _d) in enumerate(seed_data.RULES, start=1):
        for order, fact_code in enumerate(conclusions, start=1):
            rows.append("(%d, %s, %d)" % (index, escape(fact_code), order * 10))
    lines.append("INSERT INTO `rule_conclusion` (`rule_id`, `fact_code`, `sort_order`) VALUES")
    lines.append(",\n".join(rows) + ";")
    lines.append("")

    #6 算法主题
    lines.append("-- ---------------------------------------------------------------- 6. 算法主题知识")
    rows = []
    for index, (code, name, diff, hours, points, path, problems) in enumerate(
            seed_data.TOPICS, start=1):
        rows.append("(%s, %s, %s, %d, %s, %s, %s, %d)" % (
            escape(code), escape(name), escape(diff), hours,
            escape(points), escape(path), escape(problems), index * 10))
    lines.append("INSERT INTO `algorithm_topic` (`topic_code`, `topic_name`, `difficulty`, "
                 "`estimated_hours`, `core_points`, `learning_path`, `typical_problems`, "
                 "`sort_order`) VALUES")
    lines.append(",\n".join(rows) + ";")
    lines.append("")
    return "\n".join(lines)


def write(path: str, content: str) -> None:
    """写文件，顺便打印一下写了多少。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    #统一用 \n，免得在 Windows 上生成出 \r\n，粘贴到别处多出怪字符
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    print("  已生成 %s（%d 字符）" % (os.path.relpath(path, BASE), len(content)))


def main() -> int:
    print("正在由 seed_data.py 生成 SQL ...")
    #两段 SQL 都套上文件头
    schema = HEADER.format(title="算法学习方向指导系统 建库建表脚本", db=DB_NAME,
                           collation=COLLATION) + SCHEMA
    init_data = HEADER.format(title="算法学习方向指导系统 初始知识数据", db=DB_NAME,
                              collation=COLLATION) + "\n" + build_init_data()

    write(os.path.join(BASE, "sql", "01_schema.sql"), schema)
    write(os.path.join(BASE, "sql", "02_init_data.sql"), init_data)

    #统计一下条数，运行结束时打印，方便核对
    fact_count = len(seed_data.FACTS)
    rule_count = len(seed_data.RULES)
    condition_count = sum(len(r[3]) for r in seed_data.RULES)
    conclusion_count = sum(len(r[4]) for r in seed_data.RULES)
    topic_count = len(seed_data.TOPICS)

    print("\n完成。统计：")
    print("  事实 %d 条 / 规则 %d 条 / 前件 %d 项 / 后件 %d 项 / 主题 %d 个"
          % (fact_count, rule_count, condition_count, conclusion_count, topic_count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
