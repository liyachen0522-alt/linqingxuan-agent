#!/usr/bin/env python3
"""抖音达人素材下载服务

链路: 达人主页链接 -> Edge 无头浏览器(CDP 注入 Cookie) -> 提取视频列表
     -> 逐条打开视频页捕获无水印直链(video/mp4) -> 下载到桌面林清轩素材/<达人名>/
"""
import os
import re
import json
import time
import threading
import subprocess
import urllib.parse
import urllib.request

import requests
import websocket

# 项目路径
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_DIR, "..", "data")
COOKIE_FILE = os.environ.get("DY_COOKIE_FILE", os.path.join(DATA_DIR, "config", "douyin_cookie.txt"))
DESKTOP_DIR = os.environ.get("KD_DESKTOP_DIR", os.path.expanduser("~/Desktop/林清轩素材"))
EDGE = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# CDP 端口基线（避免与用户浏览器冲突）
_BASE_PORT = 9350
_browser_lock = threading.Lock()
_browser = {"proc": None, "ws": None, "port": None}

# 后台任务状态
TASKS = {}
_tasks_lock = threading.Lock()


# ========== Cookie 管理 ==========

def load_cookie() -> str:
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def has_cookie() -> bool:
    c = load_cookie()
    return bool(c and "sessionid" in c or c and "sid_tt" in c)


def save_cookie(cookie: str):
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        f.write(cookie.strip())


def _cookie_pairs(cookie: str) -> list:
    pairs = []
    for item in cookie.split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        name, _, value = item.partition("=")
        pairs.append((name.strip(), value.strip()))
    return pairs


# ========== Edge 无头浏览器（CDP） ==========

def _find_free_port() -> int:
    """从基线端口开始找空闲端口"""
    import socket
    for port in range(_BASE_PORT, _BASE_PORT + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return _BASE_PORT


def start_browser():
    """启动/复用 Edge 无头实例，注入 Cookie + 反自动化，返回 (proc, ws)"""
    global _browser
    with _browser_lock:
        # 复用已启动的浏览器
        if _browser["ws"]:
            try:
                _cdp(_browser["ws"], "Runtime.evaluate", {"expression": "1"})
                return _browser["proc"], _browser["ws"]
            except Exception:
                _browser["ws"].close()
                _browser["ws"] = None

        port = _find_free_port()
        profile = f"/tmp/dy_profile_{port}"
        proc = subprocess.Popen([
            EDGE, "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--remote-allow-origins=*", f"--user-agent={UA}",
            f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
            "--window-size=1470,956", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 等待 CDP 可用
        ws = None
        try:
            for _ in range(40):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                        json.load(r)
                    break
                except Exception:
                    if proc.poll() is not None:
                        raise RuntimeError("Edge 启动失败")
                    time.sleep(0.5)
            else:
                raise RuntimeError("CDP 连接超时")

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as r:
                targets = json.load(r)
            page = next(t for t in targets if t["type"] == "page")
            ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30)
            tmp = _CdpClient(ws)

            # 反自动化检测
            tmp.cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": ("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                           "window.chrome = window.chrome || {runtime: {}};")
            })

            # 注入 Cookie（多域）
            cookie = load_cookie()
            for name, value in _cookie_pairs(cookie):
                for domain in (".douyin.com", ".iesdouyin.com", ".snssdk.com", ".amemv.com"):
                    tmp.cmd("Network.setCookie",
                            {"name": name, "value": value, "domain": domain, "path": "/"})

            tmp.cmd("Network.enable")
            tmp.cmd("Page.enable")
            _browser.update(proc=proc, ws=ws, port=port)
            return proc, ws
        except Exception:
            if ws:
                try:
                    ws.close()
                except Exception:
                    pass
            proc.terminate()
            raise


