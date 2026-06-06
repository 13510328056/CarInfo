import json
import random
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup, FeatureNotFound

CATEGORY_ORDER = [
    "政策动态",
    "企业落地",
    "技术动态",
    "招标采购",
    "行业观点/海外资讯"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.97"
]


def _random_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0"
    }


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split()) if text else ""


def shorten_url(url: str, max_len: int = 30) -> str:
    """缩短过长的 URL 用于排版显示，只保留域名 + 关键路径片段。"""
    if not url:
        return ""
    if len(url) <= max_len + 10:
        return url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        if len(path) > 15:
            path = path[:12] + "…"
        short = f"{domain}{path}" if path else domain
        return short if len(short) <= max_len else short[:max_len] + "…"
    except Exception:
        return url[:max_len] + "…" if len(url) > max_len else url


_SKIP_IMG_PATTERNS = re.compile(
    r"logo|icon|avatar|wechat|qrcode|scalecode|label_sm|wuzhangai|banner|sprite|placeholder|loading|footer|header",
    re.I
)


def _is_content_image(img_url: str) -> bool:
    """判断图片 URL 是否可能是文章内容图（而非 logo/图标）。"""
    if not img_url:
        return False
    if not img_url.startswith("http"):
        return False
    if _SKIP_IMG_PATTERNS.search(img_url):
        return False
    # 跳过常见的小尺寸图标路径
    skip_paths = ["/static/media/", "/_next/static/", "/assets/", "/images/icons/"]
    for p in skip_paths:
        if p in img_url:
            return False
    return True


def extract_og_image(soup: BeautifulSoup, base_url: str = "") -> str:
    """从文章页面提取 OG 缩略图 URL，逐级降级。"""
    # 1. og:image
    meta = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
    if meta and meta.get("content"):
        img_url = meta["content"].strip()
        if _is_content_image(img_url):
            return img_url
        if base_url:
            full = urljoin(base_url, img_url)
            if _is_content_image(full):
                return full
    # 2. twitter:image
    meta = soup.find("meta", attrs={"name": "twitter:image"})
    if meta and meta.get("content"):
        img_url = meta["content"].strip()
        if _is_content_image(img_url):
            return img_url
        if base_url:
            full = urljoin(base_url, img_url)
            if _is_content_image(full):
                return full
    # 3. article 容器内的第一张内容图
    article = soup.find("article") or soup.find("div", class_=re.compile(r"article|content|post|news|main", re.I))
    if article:
        for img in article.find_all("img"):
            src = img.get("src", "").strip() or img.get("data-src", "").strip()
            if src:
                full = urljoin(base_url, src) if base_url else src
                if _is_content_image(full):
                    return full
    # 4. 页面上任一内容图
    for img in soup.find_all("img"):
        src = img.get("src", "").strip() or img.get("data-src", "").strip()
        if src:
            full = urljoin(base_url, src) if base_url else src
            if _is_content_image(full):
                return full
    return ""


def make_soup(html: str):
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")


def count_keywords(text: str, keywords):
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def extract_publish_time(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r"(\d{4}[./\-]\d{1,2}[./\-]\d{1,2})",
        r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})",
        r"(\d{4}年\d{1,2}月\d{1,2}日)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _clean_title(title: str) -> str:
    """清理标题：去除网站后缀、多余空格。"""
    if not title:
        return ""
    title = normalize_text(title)
    # 去除常见的网站后缀分隔符
    for sep in [" _ ", " - ", " | ", "| ", " |", "_澎湃", " - 澎湃", "_中国", "_直播", "_总编", "_汽"]:
        idx = title.find(sep)
        if idx > 0:
            suffix = title[idx + len(sep):]
            if len(suffix) < 12 or any(kw in suffix for kw in ["网", "新闻", "The Paper", "澎湃", "媒体", "频道", "客户端", "直播", "总编辑", "汽车报", "日报", "晚报", "快讯", "周刊", "现场", "汽车"]):
                title = title[:idx]
                break
    return normalize_text(title)


def extract_article_summary(soup: BeautifulSoup) -> str:
    paragraphs = []
    article = soup.find("article")
    container = article if article else soup.find("div", class_=re.compile("article|content|post|news|main", re.I))
    if container:
        for p in container.find_all("p"):
            text = normalize_text(p.get_text())
            if text:
                paragraphs.append(text)
            if len(paragraphs) >= 4:
                break
    if not paragraphs:
        # Fallback: 找正文区域 —— 任意含 5+ 个长段落（>40字）的元素
        for el in soup.find_all(["div", "article", "section"]):
            ps = el.find_all("p")
            long_ps = [p for p in ps if len(p.get_text().strip()) > 40]
            if len(long_ps) >= 5:
                for p in long_ps[:4]:
                    text = normalize_text(p.get_text())
                    if text:
                        paragraphs.append(text)
                break
    if not paragraphs:
        for p in soup.find_all("p")[:4]:
            text = normalize_text(p.get_text())
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_title(soup: BeautifulSoup, url: str) -> str:
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text()
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text() if h1 else url
    return _clean_title(title)


