# 资讯日报助手 — 软件需求说明书

## 1. 项目概述

### 1.1 产品定位
本地运行的 Web 应用，用于从多渠道（网页搜索、RSS 订阅）自动抓取行业资讯，通过关键词分类整理，生成可发布的日报报告（纯文本 / HTML / 公众号格式），并支持一键发布到微信公众号草稿箱。

### 1.2 核心流程（4 步工作流）

```
① 内容源设置 → ② 过滤配置 → ③ 抓取资讯 → ④ 内容管理与发布
```

### 1.3 技术栈
- **后端**: Python 3.14, Flask 3, requests, BeautifulSoup4, lxml, feedparser
- **前端**: 原生 HTML5 / CSS3 / JavaScript (ES6+)
- **存储**: 本地 JSON 文件 (data/ 目录)
- **集成**: 微信公众号 API (草稿箱)

---

## 2. 数据模型

### 2.1 配置 (data/config.json)

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `channels` | string[] | 网页抓取渠道 URL 列表 | 10 个默认搜索引擎/行业站 |
| `keywords` | string[] | 网页抓取搜索关键词 | 12 个中文无人车关键词 |
| `categories` | object | 分类关键词映射表 | 5 个分类，每个含中英文关键词 |
| `template` | object | 报告模板配置 | 标题样式、话术等 |
| `wechat` | object | 微信公众号凭证 | appid, appsecret, name |
| `rss_sources` | string[] | RSS 订阅源 URL 列表 | 自动从 OPML 导入 |

### 2.2 分类关键词体系（5 大板块）

每个分类同时支持中英文关键词（子串匹配，不区分大小写）：

| 分类 | 中文关键词 | 英文关键词 |
|------|-----------|-----------|
| 政策动态 | 政策, 新规, 补贴, 路测, 试点, 规范, 公告, 安全运营 | regulation, policy, legislation, regulatory, permit, approval, certification, NHTSA, safety standard, government, legal, law |
| 企业落地 | 园区, 上线, 合作, 签约, 落地, 投放, 运营, 项目 | launch, deploy, partnership, rollout, commercial, pilot, investment, funding, service, delivery, operation |
| 技术动态 | 传感器, 调度, 算法, 平台, 车路协同, 续航, 避障, AI | LiDAR, radar, computer vision, deep learning, perception, HD map, V2X, connectivity, chip, SoC, software, simulation, neural network, sensor, algorithm, transformer, OTA |
| 招标采购 | 招标, 中标, 预算, 采购, 公告, 服务需求 | tender, bid, procurement, contract, RFP, vendor, supplier |
| 行业观点/海外资讯 | 专家, 趋势, 海外, 解读, 观点, 案例, 行业观察 | analysis, opinion, report, forecast, market, research, insight, survey, outlook, trend |

### 2.3 资讯条目 (data/news.json)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一 ID (news_YYYYMMDD_NNN) |
| `title` | string | 文章标题（已清洗网站后缀） |
| `publish_time` | string | 发布时间（自由格式） |
| `source` | string | 来源域名或 Feed 标题 |
| `content` | string | 纯文本摘要（≤500 字符） |
| `image_url` | string | OG 缩略图 URL |
| `category` | string | 自动分类结果 |
| `keywords` | string[] | 使用的关键词 |
| `url` | string | 原文链接 |
| `created_at` | string | ISO 时间戳 |

### 2.4 历史报告 (data/history.json)

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 报告日期 |
| `report` | object | 含 format 和 report 字段 |
| `saved_at` | string | ISO 时间戳 |

---

## 3. API 接口

