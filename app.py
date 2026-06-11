from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

from services import build_report_mp, build_report_mp_html, classify_news, crawl_channels, crawl_rss_feeds, parse_opml, train_news_classifier, verify_channel, verify_rss_feed
from storage import (
    add_news_item,
    archive_report,
    generate_news_id,
    get_config,
    get_history,
    get_news_list,
    save_config,
    save_history,
    save_news_list,
    update_news_item,
)
from wechat import create_draft, replace_images_in_html

app = Flask(__name__, static_folder="static", static_url_path="", template_folder="templates")


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        data = request.get_json(force=True)
        if not data:
            return jsonify({"success": False, "message": "缺少配置数据"}), 400
        config = get_config()
        config.update(data)
        save_config(config)
        return jsonify({"success": True, "data": config})
    config = get_config()
    # 若 rss_sources 为空，自动从 AV_Feeds.opml 加载
    if not config.get("rss_sources") and OPML_PATH.exists():
        from services import parse_opml
        feeds = parse_opml(str(OPML_PATH))
        if feeds:
            config["rss_sources"] = [url for _, url in feeds]
            save_config(config)
    return jsonify({"success": True, "data": config})


@app.route("/api/news", methods=["GET", "POST"])
def api_news():
    if request.method == "POST":
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"success": False, "message": "缺少资讯内容"}), 400
        news_id = generate_news_id()
        item = {
            "id": news_id,
            "title": payload.get("title", "").strip(),
            "publish_time": payload.get("publish_time", "").strip() or datetime.now().strftime("%Y-%m-%d"),
            "source": payload.get("source", "手动录入").strip(),
            "content": payload.get("content", "").strip(),
            "category": payload.get("category", "行业观点/海外资讯").strip(),
            "keywords": payload.get("keywords", []),
            "url": payload.get("url", ""),
            "created_at": datetime.now().isoformat()
        }
        add_news_item(item)
        return jsonify({"success": True, "data": item})
    return jsonify({"success": True, "data": get_news_list()})


@app.route("/api/news/clear", methods=["POST"])
def api_clear_news():
    save_news_list([])
    return jsonify({"success": True, "message": "资讯列表已清空"})


@app.route("/api/news/<news_id>", methods=["PUT", "DELETE"])
def api_update_or_delete_news(news_id):
    if request.method == "DELETE":
        news_list = get_news_list()
        new_list = [item for item in news_list if item.get("id") != news_id]
        if len(new_list) == len(news_list):
            return jsonify({"success": False, "message": "未找到指定资讯"}), 404
        save_news_list(new_list)
        return jsonify({"success": True, "message": "资讯已删除"})
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"success": False, "message": "缺少更新数据"}), 400
    updated = update_news_item(news_id, payload)
    if not updated:
        return jsonify({"success": False, "message": "未找到指定资讯"}), 404
    return jsonify({"success": True, "data": updated})


@app.route("/api/news/crawl", methods=["POST"])
def api_crawl():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"success": False, "message": "缺少抓取参数"}), 400
    channel_urls = payload.get("channel_urls") or get_config().get("channels", [])
    rss_urls = payload.get("rss_urls") or get_config().get("rss_sources", [])
    keywords = payload.get("keywords") or get_config().get("keywords", [])
    category_keywords = payload.get("category_keywords") or get_config().get("categories", {})
    time_range = payload.get("time_range")
    try:
        # 1. 网页爬取（原有逻辑，用 keywords 过滤）
        result = crawl_channels(channel_urls, keywords, category_keywords, time_range)
        # 2. RSS 抓取（不额外关键词过滤，仅做全局分类）
        rss_result = crawl_rss_feeds(rss_urls, category_keywords, time_range)
    except Exception as e:
        return jsonify({"success": False, "message": f"抓取失败: {str(e)}"}), 500

    # 合并 & URL 去重（优先保留网页爬取结果，RSS 内容可能被截断）
    all_results = list(result["results"])
    seen_urls = {item.get("url") for item in all_results}
    for item in rss_result["results"]:
        if item.get("url") and item["url"] not in seen_urls:
            all_results.append(item)
            seen_urls.add(item["url"])

    existing_urls = {item.get("url") for item in get_news_list()}
    added_items = []
    for item in all_results:
        if item.get("url") and item["url"] not in existing_urls:
            item_data = {
                "id": generate_news_id(),
                "title": item["title"],
                "publish_time": item["publish_time"] or datetime.now().strftime("%Y-%m-%d"),
                "source": item["source"],
                "content": item["content"],
                "image_url": item.get("image_url", ""),
                "category": item.get("category", "行业观点/海外资讯"),
                "keywords": keywords,
                "url": item["url"],
                "created_at": datetime.now().isoformat()
            }
            add_news_item(item_data)
            added_items.append(item_data)
            existing_urls.add(item["url"])
    # 训练 ML 分类器（如果有新增数据）
    if added_items:
        from services import train_news_classifier
        train_news_classifier(get_news_list())
    return jsonify({"success": True, "data": all_results, "added_count": len(added_items), "crawl_info": {
        "total": result["total"],
        "succeeded": result["succeeded"],
        "details": result["details"],
        "rss_total": rss_result["total"],
        "rss_errors": rss_result["errors"]
    }})