def close_browser():
    global _browser
    with _browser_lock:
        if _browser["ws"]:
            try:
                _browser["ws"].close()
            except Exception:
                pass
        if _browser["proc"] and _browser["proc"].poll() is None:
            _browser["proc"].terminate()
        _browser.update(proc=None, ws=None, port=None)


# ---------- 更可靠的 CDP 封装 ----------

class _CdpClient:
    def __init__(self, ws):
        self.ws = ws
        self._id = 0
        self._lock = threading.Lock()

    def cmd(self, method, params=None, timeout=30):
        with self._lock:
            self._id += 1
            mid = self._id
            self.ws.settimeout(timeout)
            self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            while True:
                m = json.loads(self.ws.recv())
                if m.get("id") == mid:
                    if "error" in m:
                        raise RuntimeError(f"CDP {method} 失败: {m['error']}")
                    return m.get("result", {})

    def eval(self, expression, timeout=30):
        r = self.cmd("Runtime.evaluate",
                     {"expression": expression, "returnByValue": True}, timeout=timeout)
        return r.get("result", {}).get("value")

    def listen(self, duration, want_method=None, want_fn=None):
        """在 duration 秒内监听事件，返回匹配 want_fn(params) 的结果列表"""
        out = []
        deadline = time.time() + duration
        self.ws.settimeout(0.3)
        while time.time() < deadline:
            try:
                m = json.loads(self.ws.recv())
            except Exception:
                time.sleep(0.15)
                continue
            if m.get("id") is not None:
                continue  # 命令响应，跳过
            method = m.get("method", "")
            if want_method and method != want_method:
                continue
            params = m.get("params", {})
            if want_fn and want_fn(params):
                out.append(params)
        self.ws.settimeout(30)
        return out


_client_ref = {"client": None}


def get_client():
    """获取全局 CDP client（启动浏览器）"""
    proc, ws = start_browser()
    if _client_ref["client"] is None or _client_ref["client"].ws != ws:
        _client_ref["client"] = _CdpClient(ws)
    return _client_ref["client"]


def restart_client():
    close_browser()
    _client_ref["client"] = None
    return get_client()


# ========== 链接解析 ==========

def extract_sec_uid(url: str) -> str:
    """从达人主页链接提取 sec_uid；支持短链（v.douyin.com）跟随重定向"""
    url = (url or "").strip()
    if not url:
        return ""
    # 已是 sec_uid（形如 MS4wLjAB...）
    m = re.search(r"(MS4wLjAB[\w-]+)", url)
    if m:
        return m.group(1)
    # /user/self -> 用 RENDER_DATA 里当前登录用户
    if "/user/self" in url:
        return "self"
    # 短链重定向
    if "v.douyin.com" in url:
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Cookie": load_cookie()},
                             allow_redirects=True, timeout=15)
            m = re.search(r"user/(MS4wLjAB[\w-]+)", r.url)
            if m:
                return m.group(1)
        except Exception:
            pass
    # 直接路径 /user/{sec_uid}
    m = re.search(r"/user/([^/?#]+)", url)
    if m:
        return m.group(1)
    return ""


def extract_aweme_id(url: str) -> str:
    """从抖音视频链接提取 aweme_id；支持 v.douyin.com 短链跟随重定向。

    覆盖形态：/video/{id}、/share/video/{id}、modal_id=、纯数字串、短链跳转。
    """
    url = (url or "").strip()
    if not url:
        return ""
    m = re.search(r"/video/(\d+)", url) or re.search(r"/share/video/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"modal_id=(\d+)", url)
    if m:
        return m.group(1)
    # 短链跟随重定向
    if "v.douyin.com" in url or "iesdouyin.com" in url:
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Cookie": load_cookie()},
                             allow_redirects=True, timeout=15)
            m = re.search(r"/video/(\d+)", r.url) or re.search(r"modal_id=(\d+)", r.url)
            if m:
                return m.group(1)
        except Exception:
            pass
    # 兜底：裸 15-20 位数字
    m = re.search(r"\b(\d{15,20})\b", url)
    return m.group(1) if m else ""


