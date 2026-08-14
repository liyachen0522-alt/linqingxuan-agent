#!/usr/bin/env python3
"""
笔记互动数据查询模块
- 自动识别小红书 / 抖音链接
- 小红书：直接 HTTP GET 笔记页 → 解析 window.__INITIAL_STATE__（SSR 渲染，无需 JS 签名）
- 抖音：通过 feishu-douyin-tool Node 服务（端口 4000）获取
- cookie 来源：环境变量 XHS_COOKIES / DY_COOKIES > Spider_XHS/.env 的 COOKIES / DY_COOKIES
"""

import os
import re
import json
import time
import subprocess
import urllib.request
from pathlib import Path

# Node 服务地址
NODE_BASE = os.environ.get("NODE_SERVICE_URL", "http://127.0.0.1:4000")

# Spider_XHS/.env 路径（存放 PC 端 cookie）
# 本文件: .../LinQingXuan-Agent/backend/utils/note_stats.py
# parents[0]=utils, [1]=backend, [2]=LinQingXuan-Agent, [3]=工作区根
SPIDER_ENV = Path(__file__).resolve().parents[3] / "Spider_XHS" / ".env"

NODE_BIN = os.environ.get("NODE_BIN", "/Users/lily/.workbuddy/binaries/node/versions/22.22.2/bin/node")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def detect_platform(url: str) -> str:
    """识别链接平台：xhs / douyin / unknown"""
    url = url.strip()
    # 小红书短链域名有 xhslink.com / xhslink.cn 两种，统一按子串匹配
    if any(d in url for d in ("xiaohongshu.com", "xhslink")):
        return "xhs"
    if any(d in url for d in ("douyin.com", "v.douyin.com", "iesdouyin.com")):
        return "douyin"
    return "unknown"


# ========== Cookie 加载 ==========

def _load_spider_env() -> dict:
    """读取 Spider_XHS/.env"""
    env = {}
    try:
        for line in SPIDER_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    except Exception:
        pass
    return env


def _xhs_cookie() -> str:
    """小红书 cookie：XHS_COOKIES 环境变量 > Spider_XHS/.env 的 COOKIES"""
    env_cookie = os.environ.get("XHS_COOKIES", "").strip()
    if env_cookie:
        return env_cookie
    return _load_spider_env().get("COOKIES", "").strip()


def _dy_cookie() -> str:
    """抖音 cookie：DY_COOKIES 环境变量 > Spider_XHS/.env 的 DY_COOKIES"""
    env_cookie = os.environ.get("DY_COOKIES", "").strip()
    if env_cookie:
        return env_cookie
    return _load_spider_env().get("DY_COOKIES", "").strip()


# ========== 小红书：直接 HTTP + __INITIAL_STATE__ ==========

