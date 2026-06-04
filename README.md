# 园区无人车每日资讯日报系统

一个本地运行的园区无人车垂直领域资讯日报生成系统，支持自动抓取、手动录入、智能分类、模板导出和公众号格式预览。

## 目录结构

```
├── app.py              # Flask 本地服务，提供 REST API
├── services.py         # 资讯抓取、分类、报告生成核心逻辑
├── storage.py          # 本地 JSON 文件存储管理
├── requirements.txt    # Python 依赖
├── static/
│   ├── index.html      # 前端页面
│   ├── app.js          # 前端交互逻辑
│   └── style.css       # 前端样式
├── data/               # 自动生成的本地配置和资讯数据（已 gitignore）
├── templates/          # Flask 模板目录（预留，当前使用静态文件）
├── .gitignore
├── setup.bat           # Windows 环境初始化
├── run.bat             # Windows 启动服务
├── start.ps1           # PowerShell 启动脚本
└── 园区无人车每日资讯报告系统软件需求说明书.md  # 原始需求文档
```

## 快速启动

1. 初始化环境：
   ```powershell
   .\setup.bat
   ```

2. 启动服务：
   ```powershell
   .\run.bat
   ```

3. 打开浏览器访问 `http://localhost:5000`

### 其他平台

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## 功能概览

- **自动抓取**：从多个搜索引擎和行业站点抓取园区无人车相关资讯
- **手动录入**：补充非抓取类资讯，支持分类选择
- **智能分类**：基于关键词匹配的自动分类（5大板块）
- **内容编辑**：资讯列表查看、编辑、删除
- **模板导出**：一键生成纯文本或 HTML 格式的公众号适配报告
- **渠道验证**：测试抓取渠道的连通性和内容可解析性
- **历史归档**：按日期存档已生成的报告，支持回溯

### 资讯分类体系

| 板块 | 覆盖内容 |
|------|---------|
| 政策动态 | 园区自动驾驶新规、路测开放、试点政策、补贴等 |
| 企业落地 | 无人车上线、项目签约、运营合作等 |
| 技术动态 | 传感器、调度平台、车路协同、算法等 |
| 招标采购 | 项目招标、中标公告、预算等 |
| 行业观点/海外资讯 | 专家解读、海外案例、趋势分析等 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/config | 获取配置 |
| POST | /api/config | 保存配置 |
| GET | /api/news | 获取资讯列表 |
| POST | /api/news | 手动录入资讯 |
| PUT/DELETE | /api/news/<id> | 更新/删除资讯 |
| POST | /api/news/crawl | 自动抓取资讯 |
| POST | /api/channels/verify | 验证渠道连通性 |
| POST | /api/news/classify | 资讯自动分类 |
| POST | /api/export | 导出报告 |
| GET | /api/history | 获取历史报告 |
| POST | /api/template/reset | 恢复默认模板 |

## 技术栈

- **后端**：Python + Flask
- **前端**：原生 HTML + CSS + JavaScript (Fetch API)
- **数据存储**：本地 JSON 文件
- **抓取**：requests + BeautifulSoup4 + lxml