@app.route("/api/channels/verify", methods=["POST"])
def api_verify_channels():
    payload = request.get_json(force=True)
    if not payload:
        print("[api_verify_channels] 缺少payload")
        return jsonify({"success": False, "message": "缺少参数"}), 400
    channel_urls = payload.get("channel_urls") or get_config().get("channels", [])
    keywords = payload.get("keywords") or get_config().get("keywords", [])
    print(f"[api_verify_channels] verify start channels={len(channel_urls)} keywords={len(keywords)}")
    results = [verify_channel(url, keywords) for url in channel_urls]
    ok_count = sum(1 for r in results if r["status"] == "ok")
    weak_count = sum(1 for r in results if r["status"] == "weak")
    fail_count = sum(1 for r in results if r["status"] == "fail")
    print(f"[api_verify_channels] summary ok={ok_count} weak={weak_count} fail={fail_count}")
    return jsonify({"success": True, "data": results, "summary": {
        "total": len(results), "ok": ok_count, "weak": weak_count, "fail": fail_count
    }})


OPML_PATH = Path(__file__).parent / "AV_Feeds.opml"


@app.route("/api/rss/import-opml", methods=["POST"])
def api_import_opml():
    """Parse AV_Feeds.opml and import all feed URLs into config.rss_sources."""
    if not OPML_PATH.exists():
        return jsonify({"success": False, "message": f"OPML 文件不存在: {OPML_PATH}"}), 404

    feeds = parse_opml(str(OPML_PATH))
    if not feeds:
        return jsonify({"success": False, "message": "OPML 文件中未找到有效的 RSS 订阅源"}), 400

    config = get_config()
    # 合并：保留已有 + 新增（去重）
    existing = set(config.get("rss_sources", []))
    new_sources = []
    imported = []
    for title, url in feeds:
        is_new = url not in existing
        imported.append({"title": title, "url": url, "new": is_new})
        if is_new:
            existing.add(url)
            new_sources.append(url)

    if new_sources:
        config["rss_sources"] = list(existing)
        save_config(config)

    return jsonify({
        "success": True,
        "data": {
            "total": len(feeds),
            "imported": imported,
            "new_added": len(new_sources),
            "rss_sources": list(existing),
        }
    })


@app.route("/api/rss/verify", methods=["POST"])
def api_rss_verify():
    """Test connectivity and parseability of RSS feeds."""
    payload = request.get_json(force=True)
    urls = payload.get("urls", []) if payload else []
    if not urls:
        return jsonify({"success": False, "message": "缺少 RSS URL"}), 400
    results = [verify_rss_feed(url) for url in urls]
    ok = sum(1 for r in results if r["status"] == "ok")
    fail = sum(1 for r in results if r["status"] == "fail")
    return jsonify({"success": True, "data": results, "summary": {"total": len(results), "ok": ok, "fail": fail}})


@app.route("/api/rss/remove", methods=["POST"])
def api_rss_remove():
    """Remove an RSS feed URL from the config."""
    payload = request.get_json(force=True)
    url_to_remove = (payload.get("url") or "").strip() if payload else ""
    if not url_to_remove:
        return jsonify({"success": False, "message": "缺少 RSS URL"}), 400
    config = get_config()
    sources = config.get("rss_sources", [])
    if url_to_remove not in sources:
        return jsonify({"success": False, "message": "未找到该 RSS 源"}), 404
    sources.remove(url_to_remove)
    config["rss_sources"] = sources
    save_config(config)
    return jsonify({"success": True, "data": {"rss_sources": sources}})


@app.route("/api/news/classify", methods=["POST"])
def api_classify():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"success": False, "message": "缺少分类参数"}), 400
    title = payload.get("news_title", "")
    content = payload.get("news_content", "")
    category_keywords = payload.get("category_keywords") or get_config().get("categories", {})
    category, match_rate = classify_news(title, content, category_keywords)
    return jsonify({"success": True, "data": {"recommend_category": category, "match_rate": match_rate}})


@app.route("/api/export", methods=["POST"])
def api_export():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"success": False, "message": "缺少导出参数"}), 400
    format_type = "mp"  # 只保留公众号格式
    news_items = payload.get("news_items") or get_news_list()
    template = dict(payload.get("template") or get_config().get("template", {}))
    attention = payload.get("attention_text", "明日持续关注园区无人车招标及落地动态")
    # 允许前端临时切换标题风格 / 结尾话术，不持久化
    if "title_style" in payload:
        template["title_selected"] = int(payload["title_style"])
    if "closing_style" in payload:
        template["closing_selected"] = int(payload["closing_style"])
    if not news_items:
        return jsonify({"success": False, "message": "没有可导出的资讯"}), 400
    try:
        report = build_report_mp(news_items, template, attention)
        report_html = build_report_mp_html(news_items, template, attention)
        archive_report(datetime.now().strftime("%Y-%m-%d"), {"format": format_type, "report": report})
    except Exception as e:
        return jsonify({"success": False, "message": f"导出失败: {str(e)}"}), 500
    return jsonify({"success": True, "data": {"report": report, "report_html": report_html, "format": format_type}})