def _http_get(url: str, cookie: str, timeout: int = 25) -> str:
    """GET 请求返回 HTML 文本"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": cookie,
        "Referer": "https://www.xiaohongshu.com/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _resolve_xhs_url(url: str, cookie: str) -> tuple:
    """
    解析小红书链接，返回 (canonical_url, note_id, xsec_token)。
    短链 xhslink.com / xhslink.cn 会跟随重定向取最终 URL。
    """
    url = url.strip()
    # 短链跟随重定向（小红书分享短链，含 .com / .cn 域名）
    if "xhslink" in url:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Cookie": cookie,
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                url = resp.geturl()
        except Exception:
            pass

    m = re.search(r"/(?:explore|discovery/item|note)/([a-f0-9]{24})", url)
    note_id = m.group(1) if m else ""
    if not note_id:
        # 兜底：取最后一段
        note_id = url.rstrip("/").split("/")[-1].split("?")[0]

    xsec = re.search(r"[?&]xsec_token=([^&]+)", url)
    xsec_token = xsec.group(1) if xsec else ""
    return url, note_id, xsec_token


def _find_object_end(html: str, start: int) -> int:
    """括号配对，处理引号字符串，找到对象字面量结束位置"""
    depth = 0
    in_str = None
    esc = False
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_str:
                in_str = None
        else:
            if c in ('"', "'", "`"):
                in_str = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
    return -1


def _extract_state_js(html: str) -> str:
    """提取 window.__INITIAL_STATE__={...} 整段赋值语句"""
    marker = "window.__INITIAL_STATE__"
    idx = html.find(marker)
    if idx == -1:
        return ""
    start = html.find("{", idx)
    if start == -1:
        return ""
    end = _find_object_end(html, start)
    if end == -1:
        return ""
    return html[idx:end]


def _js_state_to_dict(js_stmt: str) -> dict:
    """用 Node VM 执行 JS 赋值语句（处理 undefined 等 JS 字面量）→ dict"""
    script = ("const window={};\n" + js_stmt +
              "\nconsole.log(JSON.stringify(window.__INITIAL_STATE__));")
    p = subprocess.run([NODE_BIN, "-e", script],
                       capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(f"页面状态解析失败: {p.stderr[:200]}")
    return json.loads(p.stdout)


def _fetch_xhs_stats_once(url: str, cookie_str: str = "") -> dict:
    """
    查询小红书笔记互动数据（单次，不含重试）。
    返回 {platform, title, author, likes, collects, comments, shares, ...}
    """
    cookie_str = cookie_str or _xhs_cookie()
    if not cookie_str:
        raise RuntimeError("未配置小红书 Cookie，请先在小红书网页版登录并配置 COOKIES")

    canon_url, note_id, xsec_token = _resolve_xhs_url(url, cookie_str)
    if not note_id:
        raise RuntimeError(f"无法从小红书链接中识别笔记ID: {url[:80]}")

    fetch_url = canon_url if xsec_token else f"https://www.xiaohongshu.com/explore/{note_id}"
    html = _http_get(fetch_url, cookie_str)

    # 反爬/错误页识别
    if len(html) < 20000 or "当前笔记暂时无法浏览" in html[:3000]:
        raise RuntimeError("笔记暂时无法浏览：可能笔记已删除、设为私密，或 Cookie 失效")

    js_stmt = _extract_state_js(html)
    if not js_stmt:
        raise RuntimeError("页面未包含笔记数据（可能需要登录或 Cookie 已失效）")

    state = _js_state_to_dict(js_stmt)
    ndm = (state.get("note") or {}).get("noteDetailMap") or {}
    note = None
    for key, val in ndm.items():
        if isinstance(val, dict) and val.get("note"):
            cand = val["note"]
            cand_id = cand.get("noteId") or key
            # 优先匹配目标笔记 ID，避免取到推荐位/其他笔记的数据
            if cand_id == note_id:
                note = cand
                break
            note = note or cand  # 兜底：无匹配时暂用第一个
    if not note:
        if xsec_token:
            raise RuntimeError(
                "笔记详情缺失：链接访问凭证可能已过期。请从小红书 App 内重新「分享 → 复制链接」粘贴最新链接")
        raise RuntimeError(
            "无法获取该笔记数据：链接缺少访问凭证。请从小红书 App 内「分享-复制链接」粘贴完整链接")

    # 硬校验：取到的笔记必须是目标笔记，防止串数据
    found_id = note.get("noteId") or ""
    if found_id and found_id != note_id:
        raise RuntimeError("返回的笔记与链接不匹配，请从 App 重新复制链接后重试")

    inter = note.get("interactInfo") or {}
    user = note.get("user") or {}
    imgs = note.get("imageList") or []
    tags = [(t.get("name") or t.get("tagName")) for t in (note.get("tagList") or [])]
    tags = [t for t in tags if t]

    return {
        "platform": "xhs",
        "platform_name": "小红书",
        "title": note.get("title", ""),
        "author": user.get("nickname", ""),
        "author_url": f"https://www.xiaohongshu.com/user/profile/{user.get('userId','')}" if user.get("userId") else "",
        "cover": (imgs[0].get("urlDefault", "") if imgs else ""),
        "type": note.get("type", ""),
        "likes": _to_int(inter.get("likedCount")),
        "collects": _to_int(inter.get("collectedCount")),
        "comments": _to_int(inter.get("commentCount")),
        "shares": _to_int(inter.get("shareCount")),
        "tags": tags,
        "note_url": fetch_url,
        "note_id": note_id,
    }


def fetch_xhs_stats(url: str, cookie_str: str = "", max_retries: int = 2) -> dict:
    """查询小红书笔记互动数据，失败自动重试（max_retries 次）。"""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return _fetch_xhs_stats_once(url, cookie_str)
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_err


# ========== 小红书：图片 + 文案下载 ==========

def fetch_xhs_note_content(url: str, cookie_str: str = "") -> dict:
    """
    获取小红书笔记完整内容（图片列表 + 文案 + 标签 + 元数据）。
    复用 _fetch_xhs_stats_once 的解析逻辑，但返回全部图片 URL 和完整文案。
    """
    cookie_str = cookie_str or _xhs_cookie()
    if not cookie_str:
        raise RuntimeError("未配置小红书 Cookie，请先在小红书网页版登录并配置 COOKIES")

    canon_url, note_id, xsec_token = _resolve_xhs_url(url, cookie_str)
    if not note_id:
        raise RuntimeError(f"无法从小红书链接中识别笔记ID: {url[:80]}")

    fetch_url = canon_url if xsec_token else f"https://www.xiaohongshu.com/explore/{note_id}"
    html = _http_get(fetch_url, cookie_str)

    if len(html) < 20000 or "当前笔记暂时无法浏览" in html[:3000]:
        raise RuntimeError("笔记暂时无法浏览：可能笔记已删除、设为私密，或 Cookie 失效")

    js_stmt = _extract_state_js(html)
    if not js_stmt:
        raise RuntimeError("页面未包含笔记数据（可能需要登录或 Cookie 已失效）")

    state = _js_state_to_dict(js_stmt)
    ndm = (state.get("note") or {}).get("noteDetailMap") or {}
    note = None
    for key, val in ndm.items():
        if isinstance(val, dict) and val.get("note"):
            cand = val["note"]
            cand_id = cand.get("noteId") or key
            if cand_id == note_id:
                note = cand
                break
            note = note or cand
    if not note:
        raise RuntimeError("无法获取笔记详情，请从 App 重新复制链接后重试")

    found_id = note.get("noteId") or ""
    if found_id and found_id != note_id:
        raise RuntimeError("返回的笔记与链接不匹配，请从 App 重新复制链接后重试")

    user = note.get("user") or {}
    imgs = note.get("imageList") or []
    tags = [(t.get("name") or t.get("tagName")) for t in (note.get("tagList") or [])]
    tags = [t for t in tags if t]
    inter = note.get("interactInfo") or {}

    # 提取所有图片的原图 URL
    image_urls = []
    for img in imgs:
        # urlDefault 是默认尺寸，urlPreNoWatermark 可能有无水印原图
        u = img.get("urlDefault") or img.get("urlPre") or ""
        if u:
            # 确保是完整 URL
            if u.startswith("//"):
                u = "https:" + u
            elif not u.startswith("http"):
                u = "https://" + u
            image_urls.append(u)

    # 视频笔记：尝试提取视频封面
    video_url = ""
    if note.get("type") == "video":
        v = note.get("video") or {}
        media = v.get("media") or {}
        stream = media.get("stream") or {}
        for fmt in ("h264", "h265", "h266", "av1"):
            streams = stream.get(fmt) or []
            if streams and isinstance(streams, list):
                video_url = streams[0].get("master_url", "") or streams[0].get("backup_urls", [""])[0]
                if video_url:
                    break
        if not video_url:
            # 兜底：consumer origin
            video_url = v.get("consumer", {}).get("origin_video_key", "")

    return {
        "platform": "xhs",
        "platform_name": "小红书",
        "title": note.get("title", "") or "",
        "desc": note.get("desc", "") or "",
        "author": user.get("nickname", "") or "未命名达人",
        "note_id": note_id,
        "note_url": fetch_url,
        "type": note.get("type", "normal"),
        "image_urls": image_urls,
        "image_count": len(image_urls),
        "video_url": video_url,
        "tags": tags,
        "likes": _to_int(inter.get("likedCount")),
        "collects": _to_int(inter.get("collectedCount")),
        "comments": _to_int(inter.get("commentCount")),
        "shares": _to_int(inter.get("shareCount")),
    }


def _download_file(url: str, dest_path: str, cookie: str, referer: str = "https://www.xiaohongshu.com/") -> int:
    """下载文件到指定路径，返回文件大小（字节）"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Cookie": cookie,
        "Referer": referer,
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)
    return len(data)


