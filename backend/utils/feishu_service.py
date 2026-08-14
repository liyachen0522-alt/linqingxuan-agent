#!/usr/bin/env python3
"""
飞书多维表格同步服务
封装飞书开放平台 bitable REST API：
- 配置持久化 (data/config/feishu.json)
- tenant_access_token 获取与缓存
- 字段自动补齐（不存在则创建）
- 批量写记录
- 连接测试

飞书 API 文档:
- 获取凭证: POST /open-apis/auth/v3/tenant_access_token/internal
- 字段列表: GET  /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
- 新增字段: POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
- 批量新增记录: POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create
"""

import json
import time
import requests
from pathlib import Path

# 配置路径: LinQingXuan-Agent/data/config/feishu.json
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR.parent / "data" / "config" / "feishu.json"

FEISHU_API = "https://open.feishu.cn/open-apis"

# 飞书字段类型常量
FT_TEXT = 1        # 多行文本
FT_NUMBER = 2      # 数字
FT_SELECT = 3      # 单选
FT_MULTI = 4       # 多选
FT_DATE = 5        # 日期（毫秒时间戳）
FT_URL = 15        # 超链接 {text, link}
FT_ATTACHMENT = 17 # 附件（素材图片等）

# 各业务库的字段定义: {字段名: 字段类型}
KOL_FIELDS = {
    "达人昵称": FT_TEXT,
    "小红书号": FT_TEXT,
    "粉丝数": FT_NUMBER,
    "互动数": FT_NUMBER,
    "图文报价": FT_NUMBER,
    "视频报价": FT_NUMBER,
    "外溢进店(30天)": FT_NUMBER,
    "30天涨粉率": FT_NUMBER,
    "位置": FT_TEXT,
    "标签": FT_MULTI,
    "主页链接": FT_TEXT,
    "同步时间": FT_DATE,
}

NOTE_FIELDS = {
    "笔记标题": FT_TEXT,
    "类型": FT_TEXT,
    "作者": FT_TEXT,
    "点赞": FT_NUMBER,
    "收藏": FT_NUMBER,
    "评论": FT_NUMBER,
    "分享": FT_NUMBER,
    "发布时间": FT_DATE,
    "笔记链接": FT_TEXT,
    "采集时间": FT_DATE,
}

CONTENT_FIELDS = {
    "平台": FT_TEXT,
    "主题": FT_TEXT,
    "角度": FT_TEXT,
    "标题": FT_TEXT,
    "正文": FT_TEXT,
    "同步时间": FT_DATE,
}

# 达人素材库的字段定义（kdocs 链接素材发布）
MATERIAL_FIELDS = {
    "素材名称": FT_TEXT,
    "来源链接": FT_URL,
    "素材图片": FT_ATTACHMENT,
    "同步时间": FT_DATE,
}


