"""知识库的初始内容，也是这里唯一的数据来源。

这个文件用纯数据描述"算法学习方向指导系统"的全部事实、规则和算法主题。
tools/export_sql.py 根据它生成 sql/ 下的建表和初始化脚本，file_repository.py
也直接读它，所以数据库里的知识和文件里的知识永远是一样的。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ..inference.models import (FACT_TYPE_DERIVED, FACT_TYPE_INPUT, Condition,
                                Fact, Rule)

#事实类别
CATEGORIES: List[Tuple[str, str, int]] = [
    ("base", "基础条件", 10),
    ("math", "数学基础", 20),
    ("ds", "数据结构基础", 30),
    ("goal", "学习目标", 40),
    ("interest", "兴趣方向", 50),
    ("time", "时间投入", 60),
    ("level", "当前水平", 70),
    ("habit", "学习习惯", 80),
    ("stage", "学习阶段", 110),
    ("route", "学习路线", 120),
    ("rec", "算法推荐", 130),
    ("advice", "学习建议", 140),
]

#事实字典
# (事实编码, 事实名称, 类别, 类型, 说明)

_I, _D = FACT_TYPE_INPUT, FACT_TYPE_DERIVED

FACTS: List[Tuple[str, str, str, str, str]] = [
    #基础条件
    ("base_programming", "有编程基础", "base", _I,
     "至少熟练掌握一门编程语言（C/C++/Java/Python 等）"),

    #数学基础
    ("math_strong", "数学基础扎实", "math", _I,
     "能看懂公式推导，不排斥数学"),
    ("math_weak", "数学基础薄弱", "math", _I,
     "对公式推导感到吃力，希望尽量少碰复杂数学"),

    #数据结构基础
    ("ds_basic", "已掌握数组/链表/栈/队列", "ds", _I,
     "能熟练使用最基本的线性数据结构"),
    ("ds_tree_graph", "已掌握树与图的基本概念", "ds", _I,
     "理解二叉树、图的存储与遍历"),

    #学习目标
    ("goal_interview", "准备求职面试", "goal", _I,
     "目标是互联网公司技术岗的笔试与面试"),
    ("goal_contest", "准备算法竞赛", "goal", _I,
     "目标是 ACM/ICPC、蓝桥杯、天梯赛等赛事"),
    ("goal_exam", "准备考研或课程考试", "goal", _I,
     "目标是研究生入学考试或校内课程考核"),
    ("goal_project", "提升工程开发能力", "goal", _I,
     "希望把算法真正用到日常开发中"),
    ("goal_research", "想做科研或算法工程", "goal", _I,
     "目标是读研、读博或从事算法研究类岗位"),

    #兴趣方向
    ("interest_ai", "对人工智能感兴趣", "interest", _I, "关注机器学习、深度学习方向"),
    ("interest_graphics", "对图形学/游戏感兴趣", "interest", _I,
     "关注渲染、几何处理、游戏引擎"),
    ("interest_data", "对数据/大数据感兴趣", "interest", _I,
     "关注数据分析、推荐、图计算"),
    ("interest_security", "对网络安全感兴趣", "interest", _I,
     "关注密码学、逆向、漏洞分析"),
    ("interest_embedded", "对嵌入式/系统底层感兴趣", "interest", _I,
     "关注操作系统、驱动、嵌入式开发"),
    ("interest_web", "对 Web 后端开发感兴趣", "interest", _I,
     "关注服务端、中间件、分布式系统"),

    #时间投入
    ("time_plenty", "每周可投入 10 小时以上", "time", _I, "学习时间比较充裕"),
    ("time_limited", "每周可投入不足 5 小时", "time", _I, "课业或工作较忙，时间碎片化"),

    #当前水平
    ("level_beginner", "算法入门阶段", "level", _I,
     "尚未系统学习过算法，或只接触过零散概念"),
    ("level_intermediate", "算法进阶阶段", "level", _I,
     "已能独立完成简单题，希望突破中等及以上难度"),

    #学习习惯
    ("habit_practice", "喜欢直接刷题实践", "habit", _I, "通过做题来理解算法"),
    ("habit_theory", "喜欢先弄懂原理再动手", "habit", _I, "先看教材与证明，再写代码"),

    #学习阶段（推理得到）
    ("stage_foundation", "处于基础夯实阶段", "stage", _D,
     "需要先把复杂度分析与基础数据结构打牢"),
    ("stage_advanced", "处于进阶提升阶段", "stage", _D,
     "具备基础后，可以进入经典算法专题"),
    ("stage_specialized", "处于专项突破阶段", "stage", _D,
     "基础扎实，适合攻克高阶专题"),

    #学习路线（推理得到）
    ("route_interview", "推荐路线：求职面试算法路线", "route", _D,
     "以笔试面试高频考点为主线"),
    ("route_contest", "推荐路线：算法竞赛路线", "route", _D,
     "以竞赛大纲为主线，覆盖面更广、难度更高"),
    ("route_ai", "推荐路线：人工智能算法路线", "route", _D,
     "以机器学习所需的算法与数学基础为主线"),
    ("route_engineering", "推荐路线：工程能力优先路线", "route", _D,
     "以日常开发中最常用的算法为主线"),
    ("route_research", "推荐路线：科研与算法工程路线", "route", _D,
     "以论文复现与算法设计能力为主线"),

    #算法推荐（推理得到）
    ("rec_complexity", "优先学习：复杂度分析与基础数据结构", "rec", _D,
     "一切算法的起点，决定后续学习效率"),
    ("rec_sorting", "学习：排序与二分查找", "rec", _D,
     "最基础也最高频的两类算法"),
    ("rec_recursion", "学习：递归与分治", "rec", _D,
     "理解递归思想，掌握分治套路"),
    ("rec_search", "学习：搜索与回溯", "rec", _D,
     "DFS/BFS、剪枝与回溯框架"),
    ("rec_greedy", "学习：贪心算法", "rec", _D,
     "区间调度、交换论证等经典模型"),
    ("rec_dp", "学习：动态规划", "rec", _D,
     "线性 DP、背包、区间 DP、树形 DP"),
    ("rec_tree", "学习：树与高级数据结构", "rec", _D,
     "并查集、堆、线段树、树状数组"),
    ("rec_graph", "学习：图论算法", "rec", _D,
     "最短路、最小生成树、拓扑排序"),
    ("rec_string", "学习：字符串算法", "rec", _D,
     "KMP、哈希、字典树、后缀数组"),
    ("rec_math", "学习：数论与组合数学", "rec", _D,
     "整除、同余、素数筛、组合计数"),
    ("rec_geometry", "学习：计算几何", "rec", _D,
     "向量运算、凸包、线段相交"),
    ("rec_ml", "学习：机器学习基础算法", "rec", _D,
     "线性回归、逻辑回归、KMeans、梯度下降"),
    ("rec_bit", "学习：位运算与状态压缩", "rec", _D,
     "位技巧与状压 DP"),
    ("rec_flow", "学习：网络流与二分图匹配", "rec", _D,
     "最大流、最小割、匈牙利算法"),
    ("rec_np", "学习：NP 完全性与近似算法", "rec", _D,
     "问题复杂度分类与近似求解思路"),

    #学习建议（推理得到）
    ("advice_language_first", "建议：先熟练掌握一门编程语言", "advice", _D,
     "把语言基础打牢再谈算法"),
    ("advice_math_first", "建议：先补齐数学基础", "advice", _D,
     "优先补初等数论、组合与概率"),
    ("advice_theory_first", "建议：先系统过一遍理论再刷题", "advice", _D,
     "避免只会套模板、题目一变就不会"),
    ("advice_oj", "建议：注册在线评测平台并建立题单", "advice", _D,
     "推荐 LeetCode、洛谷、Codeforces 等"),
    ("advice_daily_practice", "建议：坚持每日一题保持手感", "advice", _D,
     "稳定的小步前进优于突击"),
    ("advice_output", "建议：坚持写题解或博客输出", "advice", _D,
     "输出是最好的复习方式"),
    ("advice_project", "建议：把算法用到实际项目里", "advice", _D,
     "在真实场景中理解算法的取舍"),
    ("advice_paper", "建议：精读经典论文与开源实现", "advice", _D,
     "从复现开始建立研究能力"),
    ("advice_contest", "建议：定期参加线上竞赛", "advice", _D,
     "用限时比赛检验训练效果"),
]

#算法主题
# (主题编码, 主题名称, 难度, 建议学时, 核心考点, 学习路径, 典型题目)

TOPICS: List[Tuple[str, str, str, int, str, str, str]] = [
    ("rec_complexity", "复杂度分析与基础数据结构", "入门", 20,
     "时间复杂度、空间复杂度、均摊分析、数组/链表/栈/队列/哈希表",
     "先学会估算复杂度，再逐个实现线性数据结构",
     "两数之和、有效的括号、最小栈、LRU 缓存"),
    ("rec_sorting", "排序与二分查找", "入门", 20,
     "快排、归并、堆排序、计数排序、二分答案、旋转数组",
     "手写一遍快排与归并，再刷二分的六种变体",
     "排序数组、搜索旋转排序数组、寻找两个正序数组的中位数"),
    ("rec_recursion", "递归与分治", "入门", 16,
     "递归三要素、主定理、归并分治、快速选择",
     "从汉诺塔、全排列入手，过渡到分治计数",
     "Pow(x,n)、数组中的第K个最大元素、多数元素"),
    ("rec_search", "搜索与回溯", "进阶", 24,
     "DFS、BFS、剪枝、回溯框架、状态去重、双向 BFS",
     "先写熟练模板，再练剪枝优化",
     "全排列、N 皇后、单词接龙、岛屿数量"),
    ("rec_greedy", "贪心算法", "进阶", 18,
     "区间调度、交换论证、反悔贪心、优先队列配合",
     "重点训练「证明贪心正确」的能力",
     "跳跃游戏、分发糖果、任务调度器、用最少数量的箭引爆气球"),
    ("rec_dp", "动态规划", "进阶", 40,
     "线性 DP、背包九讲、区间 DP、树形 DP、状压 DP、数位 DP",
     "先按「状态定义—转移方程—边界」三步走，再总结模型",
     "最长递增子序列、零钱兑换、编辑距离、打家劫舍"),
    ("rec_tree", "树与高级数据结构", "进阶", 36,
     "并查集、堆、线段树、树状数组、单调栈、字典树",
     "先掌握并查集与堆，再攻线段树与树状数组",
     "二叉树遍历、最近公共祖先、区间和检索"),
    ("rec_graph", "图论算法", "进阶", 36,
     "拓扑排序、最短路（Dijkstra/Bellman-Ford/Floyd）、最小生成树、强连通分量",
     "从存图方式讲起，再逐个实现经典算法",
     "课程表、网络延迟时间、连接所有点的最小费用"),
    ("rec_string", "字符串算法", "进阶", 24,
     "KMP、字符串哈希、字典树、后缀数组、Manacher",
     "先吃透 KMP 的 next 数组含义",
     "实现 strStr、最长回文子串、单词替换"),
    ("rec_math", "数论与组合数学", "高级", 30,
     "整除与同余、欧几里得算法、素数筛、快速幂、组合计数、容斥原理",
     "按「整除—同余—筛法—计数」的顺序推进",
     "Pow(x,n)、计数质数、组合总和"),
    ("rec_geometry", "计算几何", "高级", 24,
     "向量与叉积、凸包、线段相交、旋转卡壳、扫描线",
     "先把向量运算封装成工具类",
     "凸包、矩形面积、直线上最多的点数"),
    ("rec_ml", "机器学习基础算法", "进阶", 40,
     "线性回归、逻辑回归、KNN、KMeans、梯度下降、评价指标",
     "手推一遍梯度，再手写一遍训练循环",
     "手写线性回归、KMeans 聚类、逻辑回归分类器"),
    ("rec_bit", "位运算与状态压缩", "进阶", 20,
     "位运算技巧、lowbit、子集枚举、状压 DP",
     "先把常见位技巧总结成小抄",
     "只出现一次的数字、比特位计数、状态压缩 TSP"),
    ("rec_flow", "网络流与二分图匹配", "高级", 28,
     "最大流（Dinic）、最小割、费用流、匈牙利算法、KM 算法",
     "先理解增广路思想，再写 Dinic",
     "最大流模板、二分图匹配、最小路径覆盖"),
    ("rec_np", "NP 完全性与近似算法", "高级", 16,
     "P/NP/NPC 定义、常见 NPC 问题归约、近似比、随机算法",
     "以理解概念和经典归约为主，不必钻牛角尖",
     "旅行商问题的近似解、集合覆盖"),
]

#规则库
# (规则编码, 规则名称, 优先级, [(条件事实, 是否取反)], [结论事实], 说明)

RULES: List[Tuple[str, str, int, List[Tuple[str, bool]], List[str], str]] = [
    #一、学习阶段判定
    ("R001", "入门阶段判定", 100, [("level_beginner", False)],
     ["stage_foundation"], "自评为入门阶段，进入基础夯实阶段"),
    ("R002", "进阶阶段判定", 100, [("level_intermediate", False)],
     ["stage_advanced"], "自评为进阶阶段，进入进阶提升阶段"),
    ("R003", "专项突破阶段判定", 90,
     [("stage_advanced", False), ("ds_tree_graph", False)],
     ["stage_specialized"], "进阶且已掌握树与图，可进入专项突破"),

    #二、学习路线判定
    ("R004", "求职面试路线", 95, [("goal_interview", False)],
     ["route_interview"], "以求职面试为目标"),
    ("R005", "算法竞赛路线", 95, [("goal_contest", False)],
     ["route_contest"], "以算法竞赛为目标"),
    ("R006", "人工智能算法路线", 92,
     [("interest_ai", False), ("math_strong", False)],
     ["route_ai"], "对 AI 感兴趣且数学扎实，走 AI 算法路线"),
    ("R007", "工程能力优先路线", 88, [("goal_project", False)],
     ["route_engineering"], "以提升工程开发能力为目标"),
    ("R008", "科研与算法工程路线", 90, [("goal_research", False)],
     ["route_research"], "以科研或算法工程为方向"),

    #三、基础补齐
    ("R009", "零基础先学编程语言", 99,
     [("level_beginner", False), ("base_programming", True)],
     ["advice_language_first", "advice_theory_first"],
     "入门且无编程基础，先补语言"),
    ("R010", "夯实复杂度与基础数据结构", 98,
     [("stage_foundation", False), ("base_programming", False)],
     ["rec_complexity", "advice_oj"], "基础阶段的第一步永远是复杂度与线性结构"),
    ("R011", "数学薄弱先补数学", 97, [("math_weak", False)],
     ["advice_math_first"], "数学薄弱会限制后续高阶专题"),
    ("R012", "数学扎实可挑战数论组合", 55,
     [("math_strong", False), ("stage_advanced", False)],
     ["rec_math"], "数学好则数论与组合可以提前安排"),

    #四、入门阶段推荐
    ("R013", "入门：排序与二分查找", 75,
     [("stage_foundation", False), ("ds_basic", False)],
     ["rec_sorting"], "有线性结构基础后先学排序与二分"),
    ("R014", "入门：递归与分治", 70,
     [("stage_foundation", False), ("ds_basic", False)],
     ["rec_recursion"], "排序之后紧接着练递归思维"),
    ("R015", "入门：搜索与回溯", 65,
     [("stage_foundation", False), ("habit_practice", False)],
     ["rec_search"], "喜欢实践的学习者可以尽早接触搜索"),

    #五、求职面试路线
    ("R016", "面试高频：动态规划", 68,
     [("route_interview", False), ("stage_advanced", False)],
     ["rec_dp"], "动态规划是面试区分度最高的考点"),
    ("R017", "面试高频：图论", 66,
     [("route_interview", False), ("ds_tree_graph", False)],
     ["rec_graph"], "图论在大厂笔试中出现频率很高"),
    ("R018", "面试加分项：字符串算法", 58,
     [("route_interview", False), ("ds_tree_graph", False)],
     ["rec_string"], "字符串题是面试的稳定得分点"),
    ("R019", "面试手撕：贪心算法", 60,
     [("route_interview", False), ("stage_advanced", False),
      ("habit_practice", False)],
     ["rec_greedy"], "面试常要求手撕贪心并说明正确性"),
    ("R020", "面试进阶：树与高级数据结构", 62,
     [("route_interview", False), ("ds_tree_graph", False),
      ("time_plenty", False)],
     ["rec_tree"], "时间充裕可以冲击线段树等进阶结构"),
    ("R021", "面试刷题节奏", 50,
     [("route_interview", False), ("time_plenty", False)],
     ["advice_daily_practice", "advice_oj"], "面试准备需要稳定的刷题量"),
    ("R022", "时间有限优先高频题", 52,
     [("route_interview", False), ("time_limited", False)],
     ["advice_daily_practice"], "时间有限就集中攻克高频题"),

    #六、算法竞赛路线
    ("R023", "竞赛必学：动态规划", 70, [("route_contest", False)],
     ["rec_dp"], "动态规划是竞赛的核心分水岭"),
    ("R024", "竞赛必学：图论与网络流", 68,
     [("route_contest", False), ("ds_tree_graph", False)],
     ["rec_graph", "rec_flow"], "竞赛图论必须覆盖到网络流"),
    ("R025", "竞赛进阶：数论与组合数学", 64,
     [("route_contest", False), ("math_strong", False)],
     ["rec_math"], "数论与组合是竞赛的常见考点"),
    ("R026", "竞赛进阶：位运算与状态压缩", 62,
     [("route_contest", False), ("math_strong", False)],
     ["rec_bit"], "状压 DP 是竞赛提分的关键技巧"),
    ("R027", "竞赛高阶：计算几何", 58,
     [("route_contest", False), ("math_strong", False),
      ("stage_specialized", False)],
     ["rec_geometry"], "计算几何属于高阶专题，放到后期"),
    ("R028", "竞赛高阶：字符串算法", 60,
     [("route_contest", False), ("stage_specialized", False)],
     ["rec_string"], "竞赛字符串要求掌握后缀数组等高级结构"),
    ("R029", "竞赛：参加线上赛保持手感", 45,
     [("route_contest", False), ("time_plenty", False)],
     ["advice_contest"], "竞赛能力靠比赛磨出来"),

    #七、人工智能路线
    ("R030", "AI 方向：机器学习基础算法", 70, [("route_ai", False)],
     ["rec_ml"], "AI 方向先打通传统机器学习算法"),
    ("R031", "AI 方向：动态规划与图论基础", 60,
     [("route_ai", False), ("stage_advanced", False)],
     ["rec_dp"], "AI 的算法岗笔试同样考 DP"),
    ("R032", "AI 方向：读论文与开源实现", 50,
     [("route_ai", False), ("time_plenty", False)],
     ["advice_paper"], "AI 方向必须建立论文阅读习惯"),
    ("R033", "AI 方向：结合项目实践", 55,
     [("route_ai", False), ("goal_project", False)],
     ["advice_project"], "AI 方向非常看重项目经历"),

    #八、工程开发路线
    ("R034", "工程方向：排序与贪心", 65, [("route_engineering", False)],
     ["rec_greedy", "rec_sorting"], "工程中最常用的两类算法"),
    ("R035", "工程方向：树与图", 60,
     [("route_engineering", False), ("ds_tree_graph", False)],
     ["rec_graph"], "依赖解析、任务调度都离不开图"),
    ("R036", "工程方向：把算法用到项目里", 55,
     [("route_engineering", False)],
     ["advice_project"], "工程方向重在看得到效果"),

    #九、按兴趣方向的推荐
    ("R037", "图形学兴趣：计算几何", 66,
     [("interest_graphics", False), ("math_strong", False)],
     ["rec_geometry"], "图形学与计算几何高度相关"),
    ("R038", "图形学兴趣：树与空间数据结构", 60,
     [("interest_graphics", False), ("ds_tree_graph", False)],
     ["rec_tree"], "场景管理需要 BVH、四叉树等结构"),
    ("R039", "数据方向：图论与网络流", 62,
     [("interest_data", False), ("ds_tree_graph", False)],
     ["rec_graph", "rec_flow"], "数据方向常做图计算与调度优化"),
    ("R040", "安全方向：字符串与位运算", 60,
     [("interest_security", False)],
     ["rec_string", "rec_bit"], "密码学与逆向离不开字符串和位运算"),
    ("R041", "嵌入式方向：位运算与状态压缩", 62,
     [("interest_embedded", False)],
     ["rec_bit"], "底层开发对位操作要求很高"),
    ("R042", "Web 后端方向：字符串与树结构", 58,
     [("interest_web", False), ("ds_tree_graph", False)],
     ["rec_string", "rec_tree"], "路由匹配与索引结构依赖这两类算法"),

    #十、通用建议
    ("R043", "理论派：先夯理论基础", 48, [("habit_theory", False)],
     ["advice_theory_first"], "先弄懂原理再动手的学习者"),
    ("R044", "实践派：保持刷题量", 48,
     [("habit_practice", False), ("time_plenty", False)],
     ["advice_daily_practice"], "喜欢实践且时间充裕，应保持题量"),
    ("R045", "专项突破：挑战 NP 完全性", 40,
     [("stage_specialized", False), ("time_plenty", False)],
     ["rec_np"], "基础扎实后可以了解问题复杂度的边界"),
    ("R046", "时间充裕：坚持输出", 42, [("time_plenty", False)],
     ["advice_output"], "时间充裕的学习者应养成输出习惯"),
    ("R047", "科研方向：精读论文", 52,
     [("route_research", False), ("time_plenty", False)],
     ["advice_paper"], "科研方向的核心能力是读论文"),
    ("R048", "科研方向：图论与动态规划", 58,
     [("route_research", False), ("ds_tree_graph", False)],
     ["rec_graph"], "科研中的建模多依赖图论与 DP"),
    ("R049", "考研考试方向：夯实基础", 66, [("goal_exam", False)],
     ["rec_complexity", "rec_sorting"], "考试更看重基础与规范"),
    ("R050", "考研考试方向：树与图", 60,
     [("goal_exam", False), ("ds_tree_graph", False)],
     ["rec_tree", "rec_graph"], "树与图是考试大题的高频考点"),
]


#装配函数
def build_facts() -> List[Fact]:
    """把 FACTS 里的元组装配成 Fact 对象。"""
    #先做出 类别编码 -> 类别中文名 的对应关系
    category_names = {code: name for code, name, _order in CATEGORIES}
    return [
        Fact(code=code, name=name, category_code=category,
             category_name=category_names.get(category, category),
             fact_type=fact_type, description=description)
        for code, name, category, fact_type, description in FACTS
    ]


def build_rules() -> List[Rule]:
    """把 RULES 里的元组装配成 Rule 对象。

    rule_id 直接用列表下标加一。只要不调整 RULES 的顺序，id 就一直稳定，
    而冲突消解第4级比的正是它。
    """
    rules = []
    for index, (code, name, priority, conditions, conclusions, desc) in enumerate(RULES, start=1):
        rules.append(Rule(
            rule_id=index,
            rule_code=code,
            rule_name=name,
            priority=priority,
            conditions=[Condition(fact_code=c, is_negate=n) for c, n in conditions],
            conclusions=list(conclusions),
            description=desc,
            is_enabled=True,
        ))
    return rules


def fact_index() -> Dict[str, Fact]:
    """做成 事实编码 -> Fact 的字典。"""
    return {fact.code: fact for fact in build_facts()}


def topic_index() -> Dict[str, Tuple]:
    """做成 主题编码 -> 元组 的字典。"""
    return {row[0]: row for row in TOPICS}