def _clean_filename(name: str, limit: int = 40) -> str:
    """清理文件名中的非法字符"""
    name = re.sub(r'[\\/:*?"<>|#\s]+', "_", (name or "").strip())
    name = name.strip("_.")
    return name[:limit] if name else "小红书笔记"


def download_xhs_note(url: str) -> dict:
    """
    下载小红书笔记的图片和文案到桌面 ~/Desktop/林清轩素材/<作者名>/。

    - 图片：下载所有原图，命名为 01.jpg, 02.jpg, ...
    - 文案：保存为 标题_文案.txt（含标题、正文、标签、互动数据、原链接）
    - 视频：如果是视频笔记，额外下载视频文件
    - 幂等：目标文件夹已存在同名文件则跳过

    返回 {status, author, title, image_count, video_downloaded, saved_dir, ...}
    """
    cookie = _xhs_cookie()
    if not cookie:
        raise RuntimeError("未配置小红书 Cookie")

    content = fetch_xhs_note_content(url, cookie)
    author = _clean_filename(content["author"])
    title = _clean_filename(content["title"]) if content["title"] else content["note_id"]
    note_id = content["note_id"]

    # 目标目录
    desktop_dir = os.environ.get("KD_DESKTOP_DIR", os.path.expanduser("~/Desktop/林清轩素材"))
    save_dir = os.path.join(desktop_dir, author)
    os.makedirs(save_dir, exist_ok=True)

    # ---- 下载图片 ----
    downloaded_images = []
    total_size = 0
    for idx, img_url in enumerate(content["image_urls"], 1):
        ext = ".jpg"
        # 从 URL 推断扩展名
        url_lower = img_url.lower().split("?")[0]
        for e in (".png", ".webp", ".jpeg", ".gif"):
            if e in url_lower:
                ext = e
                break
        fname = f"{idx:02d}_{title}{ext}"
        fpath = os.path.join(save_dir, fname)

        if os.path.exists(fpath) and os.path.getsize(fpath) > 1000:
            # 已存在，跳过
            downloaded_images.append({"name": fname, "status": "exists", "size": os.path.getsize(fpath)})
            total_size += os.path.getsize(fpath)
            continue

        try:
            size = _download_file(img_url, fpath, cookie)
            downloaded_images.append({"name": fname, "status": "downloaded", "size": size})
            total_size += size
        except Exception as e:
            downloaded_images.append({"name": fname, "status": "error", "error": str(e)[:100]})

    # ---- 下载视频（如果是视频笔记）----
    video_result = None
    if content.get("video_url") and content["video_url"].startswith("http"):
        vname = f"{title}_{note_id}.mp4"
        vpath = os.path.join(save_dir, vname)
        if os.path.exists(vpath) and os.path.getsize(vpath) > 10000:
            video_result = {"name": vname, "status": "exists", "size": os.path.getsize(vpath)}
        else:
            try:
                vsize = _download_file(content["video_url"], vpath, cookie)
                video_result = {"name": vname, "status": "downloaded", "size": vsize}
                total_size += vsize
            except Exception as e:
                video_result = {"name": vname, "status": "error", "error": str(e)[:100]}

    # ---- 保存文案 ----
    txt_name = f"{title}_文案.txt"
    txt_path = os.path.join(save_dir, txt_name)
    lines = []
    lines.append(f"标题：{content['title']}")
    lines.append(f"作者：{content['author']}")
    lines.append(f"笔记ID：{note_id}")
    lines.append(f"类型：{'视频笔记' if content['type'] == 'video' else '图文笔记'}")
    lines.append("")
    lines.append("─" * 40)
    lines.append("【正文】")
    lines.append(content["desc"] or "(无文案)")
    lines.append("")
    if content["tags"]:
        lines.append("─" * 40)
        lines.append("【标签】")
        lines.append(" ".join(f"#{t}" for t in content["tags"]))
        lines.append("")
    lines.append("─" * 40)
    lines.append("【互动数据】")
    lines.append(f"点赞：{content['likes']}  收藏：{content['collects']}  评论：{content['comments']}  转发：{content['shares']}")
    lines.append("")
    lines.append("─" * 40)
    lines.append("【原链接】")
    lines.append(content["note_url"])
    lines.append("")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    ok_count = sum(1 for i in downloaded_images if i["status"] in ("downloaded", "exists"))
    has_new = any(i["status"] == "downloaded" for i in downloaded_images)
    all_exist = all(i["status"] == "exists" for i in downloaded_images) and downloaded_images

    return {
        "status": "exists" if all_exist else ("downloaded" if has_new else "empty"),
        "author": content["author"],
        "title": content["title"],
        "note_id": note_id,
        "type": content["type"],
        "image_count": len(downloaded_images),
        "images_downloaded": ok_count,
        "images": downloaded_images,
        "video": video_result,
        "text_saved": True,
        "text_path": txt_name,
        "total_size": total_size,
        "save_dir": save_dir,
        "tags": content["tags"],
    }


