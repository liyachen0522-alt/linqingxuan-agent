#!/usr/bin/env python3
"""
林清轩黑金霜 - 种草智能体后端服务
Flask API: 小红书采集 / 抖音采集 / 内容生成 / 数据导出
"""

import os
import sys
import json
import time
import uuid
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

# 路径配置
BASE_DIR = Path(__file__).resolve().parent
SPIDER_XHS_DIR = BASE_DIR.parent.parent / "Spider_XHS"
sys.path.insert(0, str(SPIDER_XHS_DIR))
sys.path.insert(0, str(BASE_DIR))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from scrapers.xhs_wrapper import XHSWrapper
from scrapers.douyin_scraper import DouyinScraper
from scrapers.pgy_wrapper import PgyWrapper
from generators.content_generator import ContentGenerator
from analyzers.sales_analyzer import analyzer as sales_analyzer
from utils.feishu_service import feishu, KOL_FIELDS, NOTE_FIELDS, CONTENT_FIELDS, MATERIAL_FIELDS, _to_ts
from utils import kdocs_service as kdocs
from utils import douyin_service as dy_svc

import requests

app = Flask(__name__, static_folder=str(BASE_DIR.parent / "frontend"), static_url_path="")
CORS(app)

# 初始化模块
xhs = XHSWrapper()
douyin = DouyinScraper()
pgy = PgyWrapper()
generator = ContentGenerator()

# 数据存储目录
DATA_DIR = BASE_DIR.parent / "data" / "output"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ========== 页面路由 ==========

@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR.parent / "frontend"), "index.html")


# ========== 小红书 API ==========

@app.route("/api/xhs/search", methods=["POST"])
def xhs_search():
    """小红书关键词搜索"""
    data = request.json or {}
    keyword = data.get("keyword", "").strip()
    num = int(data.get("num", 20))
    if not keyword:
        return jsonify({"success": False, "msg": "关键词不能为空"})

    try:
        result = xhs.search(keyword, num)
        # 保存到本地
        save_data(f"xhs_search_{keyword}_{int(time.time())}.json", result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/xhs/note_detail", methods=["POST"])
def xhs_note_detail():
    """获取小红书笔记详情"""
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "msg": "笔记URL不能为空"})

    try:
        result = xhs.get_note_detail(url)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/xhs/comments", methods=["POST"])
def xhs_comments():
    """获取小红书笔记评论"""
    data = request.json or {}
    note_id = data.get("note_id", "").strip()
    xsec_token = data.get("xsec_token", "").strip()
    if not note_id:
        return jsonify({"success": False, "msg": "笔记ID不能为空"})

    try:
        result = xhs.get_comments(note_id, xsec_token)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/xhs/batch_search", methods=["POST"])
def xhs_batch_search():
    """批量关键词搜索"""
    data = request.json or {}
    keywords = data.get("keywords", [])
    num = int(data.get("num", 10))
    if not keywords:
        return jsonify({"success": False, "msg": "关键词列表不能为空"})

    try:
        results = {}
        for kw in keywords:
            results[kw] = xhs.search(kw, num)
            time.sleep(2)  # 避免频率限制
        return jsonify({"success": True, "data": results})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


# ========== 抖音 API ==========

@app.route("/api/douyin/search", methods=["POST"])
def douyin_search():
    """抖音关键词搜索"""
    data = request.json or {}
    keyword = data.get("keyword", "").strip()
    num = int(data.get("num", 20))
    if not keyword:
        return jsonify({"success": False, "msg": "关键词不能为空"})

    try:
        result = douyin.search(keyword, num)
        save_data(f"douyin_search_{keyword}_{int(time.time())}.json", result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/douyin/cookie_status", methods=["GET"])
def douyin_cookie_status():
    """检查抖音Cookie状态"""
    try:
        has_cookie = douyin.has_cookie()
        return jsonify({"success": True, "has_cookie": has_cookie})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/douyin/set_cookie", methods=["POST"])
def douyin_set_cookie():
    """设置抖音Cookie"""
    data = request.json or {}
    cookie = data.get("cookie", "").strip()
    if not cookie:
        return jsonify({"success": False, "msg": "Cookie不能为空"})

    try:
        douyin.set_cookie(cookie)
        return jsonify({"success": True, "msg": "Cookie已保存"})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})


# ========== 抖音达人素材下载（桌面直下） ==========