| 路由 | 方法 | 功能 | 请求参数 | 返回说明 |
|------|------|------|---------|---------|
| `/` | GET | 前端首页 | — | index.html |
| `/api/config` | GET | 获取配置 | — | 完整配置对象 |
| `/api/config` | POST | 更新配置 | channels, keywords, categories, template, rss_sources | 更新后的配置 |
| `/api/news` | GET | 获取全部资讯 | — | 资讯数组 |
| `/api/news` | POST | 手动录入 | title, source, publish_time, category, content | 新建的条目 |
| `/api/news/clear` | POST | 清空全部 | — | 成功/失败 |
| `/api/news/<id>` | PUT | 编辑单条 | title, source, publish_time, category, content | 更新后的条目 |
| `/api/news/<id>` | DELETE | 删除单条 | — | 成功/失败 |
| `/api/news/crawl` | POST | 抓取资讯 | channel_urls, rss_urls, keywords, category_keywords, time_range | 抓取结果 + 新增计数 |
| `/api/channels/verify` | POST | 验证网页渠道 | channel_urls, keywords | 各渠道状态 (ok/weak/fail) |
| `/api/rss/import-opml` | POST | 导入 OPML | — | 导入统计 |
| `/api/rss/verify` | POST | 验证 RSS 源 | urls | 各源状态 (ok/fail) + 标题/条目数 |
| `/api/rss/remove` | POST | 删除 RSS 源 | url | 更新后的 rss_sources |
| `/api/news/classify` | POST | 文本分类 | news_title, news_content, category_keywords | 推荐分类 + 匹配率 |
| `/api/export` | POST | 生成报告 | format, news_items, template, attention_text, title_style, closing_style | 报告内容 (text/html/mp) |
| `/api/wechat/publish` | POST | 发布到公众号 | news_items, attention_text, title_style, closing_style | media_id |
| `/api/history` | GET | 获取历史 | — | 历史报告数组 |
| `/api/history` | DELETE | 清空历史 | — | 成功/失败 |
| `/api/template/reset` | POST | 重置模板 | — | 更新后的配置 |

---

## 4. 后端逻辑

### 4.1 网页抓取 (crawl_channels)

**流程**:
1. 遍历 channels 中的每个 URL
2. 根据页面类型分流：
   - **文章页** → 直接 `extract_news_from_html()` 提取结构化数据
   - **百度新闻搜索页** → `parse_baidu_news()` 从 s-data JSON 解析
   - **普通列表页** → `_extract_article_links()` 提取链接 → 逐条 `crawl_article_page()`
3. 过滤条件：摘要 ≥ 80 字符 + 关键词匹配 > 0 或含核心词
4. URL 去重后返回

**反爬检测**: 检查 Cloudflare challenge、reCAPTCHA 等信号（响应 < 30KB）

### 4.2 RSS 抓取 (crawl_rss_feeds)

**特征**:
- 并行抓取（ThreadPoolExecutor，默认 8 并发）
- 每个 Feed 超时 20s
- 不额外关键词过滤（RSS 源本身有针对性）
- 仅受 time_range 约束
- 复用现有分类器进行分类

### 4.3 分类器 (classify_news)

**算法**: 纯关键词子串匹配，统计每个分类的关键词命中数，最高分获胜。
**兜底**: 默认分类「行业观点/海外资讯」
**分数**: `min(100, 命中数 × 20)`

### 4.4 报告生成

支持四种格式：

| 格式 | 生成函数 | 用途 |
|------|---------|------|
| 纯文本 | `build_report_text()` | Markdown 风格文本 |
| HTML | `build_report_html()` | 网页预览（白色背景+圆角卡片） |
| 公众号文本 | `build_report_mp()` | 微信编辑器文本 |
| 公众号 HTML | `build_report_mp_html()` | 发布到微信草稿箱（含 data-src 图片+内联样式） |

**报告结构**:
1. 标题（可配置）
2. 今日速览（前 3 条）
3. 按分类分组展示（政策动态 / 企业落地 / 招标采购 / 技术动态 / 行业观点）
4. 明日关注
5. 结尾话术（可配置）

### 4.5 OPML 导入

- 文件路径: `./AV_Feeds.opml`
- 解析标准 OPML 2.0 格式（支持嵌套 outline）
- 去重后合并到 `rss_sources`
- 首次配置加载时自动导入（若 rss_sources 为空）

### 4.6 微信公众号发布

**流程**:
1. 获取 access_token（自动缓存 2h）
2. 上传缩略图（从 static/thumbnail.png 或生成占位图）
3. 调用 `/cgi-bin/draft/add` 创建草稿
4. 标题截断 ≤30 字节，摘要截断 ≤60 字节

---

## 5. 前端 UI

### 5.1 页面布局（4 步工作流）

```
┌─ ① 内容源设置 ────────────── (蓝色 #00b4d8) ─┐
│  [🌐 网页抓取 | 📡 RSS 订阅] (sheet 标签)      │
│  ├─ 网页抓取：渠道 URL + 关键词 + 验证按钮       │
│  └─ RSS 订阅：Feed URL + 导入 + 验证 + 删除     │
└──────────────────────────────────────────────┘

┌─ ② 过滤配置 ──────────────── (绿色 #07c160) ─┐
│  分类关键词 + [保存配置] [恢复默认]              │
└──────────────────────────────────────────────┘

┌─ ③ 抓取资讯 ──────────────── (琥珀 #f59e0b) ─┐
│  [🚀 开始抓取] + 结果（分页 10 条/页）           │
└──────────────────────────────────────────────┘

┌─ ④ 内容管理与发布 ─────────── (紫色 #a855f7) ─┐
│  [📋 内容管理 | 📤 导出发布] (sheet 标签)        │
│  ├─ 内容管理：手动录入 + 资讯列表(分页) + 历史    │
│  └─ 导出发布：报告生成 + 公众号配置               │
└──────────────────────────────────────────────┘
```