# ========== 抖音：Edge 无头浏览器（CDP）方案 ==========
# feishu-douyin-tool 的 X-Bogus 签名已失效（接口返回 200 空响应），
# 长期方案：复用 Edge 无头实例加载视频页，监听浏览器自带的 aweme/detail 接口。

def _dy_cookie_str() -> str:
    """抖音 cookie：DY_COOKIES 环境变量 > Spider_XHS/.env 的 DY_COOKIES"""
    return _dy_cookie()


def fetch_dy_stats(url: str, cookie_str: str = "", max_retries: int = 1) -> dict:
    """
    查询抖音视频互动数据（通过 Edge CDP）。
    返回 {platform, title, author, likes, comments, shares, collects, ...}
    """
    from utils.douyin_cdp import fetch_dy_stats as _cdp_fetch

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return _cdp_fetch(url)
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
    raise last_err


# ========== 主入口 ==========

def fetch_note_stats(url: str) -> dict:
    """主入口：自动识别平台，返回互动数据。失败抛 RuntimeError。"""
    platform = detect_platform(url)
    if platform == "xhs":
        return fetch_xhs_stats(url)
    elif platform == "douyin":
        return fetch_dy_stats(url)
    else:
        raise RuntimeError(f"无法识别链接平台，支持小红书和抖音链接，当前链接: {url}")


