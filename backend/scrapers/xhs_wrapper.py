#!/usr/bin/env python3
"""
小红书采集模块 - 封装 Spider_XHS
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Spider_XHS 路径
SPIDER_XHS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Spider_XHS"
sys.path.insert(0, str(SPIDER_XHS_DIR))

# Node.js 路径
NODE_BIN = "/Users/lily/.workbuddy/binaries/node/versions/22.22.2/bin/node"
# Python venv 路径
PYTHON_BIN = "/Users/lily/.workbuddy/binaries/python/envs/default/bin/python"


class XHSWrapper:
    """小红书采集封装器"""

    def __init__(self):
        self._api = None
        self._cookies_str = None

    def reset(self):
        """重置内部状态，下次调用时重新从 .env 加载 Cookie"""
        self._api = None
        self._cookies_str = None

    def _ensure_init(self):
        """延迟初始化，避免导入失败"""
        if self._api is not None:
            return

        from xhs_utils.common_util import init
        from apis.xhs_pc_apis import XHS_Apis
        from xhs_utils.xhs_pc import XHSPcAuth
        from dotenv import load_dotenv

        # init() 内部 load_dotenv() 从 CWD 加载，后端运行时 CWD 是 backend/
        # 而非 Spider_XHS/，导致 .env 找不到、Cookie 为 None。
        # 这里显式从 Spider_XHS/.env 加载，确保 Cookie 可用。
        # override=True 确保扫码刷新后新 Cookie 覆盖旧的环境变量
        env_path = SPIDER_XHS_DIR / ".env"
        if env_path.exists():
            load_dotenv(str(env_path), override=True)

        cookies_str, base_path = init()
        if not cookies_str:
            raise Exception(
                "小红书 Cookie 未配置：请在 Spider_XHS/.env 中设置 COOKIES 字段"
            )
        self._cookies_str = cookies_str
        auth = XHSPcAuth.from_cookie(cookies_str)
        # 搜索 API 不需要 user_id（只有 homefeed/feed 才需要 xy-direction）
        # 跳过 bootstrap() 避免 user/me 调用在 Cookie 过期时直接报错
        self._api = XHS_Apis(auth)

    def search(self, keyword: str, num: int = 20) -> list:
        """搜索笔记"""
        self._ensure_init()
        success, msg, notes = self._api.search_some_note(keyword, require_num=num)
        if not success:
            # 友好提示：Cookie 过期时引导用户扫码刷新
            if "过期" in (msg or "") or "登录" in (msg or ""):
                raise Exception(
                    "小红书登录已过期，请在页面点击「扫码刷新」重新登录"
                )
            raise Exception(f"搜索失败: {msg}")

        result = []
        if notes:
            for n in notes:
                if n.get("model_type") != "note":
                    continue
                card = n.get("note_card", {})
                interact = card.get("interact_info", {})
                note_id = n.get("id", "")
                xsec_token = n.get("xsec_token", "")
                result.append({
                    "note_id": note_id,
                    "xsec_token": xsec_token,
                    "title": card.get("display_title", "无标题"),
                    "type": "视频" if card.get("type") == "video" else "图文",
                    "author": card.get("user", {}).get("nickname", "未知"),
                    "author_id": card.get("user", {}).get("user_id", ""),
                    "likes": self._parse_count(interact.get("liked_count", "0")),
                    "collected": self._parse_count(interact.get("collected_count", "0")),
                    "comments": self._parse_count(interact.get("comment_count", "0")),
                    "shares": self._parse_count(interact.get("share_count", "0")),
                    "url": f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}" if note_id else "",
                    "cover_url": card.get("cover", {}).get("url_default", "") if card.get("cover") else "",
                })
        return result

    def get_note_detail(self, url: str) -> dict:
        """获取笔记详情"""
        self._ensure_init()
        success, msg, detail = self._api.get_note_info(url)
        if not success:
            raise Exception(f"获取详情失败: {msg}")

        items = detail.get("data", {}).get("items", [])
        if not items:
            raise Exception("未找到笔记数据")

        note = items[0].get("note_card", {})
        interact = note.get("interact_info", {})
        tags = [t.get("name", "") for t in note.get("tag_list", []) if t.get("name")]
        images = []
        for img in note.get("image_list", []):
            url_list = img.get("url_default", "") if isinstance(img, dict) else str(img)
            images.append(url_list)

        return {
            "note_id": note.get("note_id", ""),
            "title": note.get("title", "无标题"),
            "desc": note.get("desc", ""),
            "type": "视频" if note.get("type") == "video" else "图文",
            "author": note.get("user", {}).get("nickname", "未知"),
            "author_id": note.get("user", {}).get("user_id", ""),
            "likes": self._parse_count(interact.get("liked_count", "0")),
            "collected": self._parse_count(interact.get("collected_count", "0")),
            "comments": self._parse_count(interact.get("comment_count", "0")),
            "shares": self._parse_count(interact.get("share_count", "0")),
            "tags": tags,
            "images": images,
            "image_count": len(images),
            "video_url": note.get("video", {}).get("media", {}).get("stream", {}).get("h264", [{}])[0].get("master_url", "") if note.get("video") else "",
            "url": url,
        }

    def get_comments(self, note_id: str, xsec_token: str = "") -> list:
        """获取笔记评论"""
        self._ensure_init()
        success, msg, comments = self._api.get_note_all_comment(note_id, xsec_token)
        if not success:
            raise Exception(f"获取评论失败: {msg}")

        result = []
        if comments:
            for c in comments:
                result.append({
                    "id": c.get("id", ""),
                    "content": c.get("content", ""),
                    "author": c.get("user", {}).get("nickname", "未知"),
                    "likes": self._parse_count(c.get("like_count", "0")),
                    "sub_comment_count": c.get("sub_comment_count", 0),
                    "create_time": c.get("create_time", ""),
                    "ip_location": c.get("ip_location", ""),
                })
        return result

    @staticmethod
    def _parse_count(val) -> int:
        """解析点赞数等，支持 '1.2万' 格式"""
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            val = val.strip()
            if "万" in val:
                try:
                    return int(float(val.replace("万", "")) * 10000)
                except ValueError:
                    return 0
            try:
                return int(val)
            except ValueError:
                return 0
        return 0
