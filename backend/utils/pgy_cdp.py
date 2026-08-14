#!/usr/bin/env python3
"""
蒲公英合作笔记明细 CDP 抓取模块。

蒲公英 notes_detail 接口要求新版 X-S-Common 签名（requests 库的旧版
x-s/x-t 签名被拒，返回 -1），但达人详情页加载时浏览器会自动调用该接口。
本模块复用常驻 Edge 无头实例（remote-debugging-port=9350），通过 CDP
监听 Network 事件抓取 notes_detail 响应体，零签名逆向成本。

用法：
    from utils import pgy_cdp
    notes = pgy_cdp.fetch_coop_notes(user_id)   # -> {"notes": [...], "total": N}
"""

import json
import time
import threading
import urllib.request

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scrapers.pgy_wrapper import pgy_wrapper  # noqa: E402
from xhs_utils.cookie_util import trans_cookies  # noqa: E402

EDGE_PORT = 9350
EDGE_BASE = f"http://127.0.0.1:{EDGE_PORT}"
NAV_WAIT = 20          # 等待达人详情页加载并触发接口
PAGE_URL = "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/{uid}"
WANT_KEY = "/api/solar/kol/data_v2/notes_detail"

_lock = threading.Lock()
_ws_conn = None         # 复用的 WebSocket 连接


