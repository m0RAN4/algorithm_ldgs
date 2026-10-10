-- ============================================================================
--  算法学习方向指导系统 建库建表脚本
--  项目：算法学习方向指导系统（Algorithm Learning Direction Guidance System）
--  数据库：algorithm_ldgs      字符集：utf8mb4      排序规则：utf8mb4_0900_ai_ci
--  说明：本文件由 tools/export_sql.py 自动生成，请勿手工修改。
-- ============================================================================

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