### 5.2 设计系统

| 属性 | 值 |
|------|-----|
| 主题 | 深色科技风（深蓝渐变背景 #0a1628 → #121e33） |
| 卡片 | 玻璃拟态（`backdrop-filter: blur(12px)`, 半透明边框） |
| 强调色 | 青色 (#00b4d8)、绿色 (#07c160)、琥珀 (#f59e0b)、紫色 (#a855f7) |
| 圆角 | 14px (卡片), 10px (输入框/按钮) |
| 字体 | system-ui, Microsoft YaHei, PingFang SC |

### 5.3 Sheet 标签页

多处使用「Excel 式 sheet 标签」切换：

| 所在区域 | 标签 1 | 标签 2 |
|---------|--------|--------|
| ① 内容源设置 | 🌐 网页抓取 | 📡 RSS 订阅 |
| ④ 内容管理与发布 | 📋 内容管理 | 📤 导出发布 |

### 5.4 资讯列表功能

- **分页**: 每页 10 条，显示页码按钮（最多 7 个），当前页高亮
- **搜索**: 实时搜索（250ms 防抖），匹配标题/来源/内容/分类
- **编辑**: 每条可编辑（标题/来源/时间/分类/内容）或删除
- **清空**: 确认后清空全部

### 5.5 抓取结果

- **分页**: 每页 10 条，页码按钮风格与资讯列表一致
- **标记**: RSS 来源文章显示橙色 RSS 标签

### 5.6 验证功能

| 验证 | 位置 | 显示 |
|------|------|------|
| 网页渠道连通性 | 内容源设置 → 网页抓取 | PASS/WEAK/FAIL 徽标 + HTTP 状态 |
| RSS 源连通性 | 内容源设置 → RSS 订阅 | PASS/FAIL 徽标 + Feed 标题 + 条目数 |
| 验证结果 | 滚动容器（最大 5 行），超出滚动 |

### 5.7 手动录入

表单字段：标题、来源、发布时间、分类（下拉选择 5 类）、内容文本区。

---

## 6. 分类逻辑

### 6.1 网页抓取分类
- 爬取时对每篇文章调用 `classify_news(title, content, category_keywords)`
- 分类结果存储在 article 的 `category` 字段

### 6.2 RSS 分类
- RSS 条目在 `_fetch_single_feed()` 中调用同一分类器
- 中英文关键词均参与匹配

### 6.3 关键词列表

| 用途 | 配置字段 | 说明 |
|------|---------|------|
| 网页抓取过滤 | `keywords` | 12 个中文词，如「园区无人车」 |
| 分类匹配 | `categories` | 5 组中英文关键词，每组 13-25 个词 |
| RSS 不过滤 | — | RSS 内容全部保留，不做关键词过滤 |

---

## 7. 部署与运行

### 7.1 启动方式
```bash
pip install -r requirements.txt
python app.py
# 访问 http://localhost:5000
```

### 7.2 依赖
```
Flask>=2.3, requests>=2.31, beautifulsoup4>=4.12,
lxml>=4.9, feedparser>=6.0
```

### 7.3 数据文件
| 文件 | 用途 | 创建时机 |
|------|------|---------|
| `data/config.json` | 系统配置 | 首次启动自动创建 |
| `data/news.json` | 资讯数据 | 首次抓取或录入 |
| `data/history.json` | 历史报告 | 首次导出 |
| `AV_Feeds.opml` | RSS 订阅清单 | 手动维护 |

---

## 8. 约束与设计决策

1. **纯本地运行**，无外部数据库依赖
2. **JSON 文件存储**，读写-修改-写入模式，无事务保障
3. **关键词分类**，非 NLP/ML 模型
4. **网页抓取用 requests + BeautifulSoup**，未使用 Selenium/Playwright
5. **RSS 并行抓取**（8 线程），非串行
6. **前端无框架**，原生 JS + CSS3
7. **微信发布**依赖官方 API，需自行申请 AppID 和 AppSecret
8. **OPML 自动导入**仅在 rss_sources 为空时触发
