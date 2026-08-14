#!/usr/bin/env python3
"""kdocs 达人素材下载与飞书发布服务

链路: kdocs 分享链接 -> Edge 渲染 DOM(或读缓存) -> 提取素材图片 URL
     -> 下载原图 -> 上传飞书 drive -> 批量写多维表格记录(附件字段)
"""
import os
import re
import sys
import time
import json
import hashlib
import subprocess
import urllib.request

import requests

# 项目路径
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
from utils.feishu_service import feishu, MATERIAL_FIELDS  # noqa: E402

FEISHU_API = "https://open.feishu.cn/open-apis"
HTML_DIR = os.environ.get("KD_HTML_DIR", "/tmp/kd_html")
MAT_DIR = os.environ.get("KD_MAT_DIR", "/tmp/kd_mat")
# 桌面下载目录（用户可直接在桌面找到素材）
DESKTOP_DIR = os.environ.get("KD_DESKTOP_DIR", os.path.expanduser("~/Desktop/林清轩素材"))
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

# 素材 CDN 域名（仅取 shapes，排除 docer-files 稻壳水印）
MATERIAL_URL_RE = re.compile(
    r"https://weboffice\.ks3-cn-beijing\.wpscdn\.cn/shapes/[^\"'\s<>]+"
)
TITLE_RE = re.compile(r"<title>([^<]*)</title>")

MIN_SIZE = 2000  # 小于该字节数视为占位图，丢弃

# 已知达人名单（可从标题中识别；分类词则不属于达人）
KNOWN_KOLS = ["金巧巧", "于适"]
CATEGORY_WORDS = [
    "随手", "plog", "po", "场景", "机制", "礼盒", "素材",
    "轻熟龄", "明星类", "随手拍", "随手po",
]


def extract_kol_name(title: str) -> str:
    """从文档标题中提取达人名称；识别不到返回空串。

    支持格式:
      「8.5林清轩明星类（金巧巧）」「林清轩明星类金巧巧」「8.7明星类2（金巧巧)」
      「8.4林清轩金巧巧2(1)」「8.12林清轩于适1」
    分类标题（plog/随手/场景/机制/礼盒）不属于达人，返回空串。
    """
    if not title:
        return ""
    # 1) 明星类（金巧巧） / 明星类金巧巧 / 明星类2（金巧巧)
    m = re.search(r"明星类[（(]?([^）)\d]+)", title)
    if m:
        name = m.group(1).strip("（）() ")
        if name and name not in CATEGORY_WORDS:
            return name
    # 2) 林清轩后紧跟达人名（排除分类词，包含匹配）
    m = re.search(r"林清轩([\u4e00-\u9fa5A-Za-z]+)", title)
    if m:
        seg = m.group(1)
        low = seg.lower()
        if not any(w.lower() in low for w in CATEGORY_WORDS):
            name = re.sub(r"[0-9]+$", "", seg).strip("（）() ")
            if name and 1 < len(name) <= 6 and all("\u4e00" <= c <= "\u9fa5" for c in name):
                return name
    # 3) 直接匹配已知达人
    for k in KNOWN_KOLS:
        if k in title:
            return k
    return ""


def clean_folder_name(title: str) -> str:
    """无达人时：清理标题做文件夹名（去日期前缀/林清轩/括号内容）"""
    t = re.sub(r"^\d+(\.\d+)?", "", title or "").strip()
    t = t.replace("林清轩", "").strip()
    t = re.sub(r"[（(][^）)]*[）)]", "", t).strip()
    t = t.strip(" -_·")
    return t