def _http_json(path, timeout=8):
    with urllib.request.urlopen(EDGE_BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _edge_alive():
    try:
        _http_json("/json/version", timeout=3)
        return True
    except Exception:
        return False


class _Cdp:
    """极简 CDP 客户端：命令/事件共用一条 WS，事件线程负责收集。"""

    def __init__(self, ws_url):
        from websocket import create_connection
        self.ws = create_connection(ws_url, timeout=30)
        self.mid = [0]
        self._evt_thread = None

    def cmd(self, method, params=None):
        self.mid[0] += 1
        req_id = self.mid[0]
        self.ws.send(json.dumps({"id": req_id, "method": method, "params": params or {}}))
        while True:
            try:
                m = json.loads(self.ws.recv())
            except Exception:
                continue
            if m.get("id") == req_id:
                return m

    def start_listener(self, on_event):
        self._stop = threading.Event()

        def loop():
            self.ws.settimeout(0.05)
            while not self._stop.is_set():
                try:
                    m = json.loads(self.ws.recv())
                except Exception:
                    continue
                try:
                    on_event(m)
                except Exception:
                    pass
        self._evt_thread = threading.Thread(target=loop, daemon=True)
        self._evt_thread.start()

    def send_async(self, method, params=None):
        """发送命令但不等待响应（用于 navigate，避免与监听线程抢消息）"""
        self.mid[0] += 1
        self.ws.send(json.dumps({"id": self.mid[0], "method": method, "params": params or {}}))

    def close(self):
        if not hasattr(self, "_stop"):
            self._stop = threading.Event()
        self._stop.set()
        try:
            self.ws.close()
        except Exception:
            pass


def _new_page_cdp(use_new_tab=False):
    """获取/新建一个 page tab 的 CDP 连接并注入 cookie。
    use_new_tab=True 时通过 /json/new 创建独立 tab（并发抓取互不串扰），用完由调用方关闭。
    """
    tab_id = None
    if use_new_tab:
        try:
            req = urllib.request.Request(EDGE_BASE + "/json/new?about:blank", method="PUT")
            with urllib.request.urlopen(req, timeout=8) as r:
                tab = json.loads(r.read().decode())
            ws_url = tab.get("webSocketDebuggerUrl")
            tab_id = tab.get("id")
            if not ws_url:
                raise RuntimeError("新建 Edge tab 失败: 无 webSocketDebuggerUrl")
        except Exception as e:
            raise RuntimeError(f"新建 Edge tab 失败: {e}") from e
    else:
        tabs = _http_json("/json")
        ws_url = next((t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page"), None)
        if not ws_url:
            raise RuntimeError("Edge 调试实例无可用页面 tab")
    cdp = _Cdp(ws_url)
    cdp.tab_id = tab_id
    cdp.cmd("Network.enable")
    cookies = trans_cookies(pgy_wrapper.cookie_str)
    for name, value in cookies.items():
        for domain in (".pgy.xiaohongshu.com", ".xiaohongshu.com"):
            cdp.cmd("Network.setCookie", {"name": name, "value": value,
                                           "domain": domain, "path": "/"})
    cdp.cmd("Page.addScriptToEvaluateOnNewDocument", {"source":
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"})
    cdp.cmd("Page.enable")
    return cdp


def _fetch_via_browser(user_id, want_key, wait=NAV_WAIT, new_tab=False):
    """导航到达人详情页，抓取 want_key 接口响应体。返回 (url, body_json) 或 (None, None)。"""
    if not _edge_alive():
        raise RuntimeError("Edge 调试实例未运行（端口 9350），请先启动浏览器")
    cdp = _new_page_cdp(use_new_tab=new_tab)
    reqs = {}
    result = {"url": None, "body": None}

    def on_event(m):
        meth = m.get("method")
        if meth == "Network.requestWillBeSent":
            r = m["params"]["request"]
            if want_key in r.get("url", ""):
                reqs[m["params"]["requestId"]] = r["url"]
        elif meth == "Network.loadingFinished":
            rid = m["params"]["requestId"]
            if rid in reqs:
                try:
                    resp = cdp.cmd("Network.getResponseBody", {"requestId": rid})
                    body = resp.get("result", {}).get("body", "")
                    if result["body"] is None and body:
                        result["url"] = reqs[rid]
                        try:
                            result["body"] = json.loads(body)
                        except Exception:
                            result["body"] = {"_raw": body[:500]}
                except Exception:
                    pass

    cdp.start_listener(on_event)
    cdp.send_async("Page.navigate", {"url": PAGE_URL.format(uid=user_id)})
    time.sleep(wait)
    cdp.close()
    if new_tab and cdp.tab_id:
        try:
            req = urllib.request.Request(f"{EDGE_BASE}/json/close/{cdp.tab_id}", method="PUT")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    return result["url"], result["body"]


def fetch_coop_notes(user_id, timeout=35, new_tab=False):
    """
    抓取达人合作笔记明细（近8条）。
    返回 {"total": N, "notes": [{noteId,title,brandName,date,readNum,likeNum,
    collectNum,isAdvertise,isVideo,imgUrl,thirdReadUserNum}, ...],
    overflow_values: 每条笔记的外溢进店量(thirdReadUserNum),
    overflow_median: 外溢进店中位数（含0）, overflow_median_nonzero: 非0笔记中位数}
    失败抛 RuntimeError。new_tab=True 时使用独立 tab 抓取（并发安全）。
    """
    url, body = _fetch_via_browser(user_id, WANT_KEY, wait=min(timeout, 20), new_tab=new_tab)
    if not body:
        raise RuntimeError(f"未捕获到合作笔记接口响应（{user_id}）")
    if body.get("code") != 0:
        raise RuntimeError(f"蒲公英接口错误: {body.get('msg')} (code={body.get('code')})")
    data = body.get("data") or {}
    notes = data.get("list") or []
    vals = [int(n.get("thirdReadUserNum") or 0) for n in notes]
    nonz = [v for v in vals if v > 0]
    import statistics
    return {
        "total": data.get("total") or len(notes),
        "notes": notes,
        "source_url": url,
        # 外溢进店中位数（蒲公英达人详情页「合作笔记」指标：近30日合作笔记中间位置的外溢进店量）
        "overflow_values": vals,
        "overflow_median": int(statistics.median(vals)) if vals else 0,
        "overflow_median_nonzero": int(statistics.median(nonz)) if nonz else 0,
        "overflow_nonzero_count": len(nonz),
    }


def ensure_edge_running():
    """确保 Edge 调试实例在运行（若未运行则返回 False，由调用方提示）"""
    return _edge_alive()


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "677c02110000000015007b1a"
    print("edge alive:", ensure_edge_running())
    try:
        res = fetch_coop_notes(uid)
        print("total:", res["total"])
        for n in res["notes"]:
            print(f"  {n.get('date')} | {n.get('title')[:24]} | {n.get('brandName')} | 阅{n.get('readNum')} 赞{n.get('likeNum')} 藏{n.get('collectNum')} | 广告:{n.get('isAdvertise')}")
    except Exception as e:
        print("ERR:", e)