def extract_source(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.replace("www.", "")
        return host
    except Exception:
        return url


def classify_news(title: str, content: str, category_keywords: dict):
    best_category = "行业观点/海外资讯"
    best_score = 0
    text = f"{title}\n{content}"
    for category, keywords in category_keywords.items():
        score = count_keywords(text, keywords)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category, min(100, best_score * 20)


def extract_publish_time_from_soup(soup: BeautifulSoup) -> str:
    candidates = []
    for meta_name in ["publishdate", "pubdate", "article:published_time", "date", "Date"]:
        meta = soup.find("meta", attrs={"name": meta_name}) or soup.find("meta", attrs={"property": meta_name})
        if meta and meta.get("content"):
            date_text = extract_publish_time(meta["content"])
            if date_text:
                return date_text
    for time_tag in soup.find_all(["time", "span"]):
        text = normalize_text(time_tag.get_text())
        if text and re.search(r"\d{4}|\d{1,2}月", text):
            date_text = extract_publish_time(text)
            if date_text:
                return date_text
    return ""


def extract_news_from_html(url: str, html: str, keywords: list, category_keywords: dict = None):
    soup = make_soup(html)
    title = extract_title(soup, url)
    source = extract_source(url)
    publish_time = extract_publish_time_from_soup(soup)
    content = extract_article_summary(soup)
    image_url = extract_og_image(soup, url)
    keyword_count = count_keywords(f"{title}\n{content}", keywords)
    keyword_match = int(min(100, keyword_count / max(1, len(keywords)) * 100))
    category = None
    if category_keywords:
        category, _ = classify_news(title, content, category_keywords)
    return {
        "title": title,
        "source": source,
        "publish_time": publish_time,
        "content": content,
        "image_url": image_url,
        "keyword_match": keyword_match,
        "url": url,
        "category": category or "行业观点/海外资讯"
    }


def _normalize_link(base_url: str, href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("#"):
        return ""
    if href.lower().startswith("http"):
        return href
    try:
        return urljoin(base_url, href)
    except Exception:
        return ""


def _is_article_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    skip_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js', '.ico', '.pdf', '.zip', '.rar', '.mp4', '.mp3')
    if any(lower.endswith(ext) for ext in skip_extensions):
        return False
    if 'search' in lower and ('query' in lower or 'wd=' in lower or 'q=' in lower):
        return False
    return True


def _extract_article_links(html: str, base_url: str, keywords: list) -> list:
    soup = make_soup(html)
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = _normalize_link(base_url, a["href"])
        if not href or href in seen or not _is_article_url(href):
            continue
        seen.add(href)
        text = normalize_text(a.get_text())
        if len(text) < 8 and not any(kw.lower() in href.lower() for kw in keywords):
            continue
        if urlparse(href).netloc and urlparse(href).netloc != urlparse(base_url).netloc:
            if not any(kw.lower() in href.lower() for kw in keywords):
                continue
        links.append((href, text))
        if len(links) >= 12:
            break
    return [href for href, _ in links]


def _is_article_page(html: str) -> bool:
    soup = make_soup(html)
    content = extract_article_summary(soup)
    if not content:
        return False
    if len(content) > 220:
        return True
    if soup.find("article") is not None:
        return True
    return False


def crawl_article_page(url: str, keywords: list, category_keywords: dict = None, time_range: dict = None) -> dict:
    response = requests.get(url, headers=_random_headers(), timeout=15)
    response.raise_for_status()
    if 'text/html' not in response.headers.get('Content-Type', ''):
        return None
    item = extract_news_from_html(url, response.text, keywords, category_keywords)
    if not item['content'] or len(item['content']) < 80:
        return None
    # 至少命中 1 个关键词才保留，避免搜罗无关内容
    if keywords and item.get("keyword_match", 0) == 0:
        # 但放宽：标题或内容包含"无人"、"自动驾"等核心词也算
        combined = (item.get("title", "") + item.get("content", "")).lower()
        core_kws = ["无人", "自动驾驶", "自动驾", "robotaxi", "robovan", "cybercab", "园区", "接驳", "巡检", "配送", "环卫"]
        if not any(kw in combined for kw in core_kws):
            return None
    if time_range:
        pub_time = item.get("publish_time", "")
        if pub_time and not _is_within_time_range(pub_time, time_range):
            return None
    return item


def parse_baidu_news(html: str, keywords: list, category_keywords: dict = None) -> list:
    """
    解析百度新闻搜索结果页（?tn=news），从 ``s-data`` JSON 中提取结构化新闻条目。
    返回列表，每项包含 title / content / source / publish_time / image_url / url / keyword_match / category。
    """
    soup = make_soup(html)
    items = []
    seen_urls = set()

    # 查找所有新闻结果容器（tpl="news-normal"）
    for result in soup.find_all("div", class_="result-op"):
        if result.get("tpl") != "news-normal":
            continue

        # 从 HTML 注释中提取 s-data JSON
        html_str = str(result)
        match = re.search(r'<!--s-data:({.*?})-->', html_str, re.DOTALL)
        if not match:
            continue

        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, KeyError):
            continue

        title_raw = data.get("title", "")
        article_url = data.get("titleUrl", "")
        summary = data.get("summary", "")
        source = data.get("sourceName", "")
        disp_time = data.get("dispTime", "")
        img_url = data.get("leftImgSrc", "")

        if not title_raw or not article_url or article_url in seen_urls:
            continue
        seen_urls.add(article_url)

        # 清理标题（去除 <em> 标签）
        title = re.sub(r'<[^>]+>', "", title_raw).strip()

        # 清理摘要
        content = re.sub(r'<[^>]+>', "", summary).strip() if summary else ""

        # 关键词匹配
        keyword_count = count_keywords(f"{title}\n{content}", keywords)
        keyword_match = int(min(100, keyword_count / max(1, len(keywords)) * 100))

        # 分类
        category = None
        if category_keywords:
            category, _ = classify_news(title, content, category_keywords)

        items.append({
            "title": title,
            "source": source or extract_source(article_url),
            "publish_time": disp_time,
            "content": content,
            "image_url": img_url if img_url and img_url.startswith("http") else "",
            "keyword_match": keyword_match,
            "url": article_url,
            "category": category or "行业观点/海外资讯",
            "_from_baidu_news": True,  # 标记来源，后续可爬取全文
        })

    return items


def _is_within_time_range(pub_time: str, time_range: dict) -> bool:
    """Check if publish_time falls within the given time_range {start, end}."""
    start_str = time_range.get("start", "")
    end_str = time_range.get("end", "")
    if not start_str and not end_str:
        return True
    try:
        from datetime import datetime as dt
        pub = dt.strptime(pub_time[:10], "%Y-%m-%d") if pub_time else None
        if not pub:
            return True
        if start_str:
            start = dt.strptime(start_str[:10], "%Y-%m-%d")
            if pub < start:
                return False
        if end_str:
            end = dt.strptime(end_str[:10], "%Y-%m-%d")
            if pub > end:
                return False
    except (ValueError, IndexError):
        pass
    return True


def crawl_channels(channel_urls: list, keywords: list, category_keywords: dict = None, time_range: dict = None) -> dict:
    results = []
    details = []
    for url in channel_urls:
        detail = {"url": url, "status": "fail", "status_code": None, "error": None, "article_count": 0}
        try:
            response = requests.get(url, headers=_random_headers(), timeout=15)
            detail["status_code"] = response.status_code
            response.raise_for_status()
            base_html = response.text
            if _is_article_page(base_html):
                item = extract_news_from_html(url, base_html, keywords, category_keywords)
                detail["status"] = "ok" if item["keyword_match"] > 0 else "no_match"
                detail["article_count"] = 1
                if item["keyword_match"] > 0:
                    if time_range and not _is_within_time_range(item.get("publish_time", ""), time_range):
                        detail["status"] = "out_of_range"
                    else:
                        results.append(item)
            else:
                # 百度新闻搜索结果页 → 使用专用解析器（从 s-data JSON 提取结构化数据）
                if "baidu.com/s" in url and "tn=news" in url:
                    baidu_items = parse_baidu_news(base_html, keywords, category_keywords)
                    article_count = 0
                    for item in baidu_items:
                        if item.get("keyword_match", 0) < 20:
                            continue
                        # 核心词兜底检查
                        combined = (item.get("title", "") + item.get("content", "")).lower()
                        core_kws = ["无人车", "无人驾驶", "自动驾驶", "robotaxi", "robovan", "园区", "接驳", "巡检", "配送", "环卫", "激光雷达"]
                        if not any(kw in combined for kw in core_kws):
                            continue
                        # 去重
                        if any(existing.get("url") == item["url"] for existing in results):
                            continue
                        results.append(item)
                        article_count += 1
                    detail["status"] = "ok" if article_count > 0 else "no_match"
                    detail["article_count"] = article_count
                else:
                    candidates = _extract_article_links(base_html, url, keywords)
                    article_count = 0
                    for article_url in candidates[:12]:
                        try:
                            article = crawl_article_page(article_url, keywords, category_keywords, time_range)
                            if article:
                                article_count += 1
                                results.append(article)
                        except Exception:
                            continue
                    detail["status"] = "ok" if article_count > 0 else "no_match"
                    detail["article_count"] = article_count
        except Exception as e:
            detail["error"] = str(e)
            detail["status"] = "fail"
        details.append(detail)
    unique_results = []
    seen_links = set()
    for item in results:
        if item.get("url") and item["url"] not in seen_links:
            unique_results.append(item)
            seen_links.add(item["url"])
    return {
        "results": unique_results,
        "details": details,
        "total": len(channel_urls),
        "succeeded": sum(1 for d in details if d["status"] == "ok")
    }


ANTI_SCRAPING_SIGNALS = [
    "Just a moment...",
    "cf-browser-verification",
    "__cf_chl_opt",
    "challenge-platform",
    "Checking your browser",
    "g-recaptcha",
    "cf-marker"
]


def verify_channel(url: str, keywords: list) -> dict:
    """Test a single channel URL for accessibility and parseability."""
    result = {"url": url, "status": "fail", "status_code": None, "response_size_kb": 0,
              "parseable": False, "keyword_match": 0, "anti_scraping_detected": False, "message": ""}
    try:
        resp = requests.get(url, headers=_random_headers(), timeout=15, allow_redirects=True)
        result["status_code"] = resp.status_code
        result["response_size_kb"] = round(len(resp.content) / 1024, 1)

        # Anti-scraping detection: challenge pages are typically small (< 30KB)
        text_lower = resp.text.lower()
        for signal in ANTI_SCRAPING_SIGNALS:
            if signal.lower() in text_lower and len(resp.content) < 30 * 1024:
                result["anti_scraping_detected"] = True
                result["message"] = f"检测到反爬机制: {signal}"
                break

        if result["anti_scraping_detected"]:
            result["status"] = "fail"
        elif resp.status_code >= 400:
            result["message"] = result["message"] or f"HTTP {resp.status_code}"
        else:
            news_item = extract_news_from_html(url, resp.text, keywords)
            article_content_ok = bool(news_item["title"]) and len(news_item["content"]) > 50
            has_keyword_match = news_item["keyword_match"] > 0

            result["parseable"] = article_content_ok or has_keyword_match
            result["keyword_match"] = news_item["keyword_match"]

            if article_content_ok and has_keyword_match:
                result["status"] = "ok"
                result["message"] = f"可正常抓取，关键词匹配 {result['keyword_match']}%"
            elif has_keyword_match:
                result["status"] = "weak"
                result["message"] = f"页面含关键词({result['keyword_match']}%)但内容提取不完整（大小: {result['response_size_kb']}KB）"
            elif result["parseable"]:
                result["status"] = "weak"
                result["message"] = f"页面可解析但未命中关键词（大小: {result['response_size_kb']}KB）"
            else:
                result["status"] = "weak"
                result["message"] = f"页面返回 {resp.status_code}，但内容提取为空（大小: {result['response_size_kb']}KB）"
    except requests.Timeout:
        result["message"] = "请求超时（15s）"
    except requests.ConnectionError as e:
        result["message"] = f"连接失败: {str(e)[:60]}"
    except Exception as e:
        result["message"] = f"验证异常: {str(e)[:60]}"
    finally:
        print(f"[verify_channel] url={url} status={result['status']} code={result['status_code']} size_kb={result['response_size_kb']} keyword_match={result['keyword_match']} anti_scraping={result['anti_scraping_detected']} message={result['message']}")
    return result




# ─── RSS / OPML 支持 ────────────────────────────────────────────────────────


def _strip_html_tags(text: str) -> str:
    """Remove HTML tags from RSS summary/description and unescape entities."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return unescape(clean)


def _rss_date_to_str(struct_time) -> str:
    """Convert feedparser time.struct_time to 'YYYY年M月D日' format."""
    if not struct_time:
        return ""
    try:
        return f"{struct_time.tm_year}年{struct_time.tm_mon}月{struct_time.tm_mday}日"
    except (AttributeError, ValueError):
        return ""


def parse_opml(filepath: str) -> list:
    
    feeds = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError, Exception) as e:
        print(f"[parse_opml] fail: {e}")
        return feeds
    body = root.find("body")
    if body is None:
        return feeds
    def _walk(parent):
        for child in parent:
            tag = child.tag.lower() if child.tag else ""
            if tag == "outline":
                url = (child.get("xmlUrl") or "").strip()
                txt = (child.get("text") or child.get("title") or "").strip()
                if url and (url.startswith("http://") or url.startswith("https://")):
                    feeds.append((txt, url))
                _walk(child)
    _walk(body)
    seen = set()
    result = []
    for t, u in feeds:
        if u not in seen:
            seen.add(u)
            result.append((t, u))
    return result


def _fetch_single_feed(url: str, category_keywords: dict, time_range: dict, timeout: int = 20) -> list:
    
    articles = []
    try:
        resp = requests.get(url, headers=_random_headers(), timeout=timeout)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            return []
        feed_title = feed.feed.get("title", "") or extract_source(url)
        for entry in feed.entries:
            title = normalize_text(entry.get("title", ""))
            link = entry.get("link", "")
            if not title or not link:
                continue
            raw = entry.get("summary", "") or entry.get("description", "")
            content = _strip_html_tags(raw)
            pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            publish_time = _rss_date_to_str(pub_struct)
            if time_range and publish_time and not _is_within_time_range(publish_time, time_range):
                continue
            source = feed_title or extract_source(link)
            image_url = ""
            if "media_content" in entry:
                for media in entry.media_content:
                    mt = media.get("type", "")
                    md = media.get("medium", "")
                    if md == "image" or mt.startswith("image/"):
                        image_url = media.get("url", "")
                        break
            if not image_url and "links" in entry:
                for lnk in entry.links:
                    if lnk.get("rel") == "enclosure" and lnk.get("type", "").startswith("image/"):
                        image_url = lnk.get("href", "")
                        break
            if not image_url and "media_thumbnail" in entry:
                thumb = entry.media_thumbnail
                if isinstance(thumb, list) and thumb:
                    image_url = thumb[0].get("url", "")
            category = "行业观点/海外资讯"
            if category_keywords:
                category, _ = classify_news(title, content, category_keywords)
            articles.append({
                "title": title, "source": source, "publish_time": publish_time,
                "content": content[:500], "image_url": image_url,
                "keyword_match": 0, "url": link, "category": category, "_from_rss": True,
            })
    except Exception:
        pass
    return articles


def crawl_rss_feeds(rss_urls: list, category_keywords: dict = None, time_range: dict = None, max_workers: int = 8) -> dict:
    
    results = []
    errors = []
    total = len(rss_urls)
    if not rss_urls:
        return {"results": [], "errors": [], "total": 0}
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_map = {}
        for url in rss_urls:
            fut = pool.submit(_fetch_single_feed, url, category_keywords, time_range)
            fut_map[fut] = url
        for fut in as_completed(fut_map):
            url = fut_map[fut]
            try:
                arts = fut.result()
                if arts:
                    results.extend(arts)
            except Exception as exc:
                errors.append({"url": url, "error": str(exc)[:100]})
    return {"results": results, "errors": errors, "total": total}


def verify_rss_feed(url: str, timeout: int = 15) -> dict:
    
    result = {"url": url, "status": "fail", "feed_title": "", "entry_count": 0, "status_code": None, "error": ""}
    try:
        resp = requests.get(url, headers=_random_headers(), timeout=timeout)
        result["status_code"] = resp.status_code
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            result["error"] = f"XML parse error: {feed.bozo_exception}"
            return result
        result["feed_title"] = feed.feed.get("title", "") or extract_source(url)
        result["entry_count"] = len(feed.entries)
        result["status"] = "ok"
        if feed.entries:
            result["last_title"] = normalize_text(feed.entries[0].get("title", ""))[:60]
        if hasattr(feed.feed, "updated_parsed") and feed.feed.updated_parsed:
            from time import mktime
            from datetime import datetime as dt
            result["last_update"] = dt.fromtimestamp(mktime(feed.feed.updated_parsed)).strftime("%Y-%m-%d %H:%M")
    except requests.Timeout:
        result["error"] = "timeout (15s)"
    except Exception as e:
        result["error"] = str(e)[:60]
    return result
CATEGORY_EMOJI = {
    "政策动态": "\U0001f4cb",       # 📋
    "企业落地": "\U0001f697",       # 🚗
    "技术动态": "\U0001f4c8",       # 📈
    "招标采购": "\U0001f4a1",       # 💡
    "行业观点/海外资讯": "\U0001f310", # 🌐
}

SCENARIO_KEYWORDS = {
    "接驳": "▫️ 接驳场景",
    "巡检": "▫️ 巡检场景",
    "配送": "▫️ 配送/环卫场景",
    "环卫": "▫️ 配送/环卫场景",
    "物流": "▫️ 配送/环卫场景",
    "快递": "▫️ 配送/环卫场景",
}

TITLE_TEMPLATES = [
    "【园区无人车·{month}月{day}日资讯日报】｜政策更新+园区落地+招标动态",
]

CLOSING_OPTIONS = [
    "每日更新园区无人车核心资讯，聚焦封闭场景自动驾驶落地，关注我，解锁更多行业干货～",
    "留言区聊聊你最关注的园区无人车场景（接驳/巡检/配送），后续将重点跟进相关资讯！",
]


def _render_title(template: dict, news_count: int) -> str:
    """根据模板配置渲染标题。"""
    now = datetime.now()
    month = now.month
    day = now.day
    count = news_count

    title_templates = template.get("title_options", TITLE_TEMPLATES)
    idx = template.get("title_selected", 0)
    if idx < 0 or idx >= len(title_templates):
        idx = 0

    tpl = title_templates[idx]
    highlights = "园区落地+政策+招标"

    # 从模板中的{highlights}占位推断是否需要从news_items取
    if "{highlights}" in tpl:
        # 取前2条标题拼接成看点
        pass  # 由调用方通过字符串替换完成

    title = tpl.replace("{month}", str(month)).replace("{day}", str(day)).replace("{count}", str(count))
    return title, idx


def _render_policy_item(item: dict, num: int) -> list:
    """政策动态：XX月XX日，[内容]，来源：[来源]"""
    date_prefix = item.get("publish_time", "")
    if date_prefix and len(date_prefix) >= 5:
        # 取月日部分
        parts = date_prefix.split("-")
        if len(parts) == 3:
            date_prefix = f"{int(parts[1])}月{int(parts[2])}日"
        else:
            date_prefix = ""
    content = item["content"][:120]
    if len(item["content"]) > 120:
        content += "…"
    url_extra = f" 📎{shorten_url(item.get('url', ''))}" if item.get("url") else ""
    if date_prefix:
        line = f"{num}. {date_prefix}，{content}，来源：{item['source']}{url_extra}"
    else:
        line = f"{num}. {item['title']}。{content}，来源：{item['source']}{url_extra}"
    return [line, ""]


def _render_landing_item(item: dict) -> list:
    """企业落地：▫️ 场景：[企业] [动作]..."""
    content = item["content"][:130]
    if len(item["content"]) > 130:
        content += "…"

    url_extra = f" 📎{shorten_url(item.get('url', ''))}" if item.get("url") else ""

    # 尝试根据关键词匹配场景前缀
    text = f"{item['title']} {content}".lower()
    matched_scenario = None
    for keyword, prefix in SCENARIO_KEYWORDS.items():
        if keyword.lower() in text:
            matched_scenario = f"{prefix}：{item['title']}，{content}，来源：{item['source']}{url_extra}"
            break

    if matched_scenario:
        return [matched_scenario, ""]
    else:
        return [f"▫️ {item['title']}。{content}，来源：{item['source']}{url_extra}", ""]


def _render_procurement_item(item: dict, num: int) -> list:
    """招标采购：[内容]，来源：[来源]"""
    content = item["content"][:130]
    if len(item["content"]) > 130:
        content += "…"
    url_extra = f" 📎{shorten_url(item.get('url', ''))}" if item.get("url") else ""
    return [f"{num}. {item['title']}。{content}，来源：{item['source']}{url_extra}", ""]


def _render_tech_item(item: dict, num: int, is_first: bool = True) -> list:
    """技术动态/行业观点："""
    content = item["content"][:130]
    if len(item["content"]) > 130:
        content += "…"
    prefix = "技术动态" if is_first else "行业观点/海外资讯"
    category = item.get("category", "")
    if category == "行业观点/海外资讯":
        prefix = "行业观点/海外资讯"
    url_extra = f" 📎{shorten_url(item.get('url', ''))}" if item.get("url") else ""
    return [f"{num}. {prefix}：{item['title']}。{content}，来源：{item['source']}{url_extra}", ""]


def _render_opinion_item(item: dict, num: int) -> list:
    """行业观点/海外资讯（通用兜底）："""
    content = item["content"][:130]
    if len(item["content"]) > 130:
        content += "…"
    url_extra = f" 📎{shorten_url(item.get('url', ''))}" if item.get("url") else ""
    return [f"{num}. {item['title']}。{content}，来源：{item['source']}{url_extra}", ""]


def build_report_mp(news_items: list, template: dict,
                    attention_text: str = "") -> str:
    """
    生成公众号格式，完全适配微信编辑器。
    按 template.md 中的规范：含 emoji 图标、加粗、板块专属排版。
    """
    now = datetime.now()
    month = now.month
    day = now.day

    # ----- 标题 -----
    title_options = template.get("title_options") or TITLE_TEMPLATES
    title_idx = template.get("title_selected", 0)
    if title_idx < 0 or title_idx >= len(title_options):
        title_idx = 0
    title_tpl = title_options[title_idx]

    highlights = "园区落地+政策+招标"
    if len(news_items) >= 2:
        h1 = news_items[0]["title"][:12]
        h2 = news_items[1]["title"][:12]
        highlights = f"{h1}+{h2}"
    elif len(news_items) == 1:
        highlights = news_items[0]["title"][:20]

    title = (title_tpl
             .replace("{month}", str(month))
             .replace("{day}", str(day))
             .replace("{highlights}", highlights)
             .replace("{count}", str(len(news_items))))

    lines = [
        title,
        "",
        "聚焦园区无人车垂直领域，每日汇总政策、落地、招标、技术核心资讯，精准覆盖园区接驳、巡检、配送、环卫等场景，助力从业者快速掌握行业动态～",
        "",
    ]

    # ----- 📢 今日速览 -----
    lines.append("\U0001f4e2 今日速览")
    lines.append("")
    for idx, item in enumerate(news_items[:3], start=1):
        lines.append(f"{idx}. **{item['title']}**")
    lines.append("")

    # ----- 按分类分组 -----
    grouped = {cat: [] for cat in CATEGORY_ORDER}
    for item in news_items:
        grouped.setdefault(item.get("category", CATEGORY_ORDER[-1]), []).append(item)

    displayed = set()

    # ----- 📋 政策动态 -----
    policy_items = grouped.get("政策动态", [])
    if policy_items:
        displayed.add("政策动态")
        lines.append("\U0001f4cb 政策动态")
        lines.append("")
        for i, item in enumerate(policy_items, start=1):
            lines.extend(_render_policy_item(item, i))

    # ----- 🚗 企业&落地案例 -----
    landing_items = grouped.get("企业落地", [])
    if landing_items:
        displayed.add("企业落地")
        lines.append("\U0001f697 企业&落地案例")
        lines.append("")
        for item in landing_items:
            lines.extend(_render_landing_item(item))

    # ----- 💡 招标&中标 -----
    procurement_items = grouped.get("招标采购", [])
    if procurement_items:
        displayed.add("招标采购")
        lines.append("\U0001f4a1 招标&中标")
        lines.append("")
        for i, item in enumerate(procurement_items, start=1):
            lines.extend(_render_procurement_item(item, i))

    # ----- 📈 技术&行业观察 -----
    tech_items = grouped.get("技术动态", [])
    if tech_items:
        displayed.add("技术动态")
        lines.append("\U0001f4c8 技术&行业观察")
        lines.append("")
        for i, item in enumerate(tech_items, start=1):
            lines.extend(_render_tech_item(item, i, is_first=(i == 1)))

    # ----- 🌐 剩余分类（行业观点/海外资讯等） -----
    for cat in CATEGORY_ORDER:
        if cat in displayed:
            continue
        items = grouped.get(cat, [])
        if not items:
            continue
        emoji = CATEGORY_EMOJI.get(cat, "\U0001f4cb")
        lines.append(f"{emoji} {cat}")
        lines.append("")
        for i, item in enumerate(items, start=1):
            if cat == "行业观点/海外资讯":
                lines.extend(_render_opinion_item(item, i))
            else:
                lines.extend(_render_opinion_item(item, i))

    # ----- ✨ 明日关注 -----
    lines.append("✨ 明日关注")
    lines.append("")
    if attention_text:
        lines.append(attention_text)
    else:
        lines.append("明日持续关注园区无人车招标及落地动态")
    lines.append("")

    # ----- 结尾话术 -----
    closing_options = template.get("closing_options") or CLOSING_OPTIONS
    closing_idx = template.get("closing_selected", 0)
    if closing_idx < 0 or closing_idx >= len(closing_options):
        closing_idx = 0
    lines.append(closing_options[closing_idx])

    return "\n".join(lines)


def _html_escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _render_html_section(title: str, content_lines: list) -> str:
    """渲染一个板块的 HTML。"""
    parts = [f'<p style="font-weight:bold;font-size:15px;margin:14px 0 6px;color:#0d3b66;">{_html_escape(title)}</p>']
    for line in content_lines:
        if not line:
            parts.append('<p style="margin:2px 0;">&nbsp;</p>')
        elif line.startswith("▫️"):
            parts.append(f'<p style="margin:4px 0;padding-left:0;color:#333;font-size:14px;line-height:1.7;">{_html_escape(line)}</p>')
        else:
            parts.append(f'<p style="margin:4px 0;color:#333;font-size:14px;line-height:1.7;">{_html_escape(line)}</p>')
    return "\n".join(parts)


def _url_to_link(text: str) -> str:
    """将文本中的"📎short_url"替换为蓝色可点击的"📎 short_url"。"""
    return re.sub(
        r'📎(https?://[^\s\'"<>，、）\)…]+)',
        r'<a href="\1" target="_blank" rel="noreferrer" style="color:#1a6b9e;text-decoration:none;border-bottom:1px solid #c8daf0;">📎 \1</a>',
        text
    )


def _html_img(img_url: str, alt: str = "") -> str:
    """生成朋友圈/公众号风格的图片 HTML 块。"""
    if not img_url:
        return ""
    return (f'<div style="margin:8px 0;border-radius:10px;overflow:hidden;'
            f'background:#f5f7fa;text-align:center;">'
            f'<img data-src="{_html_escape(img_url)}" alt="{_html_escape(alt)}" '
            f'style="width:100%;max-width:100%;display:block;object-fit:cover;'
            f'max-height:300px;" /></div>')


def build_report_mp_html(news_items: list, template: dict,
                          attention_text: str = "") -> str:
    """
    生成专业公众号风格 HTML（含内联样式），
    卡片式排版 + 缩略图 + 缩短的原文链接。
    """
    now = datetime.now()
    month = now.month
    day = now.day

    # ----- 标题 -----
    title_options = template.get("title_options") or TITLE_TEMPLATES
    title_idx = template.get("title_selected", 0)
    if title_idx < 0 or title_idx >= len(title_options):
        title_idx = 0
    title_tpl = title_options[title_idx]
    highlights = "园区落地+政策+招标"
    if len(news_items) >= 2:
        h1 = news_items[0]["title"][:12]
        h2 = news_items[1]["title"][:12]
        highlights = f"{h1}+{h2}"
    elif len(news_items) == 1:
        highlights = news_items[0]["title"][:20]
    title = (title_tpl
             .replace("{month}", str(month))
             .replace("{day}", str(day))
             .replace("{highlights}", highlights)
             .replace("{count}", str(len(news_items))))

    # ----- 结尾话术 -----
    closing_options = template.get("closing_options") or CLOSING_OPTIONS
    closing_idx = template.get("closing_selected", 0)
    if closing_idx < 0 or closing_idx >= len(closing_options):
        closing_idx = 0

    # ----- 按分类分组 -----
    grouped = {cat: [] for cat in CATEGORY_ORDER}
    for item in news_items:
        grouped.setdefault(item.get("category", CATEGORY_ORDER[-1]), []).append(item)

    parts = [
        '<meta charset="utf-8">',
        '<section style="padding:2px 12px 20px;font-size:15px;color:#222;line-height:1.8;max-width:620px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,Microsoft YaHei,PingFang SC,sans-serif;">',
        # ---- 标题 ----
        f'<p style="font-size:18px;font-weight:bold;text-align:center;color:#0d3b66;margin:16px 0 2px;letter-spacing:0.03em;">{_html_escape(title)}</p>',
        # ---- 引导语 ----
        '<p style="font-size:14px;text-align:center;color:#7a8ba8;margin:4px 0 20px;line-height:1.6;">聚焦园区无人车垂直领域 · 每日汇总政策、落地、招标、技术核心资讯</p>',
        # ---- 分割线 ----
        '<div style="height:1px;background:linear-gradient(90deg,transparent,#dce3f5,transparent);margin:0 0 20px;"></div>',
    ]

    # ===== 📢 今日速览 =====
    if news_items:
        parts.append('<p style="font-weight:bold;font-size:16px;margin:0 0 10px;color:#0d3b66;">📢 今日速览</p>')
        for idx, item in enumerate(news_items[:3], start=1):
            parts.append(
                f'<p style="margin:4px 0 4px 18px;font-size:14px;line-height:1.7;">'
                f'<span style="font-weight:bold;color:#1a6b9e;">{idx}.</span> '
                f'<strong>{_html_escape(item["title"])}</strong></p>'
            )
        parts.append('<div style="height:1px;background:linear-gradient(90deg,transparent,#eef3fa,transparent);margin:16px 0;"></div>')

    # ===== 各分类卡片 =====
    displayed = set()

    # 分类标题定义（带 emoji）
    SECTION_META = [
        ("政策动态", "📋", "政策动态"),
        ("企业落地", "🚗", "企业&amp;落地案例"),
        ("招标采购", "💡", "招标&amp;中标"),
        ("技术动态", "📈", "技术&amp;行业观察"),
        ("行业观点/海外资讯", "🌐", "行业观点/海外资讯"),
    ]

    for cat_key, emoji, section_title in SECTION_META:
        items = grouped.get(cat_key, [])
        if not items:
            continue
        displayed.add(cat_key)

        # 板块标题
        parts.append(
            f'<p style="font-weight:bold;font-size:16px;margin:22px 0 12px;color:#0d3b66;">{emoji} {section_title}</p>'
        )

        for i, item in enumerate(items):
            title_text = _html_escape(item.get("title", ""))
            content_text = _html_escape(item.get("content", ""))
            source_text = _html_escape(item.get("source", ""))
            img_url = item.get("image_url", "").strip()
            item_url = item.get("url", "")
            short_link = shorten_url(item_url) if item_url else ""

            # ---- 卡片开始 ----
            parts.append(
                '<div style="background:#f8faff;border-radius:12px;padding:14px 16px;'
                'margin-bottom:12px;border:1px solid #eef2f8;">'
            )

            # 标题（带编号）
            parts.append(
                f'<p style="margin:0 0 6px;font-size:15px;font-weight:600;color:#1a2a47;">'
                f'{title_text}</p>'
            )

            # 缩略图
            if img_url:
                parts.append(_html_img(img_url, item.get("title", "")))

            # 内容摘要（截取前 150 字）
            content_short = content_text[:150]
            if len(content_text) > 150:
                content_short += "…"
            if content_short:
                parts.append(
                    f'<p style="margin:0 0 8px;font-size:14px;color:#444;line-height:1.7;">'
                    f'{content_short}</p>'
                )

            # 底部：来源 + 原文链接（缩短）
            meta_parts_inner = []
            if source_text:
                meta_parts_inner.append(
                    f'<span style="font-size:12px;color:#8a9bb5;">{source_text}</span>'
                )
            if item_url:
                meta_parts_inner.append(
                    f'<a href="{_html_escape(item_url)}" style="font-size:12px;color:#1a6b9e;'
                    f'text-decoration:none;border-bottom:1px solid #c8daf0;">'
                    f'📎 {_html_escape(short_link)}</a>'
                )
            if meta_parts_inner:
                parts.append(
                    f'<p style="margin:0;display:flex;gap:12px;'
                    f'align-items:center;">{" · ".join(meta_parts_inner)}</p>'
                )

            # ---- 卡片结束 ----
            parts.append("</div>")

    # ===== ✨ 明日关注 =====
    parts.append('<div style="height:1px;background:linear-gradient(90deg,transparent,#dce3f5,transparent);margin:20px 0 16px;"></div>')
    parts.append('<p style="font-weight:bold;font-size:15px;margin:0 0 8px;color:#0d3b66;">✨ 明日关注</p>')
    if attention_text:
        parts.append(f'<p style="margin:0 0 16px;font-size:14px;color:#555;line-height:1.7;">{_html_escape(attention_text)}</p>')
    else:
        parts.append('<p style="margin:0 0 16px;font-size:14px;color:#555;line-height:1.7;">明日持续关注园区无人车招标及落地动态</p>')

    # ===== 结尾话术 =====
    parts.append(
        f'<div style="height:1px;background:linear-gradient(90deg,transparent,#dce3f5,transparent);margin:0 0 14px;"></div>'
    )
    parts.append(
        f'<p style="margin:0;font-size:13px;color:#7a8ba8;text-align:center;line-height:1.6;">'
        f'{_html_escape(closing_options[closing_idx])}</p>'
    )

    parts.append("</section>")
    return "\n".join(parts)


def build_report_text(news_items: list, template: dict, attention_text: str = "明日持续关注园区无人车招标及落地动态") -> str:
    def format_line(text: str) -> str:
        return normalize_text(text)

    date_text = datetime.now().strftime("%Y年%m月%d日")
    highlights = " / ".join([item["title"] for item in news_items[:3]]) or "今日园区无人车资讯"
    title = template["title_format"].format(date=date_text, highlights=highlights)
    lines = [title, "", "聚焦园区无人车垂直领域，每日汇总政策、落地、招标、技术核心资讯，精准覆盖园区接驳、巡检、配送、环卫等场景，助力从业者快速掌握行业动态～", "", f"### {template['summary_title']}"]

    for index, item in enumerate(news_items[:3], start=1):
        lines.append(f"{index}. {item['title']}")
    lines.append("")

    grouped = {category: [] for category in CATEGORY_ORDER}
    for item in news_items:
        grouped.setdefault(item.get("category", CATEGORY_ORDER[-1]), []).append(item)

    # Map section titles (keys) to category keys (values) for the first 4 categories
    category_section_map = {
        "政策动态": template["policy_title"],
        "企业落地": template["landing_title"],
        "招标采购": template["procurement_title"],
        "技术动态": template["tech_title"],
    }
    displayed = set()
    for category_key, section_name in category_section_map.items():
        items = grouped.get(category_key, [])
        if not items:
            continue
        displayed.add(category_key)
        lines.append(f"### {section_name}")
        for num, item in enumerate(items, start=1):
            lines.append(f"{num}. {item['title']} \n{item['content']} 来源：{item['source']}")
        lines.append("")

    # Remaining categories not yet displayed (e.g. 行业观点/海外资讯)
    for category_key in CATEGORY_ORDER:
        if category_key in displayed:
            continue
        items = grouped.get(category_key, [])
        if not items:
            continue
        lines.append(f"### {category_key}")
        for num, item in enumerate(items, start=1):
            lines.append(f"{num}. {item['title']} \n{item['content']} 来源：{item['source']}")
        lines.append("")

    lines.append(f"### {template['follow_title']}")
    lines.append(attention_text)
    lines.append("")
    lines.append(template["closing_paragraph"])
    return "\n\n".join(lines)


def build_report_html(news_items: list, template: dict, attention_text: str = "明日持续关注园区无人车招标及落地动态") -> str:
    text = build_report_text(news_items, template, attention_text)
    html_parts = ['<div style="font-family: Arial, sans-serif; line-height: 1.8; color: #222; background:#fff; padding:20px; border-radius:8px; max-width: 680px; margin: 0 auto;">']
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            html_parts.append(f'<h3 style="margin: 20px 0 10px; font-size: 16px; color: #0d3b66;">{stripped[4:]}</h3>')
        elif stripped.startswith("## "):
            html_parts.append(f'<h2 style="margin: 24px 0 12px; font-size: 20px; color: #0d3b66;">{stripped[3:]}</h2>')
        elif stripped and stripped[0].isdigit() and ". " in stripped[:4]:
            html_parts.append(f'<p style="margin: 6px 0; color:#222;">{stripped}</p>')
        elif stripped == "":
            html_parts.append('<br />')
        else:
            html_parts.append(f'<p style="margin: 8px 0; color:#222;">{stripped}</p>')
    html_parts.append('</div>')
    return "\n".join(html_parts)