def safe_folder_name(name: str) -> str:
    """去掉文件夹名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|\s]+', "", name).strip(" .") or "未命名素材"


def desktop_folder_name(link_id: str, title: str) -> str:
    """确定桌面文件夹名：优先达人名，其次清理后的标题，最后回退链接ID"""
    kol = extract_kol_name(title)
    if kol:
        return safe_folder_name(kol)
    cleaned = clean_folder_name(title)
    if cleaned:
        return safe_folder_name(cleaned)
    return link_id


def link_id_of(url: str) -> str:
    """从分享链接/纯 link_id 中提取 link_id"""
    url = url.strip()
    if url.startswith("http"):
        return url.rstrip("/").rsplit("/", 1)[-1]
    return url


def render_link(link_id: str, timeout=40) -> str | None:
    """用 Edge 无头渲染分享页，返回 DOM；失败返回 None"""
    out = os.path.join(HTML_DIR, f"{link_id}.html")
    os.makedirs(HTML_DIR, exist_ok=True)
    url = f"https://www.kdocs.cn/l/{link_id}"
    cmd = (
        f'"{EDGE}" --headless --disable-gpu --no-sandbox --disable-dev-shm-usage '
        f'--virtual-time-budget=12000 --dump-dom "{url}"'
    )
    try:
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, timeout=timeout)
        dom = r.stdout.decode("utf-8", errors="replace")
        if len(dom) > 5000:
            with open(out, "w", encoding="utf-8") as f:
                f.write(dom)
            return dom
    except Exception:
        pass
    # 兜底：读已有缓存
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return open(out, encoding="utf-8", errors="replace").read()
    return None


def get_dom(link_id: str) -> str | None:
    """优先读缓存 HTML，缺失则尝试渲染"""
    out = os.path.join(HTML_DIR, f"{link_id}.html")
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return open(out, encoding="utf-8", errors="replace").read()
    return render_link(link_id)


def extract_title(dom: str) -> str:
    m = TITLE_RE.search(dom)
    title = m.group(1).strip() if m else ""
    # 去掉站点后缀
    for suffix in ("_金山文档", "-金山文档", "金山文档", "WPS", "Kdocs"):
        title = title.replace(suffix, "")
    return title.strip() or "未命名素材"


def extract_material_urls(dom: str) -> list[str]:
    urls = []
    for m in MATERIAL_URL_RE.finditer(dom):
        u = m.group(0).replace("&amp;", "&")
        if u not in urls:
            urls.append(u)
    return urls


def download_material(url: str, out_dir: str):
    """下载素材图，返回 (本地路径, 大小)；失败返回 (None, 原因)"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=30).read()
        if len(data) < MIN_SIZE:
            return None, f"文件过小({len(data)}B)"
        h = hashlib.sha256(url.encode()).hexdigest()[:16]
        ext = ".webp" if ".webp" in url else ".png"
        fn = f"{h}{ext}"
        path = os.path.join(out_dir, fn)
        with open(path, "wb") as f:
            f.write(data)
        return path, len(data)
    except Exception as e:
        return None, str(e)


def upload_to_feishu(path: str, token: str, cfg: dict):
    """上传图片到飞书 drive，返回 file_token"""
    size = os.path.getsize(path)
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    mime = {
        "webp": "image/webp", "png": "image/png",
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
    }.get(ext, "image/png")
    name = os.path.basename(path)
    with open(path, "rb") as f:
        files = {"file": (name, f, mime)}
        data = {
            "file_name": name,
            "parent_type": "bitable_file",
            "parent_node": cfg["app_token"],
            "size": str(size),
        }
        r = requests.post(
            f"{FEISHU_API}/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {token}"},
            data=data, files=files, timeout=30,
        )
    res = r.json()
    if res.get("code") != 0:
        raise RuntimeError(f"上传飞书失败: {res.get('msg')} (code={res.get('code')})")
    return res["data"]["file_token"]


def list_published_links() -> set:
    """查询表格中已发布的来源链接 link_id 集合（用于去重）"""
    try:
        cfg = feishu.get_config()
        token = feishu._get_token()
        url = f"{FEISHU_API}/bitable/v1/apps/{cfg['app_token']}/tables/{cfg['table_id']}/records"
        page_token = None
        done = set()
        while True:
            params = {"page_size": 200}
            if page_token:
                params["page_token"] = page_token
            r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                             params=params, timeout=15)
            data = r.json()
            if data.get("code") != 0:
                break
            for rec in data.get("data", {}).get("items", []):
                link = rec.get("fields", {}).get("来源链接", {})
                if isinstance(link, dict) and link.get("text"):
                    done.add(link["text"])
            page_token = data.get("data", {}).get("page_token")
            if not page_token or not data.get("data", {}).get("has_more"):
                break
        return done
    except Exception:
        return set()


