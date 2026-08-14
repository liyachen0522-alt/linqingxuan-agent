# 林清轩黑金霜 · 种草智能体

## 项目概述
基于 Spider_XHS 小红书爬虫 + 自建抖音爬虫 + 蒲公英平台 + AI 内容生成引擎，打造的小红书/抖音双平台种草工具。

支持：关键词搜索、笔记互动数据查询、KOL 筛选、内容生成、素材下载、扫码登录刷新 Cookie。

## 项目结构
```
LinQingXuan-Agent/
├── start.sh                        # 一键启动脚本
├── requirements.txt                # Python 依赖
├── backend/
│   ├── app.py                      # Flask 主服务（端口 5210）
│   ├── desktop_download.html       # 工具下载页（/tool/）
│   ├── plugin.html                 # 飞书插件页
│   ├── scrapers/
│   │   ├── xhs_wrapper.py          # 小红书采集（封装 Spider_XHS）
│   │   ├── douyin_scraper.py       # 抖音采集（SSR + API 双模式）
│   │   ├── pgy_wrapper.py          # 蒲公英 KOL 数据
│   │   └── douyin_sign.js          # 抖音签名生成
│   ├── generators/
│   │   └── content_generator.py    # 内容生成引擎
│   ├── analyzers/
│   │   └── sales_analyzer.py       # 销售数据分析
│   └── utils/
│       ├── note_stats.py           # 小红书笔记互动查询 + 图片文案下载
│       ├── douyin_service.py       # 抖音视频下载服务
│       ├── douyin_cdp.py           # 抖音 CDP 浏览器控制
│       ├── feishu_service.py       # 飞书多维表格服务
│       ├── kdocs_service.py        # 金山文档服务
│       └── pgy_cdp.py              # 蒲公英 CDP 浏览器控制
├── frontend/
│   └── index.html                  # 可视化工具页面
├── deploy/
│   ├── guard.sh                    # 守护进程（崩溃自动拉起）
│   ├── install.sh                  # 安装脚本
│   ├── run_backend.sh              # 后端启动
│   ├── run_edge.sh                 # Edge 无头启动
│   ├── run_node.sh                 # Node 服务启动
│   ├── start_guard.sh              # 启动守护
│   ├── stop_guard.sh               # 停止守护
│   └── uninstall.sh                # 卸载脚本
├── data/
│   └── output/                     # 采集数据存储（自动生成）
├── docs/
│   ├── 飞书素材下载插件使用指南.md
│   ├── 飞书多维表格接入指南.md
│   └── 内网共享使用说明.md
└── logs/                           # 运行日志（自动生成）
```

## 外部依赖

本项目依赖两个外部项目，需放在与本项目同级目录：

### 1. Spider_XHS（小红书数据源）
```bash
git clone https://github.com/cv-cat/Spider_XHS.git ../Spider_XHS
cd ../Spider_XHS
pip install -r requirements.txt
# 配置 .env 文件，填入小红书 Cookie
cp .env.example .env  # 或手动创建
```

`.env` 需要配置：
- `COOKIES` — 小红书 PC 端 Cookie（搜索/笔记互动查询需要）
- `DY_COOKIES` — 抖音 Cookie（可选，抖音互动查询用）

### 2. feishu-douyin-tool（抖音视频互动数据）
```bash
# 需自行获取，放在 ../feishu-douyin-tool/
cd ../feishu-douyin-tool/backend
npm install
```

## 快速启动

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 配置外部依赖（见上方）

# 3. 启动
./start.sh
# 访问 http://localhost:5210
```

### 守护模式（推荐）
```bash
./deploy/start_guard.sh
# 崩溃自动拉起，停止：./deploy/stop_guard.sh
```

## 功能说明

| 功能 | 说明 | 端口/路径 |
|------|------|-----------|
| 主页 | 可视化工具页面 | `http://localhost:5210` |
| 工具页 | 素材下载工具 | `http://localhost:5210/tool/` |
| 小红书搜索 | 关键词搜索笔记 | POST `/api/xhs/search` |
| 笔记互动查询 | 点赞/评论/收藏/转发 | POST `/api/note/stats` |
| 小红书下载 | 图片+文案下载 | POST `/api/xhs/download_note` |
| 扫码登录 | 刷新小红书 Cookie | POST `/api/xhs/qr_login/start` |
| 抖音搜索 | 关键词搜索视频 | POST `/api/douyin/search` |
| 抖音下载 | 单视频无水印下载 | POST `/api/douyin/single_download` |
| 蒲公英 KOL | KOL 筛选+匹配 | POST `/api/pgy/*` |

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Flask 后端 | 5210 | 主服务 |
| Edge 无头 | 9350 | 蒲公英/合作笔记抓取 |
| Node 服务 | 4000 | 抖音视频互动数据 |

## 技术栈
- Python 3.13 + Flask
- Spider_XHS（小红书数据源）
- 自建抖音爬虫（CDP + SSR + API）
- 蒲公英平台 KOL 数据
- 飞书多维表格 API
- 纯 HTML/CSS/JS 前端

## Cookie 刷新
小红书 Cookie 会定期过期。过期后在主页点「📱 扫码刷新登录」按钮，用小红书 APP 扫码即可自动刷新，无需重启服务。
