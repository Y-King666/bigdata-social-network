# 基于大数据的社交网络分析系统

本项目以新冠疫情期间的公开微博数据为对象，完成数据清洗、社交网络构建、社区发现、影响力分析、传播级联分析、话题与情感分析、空间分析和交互式可视化，并提供一套可本机演示的“历史回放 + 模拟实时监测”系统。

仓库只保存源代码、运行配置和必要技术说明。原始微博数据、用户画像、Parquet 中间结果、图表产物和环境文件不进入版本库。

## 主要功能

- 网络关系图谱：构建用户级转发网络，计算 PageRank、度分布、连通分量和社区结构。
- 热点话题：提取微博话题，分析话题日趋势，并与微博热搜榜进行覆盖率和相关性对照。
- 传播路线：还原转发级联，展示级联规模、增长节奏和传播模拟。
- 空间热点：基于地理标签生成网格热力与省份分布。
- 用户分析：查询用户画像、网络指标、社区归属和两个用户之间的最短转发链路。
- 情感分析：使用知网 HowNet 情感词典和 Aho-Corasick 多模式匹配完成全量极性标注。
- 模拟实时监测：历史事件回放、Spark Structured Streaming 微批聚合、实时大屏和规则告警。

## 主要结果

| 指标 | 结果 |
|---|---:|
| 关键词筛选推文 | 40,893,832 条 |
| 带地理标签推文 | 45,901,994 条 |
| 用户画像 | 20,000,000 条 |
| 用户级转发边 | 3,216,970 条 |
| 转发网络节点 | 2,336,558 个 |
| 可识别传播级联 | 293,631 个 |
| Leiden 社区 | 41,837 个，模块度 0.7985 |
| 推文话题 | 564,870 个 |
| 热搜记录 | 1,618,848 条 |

项目重点结论包括：

- 转发网络近似单向广播结构，94.2% 的节点没有入度，最大强连通分量只有 82 个节点。
- 粉丝量与实际传播力并不等价。一条由 239 个粉丝的账号发出的微博获得 18,114 次转发，与另一条粉丝量超过 1 亿的微博传播规模接近。
- 在疫情相关话题范围内，站内发帖量与热搜热度几乎不相关，热搜榜反映的是另一种公众注意力。
- 转发关系存在显著地域同质性，同省连接约为随机基准的 2.11 倍；性别同质性不明显。

## 系统页面

系统包含九个页面：

`监测大屏`、`数据概览`、`空间热点`、`热点话题`、`传播分析`、`影响力与社区`、`用户画像查询`、`关系发现`、`传播模拟`。

其中“实时监测”是基于历史数据回放的模拟实时链路，不是平台实时数据接入。

## 项目结构

```text
app/             Streamlit 多页分析系统
dashboard/       独立历史分析与实时监测 Web 前端
scripts/         数据处理、图分析、情感分析、地理分析脚本
stream/          历史回放与 Structured Streaming 模拟实时链路
docs/            空间分析等技术说明
data/            原始数据与 Parquet（被 .gitignore 排除）
output/          中间分析结果与图表（被 .gitignore 排除）
```

## 数据来源声明

本仓库不对下列数据重新授权，也不分发原始数据文件。使用者应自行从原始发布渠道获取数据，并遵守数据集发布方的最新许可、使用条款和隐私要求。仓库中的分析代码和结果仅用于研究与演示。

### 1. Weibo-COV 微博数据

项目主体数据为 **Weibo-COV**，这是针对新冠疫情期间微博公开内容整理的大规模公开数据集。本项目实际使用：

| 数据部分 | 规模 | 项目用途 | 来源 |
|---|---:|---|---|
| Weibo-COV 1.0 关键词筛选推文 | 40,893,832 条 | 转发网络、话题、情感、传播分析 | 官方数据仓库存档的 1.0 数据 |
| Weibo-COV 1.0 带地理标签推文 | 45,901,994 条 | 地理网格与区域热点分析 | 官方数据仓库存档的 1.0 数据 |
| Weibo-COV 2.0 用户画像 | 20,000,000 条 | 性别、省份、粉丝数等属性分析 | 官方数据仓库存档的 2.0 用户池 |

官方项目：