@app.route("/api/douyin/status", methods=["GET"])
def douyin_dl_status():
    """抖音素材下载器：Cookie 状态与保存位置"""
    return jsonify({
        "success": True,
        "data": {
            "has_cookie": dy_svc.has_cookie(),
            "desktop_dir": dy_svc.DESKTOP_DIR,
        }
    })


@app.route("/api/douyin/save_cookie", methods=["POST"])
def douyin_save_cookie():
    """抖音素材下载器：保存 Cookie 到本地配置"""
    data = request.json or {}
    cookie = (data.get("cookie") or "").strip()
    if not cookie:
        return jsonify({"success": False, "msg": "Cookie 不能为空"})
    try:
        dy_svc.save_cookie(cookie)
        return jsonify({"success": True, "msg": "✅ 抖音 Cookie 已保存，可直接下载达人视频"})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/douyin/profile", methods=["POST"])
def douyin_profile():
    """解析达人主页，返回视频列表（不下载）"""
    data = request.json or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"success": False, "msg": "请输入达人主页链接"})
    try:
        sec_uid = dy_svc.extract_sec_uid(url)
        if not sec_uid:
            return jsonify({"success": False,
                            "msg": "无法识别链接，请粘贴形如 https://www.douyin.com/user/xxx 的主页链接"})
        profile = dy_svc.fetch_profile_videos(sec_uid)
        if not profile["videos"]:
            return jsonify({"success": False,
                            "msg": f"未获取到视频列表（达人「{profile['nickname']}」暂无可见视频，或需要登录）",
                            "data": profile})
        return jsonify({"success": True, "data": profile,
                        "msg": f"✅ 达人「{profile['nickname']}」，共 {profile['aweme_count']} 条视频"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": f"解析失败: {e}"})


@app.route("/api/douyin/download", methods=["POST"])
def douyin_download():
    """后台任务：下载达人主页全部视频到桌面 林清轩素材/<达人名>/"""
    data = request.json or {}
    urls = data.get("urls") or []
    if isinstance(urls, str):
        urls = [l.strip() for l in urls.replace("\n", ",").split(",") if l.strip()]
    if not urls:
        return jsonify({"success": False, "msg": "urls 不能为空"})
    try:
        task_id = dy_svc.create_task(urls)
        return jsonify({"success": True, "task_id": task_id,
                        "msg": f"已创建下载任务 {task_id}"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": f"创建任务失败: {e}"})


@app.route("/api/douyin/single_download", methods=["POST"])
def douyin_single_download():
    """单条抖音视频链接直接下载（支持 v.douyin.com 短链 / video/{id} / share 链接）"""
    data = request.json or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"success": False, "msg": "请输入视频链接"})
    try:
        result = dy_svc.download_single_video(url)
        status = "已存在，跳过下载" if result["status"] == "exists" else "下载完成"
        return jsonify({
            "success": True,
            "data": result,
            "msg": f"✅ {status}：林清轩素材/{result['nickname']}/（{result.get('size', 0) // 1024}KB）",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": f"下载失败: {e}"})


@app.route("/api/douyin/progress", methods=["GET"])
def douyin_progress():
    """查询下载任务进度"""
    task_id = request.args.get("task_id", "")
    t = dy_svc.get_task(task_id)
    if not t:
        return jsonify({"success": False, "msg": "任务不存在"})
    return jsonify({"success": True, "data": t})


# ========== 内容生成 API ==========

@app.route("/api/generate/xhs", methods=["POST"])
def generate_xhs():
    """生成小红书种草文案"""
    data = request.json or {}
    topic = data.get("topic", "林清轩黑金霜")
    angle = data.get("angle", "anti_aging")  # anti_aging, ingredient, lifestyle, gift
    tone = data.get("tone", "professional_friendly")  # professional_friendly, casual, emotional
    target_audience = data.get("target_audience", "25-35岁女性")
    extra_info = data.get("extra_info", "")

    try:
        result = generator.generate_xhs_content(topic, angle, tone, target_audience, extra_info)
        save_data(f"xhs_content_{int(time.time())}.json", result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/generate/douyin", methods=["POST"])
def generate_douyin():
    """生成抖音短视频脚本"""
    data = request.json or {}
    topic = data.get("topic", "林清轩黑金霜")
    video_type = data.get("video_type", "experience")  # experience, science, unboxing, comparison
    duration = data.get("duration", "30-60s")  # 15-30s, 30-60s, 60-120s
    target_audience = data.get("target_audience", "25-35岁女性")
    extra_info = data.get("extra_info", "")

    try:
        result = generator.generate_douyin_content(topic, video_type, duration, target_audience, extra_info)
        save_data(f"douyin_content_{int(time.time())}.json", result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/generate/titles", methods=["POST"])
def generate_titles():
    """生成标题选项"""
    data = request.json or {}
    topic = data.get("topic", "林清轩黑金霜")
    angle = data.get("angle", "anti_aging")
    count = int(data.get("count", 10))

    try:
        result = generator.generate_titles(topic, angle, count)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


# ========== 数据导出 API ==========

@app.route("/api/export", methods=["POST"])
def export_data():
    """导出数据为JSON文件"""
    data = request.json or {}
    filename = data.get("filename", f"export_{int(time.time())}.json")
    save_data(filename, data.get("data", {}))
    return jsonify({"success": True, "path": str(DATA_DIR / filename)})


@app.route("/api/history", methods=["GET"])
def get_history():
    """获取历史采集数据列表"""
    files = []
    for f in sorted(DATA_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        files.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "time": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify({"success": True, "data": files[:50]})


# ========== 蒲公英 API ==========

@app.route("/api/pgy/status", methods=["GET"])
def pgy_status():
    """检查蒲公英 Cookie 状态"""
    try:
        data = pgy.get_cookie_status()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/pgy/categories", methods=["GET"])
def pgy_categories():
    """获取蒲公英达人类目树"""
    try:
        data = pgy.get_categories()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/pgy/kols", methods=["POST"])
def pgy_kols():
    """获取蒲公英达人列表"""
    data = request.json or {}
    page = int(data.get("page", 1))
    category = (data.get("category") or "").strip() or None
    num = int(data.get("num", 20))
    keyword = (data.get("keyword") or "").strip() or None
    min_fans = int(data.get("min_fans") or 0) or None
    min_overflow = int(data.get("min_overflow") or 0) or None
    try:
        result = pgy.get_kols(page=page, category=category, num=num,
                              keyword=keyword, min_fans=min_fans, min_overflow=min_overflow)
        save_data(f"pgy_kols_{category or 'all'}_{int(time.time())}.json", result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/pgy/kol_detail", methods=["POST"])
def pgy_kol_detail():
    """获取蒲公英达人详情（粉丝画像/历史趋势/笔记数据）"""
    data = request.json or {}
    user_id = data.get("user_id", "").strip()
    if not user_id:
        return jsonify({"success": False, "msg": "达人ID不能为空"})
    try:
        result = pgy.get_kol_detail(user_id)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/pgy/kols_by_link", methods=["POST"])
def pgy_kols_by_link():
    """
    输入蒲公英达人链接 → 自动解析 userId → 返回达人主页完整数据
    （基础信息/报价 + 数据摘要 + 粉丝画像 + 笔记表现 + 标签 + 相似达人 + 外溢合作指标）
    """
    data = request.json or {}
    link = (data.get("link") or "").strip()
    if not link:
        return jsonify({"success": False, "msg": "请粘贴蒲公英达人链接"})
    user_id, source = pgy.extract_user_id(link)
    if not user_id:
        return jsonify({"success": False, "msg": "无法从链接中识别达人ID，请确认是蒲公英达人主页链接（如 …/pre-trade/blogger-detail/xxx 或 …/advertiser/kol/xxx）"})
    try:
        full = pgy.get_blogger_full(user_id)
        full["source_link"] = source
        save_data(f"pgy_kol_link_{int(time.time())}.json", full)
        return jsonify({"success": True, "data": full})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


# 合作笔记明细缓存：{userId: {"ts": epoch, "data": {...}}}
_coop_notes_cache = {}
_COOP_CACHE_TTL = 600  # 10 分钟

@app.route("/api/pgy/coop_notes", methods=["POST"])
def pgy_coop_notes():
    """抓取达人合作笔记明细（近8条：品牌/标题/阅读/点赞/收藏）。

    通过 Edge 无头浏览器 + CDP 抓取（蒲公英该接口需新版签名，requests 不可用）。
    带 10 分钟缓存，避免重复抓取。
    """
    data = request.json or {}
    link = (data.get("link") or data.get("user_id") or "").strip()
    if not link:
        return jsonify({"success": False, "msg": "请粘贴蒲公英达人链接或达人ID"})
    user_id, source = pgy.extract_user_id(link)
    if not user_id:
        return jsonify({"success": False, "msg": "无法从链接中识别达人ID"})
    now = time.time()
    cached = _coop_notes_cache.get(user_id)
    if cached and now - cached["ts"] < _COOP_CACHE_TTL:
        return jsonify({"success": True, "data": cached["data"], "cached": True})
    try:
        result = pgy.get_coop_notes(user_id)
        _coop_notes_cache[user_id] = {"ts": now, "data": result}
        return jsonify({"success": True, "data": result, "cached": False})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/pgy/brand_match", methods=["POST"])
def pgy_brand_match():
    """AI 品牌匹配评估：输入自然语言品牌画像 → 拉取蒲公英达人 → 规则预筛 + 大模型精评 → 推荐名单。

    入参: {brand_profile: 自然语言画像, num: 拉取数量(默认50), top_n: 榜单长度(默认10),
           category: 可选，类目名（转 contentTag 定向拉取）}
    返回: {scanned, best: [{name,user_id,fans,price,rule_score,llm_score,final_score,tags,hit_cats,reasons,suggestion}],
           profile, llm_enabled}
    """
    data = request.json or {}
    brand_profile = (data.get("brand_profile") or "").strip()
    if not brand_profile:
        return jsonify({"success": False, "msg": "请描述品牌画像，例如：高端护肤品牌，主打抗老精华，目标25-35岁女性，客单价300-800，单次投放预算10万，风格高级简约"})
    if not pgy.has_cookie():
        return jsonify({"success": False, "msg": "未配置蒲公英 Cookie（Spider_XHS/.env 的 PGY_COOKIES），无法拉取达人"})
    num = max(10, min(200, int(data.get("num") or 50)))
    top_n = max(3, min(30, int(data.get("top_n") or 10)))
    category = (data.get("category") or "").strip() or None

    try:
        from apis.xhs_pugongying_apis import PuGongYingAPI
        from apis.pgy_brand_match import parse_brand_profile, select_best_kols
        from xhs_utils.cookie_util import trans_cookies

        cookies = trans_cookies(pgy.cookie_str)
        api = PuGongYingAPI()
        # 类目 → contentTag 定向拉取（类目名直接透传，蒲公英按 taxonomy1Tag 过滤）
        kol_list = api.get_some_user(num=num, cookies=cookies,
                                     contentTag=[category] if category else None)
        if not kol_list:
            return jsonify({"success": False, "msg": "未拉取到达人，请检查蒲公英 Cookie 是否有效"})

        profile = parse_brand_profile(brand_profile)
        best = select_best_kols(kol_list, profile, cookies=cookies, top_n=top_n)
        # 补头像/报价字段（select_best_kols 通用返回不含，前端渲染需要）
        kol_by_uid = {str(k.get("userId")): k for k in kol_list if isinstance(k, dict)}
        for b in best:
            k = kol_by_uid.get(str(b.get("user_id")))
            if k:
                b["head_photo"] = k.get("headPhoto") or ""
                if not b.get("price"):
                    pp = k.get("picturePrice")
                    b["price"] = int(pp) if isinstance(pp, (int, float)) and pp else None
        llm_enabled = bool(os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))

        save_data(f"pgy_brand_match_{int(time.time())}.json", {
            "brand_profile": brand_profile, "scanned": len(kol_list),
            "profile": profile, "llm_enabled": llm_enabled, "best": best,
        })
        mode = "规则+大模型精评" if llm_enabled else "规则预筛（未配置 LLM_API_KEY，自动降级）"
        return jsonify({
            "success": True,
            "data": {"scanned": len(kol_list), "best": best,
                     "profile": profile, "llm_enabled": llm_enabled,
                     "mode": mode},
            "msg": f"✅ 已从 {len(kol_list)} 位达人中评估出 Top {len(best)}（{mode}）",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


# ========== 笔记互动数据查询 ==========

@app.route("/api/note/stats", methods=["POST"])
def note_stats():
    """输入小红书/抖音链接，返回点赞/评论/转发/收藏"""
    try:
        data = request.get_json(force=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"success": False, "msg": "请输入链接"})

        from utils.note_stats import fetch_note_stats, detect_platform
        platform = detect_platform(url)
        if platform == "unknown":
            return jsonify({"success": False, "msg": "无法识别链接平台，支持小红书和抖音链接"})

        result = fetch_note_stats(url)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/note/stats_batch", methods=["POST"])
def note_stats_batch():
    """批量查询：一次传入多条小红书/抖音链接，逐条返回互动数据"""
    try:
        data = request.get_json(force=True) or {}
        urls = data.get("urls") or []
        if isinstance(urls, str):
            # 兼容换行分隔的文本
            urls = urls.splitlines()
        urls = [u.strip() for u in urls if u and u.strip()]
        if not urls:
            return jsonify({"success": False, "msg": "请至少输入一条链接"})
        if len(urls) > 50:
            return jsonify({"success": False, "msg": "一次最多查询 50 条链接"})

        interval = float(data.get("interval") or 1.5)
        interval = min(max(interval, 0.5), 5.0)

        from utils.note_stats import fetch_note_stats_batch
        result = fetch_note_stats_batch(urls, interval=interval)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/note/cookie_status", methods=["GET"])
def note_cookie_status():
    """检查小红书/抖音 cookie 配置状态"""
    try:
        from utils.note_stats import check_cookie_status
        return jsonify({"success": True, "data": check_cookie_status()})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})


# ========== 小红书扫码登录刷新 Cookie ==========

# 全局存储扫码登录会话（同一时间只允许一个）
_qr_login_session = {}


@app.route("/api/xhs/qr_login/start", methods=["POST"])
def xhs_qr_login_start():
    """生成小红书登录二维码，返回 qr_url 供前端展示"""
    global _qr_login_session
    try:
        from apis.xhs_pc_login_apis import XHSLoginApi

        login = XHSLoginApi()
        # 1) 初始化匿名设备
        cookies = login.generate_init_cookies()
        # 2) 获取二维码
        success, msg, qr_data = login.generate_qrcode(cookies)
        if not success:
            return jsonify({"success": False, "msg": f"获取二维码失败: {msg}"})
        cookies = qr_data["cookies"]
        # 3) 预检查 + webprofile
        success, msg, cookies = login.check_qrcode_status(
            qr_data["qr_id"], qr_data["code"], cookies
        )
        if msg != "请扫描二维码":
            return jsonify({"success": False, "msg": f"二维码状态异常: {msg}"})
        login.ensure_webprofile(cookies)

        # 生成二维码 base64 图片（前端直接 <img src="data:image/png;base64,...">）
        import qrcode, io, base64
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(qr_data["qr_url"])
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        # 保存会话
        _qr_login_session = {
            "login_api": login,
            "cookies": cookies,
            "qr_id": qr_data["qr_id"],
            "code": qr_data["code"],
            "qr_url": qr_data["qr_url"],
            "created_at": time.time(),
        }
        return jsonify({
            "success": True,
            "data": {"qr_url": qr_data["qr_url"], "qr_image": qr_b64},
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/xhs/qr_login/poll", methods=["GET"])
def xhs_qr_login_poll():
    """轮询扫码登录状态，成功则自动保存 Cookie 到 .env"""
    global _qr_login_session
    if not _qr_login_session:
        return jsonify({"success": False, "msg": "没有进行中的扫码会话"})

    # 超过 3 分钟自动清除
    if time.time() - _qr_login_session["created_at"] > 180:
        _qr_login_session = {}
        return jsonify({"success": False, "msg": "二维码已过期，请重新生成"})

    try:
        login = _qr_login_session["login_api"]
        cookies = _qr_login_session["cookies"]
        qr_id = _qr_login_session["qr_id"]
        code = _qr_login_session["code"]

        success, msg, cookies = login.check_qrcode_status(qr_id, code, cookies)
        _qr_login_session["cookies"] = cookies  # 更新 cookies

        if not success:
            # 状态码: 0=等待扫码, 1=已扫码等待确认, 3=已过期
            return jsonify({"success": True, "data": {"status": "waiting", "msg": msg}})

        # 扫码确认成功，验证登录状态
        ok, user_info, cookies = login.get_user_info(cookies)
        if not ok or user_info.get("guest") is not False:
            return jsonify({"success": False, "msg": "登录验证失败，请重试"})

        # 转为 Cookie 字符串
        cookies_str = login.cookies_to_str(cookies)

        # 保存到 Spider_XHS/.env
        env_path = SPIDER_XHS_DIR / ".env"
        _update_env_cookie(env_path, "COOKIES", cookies_str)

        # 重置 XHSWrapper，下次搜索时自动从 .env 重新加载新 Cookie
        xhs.reset()

        # 清除会话
        nickname = user_info.get("nickname", "未知")
        _qr_login_session = {}

        return jsonify({
            "success": True,
            "data": {"status": "success", "nickname": nickname},
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


def _update_env_cookie(env_path: Path, key: str, value: str):
    """更新 .env 文件中指定 key 的值"""
    lines = []
    found = False
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}='{value}'")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}='{value}'")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ========== 小红书笔记图片+文案下载 ==========

@app.route("/api/xhs/download_note", methods=["POST"])
def xhs_download_note():
    """下载小红书笔记图片+文案到桌面（支持短链 xhslink / 完整链接，可批量）"""
    try:
        data = request.get_json(force=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"success": False, "msg": "请输入小红书链接"})

        from utils.note_stats import download_xhs_note
        result = download_xhs_note(url)

        status_msg = "已存在，跳过" if result["status"] == "exists" else "下载完成"
        img_info = f"{result['images_downloaded']} 张图片"
        if result.get("video"):
            img_info += f" + 视频({result['video']['status']})"
        return jsonify({
            "success": True,
            "data": result,
            "msg": f"✅ {status_msg}：{result['author']}/{result['title']}（{img_info} + 文案.txt）",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


# ========== 销售分析 API ==========

@app.route("/api/sales/summary", methods=["GET"])
def sales_summary():
    """销售总览"""
    try:
        data = sales_analyzer.summary()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/sales/region", methods=["GET"])
def sales_region():
    """按区域分析"""
    try:
        category = request.args.get("category")
        data = sales_analyzer.by_region(category)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/sales/category", methods=["GET"])
def sales_category():
    """按品类分析"""
    try:
        data = sales_analyzer.by_category()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/sales/monthly", methods=["GET"])
def sales_monthly():
    """月度趋势"""
    try:
        category = request.args.get("category")
        region = request.args.get("region")
        data = sales_analyzer.by_month(category, region)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/sales/level", methods=["GET"])
def sales_level():
    """按会员等级分析"""
    try:
        data = sales_analyzer.by_level()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/sales/top_products", methods=["GET"])
def sales_top_products():
    """产品排行"""
    try:
        category = request.args.get("category")
        limit = int(request.args.get("limit", 20))
        data = sales_analyzer.top_products(category, limit)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/sales/matrix", methods=["GET"])
def sales_matrix():
    """区域×品类交叉矩阵"""
    try:
        data = sales_analyzer.region_category_matrix()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/sales/heijin", methods=["GET"])
def sales_heijin():
    """黑金霜专题"""
    try:
        data = sales_analyzer.heijin_detail()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


# ========== 飞书同步 API ==========

@app.route("/api/feishu/config", methods=["GET"])
def feishu_config_get():
    """获取飞书配置（secret 打码返回）"""
    cfg = feishu.get_config()
    return jsonify({
        "success": True,
        "data": {
            "app_id": cfg.get("app_id", ""),
            "app_token": cfg.get("app_token", ""),
            "table_id": cfg.get("table_id", ""),
            "has_secret": bool(cfg.get("app_secret")),
            "configured": feishu.is_configured(),
        }
    })


@app.route("/api/feishu/config", methods=["POST"])
def feishu_config_save():
    """保存飞书配置（secret 留空则保留原值）"""
    data = request.json or {}
    cfg = feishu.get_config()
    if not data.get("app_secret"):
        data["app_secret"] = cfg.get("app_secret", "")
    saved = feishu.save_config(data)
    return jsonify({"success": True, "data": {"configured": feishu.is_configured()}})


@app.route("/api/feishu/test", methods=["POST"])
def feishu_test():
    """测试飞书连接"""
    try:
        result = feishu.test_connection()
        return jsonify({"success": result["ok"], "msg": result["msg"], "data": result})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/feishu/sync_kols", methods=["POST"])
def feishu_sync_kols():
    """同步达人列表到飞书"""
    data = request.json or {}
    kols = data.get("kols") or []
    if not kols:
        return jsonify({"success": False, "msg": "没有可同步的达人数据"})
    try:
        records = feishu.kols_to_records(kols)
        added = feishu.add_records(records, auto_fields=KOL_FIELDS)
        return jsonify({"success": True, "msg": f"✅ 已同步 {added} 位达人到飞书「达人库」"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/feishu/sync_notes", methods=["POST"])
def feishu_sync_notes():
    """同步笔记数据到飞书"""
    data = request.json or {}
    notes = data.get("notes") or []
    if not notes:
        return jsonify({"success": False, "msg": "没有可同步的笔记数据"})
    try:
        records = feishu.notes_to_records(notes)
        added = feishu.add_records(records, auto_fields=NOTE_FIELDS)
        return jsonify({"success": True, "msg": f"✅ 已同步 {added} 条笔记到飞书「笔记库」"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/feishu/sync_content", methods=["POST"])
def feishu_sync_content():
    """同步生成内容到飞书"""
    data = request.json or {}
    items = data.get("items") or []
    if not items:
        return jsonify({"success": False, "msg": "没有可同步的内容"})
    try:
        records = feishu.content_to_records(items)
        added = feishu.add_records(records, auto_fields=CONTENT_FIELDS)
        return jsonify({"success": True, "msg": f"✅ 已同步 {added} 条内容到飞书「内容库」"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/feishu/sync_sales", methods=["POST"])
def feishu_sync_sales():
    """同步销售关键指标快照到飞书"""
    try:
        s = sales_analyzer.summary()
        now_ts = int(time.time() * 1000)
        record = {
            "销售总额": round(s.get("total_amount", 0), 2),
            "销售件数": s.get("total_qty", 0),
            "平均单价": round(s.get("avg_unit_price", 0), 2),
            "黑金霜销售额": round(s.get("hj_amount", 0), 2),
            "黑金霜销量": s.get("hj_qty", 0),
            "黑金霜占比": s.get("hj_pct", 0),
            "数据周期": f"{s.get('month_range', '')}（{s.get('row_count', 0)}行）",
            "同步时间": now_ts,
        }
        fields = {
            "销售总额": 2, "销售件数": 2, "平均单价": 2,
            "黑金霜销售额": 2, "黑金霜销量": 2, "黑金霜占比": 2,
            "数据周期": 1, "同步时间": 5,
        }
        added = feishu.add_records([record], auto_fields=fields)
        return jsonify({"success": True, "msg": f"✅ 已同步销售快照到飞书（黑金霜占比 {s.get('hj_pct')}%）"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/feishu/tool_status", methods=["GET"])
def feishu_tool_status():
    """检查 feishu-douyin-tool(4000) 服务状态"""
    try:
        resp = requests.get("http://localhost:4000/", timeout=3)
        return jsonify({"success": True, "data": {"online": resp.status_code == 200, "port": 4000}})
    except Exception:
        return jsonify({"success": True, "data": {"online": False, "port": 4000}})


def _load_xhs_cookie():
    """从 Spider_XHS/.env 读取 PC 端小红书 Cookie"""
    try:
        from dotenv import load_dotenv
        env_path = SPIDER_XHS_DIR / ".env"
        load_dotenv(env_path)
        return os.environ.get("COOKIES", "")
    except Exception:
        return ""


@app.route("/api/feishu/proxy_note", methods=["POST"])
def feishu_proxy_note():
    """代理 feishu-douyin-tool 抓取小红书笔记详情（可同步到飞书）"""
    data = request.json or {}
    url = (data.get("url") or "").strip()
    sync = bool(data.get("sync"))
    if not url:
        return jsonify({"success": False, "msg": "笔记URL不能为空"})

    cookie = data.get("cookie") or _load_xhs_cookie()
    try:
        resp = requests.post(
            "http://localhost:4000/redbook/getNoteInfo",
            json={"url": url, "cookie": cookie},
            timeout=30,
        )
        result = resp.json()
        if result.get("code") != 0:
            return jsonify({"success": False, "msg": f"抓取失败: {result.get('msg')}"})
        note = result.get("data") or {}
        note["url"] = url

        extra = ""
        if sync:
            records = feishu.notes_to_records([note])
            added = feishu.add_records(records, auto_fields=NOTE_FIELDS)
            extra = f"，已同步到飞书 {added} 条"
        save_data(f"proxy_note_{int(time.time())}.json", note)
        return jsonify({"success": True, "data": note, "msg": f"抓取成功{extra}"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": f"feishu-douyin-tool(4000) 服务未启动或异常: {e}"})


# ========== kdocs 素材下载 API（供飞书插件调用） ==========

@app.route("/plugin/")
def plugin_page():
    """飞书多维表格自定义插件页面"""
    return send_from_directory(str(BASE_DIR), "plugin.html")


@app.route("/tool/")
def desktop_tool_page():
    """桌面下载工具入口页（替代飞书插件，直接下载素材到桌面）"""
    return send_from_directory(str(BASE_DIR), "desktop_download.html")


@app.route("/api/kdocs/desktop_fetch", methods=["POST"])
def kdocs_desktop_fetch():
    """批量处理 kdocs 素材链接：渲染 -> 提取 -> 下载到桌面（不经过飞书）

    入参: {links: [link_id 或完整链接...]}
    下载目录: ~/Desktop/林清轩素材/<link_id>/
    """
    body = request.get_json(force=True, silent=True) or {}
    links = body.get("links") or []
    if isinstance(links, str):
        links = [l.strip() for l in links.replace("\n", ",").split(",") if l.strip()]
    if not links:
        return jsonify({"success": False, "msg": "links 不能为空"})

    try:
        result = kdocs.download_many_to_desktop(links)
        result["success"] = True
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": f"处理失败: {e}"})


@app.route("/api/kdocs/open_desktop", methods=["POST"])
def kdocs_open_desktop():
    """在 Finder 中打开桌面素材文件夹"""
    try:
        folder = kdocs.DESKTOP_DIR
        os.makedirs(folder, exist_ok=True)
        subprocess.Popen(["open", folder])
        return jsonify({"success": True, "msg": f"已打开 {folder}"})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/kdocs/organize", methods=["POST"])
def kdocs_organize():
    """把桌面素材文件夹整理为「达人名/分类名」（合并重复链接）"""
    try:
        result = kdocs.organize_desktop_folders()
        result["success"] = True
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/kdocs/desktop_list", methods=["GET"])
def kdocs_desktop_list():
    """列出桌面素材目录中已下载的文件夹与图片数量"""
    try:
        root = kdocs.DESKTOP_DIR
        groups = []
        if os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                folder = os.path.join(root, name)
                if not os.path.isdir(folder):
                    continue
                files = [f for f in sorted(os.listdir(folder)) if os.path.isfile(os.path.join(folder, f))]
                if files:
                    groups.append({"name": name, "count": len(files)})
        return jsonify({"success": True, "data": {"desktop_dir": root, "groups": groups}})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)})


@app.route("/api/kdocs/fetch", methods=["POST"])
def kdocs_fetch():
    """批量处理 kdocs 素材链接：渲染 -> 提取 -> 下载 -> 上传飞书 -> 写记录

    入参: {links: [link_id 或完整链接...], app_token?, table_id?}
    若传入 app_token/table_id 则切换飞书目标表格（插件当前打开的表）
    """
    body = request.get_json(force=True, silent=True) or {}
    links = body.get("links") or []
    if isinstance(links, str):
        links = [l.strip() for l in links.replace("\n", ",").split(",") if l.strip()]
    if not links:
        return jsonify({"success": False, "msg": "links 不能为空"})

    # 支持覆盖目标表格（插件把当前打开的表格传进来）
    if body.get("app_token") or body.get("table_id"):
        cfg = feishu.get_config()
        new_cfg = dict(cfg)
        if body.get("app_token"):
            new_cfg["app_token"] = str(body["app_token"]).strip()
        if body.get("table_id"):
            new_cfg["table_id"] = str(body["table_id"]).strip()
        feishu.save_config(new_cfg)

    try:
        result = kdocs.publish_many(links)
        result["success"] = True
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "msg": f"处理失败: {e}"})


@app.route("/api/kdocs/render", methods=["POST"])
def kdocs_render():
    """单独触发渲染：{links:[...]}，返回每个链接的渲染状态"""
    body = request.get_json(force=True, silent=True) or {}
    links = body.get("links") or []
    if isinstance(links, str):
        links = [l.strip() for l in links.replace("\n", ",").split(",") if l.strip()]
    out = []
    for raw in links:
        lid = kdocs.link_id_of(raw)
        dom = kdocs.render_link(lid)
        urls = kdocs.extract_material_urls(dom) if dom else []
        title = kdocs.extract_title(dom) if dom else ""
        out.append({"link": lid, "ok": bool(dom), "title": title,
                    "material_count": len(urls),
                    "cached": os.path.exists(os.path.join(kdocs.HTML_DIR, f"{lid}.html"))})
    return jsonify({"success": True, "results": out})


# ========== 工具函数 ==========

def save_data(filename: str, data):
    """保存数据到本地文件"""
    filepath = DATA_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("=" * 50)
    print("  林清轩黑金霜种草智能体 v1.0")
    print("  访问地址: http://localhost:5210")
    print("=" * 50)
    # 生产模式：debug=False（内网共享时 Werkzeug debugger 有任意代码执行风险）
    app.run(host="0.0.0.0", port=5210, debug=False)
