# Boss-Crawler

招聘数据爬虫与智能分析系统。

## 功能

- **矩阵式爬取** - 按城市、经验、学历、工作类型多维度抓取 Boss 直聘职位
- **去重清洗** - 基于 URL 和文本相似度去重
- **LLM 分析** - 提取技能要求并评分，生成学习路径建议
- **可视化展示** - React + ECharts 数据可视化

## 效果演示

## 脚本

| 脚本 | 说明 |
|------|------|
| `crawl_boss.py` | 爬取职位数据 |
| `analyzer_llm.py` | LLM 分析技能需求 |
| `main.py` | 入口（预留）|

## 快速开始

安装[opencli](https://github.com/jackwener/OpenCLI)

```bash
# 安装依赖
uv sync

# 复制环境配置
cp .env.example .env
# 编辑 .env 填入 API_KEY 和 BASE_URL

# 爬取数据
uv run crawl_boss.py --city 南京 --experience '在校生(实习)' --jobType 实习 --degree 本科

# 可视化
cd boss-visualizer && pnpm install && pnpm dev
```

## 输出文件

> 暂时是这样，后续开发会调整

- `boss_jobs.json` / `boss_jobs.csv` - 原始职位数据
- `llm_skills_analysis.xlsx` - 带技能分析的职位表
- `skill_statistics.xlsx` - 技能统计表