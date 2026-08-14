#!/usr/bin/env python3
"""
抖音视频互动数据 CDP 抓取模块（长期方案）。

背景：feishu-douyin-tool 的 X-Bogus 签名已失效（详情 API 返回 200 空响应），
改用常驻 Edge 无头实例（remote-debugging-port=9350）加载视频页，监听浏览器
自带调用的 /aweme/v1/web/aweme/detail 接口响应，零签名逆向成本。

支持链接：
  - https://v.douyin.com/xxxx/    （短链，浏览器自动跳转）
  - https://www.douyin.com/video/xxxx
  - https://www.douyin.com/note/xxxx   （图集笔记）

用法：
    from utils import douyin_cdp
    data = douyin_cdp.fetch_dy_stats("https://v.douyin.com/xxxx/")
    返回 {platform, title, author, likes, collects, comments, shares, ...}
    失败抛 RuntimeError
"""

import json
import re
import sys
import time
import threading
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from utils.pgy_cdp import _Cdp, _http_json, EDGE_BASE  # noqa: E402

# 监听的详情接口关键字
WANT_KEY = "/aweme/v1/web/aweme/detail/"
NAV_TIMEOUT = 20          # 单条最多等待秒数
CHECK_INTERVAL = 0.5      # 轮询间隔


def _edge_alive() -> bool:
    try:
        _http_json("/json/version", timeout=3)
        return True
    except Exception:
        return False


def _dy_cookie_pairs() -> dict:
    """读取 DY_COOKIES（环境变量 > Spider_XHS/.env）并解析为 dict"""
    cookie_str = ""
    try:
        from note_stats import _dy_cookie  # noqa: F401
        cookie_str = _dy_cookie()
    except Exception:
        pass
    if not cookie_str:
        return {}
    pairs = {}
    for p in cookie_str.split(";"):
        p = p.strip()
        if "=" in p:
            k, v = p.split("=", 1)
            pairs[k.strip()] = v.strip()
    return pairs


def _inject_dy_cookies(cdp: _Cdp):
    """注入抖音关键 cookie（ttwid / odin_tt / sessionid_ss 等），提升数据获取成功率"""
    pairs = _dy_cookie_pairs()
    keys = ("ttwid", "odin_tt", "sessionid_ss", "passport_csrf_token",
            "uid_tt", "sid_tt", "msToken", "passport_auth_status", "sid_guard")
    injected = 0
    for name, value in pairs.items():
        if name in keys and value:
            cdp.cmd("Network.setCookie", {"name": name, "value": value,
                                          "domain": ".douyin.com", "path": "/"})
            injected += 1
    return injected


def _new_tab():
    """创建独立 tab，返回 (cdp, tab_id)"""
    req = urllib.request.Request(EDGE_BASE + "/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(req, timeout=8) as r:
        tab = json.loads(r.read().decode())
    ws_url = tab.get("webSocketDebuggerUrl")
    tab_id = tab.get("id")
    if not ws_url:
        raise RuntimeError("新建 Edge tab 失败: 无 webSocketDebuggerUrl")
    cdp = _Cdp(ws_url)
    cdp.cmd("Network.enable")
    cdp.cmd("Page.enable")
    cdp.cmd("Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"})
    return cdp, tab_id


def _close_tab(tab_id):
    try:
        req = urllib.request.Request(f"{EDGE_BASE}/json/close/{tab_id}", method="PUT")
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _extract_from_detail(body: dict) -> dict:
    """从 aweme_detail 接口响应中提取互动数据"""
    ad = body.get("aweme_detail") or {}
    if not ad:
        raise RuntimeError("抖音详情响应中无 aweme_detail 数据")
    st = ad.get("statistics") or {}
    author = ad.get("author") or {}
    aweme_type = ad.get("aweme_type", 0)

    def to_int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    return {
        "platform": "douyin",
        "platform_name": "抖音",
        "title": ad.get("desc", ""),
        "author": author.get("nickname", ""),
        "author_url": f"https://www.douyin.com/user/{author.get('sec_uid','')}" if author.get("sec_uid") else "",
        "cover": "",
        "type": "视频" if to_int(aweme_type) == 0 else "图集",
        "likes": to_int(st.get("digg_count")),
        "collects": to_int(st.get("collect_count")),
        "comments": to_int(st.get("comment_count")),
        "shares": to_int(st.get("share_count")),
        "tags": [],
        "note_url": "",
        "video_id": ad.get("aweme_id", ""),
        "source": "cdp",
    }


def fetch_dy_stats(url: str, timeout: int = NAV_TIMEOUT) -> dict:
    """
    通过 Edge 无头浏览器获取抖音视频互动数据。
    浏览器打开链接（短链自动跳转）→ 监听 detail 接口 → 解析 statistics。
    失败抛 RuntimeError。
    """
    if not _edge_alive():
        raise RuntimeError("Edge 调试实例未运行（端口 9350），请先启动浏览器后重试")

    cdp, tab_id = _new_tab()
    result = {"body": None, "url": None}
    reqs = {}
    lock = threading.Lock()

    def on_event(m):
        meth = m.get("method")
        try:
            if meth == "Network.requestWillBeSent":
                r = m["params"]["request"]
                if WANT_KEY in r.get("url", ""):
                    reqs[m["params"]["requestId"]] = r["url"]
            elif meth == "Network.loadingFinished":
                rid = m["params"]["requestId"]
                if rid in reqs:
                    with lock:
                        if result["body"] is not None:
                            return
                    try:
                        resp = cdp.cmd("Network.getResponseBody", {"requestId": rid})
                        body = resp.get("result", {}).get("body", "")
                        if body:
                            with lock:
                                result["body"] = json.loads(body)
                                result["url"] = reqs[rid]
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        cdp.start_listener(on_event)
        injected = _inject_dy_cookies(cdp)
        cdp.send_async("Page.navigate", {"url": url})
        # 轮询等待详情接口响应
        deadline = time.time() + timeout
        while time.time() < deadline:
            with lock:
                if result["body"] is not None:
                    break
            time.sleep(CHECK_INTERVAL)
    finally:
        try:
            cdp.close()
        except Exception:
            pass
        _close_tab(tab_id)

    if result["body"] is None:
        raise RuntimeError(
            "抖音数据获取超时：视频可能已删除、设为私密，或需要登录（请更新 DY_COOKIES）")
    return _extract_from_detail(result["body"])


if __name__ == "__main__":
    import sys as _s
    u = _s.argv[1] if len(_s.argv) > 1 else "https://v.douyin.com/vC__U_h0uQk/"
    print("edge alive:", _edge_alive())
    try:
        d = fetch_dy_stats(u)
        print(f"{d['platform_name']} | {d['title'][:40]} | 作者:{d['author']} | "
              f"赞{d['likes']} 藏{d['collects']} 评{d['comments']} 转{d['shares']}")
    except Exception as e:
        print("ERR:", e)
