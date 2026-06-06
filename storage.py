import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"
NEWS_PATH = DATA_DIR / "news.json"
HISTORY_PATH = DATA_DIR / "history.json"

DEFAULT_CONFIG = {
    "channels": [
        "https://cn.bing.com/search?q=园区无人车+园区自动驾驶&setlang=zh-Hans",
        "https://www.baidu.com/s?wd=园区无人车+园区自动驾驶&ie=utf-8",
        "https://www.sogou.com/sogou?query=园区无人车+自动驾驶&ie=utf8",
        "https://www.chinabidding.com.cn/search?keyword=无人车",
        "https://www.bidcenter.com.cn/Search/?keyword=无人车",
        "https://auto.gasgoo.com/",
        "https://www.autohome.com.cn/bestauto/",
        "https://www.d1ev.com/",
        "https://www.thepaper.cn/tag/47646",
        "https://www.baidu.com/s?tn=news&rtt=1&bsst=1&wd=专业资讯+无人车&cl=2"
    ],
    "keywords": [
        "园区无人车",
        "园区自动驾驶",
        "无人接驳车",
        "巡检",
        "配送",
        "环卫",
        "低速无人车",
        "自动驾驶 园区",
        "无人配送车",
        "接驳车",
        "无人驾驶",
        "自动驾驶"
    ],
    "categories": {
        "政策动态": ["政策", "新规", "补贴", "路测", "试点", "规范", "公告", "安全运营",
                    "regulation", "policy", "legislation", "regulatory", "permit", "approval",
                    "certification", "NHTSA", "safety standard", "government", "legal", "law"],
        "企业落地": ["园区", "上线", "合作", "签约", "落地", "投放", "运营", "项目",
                    "launch", "deploy", "partnership", "rollout", "commercial", "pilot",
                    "investment", "funding", "service", "delivery", "operation"],
        "技术动态": ["传感器", "调度", "算法", "平台", "车路协同", "续航", "避障", "AI",
                    "LiDAR", "radar", "computer vision", "deep learning", "perception",
                    "HD map", "V2X", "connectivity", "chip", "SoC", "software", "simulation",
                    "neural network", "sensor", "algorithm", "transformer", "OTA"],
        "招标采购": ["招标", "中标", "预算", "采购", "公告", "服务需求",
                    "tender", "bid", "procurement", "contract", "RFP", "vendor", "supplier"],
        "行业观点/海外资讯": ["专家", "趋势", "海外", "解读", "观点", "案例", "行业观察",
                        "analysis", "opinion", "report", "forecast", "market", "research",
                        "insight", "survey", "outlook", "trend"]
    },
    "template": {
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
    },
    "rss_sources": [
    ]
}

DEFAULT_NEWS = []
DEFAULT_HISTORY = []


def _ensure_file(path: Path, default_data):
    if not path.exists():
        path.write_text(json.dumps(default_data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path, default_data):
    _ensure_file(path, default_data)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_data


def _save_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def get_config():
    config = _load_json(CONFIG_PATH, DEFAULT_CONFIG)
    if not isinstance(config, dict):
        return dict(DEFAULT_CONFIG)

    return {
        "channels": config.get("channels") if isinstance(config.get("channels"), list) and config.get("channels") else list(DEFAULT_CONFIG["channels"]),
        "keywords": config.get("keywords") if isinstance(config.get("keywords"), list) and config.get("keywords") else list(DEFAULT_CONFIG["keywords"]),
        "categories": dict(config.get("categories") or DEFAULT_CONFIG["categories"]),
        "template": {**DEFAULT_CONFIG["template"], **(config.get("template") or {})},
        "wechat": dict(config.get("wechat") or {}),
        "rss_sources": config.get("rss_sources") if isinstance(config.get("rss_sources"), list) else list(DEFAULT_CONFIG["rss_sources"])
    }


def save_config(config):
    _save_json(CONFIG_PATH, config)


def get_news_list():
    return _load_json(NEWS_PATH, DEFAULT_NEWS)


def save_news_list(news_list):
    _save_json(NEWS_PATH, news_list)


def get_history():
    return _load_json(HISTORY_PATH, DEFAULT_HISTORY)


def save_history(history):
    _save_json(HISTORY_PATH, history)


def generate_news_id():
    today = datetime.now().strftime("%Y%m%d")
    news_list = get_news_list()
    count = sum(1 for item in news_list if item.get("id", "").startswith(f"news_{today}"))
    return f"news_{today}_{count + 1:03d}"


def add_news_item(item):
    news_list = get_news_list()
    news_list.insert(0, item)
    save_news_list(news_list)
    return item


def update_news_item(news_id, updates):
    news_list = get_news_list()
    for index, item in enumerate(news_list):
        if item.get("id") == news_id:
            item.update(updates)
            news_list[index] = item
            save_news_list(news_list)
            return item
    return None


def archive_report(date_key, report):
    history = get_history()
    history.insert(0, {"date": date_key, "report": report, "saved_at": datetime.now().isoformat()})
    save_history(history)
    return history
