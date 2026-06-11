"""微信公众号 API 客户端：获取 access_token、上传缩略图、创建草稿。"""

import io
import json
import os
import re
import struct
import time
import zlib
from pathlib import Path
from urllib.parse import urlparse

import requests

# 内存中缓存的 access_token
_token_cache: dict = {"token": None, "expires_at": 0}
# 内存中缓存的 thumb_media_id
_thumb_cache: dict = {"media_id": None, "expires_at": 0}
# 内存中缓存的已上传图片 URL（外链 → 微信 CDN URL）
_image_url_cache: dict = {}
# 缓存上传失败的 URL，避免重复尝试
_failed_image_urls: set = set()

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


def _get_access_token(appid: str, appsecret: str) -> str:
    """获取（或刷新）access_token，自动缓存。"""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    resp = requests.get(
        f"{WECHAT_API_BASE}/token",
        params={"grant_type": "client_credential", "appid": appid, "secret": appsecret},
        timeout=10,
    )
    data = resp.json()
    if "access_token" in data:
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 7200)
        return data["access_token"]

    raise RuntimeError(f"获取 access_token 失败: {data.get('errmsg', str(data))}")


# ---------------------------------------------------------------------------
# 缩略图：从项目目录加载图片并上传为永久素材
# ---------------------------------------------------------------------------

_THUMBNAIL_PATH = Path(__file__).parent / "static" / "thumbnail.png"


def _load_thumbnail() -> bytes:
    """从项目 static/thumbnail.png 读取缩略图。"""
    if not _THUMBNAIL_PATH.exists():
        # 回退：生成一个简单的纯色占位图
        return _make_fallback_png()
    return _THUMBNAIL_PATH.read_bytes()


def _make_fallback_png(width: int = 300, height: int = 200) -> bytes:
    """当缩略图文件不存在时，用纯 Python 生成一张蓝色 PNG 作为后备。"""
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

    raw = b""
    for y in range(height):
        raw += b"\x00"
        for x in range(width):
            r = 30
            g = 80 + int(120 * y / height)
            b_val = 180 + int(75 * x / width)
            raw += struct.pack("BBB", r, min(g, 255), min(b_val, 255))

    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")

    return sig + ihdr + idat + iend


def _upload_thumb(appid: str, appsecret: str) -> str:
    """上传默认缩略图到微信永久素材，返回 thumb_media_id。"""
    now = time.time()
    if _thumb_cache["media_id"] and now < _thumb_cache["expires_at"] - 300:
        return _thumb_cache["media_id"]

    token = _get_access_token(appid, appsecret)
    png_data = _load_thumbnail()

    files = {"media": ("thumb.png", png_data, "image/png")}
    resp = requests.post(
        f"{WECHAT_API_BASE}/material/add_material",
        params={"access_token": token, "type": "image"},
        files=files,
        timeout=15,
    )
    data = resp.json()
    if "media_id" in data:
        _thumb_cache["media_id"] = data["media_id"]
        _thumb_cache["expires_at"] = now + 86400 * 28  # 永久素材不过期，保守 28 天刷新
        return data["media_id"]

    raise RuntimeError(f"上传缩略图失败: {data.get('errmsg', str(data))}")


# ---------------------------------------------------------------------------
# 内容图片上传：将正文中的外网图片上传到微信 CDN，防止外链被屏蔽
# ---------------------------------------------------------------------------

