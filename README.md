# 算法学习方向指导系统
AI生成的README.md文档，自行判断信息：
基于产生式规则（IF-THEN）的正向推理小型专家系统。用户在前端勾选自身情况，
系统通过「匹配 → 冲突消解 → 执行」的推理循环，推出适合的算法学习方向、
学习路线、所处学习阶段与学习建议。

后端只用 Python 标准库实现，没有第三方依赖；前端是原生 HTML/CSS/JS，无构建步骤。
知识库有 MySQL 与内置文件两种实现，推理机代码完全相同。

## 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.8 及以上（开发环境为 3.14） |
| MySQL | 8.0（仅在知识源选 `db` 时需要；5.7 见常见问题） |
| 第三方 Python 包 | 不需要 |
| 前端构建工具 | 不需要 |

## 运行步骤

### 1. 建库建表

按顺序执行 `sql` 目录下的两个脚本：

```bash
mysql -u root -p < sql/01_schema.sql
```

```bash
mysql -u root -p < sql/02_init_data.sql
```

- `01_schema.sql` —— 创建数据库 `algorithm_ldgs` 和 9 张表。脚本开头会先
  `DROP TABLE`，**重复执行会清空已有数据**。
- `02_init_data.sql` —— 写入初始知识。

### 2. 配置 .env

把 `.env.example` 复制一份改名为 `.env`：

```bash
copy .env.example .env
```

然后打开 `.env`，至少把数据库密码填上：

```ini
LDGS_DB_PASSWORD=你的MySQL密码
```

`.env` 是本地配置文件，已在 `.gitignore` 中排除。

### 3. 启动

```bash
python app.py
```

浏览器会自动打开 <http://127.0.0.1:8000/>，按 `Ctrl+C` 停止服务。

暂时不想配数据库，可以用内置知识库启动：

```bash
python app.py --source file
```

## 命令行参数

```bash
python app.py                启动 Web 服务（知识源 = MySQL，默认）
python app.py --source file  用内置文件知识库启动（无需数据库）
python app.py --check        只做自检，不启动服务
python app.py --port 8080    指定端口
python app.py --host 0.0.0.0 指定监听地址
python app.py --no-browser   不自动打开浏览器
```

`--check` 会验证数据库连通性、统计事实库与规则库规模，并跑一次完整推理，
不启动服务：

```bash
python app.py --source file --check
```

## 配置项

所有可调项都通过环境变量控制，名字统一以 `LDGS_` 开头。
优先级：系统环境变量 > `.env` 文件 > `config.py` 里的默认值。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LDGS_DB_HOST` | `127.0.0.1` | MySQL 地址 |
| `LDGS_DB_PORT` | `3306` | MySQL 端口 |
| `LDGS_DB_USER` | `root` | MySQL 用户 |
| `LDGS_DB_PASSWORD` | *（空）* | MySQL 密码，在 `.env` 里填 |
| `LDGS_DB_NAME` | `algorithm_ldgs` | 数据库名，需与建表脚本一致 |
| `LDGS_DB_TIMEOUT` | `8` | 连接超时（秒） |
| `LDGS_HOST` | `127.0.0.1` | HTTP 监听地址 |
| `LDGS_PORT` | `8000` | HTTP 监听端口 |
| `LDGS_MAX_ROUNDS` | `200` | 单次推理最大轮次 |
| `LDGS_KNOWLEDGE_SOURCE` | `db` | 知识源：`db` 或 `file` |

## 知识源的两种模式

| 模式 | 启动方式 | 数据来源 | 特点 |
| --- | --- | --- | --- |
| `db` | `python app.py` | MySQL 数据库 | 功能完整：规则可增删改查、咨询记录会入库 |
| `file` | `python app.py --source file` | `backend/knowledge/seed_data.py` | 免数据库；规则只读，咨询记录不落库 |

两种模式跑出的推理结果一致。

## 目录结构

```
algorithm_ldgs/
├── app.py            程序入口
├── config.py         配置项，支持 .env / 环境变量覆盖
├── .env.example      环境变量模板（复制成 .env 后填写）
├── backend/          后端
│   ├── api/          接口层
│   ├── service/      服务层
│   ├── inference/    推理机
│   └── knowledge/    知识库（MySQL / 文件两种实现）
├── frontend/         前端（index.html + css + js）
├── sql/              建表与初始数据脚本
└── tools/            开发工具
```

## 常见问题

**端口被占用**
换一个端口：`python app.py --port 8080`。

**提示「数据库连接失败」**
逐项检查：`.env` 里的密码有没有填、MySQL 服务有没有启动、`sql/` 下两个脚本
有没有按顺序执行过、`.env` 里的 `LDGS_DB_NAME` 是否与实际库名一致。
想先跳过数据库，用 `python app.py --source file`。

**规则库页面的编辑按钮是灰的**
说明当前是 `file` 知识源模式，内置文件知识库是只读的。
改用 `python app.py`（MySQL 模式）即可编辑。

**中文显示成乱码**
程序已在启动时把 Windows 控制台切到 UTF-8。若仍乱码，在命令前加 `chcp 65001`，
或把终端字体换成支持中文的等宽字体。

**执行脚本报 `Unknown collation: 'utf8mb4_0900_ai_ci'`**
建表脚本用的是 MySQL 8.0 的排序规则，5.7 不认识它。把 `sql/01_schema.sql` 里
出现的 `utf8mb4_0900_ai_ci` 全部替换成 `utf8mb4_general_ci` 再执行。