def _to_ts(value):
    """把日期字符串/时间戳转为飞书日期字段的毫秒时间戳"""
    if value is None:
        return int(time.time() * 1000)
    if isinstance(value, (int, float)):
        # 秒级 → 毫秒级
        return int(value * 1000) if value < 1e12 else int(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return int(time.mktime(time.strptime(str(value)[:19], fmt)) * 1000)
        except Exception:
            continue
    return int(time.time() * 1000)


class FeishuService:
    def __init__(self):
        self._token = None
        self._token_expire_at = 0

    # ---------- 配置 ----------
    def get_config(self):
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"app_id": "", "app_secret": "", "app_token": "", "table_id": ""}

    def save_config(self, config):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        # 只保留合法字段，避免写入脏数据
        clean = {k: (config.get(k) or "").strip() for k in ("app_id", "app_secret", "app_token", "table_id")}
        CONFIG_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        self._token = None
        return clean

    def is_configured(self):
        cfg = self.get_config()
        return all(cfg.get(k) for k in ("app_id", "app_secret", "app_token", "table_id"))

    # ---------- Token ----------
    def _get_token(self):
        now = time.time()
        if self._token and self._token_expire_at > now + 60:
            return self._token

        cfg = self.get_config()
        if not cfg.get("app_id") or not cfg.get("app_secret"):
            raise ValueError("未配置飞书 App ID / App Secret，请先在设置页填写")

        resp = requests.post(
            f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
            json={"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"获取飞书 token 失败: {data.get('msg')} (code={data.get('code')})")

        self._token = data["tenant_access_token"]
        self._token_expire_at = now + int(data.get("expire", 7200))
        return self._token

    def _headers(self):
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    # ---------- 表结构 ----------
    def list_fields(self):
        """返回 {字段名: 字段对象}"""
        cfg = self.get_config()
        if not cfg.get("app_token") or not cfg.get("table_id"):
            raise ValueError("未配置多维表格 App Token / Table ID，请先在设置页填写")
        url = f"{FEISHU_API}/bitable/v1/apps/{cfg['app_token']}/tables/{cfg['table_id']}/fields"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"获取表格字段失败: {data.get('msg')} (code={data.get('code')})")
        return {f["field_name"]: f for f in data["data"]["items"]}

    def ensure_fields(self, field_map: dict):
        """确保字段存在，缺少则创建。
        field_map: {字段名: 字段类型}
        返回 {字段名: field_id}
        """
        existing = self.list_fields()
        result = {name: info["field_id"] for name, info in existing.items() if name in field_map}

        cfg = self.get_config()
        url = f"{FEISHU_API}/bitable/v1/apps/{cfg['app_token']}/tables/{cfg['table_id']}/fields"
        for name, ftype in field_map.items():
            if name in result:
                continue
            resp = requests.post(url, headers=self._headers(), json={"field_name": name, "type": ftype}, timeout=15)
            data = resp.json()
            if data.get("code") == 0:
                result[name] = data["data"]["field"]["field_id"]
            elif data.get("code") == 1254041:  # 字段已存在（并发场景）
                result[name] = self.list_fields().get(name, {}).get("field_id")
            else:
                raise ValueError(f"创建字段「{name}」失败: {data.get('msg')} (code={data.get('code')})")
            time.sleep(0.2)  # 避免接口限频
        return result

    # ---------- 记录写入 ----------
    def add_records(self, records: list, auto_fields: dict = None, batch=100):
        """批量写入记录（最多可分多批）。
        records: [{字段名: 值}]，值按飞书字段类型规范传入
        auto_fields: 可选，若提供则先自动补齐字段
        返回成功写入条数
        """
        if not records:
            return 0
        if auto_fields:
            self.ensure_fields(auto_fields)

        cfg = self.get_config()
        url = f"{FEISHU_API}/bitable/v1/apps/{cfg['app_token']}/tables/{cfg['table_id']}/records/batch_create"
        added = 0
        for i in range(0, len(records), batch):
            chunk = records[i:i + batch]
            resp = requests.post(
                url, headers=self._headers(),
                json={"records": [{"fields": r} for r in chunk]},
                timeout=30,
            )
            data = resp.json()
            if data.get("code") != 0:
                raise ValueError(f"写入记录失败: {data.get('msg')} (code={data.get('code')})")
            added += len(data.get("data", {}).get("records", chunk))
        return added

    # ---------- 连接测试 ----------
    def test_connection(self):
        if not self.is_configured():
            return {"ok": False, "msg": "配置不完整，请填写全部 4 项"}
        try:
            self._get_token()
        except Exception as e:
            return {"ok": False, "msg": f"App ID / App Secret 校验失败：{e}"}
        try:
            fields = self.list_fields()
            return {
                "ok": True,
                "msg": f"连接成功！表格内现有 {len(fields)} 个字段，同步时会自动补齐缺失字段",
                "fields": sorted(fields.keys())[:20],
            }
        except Exception as e:
            return {"ok": False, "msg": f"App Token / Table ID 校验失败：{e}"}

    # ---------- 业务数据映射 ----------
    def kols_to_records(self, kols):
        records = []
        for k in kols:
            tags = k.get("personalTags") or []
            tag_names = []
            for t in tags:
                if isinstance(t, str):
                    tag_names.append(t)
                elif isinstance(t, dict):
                    tag_names.append(t.get("name") or "")
            records.append({
                "达人昵称": k.get("name") or "",
                "小红书号": k.get("redId") or "",
                "粉丝数": k.get("fansCount") or 0,
                "互动数": k.get("interMidNum") or k.get("fansEngageNum") or 0,
                "图文报价": k.get("picturePrice") or 0,
                "视频报价": k.get("videoPrice") or 0,
                "外溢进店(30天)": k.get("overflowNum") or 0,
                "30天涨粉率": k.get("fans30GrowthRate") or 0,
                "位置": k.get("location") or "",
                "标签": tag_names,
                "主页链接": f"https://www.xiaohongshu.com/user/profile/{k.get('userId')}" if k.get("userId") else "",
                "同步时间": int(time.time() * 1000),
            })
        return records

    def notes_to_records(self, notes):
        records = []
        for n in notes:
            records.append({
                "笔记标题": n.get("title") or n.get("desc") or "",
                "类型": n.get("type") or "图文",
                "作者": n.get("nickname") or n.get("author") or "",
                "点赞": n.get("likeCount") or 0,
                "收藏": n.get("collectionCount") or 0,
                "评论": n.get("commentCount") or 0,
                "分享": n.get("shareCount") or 0,
                "发布时间": _to_ts(n.get("releaseTime") or n.get("time")),
                "笔记链接": n.get("url") or n.get("noteUrl") or "",
                "采集时间": int(time.time() * 1000),
            })
        return records

    def content_to_records(self, items):
        records = []
        for c in items:
            records.append({
                "平台": c.get("platform") or "",
                "主题": c.get("topic") or "",
                "角度": c.get("angle") or c.get("video_type") or "",
                "标题": c.get("title") or "",
                "正文": c.get("body") or c.get("script") or "",
                "同步时间": int(time.time() * 1000),
            })
        return records

    def generic_records(self, records):
        """通用记录：透传 {字段名: 值}，值对象可含 {type, value} 指定飞书类型"""
        out = []
        for r in records:
            fields = {}
            for k, v in r.items():
                if isinstance(v, dict) and "value" in v:
                    fields[k] = v["value"]
                else:
                    fields[k] = v
            out.append(fields)
        return out


# 单例
feishu = FeishuService()
