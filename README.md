# 资讯日报助手

一个本地运行的通用资讯日报生成系统。支持多渠道资讯抓取（网页搜索 + RSS 订阅）、智能分类、分页检索、报告生成与微信公众号一键发布。

---

## 快速启动

### 方式一：Docker 部署

```bash
git clone https://github.com/13510328056/CarInfo.git
cd CarInfo
docker compose up -d
# 访问 http://localhost:5000
```

### 方式二：本地运行

```bash
pip install -r requirements.txt
python app.py
# 访问 http://localhost:5000
```

---

## 功能概览

### 4 步工作流

| 步骤 | 功能 | 说明 |
|------|------|------|
| ① 内容源设置 | 网页渠道 + RSS 订阅 | 配置抓取来源，支持 OPML 批量导入（20+ 源） |
| ② 过滤配置 | 分类关键词 | 5 大板块，中英文双语关键词，匹配即分类 |
| ③ 抓取资讯 | 并行抓取 + 验证 | 网页 8 线程 RSS 并行，验证连通性 |
| ④ 内容管理与发布 | 编辑 + 分页 + 导出 | 列表分页/搜索，4 种格式报告，一键微信发布 |

### 内容源

| 类型 | 说明 | 验证 |
|------|------|------|
| **网页渠道** | 搜索引擎、行业站点、新闻列表页 | HTTP 状态 + 反爬检测 + 关键词匹配度 |
| **RSS 订阅** | 标准 RSS 2.0 / Atom Feed | XML 可解析性 + Feed 标题 + 条目数 |
| **OPML 导入** | 首次启动 `rss_sources` 为空时自动加载 `AV_Feeds.opml` | — |

### 分类体系（5 大板块）

| 分类 | 中文关键词 | 英文关键词 |
|------|-----------|-----------|
| 政策动态 | 政策, 新规, 补贴, 路测, 试点... | regulation, policy, legislation, NHTSA... |
| 企业落地 | 园区, 上线, 合作, 签约, 落地... | launch, deploy, partnership, commercial... |
| 技术动态 | 传感器, 调度, 算法, 车路协同... | LiDAR, radar, deep learning, V2X... |
| 招标采购 | 招标, 中标, 预算, 采购... | tender, bid, procurement, RFP... |
| 行业观点/海外资讯 | 专家, 趋势, 海外, 解读... | analysis, opinion, report, forecast... |

> 分类基于关键词子串匹配，非 NLP 模型，中英文均支持。

### 报告生成

| 格式 | 用途 |
|------|------|
| 公众号格式 (mp) | 微信公众号草稿箱（内联样式 + data-src 图片） |
| 纯文本 | Markdown 风格文字报告 |
| HTML 预览 | 网页端预览（白色背景 + 圆角卡片） |

### 资讯管理

- **分页显示**：每页 10 条，带数字页码（最多 7 个）
- **实时搜索**：250ms 防抖，匹配标题/来源/内容/分类
- **编辑/删除**：每条可修改或删除
- **历史归档**：已生成报告按日期存档，支持回溯

### 微信公众号发布