def publish_link(link_id: str) -> dict:
    """处理单条链接: 提取 -> 下载 -> 上传 -> 写记录

    返回 {link, title, count, status, detail}
    status: published(已发布) / skipped(无素材) / exists(已存在) / error
    """
    cfg = feishu.get_config()
    if not feishu.is_configured():
        return {"link": link_id, "title": "", "count": 0,
                "status": "error", "detail": "飞书未配置"}

    dom = get_dom(link_id)
    if not dom:
        return {"link": link_id, "title": "", "count": 0,
                "status": "error", "detail": "页面渲染失败/无缓存，稍后重试"}

    title = extract_title(dom)
    urls = extract_material_urls(dom)
    if not urls:
        return {"link": link_id, "title": title, "count": 0,
                "status": "skipped", "detail": "该表无 shapes 素材"}

    # 去重
    if link_id in list_published_links():
        return {"link": link_id, "title": title, "count": len(urls),
                "status": "exists", "detail": "已发布过"}

    # 下载 + 上传
    out_dir = os.path.join(MAT_DIR, link_id)
    os.makedirs(out_dir, exist_ok=True)
    token = feishu._get_token()
    uploaded = []
    failed = []
    for url in urls:
        path, info = download_material(url, out_dir)
        if not path:
            failed.append(f"下载失败:{info}")
            continue
        try:
            ftok = upload_to_feishu(path, token, cfg)
            uploaded.append({
                "file_token": ftok,
                "name": os.path.basename(path),
                "type": "image",
            })
        except Exception as e:
            failed.append(f"上传失败:{e}")

    if not uploaded:
        return {"link": link_id, "title": title, "count": 0,
                "status": "error", "detail": "; ".join(failed) or "无可用素材"}

    # 写记录（来源链接为超链接对象）
    record = {
        "素材名称": f"{title}（{len(uploaded)}张）",
        "来源链接": {"text": link_id, "link": f"https://www.kdocs.cn/l/{link_id}"},
        "素材图片": uploaded,
        "同步时间": int(time.time() * 1000),
    }
    try:
        added = feishu.add_records([record], auto_fields=MATERIAL_FIELDS)
        detail = f"发布成功 {len(uploaded)} 张"
        if failed:
            detail += "；" + "; ".join(failed[:3])
        return {"link": link_id, "title": title, "count": len(uploaded),
                "status": "published", "detail": detail}
    except Exception as e:
        return {"link": link_id, "title": title, "count": len(uploaded),
                "status": "error", "detail": f"写记录失败:{e}"}


def publish_many(links: list[str]) -> dict:
    results = []
    ok = exists = skipped = err = 0
    for raw in links:
        lid = link_id_of(raw)
        if not lid:
            continue
        try:
            res = publish_link(lid)
        except Exception as e:
            res = {"link": lid, "title": "", "count": 0, "status": "error", "detail": str(e)}
        results.append(res)
        if res["status"] == "published":
            ok += 1
        elif res["status"] == "exists":
            exists += 1
        elif res["status"] == "skipped":
            skipped += 1
        else:
            err += 1
    return {
        "ok": ok, "exists": exists, "skipped": skipped, "error": err,
        "total": len(results), "results": results,
    }


# ========== 桌面下载模式（不经过飞书，直接下载到桌面） ==========

