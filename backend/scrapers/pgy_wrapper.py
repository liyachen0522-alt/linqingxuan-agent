#!/usr/bin/env python3
"""
蒲公英平台（pgy.xiaohongshu.com）采集封装
依赖 Spider_XHS 的 PuGongYingAPI，使用品牌账号 Cookie（PGY_COOKIES）
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
SPIDER_XHS_DIR = BASE_DIR / "Spider_XHS"
sys.path.insert(0, str(SPIDER_XHS_DIR))

from dotenv import load_dotenv
from xhs_utils.cookie_util import trans_cookies
from xhs_utils.http_util import REQUEST_TIMEOUT

# 加载 .env（Spider_XHS/.env 中的 PGY_COOKIES）
load_dotenv(str(SPIDER_XHS_DIR / ".env"))


class PgyWrapper:
    """蒲公英平台 API 封装"""

    def __init__(self):
        self.cookie_str = os.environ.get("PGY_COOKIES", "").strip()
        self._api = None
        self._cookies = None

    # ---------- 基础 ----------

    def _ensure_api(self):
        """懒加载 PuGongYingAPI"""
        if self._api is None:
            from apis.xhs_pugongying_apis import PuGongYingAPI
            self._api = PuGongYingAPI()
        return self._api

    def has_cookie(self):
        return bool(self.cookie_str)

    def get_cookie_status(self):
        """检查蒲公英 Cookie 状态"""
        if not self.has_cookie():
            return {"has_cookie": False, "msg": "未配置蒲公英 Cookie（.env 中 PGY_COOKIES）"}
        try:
            info = self.get_self_info()
            return {
                "has_cookie": True,
                "valid": True,
                "nickname": info.get("nickName"),
                "company": info.get("companyName"),
                "shop": info.get("arkShopName"),
                "role": info.get("role"),
                "userId": info.get("userId"),
                "permissions": info.get("permissions", []),
            }
        except Exception as e:
            return {"has_cookie": True, "valid": False, "msg": str(e)}

    def get_self_info(self):
        """获取当前品牌账号信息"""
        api = self._ensure_api()
        cookies = trans_cookies(self.cookie_str)
        result = api.get_self_info(cookies)
        if result.get("code") != 0:
            raise Exception(f"蒲公英登录无效: {result.get('msg')} (code={result.get('code')})")
        return result.get("data", {})

    # ---------- 类目 ----------

    def get_categories(self):
        """获取达人类目树"""
        api = self._ensure_api()
        cookies = trans_cookies(self.cookie_str)
        return api.get_all_categories(cookies)

    # ---------- 达人列表 ----------

    def get_kols(self, page=1, category=None, num=20, sort=None, keyword=None,
                 min_fans=None, min_overflow=None):
        """
        获取达人列表
        category: 一级类目名，如 "美妆" / "护肤"
        sort: 排序，comprehensiverank(综合) / fansrank(粉丝) / price(报价)
        keyword: 昵称/标签关键词过滤
        min_fans: 最低粉丝数过滤
        min_overflow: 最低外溢进店数过滤
        """
        api = self._ensure_api()
        cookies = trans_cookies(self.cookie_str)

        # 构造 contentTag
        content_tag = None
        if category:
            categories = self.get_categories()
            for c in categories:
                if category in c.get("taxonomy1Tag", ""):
                    content_tag = [c["taxonomy1Tag"]]
                    break

        user_list, total = api.get_user_by_page(page, cookies, content_tag)
        # 格式化为前端友好结构
        kols = []
        for u in user_list:
            kol = self._format_kol(u)
            if keyword and keyword not in kol.get("name", "") and keyword not in str(kol.get("personal_tags", "")):
                continue
            if min_fans and (kol.get("fansCount") or 0) < min_fans:
                continue
            if min_overflow and (kol.get("overflowNum") or 0) < min_overflow:
                continue
            kols.append(kol)
        return {"total": total, "kols": kols[:num]}

    @staticmethod
    def _format_kol(u):
        """蒲公英原始数据 → 前端友好结构"""
        # 粉丝数（fansNum 是真实值，fansCount 可能为0）
        fans_num = u.get("fansNum") or 0
        try:
            fans_num = int(fans_num)
        except (ValueError, TypeError):
            fans_num = 0
        if fans_num >= 10000:
            fans_str = f"{fans_num / 10000:.1f}万"
        elif fans_num > 0:
            fans_str = str(fans_num)
        else:
            fans_str = "0"

        # 报价
        def _price(p):
            if not p:
                return None
            if isinstance(p, dict):
                return p.get("value") or p.get("str") or p.get("min")
            return p

        picture_price = _price(u.get("picturePrice"))
        video_price = _price(u.get("videoPrice"))
        lower_price = _price(u.get("lowerPrice"))

        # 位置
        location = u.get("location") or ""
        if isinstance(location, dict):
            location = location.get("name") or location.get("value") or ""

        return {
            "userId": u.get("userId"),
            "name": u.get("name"),
            "redId": u.get("redId"),
            "headPhoto": u.get("headPhoto"),
            "location": location,
            "type": u.get("type"),
            "userType": u.get("userType"),
            "fansCount": fans_num,
            "fansCountStr": fans_str,
            "totalNoteCount": u.get("totalNoteCount") or u.get("businessNoteCount") or 0,
            "businessNoteCount": u.get("businessNoteCount") or 0,
            "picturePrice": picture_price,
            "videoPrice": video_price,
            "lowerPrice": lower_price,
            "showPrice": u.get("showPrice"),
            "personalTags": u.get("personalTags") or u.get("featureTags") or [],
            "recommend": u.get("recommend"),
            "homePageDisplay": u.get("homePageDisplay"),
            # 达人质量/外溢字段
            "gender": u.get("gender"),
            "currentLevel": u.get("currentLevel"),
            "fans30GrowthRate": u.get("fans30GrowthRate"),
            "fans30GrowthNum": u.get("fans30GrowthNum"),
            "fansEngageNum": u.get("fansEngageNum"),
            # 外溢进店：优先 overflowNum，退而用 30天商品点击UV(mCpuvNum30d) 作为代理指标
            "overflowNum": u.get("overflowNum") or u.get("mCpuvNum30d") or 0,
            "mCpuvNum30d": u.get("mCpuvNum30d") or 0,
            "fansActiveIn28dLv": u.get("fansActiveIn28dLv"),
            "fansEngageNum30dLv": u.get("fansEngageNum30dLv"),
            "clickMidNum": u.get("clickMidNum"),
            "interMidNum": u.get("interMidNum"),
            "fansRiseNum": u.get("fansRiseNum"),
            "predictiveExposure": u.get("predictiveExposure"),
            "kolType": u.get("kolType"),
            "cooperType": u.get("cooperType"),
        }

    # ---------- 达人详情 ----------

    def get_kol_detail(self, user_id):
        """获取达人详细数据（粉丝画像、历史趋势、笔记数据）"""
        api = self._ensure_api()
        cookies = trans_cookies(self.cookie_str)
        result = {}
        detail = api.get_user_detail(user_id, cookies)
        if detail.get("code") == 0:
            result["detail"] = detail.get("data", {})
        else:
            result["detail_error"] = detail.get("msg")
        fans = api.get_user_fans_detail(user_id, cookies)
        if fans.get("code") == 0:
            result["fans"] = fans.get("data", {})
        else:
            result["fans_error"] = fans.get("msg")
        notes = api.get_user_notes_detail(user_id, cookies)
        if notes.get("code") == 0:
            result["notes"] = notes.get("data", {})
        else:
            result["notes_error"] = notes.get("msg")
        return result

    # ---------- 链接解析 & 达人主页完整数据 ----------

    @staticmethod
    def extract_user_id(url_or_id):
        """
        从蒲公英链接中解析 userId（24位hex 或数字）。
        支持：blogger-detail/{id} / advertiser/kol/{id} / mcn/kol/{id} / kol/{id}、
        直接传 userId、带查询参数的完整链接；短链自动跟随重定向。
        返回 (user_id, source_url)；解析失败返回 (None, None)。
        """
        import re as _re
        import requests as _req

        if not url_or_id:
            return None, None
        text = str(url_or_id).strip()

        # 1) 直接就是 userId
        if _re.fullmatch(r"[0-9a-f]{24}", text):
            return text, text
        if _re.fullmatch(r"\d{6,20}", text):
            return text, text

        # 2) 完整链接：从路径中提取 userId 段
        for pat in (
            r"/(?:blogger-detail|advertiser/kol|mcn/kol|infra_v2/mcn/kol|kol)/([0-9a-f]{24})",
            r"/(?:blogger-detail|advertiser/kol|mcn/kol|kol)/(\d{6,20})",
        ):
            m = _re.search(pat, text)
            if m:
                return m.group(1), text
        # 路径任意位置出现 24 位 hex 段
        m = _re.search(r"/([0-9a-f]{24})(?:[/?#]|$)", text)
        if m:
            return m.group(1), text
        m = _re.search(r"/(\d{6,20})(?:[/?#]|$)", text)
        if m:
            return m.group(1), text

        # 3) 短链：跟随重定向后再解析
        if text.startswith("http"):
            try:
                r = _req.get(text, timeout=12, allow_redirects=True, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"})
                final = r.url
                r.close()
                if final and final != text:
                    return PgyWrapper.extract_user_id(final)
            except Exception:
                pass
        return None, None

    def get_blogger_base(self, user_id):
        """达人基础信息（昵称/头像/报价/粉丝数/标签/MCN）——达人主页核心数据源"""
        api = self._ensure_api()
        cookies = trans_cookies(self.cookie_str)
        path = f"/api/solar/cooperator/user/blogger/{user_id}"
        headers = api._signed_headers(cookies, path)
        import requests as _req
        r = _req.get(api.base_url + path, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
        res = r.json()
        if res.get("code") != 0:
            raise Exception(f"查询达人失败: {res.get('msg')} (code={res.get('code')})")
        return res.get("data", {})

    def get_blogger_extras(self, user_id):
        """
        达人主页补充数据（单项失败不影响整体）：
        fans_profile 粉丝画像 / fans_history 粉丝趋势 / feature_tags 特征标签 /
        content_tags 内容标签 / notes_detail 笔记列表 / similar 相似达人
        """
        api = self._ensure_api()
        cookies = trans_cookies(self.cookie_str)
        out = {}

        def _safe(key, fn):
            try:
                out[key] = fn()
            except Exception as e:
                out[f"{key}_error"] = str(e)

        _safe("fans_profile", lambda: api.get_fans_profile(user_id, cookies))
        _safe("fans_history", lambda: api.get_user_fans_history(user_id, cookies))
        _safe("feature_tags", lambda: api.get_kol_feature_tags(user_id, cookies))
        _safe("content_tags", lambda: api.get_kol_content_tags(user_id, cookies))
        _safe("notes_detail", lambda: api.get_notes_detail(user_id, cookies))
        _safe("similar", lambda: api.get_similar_kol(user_id, cookies))
        return out

    def get_blogger_full(self, user_id):
        """一次拉取达人主页完整数据（基础信息 + 数据摘要 + 粉丝摘要 + 笔记表现 + 补充数据）"""
        base = self.get_blogger_base(user_id)
        full = {"base": base, "userId": user_id}

        # 数据摘要 / 粉丝摘要 / 笔记表现（get_kol_detail 已有）
        detail = self.get_kol_detail(user_id)
        for k, v in detail.items():
            full[k] = v

        # 补充数据
        extras = self.get_blogger_extras(user_id)
        for k, v in extras.items():
            full[k] = v

        # 外溢进店 & 合作笔记 聚合字段（源自 blogger 接口，零额外请求）
        full["overflow"] = self._extract_overflow(base)
        return full

    @staticmethod
    def _extract_overflow(base):
        """从达人基础信息中提取「外溢进店 & 合作笔记」指标"""
        return {
            # 外溢进店核心指标
            "mCpuvNum30d": base.get("mCpuvNum30d") or 0,          # 近30天商品点击UV（外溢进店）
            "estimateCpuv30d": base.get("estimateCpuv30d") or 0,  # 预估近30天商品点击UV
            "overflowNum": base.get("overflowNum") or 0,          # 外溢进店数（部分达人返回）
            # 合作笔记
            "coopNoteNum30d": base.get("coopNoteNum30d") or 0,    # 近30天合作笔记数
            "readMidCoop30": base.get("readMidCoop30") or 0,      # 近30天合作笔记阅读中位数
            "interMidCoop30": base.get("interMidCoop30") or 0,    # 近30天合作笔记互动中位数
            "accumCoopImpMedinNum30d": base.get("accumCoopImpMedinNum30d") or 0,  # 合作笔记累计曝光中位数
            "accumCommonImpMedinNum30d": base.get("accumCommonImpMedinNum30d") or 0,
            # 效果效率
            "efficiencyValidUser": base.get("efficiencyValidUser") or 0,
            "predictiveExposure": base.get("predictiveExposure") or 0,  # 预估曝光
        }

    def get_coop_notes(self, user_id):
        """抓取达人合作笔记明细（近8条：品牌/标题/阅读/点赞/收藏）。

        蒲公英 notes_detail 需新版 X-S-Common 签名，requests 不可用，
        通过 Edge 无头 + CDP 抓达人详情页自动加载的接口响应。
        返回 {"total": N, "notes": [...]}；失败抛 RuntimeError。
        """
        from utils.pgy_cdp import fetch_coop_notes, ensure_edge_running
        if not ensure_edge_running():
            raise RuntimeError("Edge 无头浏览器未运行（端口 9350），无法抓取合作笔记明细")
        return fetch_coop_notes(user_id)

    @staticmethod
    def format_blogger_for_kol(base):
        """把达人基础信息转换为 kol 列表格式（供飞书同步复用）"""
        fans_num = int(base.get("fansCount") or 0)
        if fans_num >= 10000:
            fans_str = f"{fans_num / 10000:.1f}万"
        else:
            fans_str = str(fans_num)
        location = base.get("location") or ""
        if isinstance(location, dict):
            location = location.get("name") or location.get("value") or ""
        return {
            "userId": base.get("userId"),
            "name": base.get("name"),
            "redId": base.get("redId"),
            "headPhoto": base.get("headPhoto"),
            "location": location,
            "fansCount": fans_num,
            "fansCountStr": fans_str,
            "totalNoteCount": base.get("totalNoteCount") or base.get("businessNoteCount") or 0,
            "businessNoteCount": base.get("businessNoteCount") or 0,
            "picturePrice": base.get("picturePrice"),
            "videoPrice": base.get("videoPrice"),
            "lowerPrice": base.get("lowerPrice"),
            "personalTags": base.get("personalTags") or [],
            "contentTags": base.get("contentTags") or [],
            "noteSign": base.get("noteSign"),
            "homePageDisplay": base.get("homePageDisplay"),
            "cooperateState": base.get("cooperateState"),
        }


# 单例
pgy_wrapper = PgyWrapper()