def _download_image(img_url: str, timeout: int = 10) -> tuple:
    """
    下载外部图片，返回 (bytes, content_type)。
    失败时返回 (None, None)。
    """
    if not img_url or not img_url.startswith("http"):
        return None, None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": urlparse(img_url).scheme + "://" + urlparse(img_url).netloc,
        }
        resp = requests.get(img_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return None, None
        return resp.content, content_type
    except Exception:
        return None, None


def _upload_image_to_wechat(appid: str, appsecret: str, img_data: bytes, filename: str = "pic.jpg") -> str:
    """
    将图片数据上传到微信的 'media/uploadimg' 接口（用于图文内容正文插图）。
    返回微信 CDN URL，失败返回空字符串。
    """
    token = _get_access_token(appid, appsecret)
    try:
        files = {"media": (filename, img_data, "image/jpeg")}
        resp = requests.post(
            f"{WECHAT_API_BASE}/media/uploadimg",
            params={"access_token": token},
            files=files,
            timeout=20,
        )
        data = resp.json()
        if "url" in data:
            return data["url"]
        print(f"[wechat] uploadimg 失败: {data.get('errmsg', str(data))}")
        return ""
    except Exception as e:
        print(f"[wechat] uploadimg 异常: {e}")
        return ""


def upload_image_for_content(appid: str, appsecret: str, external_url: str) -> str:
    """
    将外部图片 URL 转换为微信 CDN URL（上传到微信服务器）。
    带缓存：同一 URL 不会重复上传。
    """
    if not external_url or not external_url.startswith("http"):
        return external_url

    # 已经是微信 CDN 的 URL，无需处理
    parsed = urlparse(external_url)
    if "qpic.cn" in parsed.netloc or "mmbiz" in parsed.netloc:
        return external_url

    # 查缓存
    if external_url in _image_url_cache:
        return _image_url_cache[external_url]

    # 之前上传失败的，不再重试
    if external_url in _failed_image_urls:
        return external_url

    # 下载
    img_data, content_type = _download_image(external_url)
    if not img_data:
        _failed_image_urls.add(external_url)
        return external_url

    # 从 Content-Type 推断扩展名
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
    ext = ext_map.get(content_type, "jpg")
    filename = f"pic_{int(time.time())}.{ext}"

    # 上传
    wx_url = _upload_image_to_wechat(appid, appsecret, img_data, filename)
    if wx_url:
        _image_url_cache[external_url] = wx_url
        return wx_url

    _failed_image_urls.add(external_url)
    return external_url


def replace_images_in_html(appid: str, appsecret: str, html_content: str) -> str:
    """
    扫描 HTML 中所有 <img> 标签的 src 和 data-src 属性，
    将外部图片上传到微信 CDN 并替换 URL，
    同时将 data-src 转为 src（微信公众号富文本要求用 src）。
    返回替换后的 HTML。
    """
    def _replace_img_attr(match):
        tag = match.group(0)
        attr = match.group(1)   # 'src' or 'data-src'
        old_url = match.group(2)

        new_url = upload_image_for_content(appid, appsecret, old_url)
        if new_url != old_url:
            # 把 data-src 也改为 src（微信要求用 src）
            return tag.replace(f'{attr}="{old_url}"', f'{attr}="{new_url}"')
        return tag

    # 匹配 <img ... src="..." ...> 和 <img ... data-src="..." ...>
    pattern = re.compile(r'(src|data-src)="([^"]+)"')
    processed = pattern.sub(_replace_img_attr, html_content)
    return processed


# ---------------------------------------------------------------------------
# 创建草稿
# ---------------------------------------------------------------------------

def create_draft(
    appid: str,
    appsecret: str,
    title: str,
    html_content: str,
    author: str = "",
    digest: str = "",
) -> dict:
    """
    在微信公众号草稿箱创建一篇图文草稿。
    自动上传默认缩略图，完成后返回 media_id。
    """
    token = _get_access_token(appid, appsecret)
    thumb_media_id = _upload_thumb(appid, appsecret)

    # 微信限制：author 需要字节级截断
    def _truncate_utf8(text: str, max_bytes: int) -> str:
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        chars = []
        total = 0
        for ch in text:
            sz = len(ch.encode("utf-8"))
            if total + sz > max_bytes:
                break
            total += sz
            chars.append(ch)
        return "".join(chars)

    safe_author = _truncate_utf8(author, 8) if author else ""

    body = {
        "title": title,
        "author": safe_author,
        "digest": digest,
        "content": html_content,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
        "thumb_media_id": thumb_media_id,
    }

    resp = requests.post(
        f"{WECHAT_API_BASE}/draft/add",
        params={"access_token": token},
        data=json.dumps({"articles": [body]}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=15,
    )
    data = resp.json()
    if "media_id" in data:
        return {"success": True, "media_id": data["media_id"], "errcode": 0}
    return {
        "success": False,
        "errcode": data.get("errcode"),
        "errmsg": data.get("errmsg", "未知错误"),
    }