def download_to_desktop(link_id: str) -> dict:
    """处理单条链接，直接下载素材到桌面文件夹（不涉及飞书）

    返回 {link, title, count, status, detail, folder, files}
    status: downloaded(已下载) / cached(桌面已有) / skipped(无素材) / error
    """
    dom = get_dom(link_id)
    if not dom:
        return {"link": link_id, "title": "", "count": 0,
                "status": "error", "detail": "页面渲染失败/无缓存，稍后重试",
                "folder": "", "files": []}

    title = extract_title(dom)
    urls = extract_material_urls(dom)
    if not urls:
        return {"link": link_id, "title": title, "count": 0,
                "status": "skipped", "detail": "该表无 shapes 素材",
                "folder": "", "files": []}

    # 桌面按「达人名/分类名」建文件夹，重复下载时跳过已存在文件
    folder_name = desktop_folder_name(link_id, title)
    folder = os.path.join(DESKTOP_DIR, folder_name)
    os.makedirs(folder, exist_ok=True)
    downloaded, skipped_existing, failed = [], 0, []

    for url in urls:
        h = hashlib.sha256(url.encode()).hexdigest()[:16]
        ext = ".webp" if ".webp" in url else ".png"
        dest = os.path.join(folder, f"{h}{ext}")
        if os.path.exists(dest) and os.path.getsize(dest) >= MIN_SIZE:
            skipped_existing += 1
            downloaded.append(os.path.basename(dest))
            continue
        path, info = download_material(url, folder)
        if not path:
            failed.append(info)
        else:
            downloaded.append(os.path.basename(path))

    if not downloaded:
        return {"link": link_id, "title": title, "count": 0,
                "status": "error", "detail": "; ".join(failed) or "无可用素材",
                "folder": folder, "files": []}

    detail = f"已保存 {len(downloaded)} 张到桌面"
    if skipped_existing:
        detail += f"（{skipped_existing} 张已存在）"
    if failed:
        detail += "；" + "; ".join(failed[:3])
    return {"link": link_id, "title": title, "count": len(downloaded),
            "status": "downloaded", "detail": detail,
            "folder": folder, "files": sorted(downloaded)}


def download_many_to_desktop(links: list[str]) -> dict:
    """批量下载到桌面，返回统计与明细"""
    results = []
    ok = skipped = err = 0
    for raw in links:
        lid = link_id_of(raw)
        if not lid:
            continue
        try:
            res = download_to_desktop(lid)
        except Exception as e:
            res = {"link": lid, "title": "", "count": 0, "status": "error",
                   "detail": str(e), "folder": "", "files": []}
        results.append(res)
        if res["status"] == "downloaded":
            ok += 1
        elif res["status"] == "skipped":
            skipped += 1
        else:
            err += 1
    return {
        "ok": ok, "skipped": skipped, "error": err,
        "total": len(results), "results": results,
        "desktop_dir": DESKTOP_DIR,
    }


def organize_desktop_folders() -> dict:
    """把桌面素材目录中按「链接ID」命名的文件夹，整理为「达人名/分类名」。

    - 读取缓存 HTML 提取标题 → 达人名/分类名
    - 目标文件夹已存在则合并文件（不覆盖同名），否则直接重命名
    - 返回整理明细
    """
    renamed, merged, failed, unchanged = [], [], [], 0
    if not os.path.isdir(DESKTOP_DIR):
        return {"renamed": renamed, "merged": merged, "failed": failed,
                "unchanged": unchanged, "desktop_dir": DESKTOP_DIR}

    for name in sorted(os.listdir(DESKTOP_DIR)):
        src = os.path.join(DESKTOP_DIR, name)
        if not os.path.isdir(src) or name.startswith("."):
            continue
        # 已经是中文/达人名格式则跳过（2字符以上且不含纯ID特征）
        if re.fullmatch(r"[a-zA-Z0-9]{8,}", name) is None and not name.isascii():
            unchanged += 1
            continue
        # 读取该链接的缓存标题
        dom = get_dom(name)
        if not dom:
            failed.append({"from": name, "reason": "无缓存，无法识别达人"})
            continue
        title = extract_title(dom)
        target = desktop_folder_name(name, title)
        dst = os.path.join(DESKTOP_DIR, target)
        if dst == src:
            unchanged += 1
            continue
        if os.path.exists(dst):
            # 合并：把源文件夹文件移入目标，跳过同名文件
            moved = 0
            for fn in os.listdir(src):
                s = os.path.join(src, fn)
                d = os.path.join(dst, fn)
                if os.path.isfile(s):
                    if not os.path.exists(d):
                        os.rename(s, d)
                        moved += 1
            # 清理空的源文件夹
            if not os.listdir(src):
                os.rmdir(src)
            merged.append({"from": name, "to": target, "moved": moved})
        else:
            try:
                os.rename(src, dst)
                renamed.append({"from": name, "to": target})
            except Exception as e:
                failed.append({"from": name, "reason": str(e)})
    return {"renamed": renamed, "merged": merged, "failed": failed,
            "unchanged": unchanged, "desktop_dir": DESKTOP_DIR}