def safe_name(name: str, fallback="未命名达人") -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', "", name or "").strip(" .")
    return name or fallback


# ========== 主页视频列表 ==========

def _parse_render_data(html_or_none):
    """从 RENDER_DATA 文本解析 JSON；无则返回 None"""
    if not html_or_none:
        return None
    try:
        return json.loads(urllib.parse.unquote(html_or_none))
    except Exception:
        return None


def _walk_find(obj, key, found=None):
    """递归查找所有 key 命中的值"""
    if found is None:
        found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                found.append(v)
            _walk_find(v, key, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk_find(v, key, found)
    return found


def fetch_profile_videos(sec_uid: str, max_scroll=4) -> dict:
    """打开达人主页，收集视频列表。

    返回 {nickname, sec_uid, aweme_count, videos: [{aweme_id, desc, create_time, cover}]}
    """
    client = get_client()
    url = "https://www.douyin.com/user/self" if sec_uid == "self" \
        else f"https://www.douyin.com/user/{sec_uid}"

    client.cmd("Page.navigate", {"url": url})
    time.sleep(10)

    # 1) 标题与 RENDER_DATA
    title = client.eval("document.title") or ""
    render_text = client.eval(
        "document.getElementById('RENDER_DATA') ? document.getElementById('RENDER_DATA').textContent : ''")

    # 2) 滚动加载更多
    for _ in range(max_scroll):
        client.eval("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2.2)

    # 3) DOM 收集视频链接 + 标题（标题即链接文本；封面找卡片内 img/背景图）
    links = client.eval("""Array.from(document.querySelectorAll('a[href*="/video/"]')).map(a=>{
        const m = (a.getAttribute('href')||'').match(/\\/video\\/(\\d+)/);
        const img = a.querySelector('img');
        const bg = img ? '' : ((a.querySelector('[style*=background]')||a.closest('[style*=background]')||{}).style||{}).backgroundImage || '';
        return {id:m?m[1]:'', title:(a.textContent||'').trim(), img: img?img.src:(bg.match(/url\\(['"]?([^'")]+)/)||[])[1]||''};
    })""") or []
    aweme_ids = []
    dom_meta = {}
    for l in links:
        aid = l.get("id", "")
        if aid and aid not in aweme_ids:
            aweme_ids.append(aid)
            dom_meta[aid] = {"desc": l.get("title", ""), "cover": l.get("img", ""),
                             "create_time": None}

    # 4) RENDER_DATA 补充元数据（desc/封面/时间），以 DOM 为主
    meta = dict(dom_meta)
    j = _parse_render_data(render_text)
    if j:
        for lst in _walk_find(j, "aweme_list"):
            for a in lst or []:
                aid = str(a.get("aweme_id", ""))
                if not aid:
                    continue
                cover = ""
                cov = a.get("video", {}).get("cover", {}) or {}
                cul = cov.get("url_list") or []
                if cul:
                    cover = cul[-1] if cul else ""
                meta.setdefault(aid, {})
                if not meta[aid].get("desc"):
                    meta[aid]["desc"] = a.get("desc", "") or ""
                meta[aid]["create_time"] = a.get("create_time")
                if not meta[aid].get("cover"):
                    meta[aid]["cover"] = cover
        # 昵称
        info = j.get("app", {}).get("user", {}).get("info", {})
        if info.get("nickname"):
            title = f"{info['nickname']}的抖音"

    nickname = re.sub(r"的抖音.*$", "", title).strip() or "未命名达人"

    videos = []
    for aid in aweme_ids:
        m = meta.get(aid, {})
        videos.append({
            "aweme_id": aid,
            "desc": m.get("desc", ""),
            "create_time": m.get("create_time"),
            "cover": m.get("cover", ""),
        })

    return {"nickname": safe_name(nickname), "sec_uid": sec_uid,
            "aweme_count": len(videos), "videos": videos}


# ========== 视频无水印直链 ==========

def _is_main_video_url(u: str) -> bool:
    """判断是否为视频主播放地址（无水印 douyinvod 直链）"""
    return "douyinvod.com" in u and "/video/tos/" in u


def fetch_play_urls(aweme_ids: list, per_timeout=12) -> dict:
    """逐个打开视频页，捕获 video/mp4 无水印直链。

    返回 {aweme_id: play_url}
    """
    client = get_client()
    result = {}

    def want(resp_params):
        rp = resp_params.get("response", {})
        mt = rp.get("mimeType", "") or ""
        u = rp.get("url", "") or ""
        return mt == "video/mp4" and _is_main_video_url(u)

    for aid in aweme_ids:
        url = f"https://www.douyin.com/video/{aid}"
        try:
            client.cmd("Page.navigate", {"url": url})
        except Exception:
            pass
        got = client.listen(per_timeout, want_fn=want)
        play = ""
        for params in got:
            u = params.get("response", {}).get("url", "") or ""
            if u:
                play = u
                break
        # 兜底：video 元素 currentSrc（直链模式）
        if not play:
            play = client.eval("(()=>{const v=document.querySelector('video');return v&&v.currentSrc&&v.currentSrc.indexOf('douyinvod')>-1?v.currentSrc:''})()") or ""
        if play:
            result[aid] = play
        time.sleep(0.5)

    return result


# ========== 单条视频直接下载 ==========

def fetch_single_video(aweme_id: str, per_timeout=15) -> dict:
    """打开单个视频页，捕获无水印直链 + 元数据（desc/作者/封面）。

    作者等信息来自页面请求的 aweme/v1/web/aweme/detail 接口响应（事件循环内即时读取）。
    返回 {aweme_id, desc, nickname, cover, play_url}
    """
    client = get_client()
    try:
        client.cmd("Network.enable")
    except Exception:
        pass
    # 加时间戳参数绕过浏览器缓存，确保 detail API 会重新请求（否则 304 无响应可监听）
    url = f"https://www.douyin.com/video/{aweme_id}?_t={int(time.time() * 1000)}"
    try:
        client.cmd("Page.navigate", {"url": url})
    except Exception:
        pass
    time.sleep(2.5)

    # 阶段1：事件循环只收集（视频直链 + detail API 的 requestId），不在循环内发命令
    play = ""
    detail_rids = []
    deadline = time.time() + per_timeout
    client.ws.settimeout(0.3)
    while time.time() < deadline:
        try:
            m = json.loads(client.ws.recv())
        except Exception:
            time.sleep(0.1)
            continue
        if m.get("id") is not None:
            continue
        if m.get("method") != "Network.responseReceived":
            continue
        rp = m.get("params", {}).get("response", {}) or {}
        mt = rp.get("mimeType", "") or ""
        u = rp.get("url", "") or ""
        # 直链
        if not play and mt == "video/mp4" and _is_main_video_url(u):
            play = u
        # 详情 API（可能有多个资源，收集后逐个读）
        if "aweme/v1/web/aweme/detail" in u and rp.get("status") == 200:
            detail_rids.append(m["params"].get("requestId", ""))
        if play and detail_rids:
            break
    client.ws.settimeout(30)

    # 阶段2：循环外逐个读 detail API body（避免与监听循环互相干扰）
    detail = None
    for rid in detail_rids:
        try:
            body = client.cmd("Network.getResponseBody", {"requestId": rid}, timeout=10)
            d = json.loads(body.get("body", "") or "{}")
            aw = d.get("aweme_detail") or {}
            if aw:
                detail = aw
                break
        except Exception:
            continue

    # 兜底：video 元素 currentSrc
    if not play:
        play = client.eval("(()=>{const v=document.querySelector('video');"
                           "return v&&v.currentSrc&&v.currentSrc.indexOf('douyinvod')>-1?v.currentSrc:''})()") or ""

    # 元数据：优先 detail API；兜底页面标题 / DOM
    desc = (detail or {}).get("desc", "") or ""
    nickname = ((detail or {}).get("author", {}) or {}).get("nickname", "") or ""
    cover = ""
    cov = ((detail or {}).get("video", {}) or {}).get("cover", {}) or {}
    cul = cov.get("url_list") or []
    if cul:
        cover = cul[-1]
    if not desc:
        title = client.eval("document.title") or ""
        desc = re.sub(r"\s*[-–—·]?\s*抖音.*$", "", title).strip()
    if not nickname:
        nickname = client.eval("""(()=>{const a=document.querySelector('[data-e2e="user-name"]');
            return a?a.textContent.trim():''})()""") or ""
    if not nickname:
        # DOM 兜底：定位「粉丝N万」所在作者卡片，取其内昵称
        nickname = client.eval("""(()=>{
          const fans = Array.from(document.querySelectorAll('*')).filter(el =>
            el.children.length===0 && /粉丝[0-9.,]+万?/.test(el.textContent||''));
          if (!fans.length) return '';
          let p = fans[0].parentElement, depth = 0;
          while (p && depth < 6) {
            if (/粉丝[0-9.,]+万?/.test(p.textContent||'')) {
              const leaves = Array.from(p.querySelectorAll('*')).filter(el=>el.children.length===0 && el.textContent.trim());
              for (const el of leaves) {
                const t = el.textContent.trim();
                if (t.length >= 2 && t.length <= 20 && !/粉丝|获赞|关注/.test(t)) return t;
              }
            }
            p = p.parentElement; depth++;
          }
          return '';
        })()""") or ""

    return {"aweme_id": aweme_id, "desc": desc,
            "nickname": nickname or "未命名达人", "cover": cover, "play_url": play}


def download_single_video(url: str) -> dict:
    """单条抖音视频链接直接下载到桌面「林清轩素材/<作者昵称>/」。

    支持 v.douyin.com 短链 / douyin.com/video/{id} / share 链接。
    返回 {aweme_id, desc, nickname, path, size, status: downloaded|exists}
    """
    aweme_id = extract_aweme_id(url)
    if not aweme_id:
        raise RuntimeError("无法识别视频链接，请粘贴 v.douyin.com 短链或 douyin.com/video/xxx 链接")

    info = fetch_single_video(aweme_id)
    if not info["play_url"]:
        raise RuntimeError("未获取到播放直链（可能视频已删除/私密，或需要登录）")

    folder = os.path.join(DESKTOP_DIR, safe_name(info["nickname"]))
    os.makedirs(folder, exist_ok=True)
    fn = f"{_clean_desc(info['desc'])}_{aweme_id}.mp4"
    dest = os.path.join(folder, fn)

    # 已存在且非空 → 跳过
    if os.path.exists(dest) and os.path.getsize(dest) > 100_000:
        return {"aweme_id": aweme_id, "desc": info["desc"], "nickname": info["nickname"],
                "path": dest, "size": os.path.getsize(dest), "status": "exists"}

    path, size = download_video(info["play_url"], dest)
    if not path:
        raise RuntimeError(f"下载失败：{size}")
    return {"aweme_id": aweme_id, "desc": info["desc"], "nickname": info["nickname"],
            "path": path, "size": size, "status": "downloaded"}


# ========== 下载 ==========

def download_video(play_url: str, dest_path: str, min_size=100_000) -> tuple:
    """下载视频文件，返回 (路径, 大小)；失败返回 (None, 原因)"""
    try:
        headers = {
            "User-Agent": UA,
            "Referer": "https://www.douyin.com/",
            "Accept": "*/*",
        }
        with requests.get(play_url, headers=headers, stream=True, timeout=90) as r:
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}"
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            tmp = dest_path + ".part"
            size = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)
            if size < min_size:
                os.remove(tmp)
                return None, f"文件过小({size}B)"
            os.rename(tmp, dest_path)
            return dest_path, size
    except Exception as e:
        return None, str(e)


