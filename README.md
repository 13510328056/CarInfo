# 园区无人车每日资讯日报系统

一个本地运行的园区无人车垂直领域资讯日报生成系统，支持自动抓取、手动录入、智能分类、模板导出和公众号格式预览。

## 目录结构

```
├── app.py              # Flask 本地服务，提供 REST API
├── services.py         # 资讯抓取、分类、报告生成核心逻辑
├── storage.py          # 本地 JSON 文件存储管理
├── wechat.py           # 微信公众号 API 客户端
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 构建文件
├── docker-compose.yml  # Docker Compose 配置
├── static/
│   ├── index.html      # 前端页面
│   ├── app.js          # 前端交互逻辑
│   ├── style.css       # 前端样式
│   └── thumbnail.png   # 公众号默认封面缩略图
├── data/               # 自动生成的本地配置和资讯数据（已 gitignore）
├── templates/          # Flask 模板目录（预留）
├── .gitignore
├── CLAUDE.md           # 项目开发规范与说明
└── 园区无人车每日资讯报告系统软件需求说明书.md
```

## 快速启动（Docker）

### 前置条件

- 安装 [Docker](https://docs.docker.com/get-docker/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)（Docker Desktop 已内置）

### 启动服务

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

打开浏览器访问 `http://localhost:5000`

### 数据持久化

系统数据存储在 `data/` 目录中，通过 Docker volume 挂载到容器内：

```yaml
volumes:
  - ./data:/app/data
```

首次启动后自动生成 `data/config.json` 和 `data/news.json`，重启容器数据不丢失。

### 更新到最新版本

```bash
git pull
docker compose up -d --build
```

## 功能概览

- **自动抓取**：从搜索引擎、行业站点和主流媒体（澎湃新闻等）抓取园区无人车相关资讯
- **手动录入**：补充非抓取类资讯，支持分类选择
- **智能分类**：基于关键词匹配的自动分类（5大板块）
- **内容编辑**：资讯列表查看、编辑、删除
- **模板导出**：一键生成专业卡片风格的公众号适配报告
- **一键发布**：配置微信公众号 AppID/AppSecret 后，直接发布到公众号草稿箱
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

## 微信公众号发布

1. 打开系统页面 → **微信公众号配置** → 填写 AppID / AppSecret / 公众号名称
2. **导出与预览** → 点击「生成报告」预览效果
3. 预览满意后点击「📤 一键发布到公众号」
4. 登录 [mp.weixin.qq.com](https://mp.weixin.qq.com/) → 草稿箱 查看和发布

> ⚠️ 发布前需将服务器的公网 IP 添加到微信公众号后台的 IP 白名单（设置 → 安全中心 → IP白名单）

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/config | 获取配置 |
| POST | /api/config | 保存配置 |
| GET | /api/news | 获取资讯列表 |
| POST | /api/news | 手动录入资讯 |
| PUT/DELETE | /api/news/<id> | 更新/删除资讯 |
| POST | /api/news/crawl | 自动抓取资讯 |
| POST | /api/news/clear | 清空资讯列表 |
| POST | /api/channels/verify | 验证渠道连通性 |
| POST | /api/news/classify | 资讯自动分类 |
| POST | /api/export | 导出报告 |
| POST | /api/wechat/publish | 发布到公众号草稿箱 |
| GET/DELETE | /api/history | 获取/清空历史报告 |
| POST | /api/template/reset | 恢复默认模板 |

## 技术栈

- **后端**：Python + Flask
- **前端**：原生 HTML + CSS + JavaScript (Fetch API)
- **数据存储**：本地 JSON 文件
- **抓取**：requests + BeautifulSoup4 + lxml
- **部署**：Docker / Docker Compose