1. 配置 AppID / AppSecret
2. 生成报告预览
3. 一键发布到草稿箱
4. 登录 [mp.weixin.qq.com](https://mp.weixin.qq.com/) → 草稿箱 → 发布

> 需将服务器公网 IP 添加到微信公众号后台 IP 白名单。

---

## 目录结构

```
├── app.py              # Flask 服务 + REST API（18 个端点）
├── services.py         # 抓取/分类/报告/OPML/RSS 验证核心逻辑
├── storage.py          # JSON 文件存储管理
├── wechat.py           # 微信公众号 API 客户端（token/素材/草稿）
├── requirements.txt    # Python 依赖
├── AV_Feeds.opml       # RSS 订阅清单（20 个自动驾驶相关源）
├── Dockerfile
├── docker-compose.yml
├── docs/
│   └── requirements.md # 详细需求说明书
├── static/
│   ├── index.html      # 前端页面（4 步工作流 + sheet 标签）
│   ├── app.js          # 前端交互逻辑（分页/搜索/验证/发布）
│   ├── style.css       # 深色科技风 UI（玻璃拟态卡片）
│   └── thumbnail.png   # 公众号默认封面
├── data/               # 自动生成的配置/资讯/历史数据（已 gitignore）
├── memory/             # 开发交互记录
├── CLAUDE.md           # 项目规范
```

---

## API 接口

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /api/config | 获取配置（rss_sources 为空时自动从 OPML 导入） |
| POST | /api/config | 更新配置 |
| GET | /api/news | 获取全部资讯 |
| POST | /api/news | 手动录入 |
| PUT/DELETE | /api/news/\<id\> | 编辑/删除单条 |
| POST | /api/news/crawl | 抓取（网页 + RSS 并行） |
| POST | /api/news/clear | 清空全部 |
| POST | /api/news/classify | 文本分类 |
| POST | /api/channels/verify | 验证网页渠道连通性 |
| POST | /api/rss/verify | 验证 RSS 源连通性 |
| POST | /api/rss/remove | 删除 RSS 源 |
| POST | /api/rss/import-opml | 从 OPML 导入订阅源 |
| POST | /api/export | 生成报告（4 种格式） |
| POST | /api/wechat/publish | 发布到微信公众号草稿箱 |
| GET/DELETE | /api/history | 获取/清空历史报告 |
| POST | /api/template/reset | 恢复默认模板 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.14 + Flask 3 |
| 前端 | 原生 HTML5 / CSS3 (Glassmorphism) / JavaScript ES6+ |
| 存储 | 本地 JSON 文件 |
| 网页抓取 | requests + BeautifulSoup 4 + lxml |
| RSS 抓取 | feedparser + ThreadPoolExecutor（8 并发） |
| 部署 | Docker / Docker Compose |

---

## 数据持久化

```
data/
├── config.json   # 渠道/关键词/分类/模板/微信配置
├── news.json     # 所有资讯条目
└── history.json  # 历史报告存档
```

备份或迁移只需复制整个 `data/` 目录。


## 目标设备 Docker 部署与更新

适用于在一台**没有图形界面、没有 Python 环境、仅安装 Docker** 的目标服务器上部署和更新。

### 首次部署

```bash
# 1. 安装 Docker（如未安装）
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker && sudo systemctl start docker

# 2. 安装 Docker Compose Plugin（如未安装）
sudo apt install docker-compose-plugin   # Debian/Ubuntu
# 或
sudo dnf install docker-compose-plugin   # CentOS/RHEL

# 3. 克隆项目
git clone https://github.com/13510328056/CarInfo.git
cd CarInfo

# 4. 创建数据目录（重要：存放持久化数据）
mkdir -p data

# 5. 构建并启动（首次约 2-5 分钟）
docker compose up -d --build

# 6. 验证运行
docker ps                     # 确认容器状态
curl http://localhost:5000    # 测试 HTTP 响应
```

访问 `http://目标设备IP:5000` 即可打开系统页面。

### 从 GitHub 拉取更新

当代码有更新时，在目标设备上执行：

```bash
cd CarInfo

# 1. 停止当前容器
docker compose down

# 2. 拉取最新代码
git pull

# 3. 重新构建并启动
docker compose up -d --build

# 4. 确认更新成功
docker compose logs --tail=20
```

> 如果本地有未提交的修改导致 `git pull` 冲突，可用 `git stash` 暂存后再拉取，拉取完用 `git stash pop` 恢复。

### 日常管理

```bash
# 查看运行状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 查看最近 100 行日志
docker compose logs --tail=100

# 重启服务
docker compose restart

# 停止服务
docker compose down
```

### 数据持久化

系统数据存储在项目根目录的 `data/` 文件夹中，通过 Docker volume 挂载到容器内：

```yaml
volumes:
  - ./data:/app/data
```

| 文件 | 内容 | 备份建议 |
|------|------|---------|
| `data/config.json` | 渠道、关键词、分类、模板、微信配置 | 定期备份 |
| `data/news.json` | 所有抓取和录入的资讯 | 按需备份 |
| `data/history.json` | 历史报告存档 | 按需备份 |
| `data/classifier.pkl` | ML 分类器模型（自动训练） | 不重要 |

**迁移到新设备**：复制整个 `data/` 目录到新项目的相同位置，重启容器即可恢复所有数据。

### 网络与防火墙

如需从其他设备（如手机、同事电脑）访问，确保放行 5000 端口：

```bash
# Linux (firewalld)
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload

# Linux (iptables)
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT

# 云服务器（阿里云/腾讯云/AWS）
# 在云控制台的「安全组」或「防火墙」规则中添加入站 TCP 5000 端口
```

### 微信公众号 IP 白名单

如需一键发布到公众号，将**部署设备的公网 IP** 添加到微信公众号后台：

1. 查询公网 IP：`curl ifconfig.me`
2. 登录 [mp.weixin.qq.com](https://mp.weixin.qq.com/)
3. 进入 **设置 → 安全中心 → IP 白名单**
4. 添加查询到的公网 IP
5. 点击保存

> ⚠️ IP 白名单添加后约 **5 分钟生效**。如果服务器公网 IP 发生变化（如重启路由器），需重新添加。

---

## 微信公众号配置

1. 在 [mp.weixin.qq.com](https://mp.weixin.qq.com/) 获取 AppID 和 AppSecret
2. 在页面 **④ 导出发布 → 微信公众号配置** 中填写
3. 将服务器 IP 加入微信公众号 IP 白名单
4. 生成报告 → 一键发布到草稿箱
