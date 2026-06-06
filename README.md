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

目标设备需安装：

- [Docker](https://docs.docker.com/get-docker/)（版本 24.0+）
- [Docker Compose](https://docs.docker.com/compose/install/)（Docker Desktop 已内置，Linux 需单独安装）
- [Git](https://git-scm.com/downloads)

验证安装：

```bash
docker --version
docker compose version
git --version
```

### 部署步骤

**1. 克隆仓库到目标设备**

```bash
  git clone https://github.com/13510328056/CarInfo.git
cd CarInfo
```

> 如果目标设备没有公网访问权限，可通过 `git pull` 在有网络的设备上拉取后，用 U 盘等介质拷贝到目标设备。

**2. 编写配置文件（首次必须）**

```bash
# 创建 data 目录
mkdir -p data

# 创建配置文件（默认配置可运行，发布微信需填写 AppID/AppSecret）
cat > data/config.json << 'CONFIG'
{
  "wechat": {
    "appid": "",
    "appsecret": "",
    "name": ""
  }
}
CONFIG
```

也可不手动创建，启动系统后在浏览器页面中配置微信公众号参数。

**3. 构建并启动**

```bash
docker compose up -d
```

首次执行会自动构建镜像，耗时约 2-5 分钟（取决于网络）。后续启动秒级完成。

**4. 确认运行状态**

```bash
# 查看容器状态
docker ps

# 查看实时日志
docker compose logs -f

# 测试 HTTP 响应
curl http://localhost:5000
```

**5. 打开浏览器**

访问 `http://目标设备IP:5000`

### 常用命令

```bash
# 启动服务（后台）
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看日志（实时）
docker compose logs -f

# 查看日志（最近 100 行）
docker compose logs --tail=100

# 重新构建镜像并启动（代码更新后执行）
git pull
docker compose up -d --build
```

### 更新到最新版本

```bash
cd CarInfo
git pull                     # 拉取最新代码
docker compose up -d --build # 重新构建并启动
```

### 数据持久化

系统数据存储在 `data/` 目录中，通过 Docker volume 挂载到容器内：

```yaml
volumes:
  - ./data:/app/data
```

该目录包含：
- `config.json` — 抓取渠道、关键词、模板、微信配置等
- `news.json` — 所有抓取和录入的资讯数据
- `history.json` — 历史报告存档

**备份数据**只需复制整个 `data/` 目录；**迁移到新设备**时复制 `data/` 目录到新项目的相同位置即可。

### 网络与防火墙

如需从其他设备访问（如手机预览），确保目标设备防火墙放行 5000 端口：

```bash
# Linux (firewalld)
firewall-cmd --add-port=5000/tcp --permanent
firewall-cmd --reload

# Linux (iptables)
iptables -A INPUT -p tcp --dport 5000 -j ACCEPT

# Windows
netsh advfirewall firewall add rule name="CarInfo" dir=in action=allow protocol=TCP localport=5000
```

### 微信公众号 IP 白名单

如需一键发布到公众号，需将 **部署设备的公网 IP** 添加到微信公众号后台：

1. 登录 [mp.weixin.qq.com](https://mp.weixin.qq.com/)
2. 进入 **设置 → 安全中心 → IP白名单**
3. 添加部署设备的公网 IP（可通过 `curl ifconfig.me` 或 `curl ip.sb` 查询）
4. 点击保存

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