def fetch_note_stats_batch(urls: list, interval: float = 1.5) -> dict:
    """
    批量查询互动数据（小红书/抖音自动识别）。
    - 逐条独立查询：单条失败不影响其他条
    - 每条之间间隔 interval 秒，降低被限流风险
    - 返回 {total, success_count, fail_count, results:[{index,url,success,data,error}]}
    """
    results = []
    total = len(urls)
    for i, u in enumerate(urls):
        item = {"index": i, "url": u, "success": False, "data": None, "error": ""}
        try:
            item["data"] = fetch_note_stats(u)
            item["success"] = True
        except Exception as e:
            item["error"] = str(e)[:300]
        results.append(item)
        if i < total - 1 and interval > 0:
            time.sleep(interval)
    return {
        "total": total,
        "success_count": sum(1 for r in results if r["success"]),
        "fail_count": sum(1 for r in results if not r["success"]),
        "results": results,
    }


def _to_int(val) -> int:
    """安全转 int"""
    if isinstance(val, (int, float)):
        return int(val)
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return 0


def check_cookie_status() -> dict:
    """检查 cookie 配置状态"""
    return {
        "xhs": bool(_xhs_cookie()),
        "douyin": bool(_dy_cookie()),
        "node_service": _check_node_service(),
        "edge_service": _check_edge_service(),
    }


def _check_edge_service() -> bool:
    """检查 Edge 无头实例是否在运行（抖音 CDP 抓取依赖）"""
    try:
        urllib.request.urlopen(f"{os.environ.get('EDGE_BASE', 'http://127.0.0.1:9350')}/json/version", timeout=3)
        return True
    except Exception:
        return False


def _check_node_service() -> bool:
    """检查 Node 服务是否在运行"""
    try:
        urllib.request.urlopen(f"{NODE_BASE}/", timeout=3)
        return True
    except Exception:
        return False