@app.route("/api/wechat/publish", methods=["POST"])
def api_wechat_publish():
    """将当前资讯生成公众号 HTML 并发布到微信草稿箱。"""
    payload = request.get_json(force=True)
    config = get_config()
    wechat_cfg = config.get("wechat", {})
    appid = payload.get("appid") or wechat_cfg.get("appid", "")
    appsecret = payload.get("appsecret") or wechat_cfg.get("appsecret", "")
    if not appid or not appsecret:
        return jsonify({"success": False, "message": "请先配置微信公众号 AppID 和 AppSecret"}), 400

    news_items = payload.get("news_items") or get_news_list()
    if not news_items:
        return jsonify({"success": False, "message": "没有可发布的资讯"}), 400

    template = config.get("template", {})
    attention = payload.get("attention_text", "明日持续关注园区无人车招标及落地动态")

    # 使用前端传入的 style 覆盖
    if "title_style" in payload:
        template["title_selected"] = int(payload["title_style"])
    if "closing_style" in payload:
        template["closing_selected"] = int(payload["closing_style"])

    try:
        # 生成用于微信的 HTML
        html_report = build_report_mp_html(news_items, template, attention)

        # 将正文中的外网图片上传到微信 CDN，防止外链被屏蔽
        print(f"[wechat] 开始上传内容图片到微信 CDN ...")
        html_report = replace_images_in_html(appid, appsecret, html_report)
        print(f"[wechat] 内容图片处理完成")

        # 纯文本用于摘要
        text_report = build_report_mp(news_items, template, attention)
        # 截取前 60 字节作为摘要（微信限制），避免截断 UTF-8 多字节字符
        raw = text_report[:120].replace("\n", " ").strip()
        while len(raw.encode("utf-8")) > 58:
            raw = raw[:-1]
        digest = raw + "…" if len(raw) < len(text_report[:120].replace("\n", " ").strip()) else raw

        # 提取标题并截断到 30 字节（微信限制）
        first_line = text_report.split("\n")[0].strip()
        title_bytes = first_line.encode("utf-8")
        if len(title_bytes) > 30:
            # 逐字符截断到 <= 30 字节
            chars = []
            total = 0
            for ch in first_line:
                sz = len(ch.encode("utf-8"))
                if total + sz > 30:
                    break
                total += sz
                chars.append(ch)
            first_line = "".join(chars)

        author = payload.get("author") or wechat_cfg.get("name", "")

        result = create_draft(appid, appsecret, first_line, html_report, author, digest)
        if result["success"]:
            return jsonify({"success": True, "data": {"media_id": result["media_id"]}})
        return jsonify({"success": False, "message": f"发布失败: {result.get('errmsg')}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"发布异常: {str(e)}"}), 500


@app.route("/api/history", methods=["GET", "DELETE"])
def api_history():
    if request.method == "DELETE":
        save_history([])
        return jsonify({"success": True, "message": "历史报告已清空"})
    return jsonify({"success": True, "data": get_history()})


@app.route("/api/template/reset", methods=["POST"])
def api_reset_template():
    config = get_config()
    default_template = {
        "title_format": "园区无人车日报·{date}｜{highlights}",
        "summary_title": "今日速览",
        "policy_title": "政策动态",
        "landing_title": "企业&落地案例",
        "procurement_title": "招标&中标",
        "tech_title": "技术&行业观察",
        "follow_title": "明日关注",
        "closing_paragraph": "每日更新园区无人车核心资讯，聚焦封闭场景自动驾驶落地，关注我，解锁更多行业干货～",
        "title_options": [
            "【园区无人车·{month}月{day}日资讯日报】｜政策更新+园区落地+招标动态"
        ],
        "title_selected": 0,
        "closing_options": [
            "每日更新园区无人车核心资讯，聚焦封闭场景自动驾驶落地，关注我，解锁更多行业干货～",
            "留言区聊聊你最关注的园区无人车场景（接驳/巡检/配送），后续将重点跟进相关资讯！"
        ],
        "closing_selected": 0
    }
    config["template"] = default_template
    save_config(config)
    return jsonify({"success": True, "data": config})


if __name__ == "__main__":
    # 启动时如果有历史数据，训练 ML 分类器
    try:
        from services import train_news_classifier
        news_data = get_news_list()
        if len(news_data) >= 15:
            train_news_classifier(news_data)
            print(f"[startup] ML 分类器已训练（{len(news_data)} 条样本）")
    except Exception:
        pass
    app.run(host="0.0.0.0", port=5000, debug=True)