def _clean_desc(desc: str, limit=30) -> str:
    desc = re.sub(r'[\\/:*?"<>|#\s]+', "_", (desc or "").strip())
    desc = desc.strip("_")
    if not desc:
        return "视频"
    return desc[:limit]


# ========== 后台任务 ==========

def create_task(urls: list) -> str:
    """创建后台下载任务，返回 task_id"""
    task_id = f"dy{int(time.time())}{len(TASKS)}"
    with _tasks_lock:
        TASKS[task_id] = {
            "state": "preparing", "urls": urls,
            "profiles": [], "total": 0, "done": 0,
            "current": "", "results": [], "error": "",
        }
    t = threading.Thread(target=_run_task, args=(task_id, urls), daemon=True)
    t.start()
    return task_id


def _update(task_id: str, **kw):
    with _tasks_lock:
        if task_id in TASKS:
            TASKS[task_id].update(kw)


def get_task(task_id: str) -> dict | None:
    with _tasks_lock:
        t = TASKS.get(task_id)
        return dict(t) if t else None


def _run_task(task_id: str, urls: list):
    try:
        all_videos = []
        profiles = []
        for raw in urls:
            sec_uid = extract_sec_uid(raw)
            if not sec_uid:
                continue
            _update(task_id, current=f"正在读取达人主页…")
            profile = fetch_profile_videos(sec_uid)
            if not profile["videos"]:
                continue
            profiles.append(profile)
            for v in profile["videos"]:
                all_videos.append({"profile": profile["nickname"], **v})

        if not all_videos:
            _update(task_id, state="done", done=0, total=0,
                    current="未获取到视频列表", error="未获取到视频列表")
            return

        _update(task_id, state="fetching", total=len(all_videos), done=0,
                profiles=profiles, current="正在解析视频直链…")
        aweme_ids = [v["aweme_id"] for v in all_videos]
        play_map = fetch_play_urls(aweme_ids)

        _update(task_id, state="downloading", total=len(all_videos), done=0,
                current="正在下载视频…")

        results = []
        ok = fail = 0
        for i, v in enumerate(all_videos, 1):
            play = play_map.get(v["aweme_id"], "")
            # 按达人分文件夹
            folder = os.path.join(DESKTOP_DIR, v["profile"])
            os.makedirs(folder, exist_ok=True)
            fn = f"{i:02d}_{_clean_desc(v['desc'])}_{v['aweme_id']}.mp4"
            dest = os.path.join(folder, fn)
            if os.path.exists(dest) and os.path.getsize(dest) > 100_000:
                results.append({**v, "status": "exists", "path": dest, "detail": "已存在，跳过"})
                ok += 1
            elif play:
                _update(task_id, current=f"[{i}/{len(all_videos)}] {v['profile']} {_clean_desc(v['desc'])}")
                path, info = download_video(play, dest)
                if path:
                    results.append({**v, "status": "downloaded", "path": path,
                                    "size": info, "detail": f"{info//1024}KB"})
                    ok += 1
                else:
                    results.append({**v, "status": "error", "path": "", "detail": f"下载失败:{info}"})
                    fail += 1
            else:
                results.append({**v, "status": "error", "path": "",
                                "detail": "未获取到播放直链（可能需登录/视频已删除）"})
                fail += 1
            _update(task_id, done=i)

        _update(task_id, state="done", results=results, ok=ok, fail=fail,
                current=f"完成：成功 {ok}，失败 {fail}")
        close_browser()
    except Exception as e:
        _update(task_id, state="error", error=str(e), current=f"任务异常：{e}")
        close_browser()