- [nghuyong/weibo-cov](https://github.com/nghuyong/weibo-cov)
- [Weibo-COV 论文 arXiv:2005.09174](https://arxiv.org/abs/2005.09174)
- [ACL Anthology 论文页面](https://aclanthology.org/2020.nlpcovid19-2.34/)

引用格式：

```bibtex
@inproceedings{hu-etal-2020-weibo,
  title     = "{W}eibo-{COV}: A Large-Scale {COVID}-19 Social Media Dataset from {W}eibo",
  author    = "Hu, Yong and Huang, Heyan and Chen, Anfan and Mao, Xian-Ling",
  booktitle = "Proceedings of the 1st Workshop on {NLP} for {COVID}-19 (Part 2) at {EMNLP} 2020",
  month     = dec,
  year      = "2020",
  address   = "Online",
  publisher = "Association for Computational Linguistics",
  url       = "https://www.aclweb.org/anthology/2020.nlpcovid19-2.34",
  doi       = "10.18653/v1/2020.nlpcovid19-2.34"
}
```

官方仓库当前提供的下载入口为百度网盘。项目没有将下载文件、解压文件或转换后的 Parquet 提交到本仓库。

### 2. 微博热搜榜补充数据

`data/weibo/hotsearch_*.csv` 共 1,618,848 条记录、26,022 个话题，时间范围为 2019-12-16 至 2020-04-17。该数据为微博公开热搜榜单的整理结果，用于“站内话题量”与“热搜热度”的交叉分析。

由于原始 CSV 未保留可核验的上游仓库标识，本 README 不填写未经确认的二次转载链接。引用时应注明原始数据来自微博公开热搜页面。

### 3. SNAP soc-Pokec 图数据

项目早期使用 [Stanford Network Analysis Project 的 soc-Pokec 数据集](https://snap.stanford.edu/data/soc-Pokec.html) 验证大规模图构建、社区发现和影响力算法。最终系统主体改用 Weibo-COV，以保证用户、文本、关系和属性能够相互关联。

### 4. 辅助微博测试数据

`data/weibo/weibo_posts.csv` 与 `data/weibo/weibo_users.csv` 是早期用于字段和关联性测试的公开微博补充数据。由于原始文件未保留明确的上游仓库地址，且其用户 ID 与 Weibo-COV 的哈希 ID 无法关联，这两份文件不参与最终系统的核心结论。

### 5. 情感词典

情感分析使用 `cnsenti` 内置的知网 HowNet 情感词典，包括正面词、负面词、否定词和程度副词。项目通过 Aho-Corasick 自动机一次扫描所有情感词，再结合局部窗口中的否定词和程度副词计算极性。

## 数据治理说明

- 原始微博用户 ID 已是哈希值，但微博正文仍可能包含个人信息，因此原始数据不进入公开仓库。
- `data/`、`output/`、`.venv/`、Spark 临时目录、流式检查点、运行日志和本地状态文件均已被 `.gitignore` 排除。
- 转发边只覆盖能在数据集中找到原微博的转发记录，重构得到的级联规模应视为下界。
- 推文集按 179 个疫情关键词筛选，话题与热搜相关性结论仅适用于疫情话题范围。
- 地理坐标表与关键词推文表是两次采集，二者按 `_id` 的匹配率有限，空间结论需要说明统计口径。
- 年龄字段缺失较多且存在占位日期，因此最终分析未使用年龄结论。

## 运行环境

- Windows 11
- Python 3.14
- Java 17
- Apache Spark 4.2.0
- 内存：至少 16 GB
- 项目路径必须为英文路径

首次运行前创建虚拟环境并安装依赖：

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Spark 在 Windows 上需要 Hadoop 运行组件。项目通过 `scripts/spark_env.py` 设置 `HADOOP_HOME`、`PYSPARK_PYTHON` 和 `PYSPARK_DRIVER_PYTHON`。

## 启动方式

先检查 Spark 环境：

```powershell
python scripts\00_smoke_test.py
```

启动 Streamlit 分析系统：

```powershell
streamlit run app\main.py
```

启动“回放器 + Structured Streaming + 监测大屏”：

```powershell
powershell -ExecutionPolicy Bypass -File stream\start_all.ps1
```

监测大屏默认地址：

```text
http://127.0.0.1:8601/
```

原始数据和中间结果未随仓库分发，因此克隆仓库后需先从 Weibo-COV 官方渠道获取数据，按 `scripts/` 中的输入路径准备 `data/` 和数据派生结果 `output/`，再启动页面。

## 文档

- [空间分析结果](docs/geo-findings.md)

## 引用本项目关注的数据集

使用或再分发数据时，请优先引用数据发布方，而不是本项目仓库。使用 Weibo-COV 时请按上方 BibTeX 引用原论文，并遵守其官方数据下载页面的要求。
