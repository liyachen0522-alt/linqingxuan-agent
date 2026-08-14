#!/usr/bin/env python3
"""
抖音数据采集模块
支持: 关键词搜索、视频详情、评论采集
使用方式: 需要用户提供抖音网页版Cookie
"""

import os
import re
import json
import time
import random
import urllib.parse
from pathlib import Path
from http.cookies import SimpleCookie

import requests

# Node.js 路径
NODE_BIN = "/Users/lily/.workbuddy/binaries/node/versions/22.22.2/bin/node"
# 签名JS文件路径
SIGN_JS_PATH = Path(__file__).resolve().parent / "douyin_sign.js"

# Cookie 保存路径
COOKIE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "douyin_cookie.txt"


class DouyinScraper:
    """抖音数据采集器"""

    BASE_URL = "https://www.douyin.com"
    SEARCH_API = "https://www.douyin.com/aweme/v1/web/general/search/single/"
    DETAIL_API = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
    COMMENT_API = "https://www.douyin.com/aweme/v1/web/comment/list/"

    def __init__(self):
        self._cookie = self._load_cookie()
        self._session = requests.Session()
        self._ms_token = ""
        self._ttwid = ""
        self._setup_session()

    def _load_cookie(self) -> str:
        """从文件加载Cookie"""
        if COOKIE_PATH.exists():
            return COOKIE_PATH.read_text(encoding="utf-8").strip()
        return ""

    def _save_cookie(self, cookie: str):
        """保存Cookie到文件"""
        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_PATH.write_text(cookie, encoding="utf-8")

    def _setup_session(self):
        """配置Session headers"""
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._session.headers.update({
            "User-Agent": ua,
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-mobile": "?0",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        })
        if self._cookie:
            self._session.headers["Cookie"] = self._cookie
            # 提取 msToken
            match = re.search(r"msToken=([^;]+)", self._cookie)
            if match:
                self._ms_token = match.group(1)

    def has_cookie(self) -> bool:
        """检查是否有Cookie"""
        return bool(self._cookie)

    def set_cookie(self, cookie: str):
        """设置Cookie"""
        self._cookie = cookie.strip()
        self._save_cookie(self._cookie)
        self._setup_session()

    def _get_a_bogus(self, params_str: str) -> str:
        """通过JS生成 a_bogus 签名"""
        if not SIGN_JS_PATH.exists():
            return ""

        try:
            import subprocess
            result = subprocess.run(
                [NODE_BIN, str(SIGN_JS_PATH), params_str],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    def search(self, keyword: str, num: int = 20) -> list:
        """
        搜索抖音视频（自动选择最佳方式）
        优先使用 SSR 页面解析，失败后尝试 API 方式
        """
        if not self._cookie:
            raise Exception("未设置抖音Cookie，请先在设置页面填入Cookie")

        # 方式1: SSR 页面解析（更可靠，不需要完美签名）
        try:
            result = self.search_without_api(keyword, num)
            if result:
                return result
        except Exception:
            pass

        # 方式2: API 直接调用（需要有效签名）
        return self._search_via_api(keyword, num)

    def _search_via_api(self, keyword: str, num: int = 20) -> list:
        """通过抖音Web API搜索"""

        # 构建查询参数
        params = {
            "search_channel": "aweme_general",
            "keyword": keyword,
            "search_source": "normal_search",
            "query_correct_type": "1",
            "is_filter_search": "0",
            "from_group_id": "",
            "offset": "0",
            "count": str(num),
            "need_filter_settings": "1",
            "list_type": "multi",
            "version_code": "170400",
            "device_platform": "web",
            "device_language": "zh",
            "device_type": "5",
        }

        if self._ms_token:
            params["msToken"] = self._ms_token

        # 生成签名
        params_str = urllib.parse.urlencode(params)
        a_bogus = self._get_a_bogus(params_str)
        if a_bogus:
            params["a_bogus"] = a_bogus

        # 发送请求
        try:
            resp = self._session.get(
                self.SEARCH_API,
                params=params,
                timeout=15,
            )
            data = resp.json()
        except Exception as e:
            raise Exception(f"抖音搜索请求失败: {e}")

        # 解析结果
        result = []
        aweme_list = data.get("data", [])
        for item in aweme_list:
            if item.get("type") != 1:
                continue
            aweme = item.get("aweme_info", {})
            if not aweme:
                continue

            video = self._parse_aweme(aweme)
            if video:
                result.append(video)

        return result[:num]

    def get_video_detail(self, video_id: str) -> dict:
        """获取视频详情"""
        if not self._cookie:
            raise Exception("未设置抖音Cookie")

        params = {
            "aweme_id": video_id,
            "device_platform": "web",
            "version_code": "170400",
        }
        if self._ms_token:
            params["msToken"] = self._ms_token

        params_str = urllib.parse.urlencode(params)
        a_bogus = self._get_a_bogus(params_str)
        if a_bogus:
            params["a_bogus"] = a_bogus

        resp = self._session.get(self.DETAIL_API, params=params, timeout=15)
        data = resp.json()
        aweme = data.get("aweme_detail", {})
        return self._parse_aweme(aweme)

    def _parse_aweme(self, aweme: dict) -> dict:
        """解析视频数据"""
        try:
            author = aweme.get("author", {})
            stats = aweme.get("statistics", {})
            video = aweme.get("video", {})

            # 获取视频播放地址
            play_url = ""
            play_addr = video.get("play_addr", {})
            if play_addr.get("url_list"):
                play_url = play_addr["url_list"][0]

            # 获取封面
            cover_url = ""
            cover = video.get("cover", {})
            if cover.get("url_list"):
                cover_url = cover["url_list"][0]

            # 获取音乐
            music_title = aweme.get("music", {}).get("title", "")

            # 标签
            tags = []
            for t in aweme.get("text_extra", []):
                if t.get("hashtag_name"):
                    tags.append(t["hashtag_name"])

            return {
                "video_id": aweme.get("aweme_id", ""),
                "desc": aweme.get("desc", ""),
                "author": author.get("nickname", "未知"),
                "author_id": author.get("uid", ""),
                "author_fans": author.get("follower_count", 0),
                "likes": stats.get("digg_count", 0),
                "comments": stats.get("comment_count", 0),
                "shares": stats.get("share_count", 0),
                "collects": stats.get("collect_count", 0),
                "plays": stats.get("play_count", 0),
                "duration": video.get("duration", 0),
                "cover_url": cover_url,
                "play_url": play_url,
                "music": music_title,
                "tags": tags,
                "create_time": aweme.get("create_time", 0),
                "url": f"https://www.douyin.com/video/{aweme.get('aweme_id', '')}",
            }
        except Exception:
            return {}

    def search_without_api(self, keyword: str, num: int = 20) -> list:
        """
        备用方案: 通过搜索页面SSR数据获取结果
        不需要API签名，但数据量有限
        """
        search_url = f"{self.BASE_URL}/search/{urllib.parse.quote(keyword)}?type=video"

        try:
            resp = self._session.get(search_url, timeout=15)
            html = resp.text
        except Exception as e:
            raise Exception(f"抖音页面请求失败: {e}")

        # 尝试从 SSR 数据中提取
        result = []
        # 方法1: 搜索 RENDER_DATA
        render_match = re.search(
            r'<script id="RENDER_DATA"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if render_match:
            try:
                raw = urllib.parse.unquote(render_match.group(1))
                data = json.loads(raw)
                # 递归搜索 aweme_info
                result = self._extract_awemes_from_ssr(data, num)
            except (json.JSONDecodeError, KeyError):
                pass

        # 方法2: 搜索 __RENDER_DATA__
        if not result:
            render_match2 = re.search(
                r'window\.__RENDER_DATA__\s*=\s*({.*?});',
                html,
                re.DOTALL,
            )
            if render_match2:
                try:
                    raw = urllib.parse.unquote(render_match2.group(1))
                    data = json.loads(raw)
                    result = self._extract_awemes_from_ssr(data, num)
                except (json.JSONDecodeError, KeyError):
                    pass

        return result[:num]

    def _extract_awemes_from_ssr(self, data, max_count: int) -> list:
        """从SSR数据中递归提取视频信息"""
        result = []

        def _find_awemes(obj):
            if len(result) >= max_count:
                return
            if isinstance(obj, dict):
                if "aweme_info" in obj:
                    video = self._parse_aweme(obj["aweme_info"])
                    if video:
                        result.append(video)
                for v in obj.values():
                    _find_awemes(v)
            elif isinstance(obj, list):
                for item in obj:
                    _find_awemes(item)

        _find_awemes(data)
        return result
