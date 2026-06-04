# 园区无人车每日资讯日报系统

## 项目概述
Flask 本地 Web 应用，用于抓取、分类和生成园区无人车垂直领域的公众号资讯日报。

## 技术栈
- Python + Flask（后端 API）
- 原生 HTML/CSS/JS（前端）
- JSON 文件存储（本地 data/ 目录）
- requests + BeautifulSoup4 + lxml（网页抓取）

## 关键文件

| 文件 | 职责 |
|------|------|
| `app.py` | Flask 路由和 API 入口 |
| `services.py` | 抓取逻辑、分类、报告生成 |
| `storage.py` | JSON 文件读写、配置管理 |
| `static/index.html` | 前端页面 |
| `static/app.js` | 前端交互 |
| `static/style.css` | 样式 |

## 数据分类体系（5大板块）
1. 政策动态
2. 企业落地
3. 技术动态
4. 招标采购
5. 行业观点/海外资讯

## 运行方式
```bash
python app.py  # 启动在 localhost:5000
```

## 设计约束
- 纯本地运行，无外部数据库依赖
- 资讯抓取通过 requests + BeautifulSoup，未使用 Selenium/Playwright
- 分类基于关键词匹配，非 NLP 模型
- 所有数据以 JSON 格式存储在 data/ 目录下
