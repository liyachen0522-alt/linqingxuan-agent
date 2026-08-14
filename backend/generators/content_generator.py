#!/usr/bin/env python3
"""
林清轩黑金霜 2.0 - 内容生成引擎
基于产品手册真实数据 + 小红书高赞笔记分析，自动生成种草文案和抖音脚本
"""

import random
import json
from datetime import datetime


class ContentGenerator:
    """种草内容生成器 - 基于林清轩黑金霜2.0产品手册"""

    # ========================
    # 产品核心数据（来源：产品手册）
    # ========================
    PRODUCT_INFO = {
        "full_name": "林清轩山茶花黑金时光肽抗皱焕亮精华霜",
        "short_name": "林清轩黑金霜 2.0",
        "version": "第2代细胞能量黑金霜",
        "brand_background": "12年专研山茶花，9年专研细胞级抗老，70+专利，30+硕博研发团队，1亿+研发投入",
        "academic_partner": "战略携手交大细胞与基因治疗研究院，共建抗皮肤衰老联合研究实验室",
    }

    # 品牌核心卖点库（全部来自产品手册真实数据）
    SELLING_POINTS = {
        "core_tech": "细胞能量因子（4重高山红山茶精萃 + 3重能量精萃：腺苷、浮游生物GP4G、依克多因）",
        "nad": "48H激活细胞年轻之芯NAD+ 120.95%",
        "atp": "48H促生线粒体供能ATP +128.25%",
        "collagen_boost": "促生胶原蛋白+157.24%，远超玻色因（I型+21.57%、III型+12.94%、IV型+25.94%、VII型+61.04%、弹性蛋白+41.12%）",
        "peptides": "专研6重黄金小分子肽（棕榈酰三肽-5、棕榈酰四肽-7、乙酰基六肽-8、芋螺肽、燕麦肽、肌肽）",
        "collagen": "100%人同源专利III型胶原蛋白（专利号：ZL2013 10033299.6）",
        "anti_temp": "专利抗温度老化原料（浮游生物提取物，专利号：ZL201580003807.3），4℃低温应激蛋白+63.90%，42℃高温应激蛋白+49.09%",
        "brightening": "院线级传明酸 + ≥98%高纯度麦角硫因 + 96%高纯度四氢姜黄素",
        "absorption": "自研专利纳米囊泡透皮吸收技术（专利号：ZL202211695584.X），毛孔千分之一大小，2.3倍渗透力，30min渗透角质层，8小时到肌肤底层",
        "texture": "丰盈乳霜质地（经典版滋润型）/ 轻盈奶霜质地（轻盈版），像融化的冰淇淋，推开就吸收",
        "9_proteins": "促生9大年轻关键蛋白（兜甲蛋白+60.27%、紧密连接蛋白+39.92%、内披蛋白+38.36%、角蛋白10+87.95%、IV型胶原+25.94%、VII型胶原+61.04%、I型胶原+21.57%、III型胶原+12.94%、弹性蛋白+41.12%）",
    }

    # 功效实测数据（来源：第三方测试机构）
    EFFICACY_DATA = {
        "10min": "10分钟光泽度+29.55%",
        "21day_wrinkle": "21天6维淡纹：法令纹-60.00%、抬头纹-41.65%、川字纹-39.49%、眼下纹-38.69%、嘴角纹-17.37%、颈纹-41.76%",
        "28day_firm": "28天紧塑脸颊+23.97%、清晰下颌线1.11度、角质层水分+122.19%、屏障强韧+19.09%、苹果肌提升+14.55%",
        "vs_medical": "堪比特殊美容项目（热玛吉级），连续使用28天，一侧脸用面霜 vs 另一侧脸做特殊美容项目，效果相当",
        "post_procedure": "光子嫩肤后30分钟即可使用，皮肤经表皮水分流失率及角质层水分含量有显著改善",
        "user_eval_10min": "96.67%受试者认可即刻淡纹、96.67%认可即刻透亮、93.33%认可即刻光泽感提升",
        "user_eval_21day": "100%受试者认可淡纹效果好、96.67%认可更紧致、100%认可更有弹性、100%认可温和无刺激",
    }

    # 安全保障
    SAFETY = {
        "0_add": "6大0添加：无矿油、无矿脂、无石蜡、无酒精、无色素、无尼泊金酯类防腐剂",
        "natural": "88%+天然来源成分（依据ISO16128标准计算）",
        "patents": "10大专利背书",
        "sensitive_safe": "30位41-59岁中国敏感皮肤受试者实测，100%认可温和无刺激",
    }

    # 产品版本
    VARIANTS = {
        "classic": "经典版（滋润型）- 干皮&混合皮挚爱，敏肌可用",
        "light": "轻盈版 - 油皮挚爱，敏肌可用",
    }

    # 用户痛点库
    PAIN_POINTS = {
        "anti_aging": [
            "自从过了25+，脸部衰老速度明显加快：法令纹越来越深",
            "一熬夜各种干纹细纹都冒出来，皮肤松松垮垮",
            "下颚线没以前清晰了，整张脸写着两个字：疲倦",
            "即使用很贵的面霜，好像也只停留在表面",
        ],
        "lifestyle": [
            "白天会议不断，晚上还要应对各种局，凌晨两点回消息",
            "开工这一个月几乎天天连轴转，看着镜子里的自己越来越焦虑",
            "三十岁之后越来越觉得，护肤不是追赶，是留白",
            "月入5W的代价就是这张熬夜脸，但脸就是战绩",
        ],
        "ingredient": [
            "胶原为什么会不足？年龄增加，NAD+水平下降，细胞能量供应不够",
            "没有力气补充新的胶原，也没力气修护受损的胶原",
            "抗老不仅要从外面补，更要从里面把细胞能量唤醒",
            "新的没有补充，旧的又被破坏，所以胶原严重缺失",
        ],
        "gift": [
            "越长大越懂，给闺蜜送礼拼的从来不是价格",
            "30+的护肤逻辑：不折腾才是最高级的自律",
            "干敏皮姐妹要是想找温和不刺激的抗皱面霜",
            "老公的嘴才是最好的测平仪——他说你变嫩了就是真嫩了",
        ],
    }

    # 小红书标题模板库（按角度分类）
    TITLE_TEMPLATES = {
        "anti_aging": [
            "求求了！脸垮有纹的，试试这瓶{product}",
            "{age}+垮脸自救成功！素颜终于敢出门啦",
            "为什么说{age}+高效抗老都要先从内在入手？",
            "假性垮脸直接变真性胶原脸！垮脸进进进！",
            "听劝！干敏皮抗老，别再盲目跟风折腾自己了",
            "熬夜垮脸被夸嫩？同事以为我偷偷去医美",
            "{age}+贵气感守恒定律：脸不垮，气不垮",
            "怕美美后「打回原形」？这瓶{product}真牛",
            "交过智商税的人，才懂这罐有多香！",
            "月入{income}丨不惧熬夜连轴转，这张脸就是战绩",
            "堪比热玛吉？21天法令纹淡了60%不是吹的",
            "光子嫩肤后能用什么面霜？这罐修护力绝了",
        ],
        "ingredient": [
            "诺贝尔奖新发现！就已经被用到护肤了？",
            "NAD+的真身到底是什么？一篇讲透",
            "成分党扒一扒：{product}到底值不值得买",
            "细胞能量因子VS玻色因，谁更强？数据说话",
            "6重小分子肽+III型胶原蛋白，这配方什么水平",
            "促生9大蛋白是什么概念？这瓶面霜有点猛",
        ],
        "lifestyle": [
            "{age}+以后，护肤不是追赶，是留白",
            "三十岁之后，把钱用在刀刃上",
            "月入{income}➕，靠它对抗复工熬夜脸",
            "不折腾才是最高级的自律",
            "越长大越懂｜给闺蜜送礼拼的从来不是价格",
            "88%天然成分+6大0添加，敏肌抗老终于不用将就",
        ],
        "gift": [
            "温峥嵘你可太会选了！这面霜淡纹真没骗人！",
            "金巧巧的护肤逻辑，被我扒明白了！",
            "51岁还能跳孔雀舞拍戏！状态真的骗不了人",
            "给闺蜜送礼推荐｜这罐面霜闭眼冲就对了",
            "贵妇按摩棒+黑金瓶身，送礼排面拉满了",
        ],
    }

    # 小红书正文结构模板
    BODY_TEMPLATES = {
        "anti_aging": [
            "{pain_point}\n\n{science_explanation}\n\n所以，抗老不仅要从外面补，更要从里面把细胞能量唤醒。让肌肤自身产生更多的胶原来深度抗老。就拿我最近用的{product}来说，做到了细胞能量抗皱，从深层激活我们的肌肤。{selling_points}\n\n{experience}\n\n{texture_desc}\n\n{usage_method}\n\n{closing}",
        ],
        "ingredient": [
            "{pain_point}\n\n{science_explanation}\n\n{product_analysis}\n\n{ingredient_breakdown}\n\n{experience}\n\n{closing}",
        ],
        "lifestyle": [
            "{pain_point}\n\n直到遇见{product}，才算把状态稳住。\n{selling_points}\n\n{experience}\n\n{texture_desc}\n\n{closing}",
        ],
        "gift": [
            "{pain_point}\n\n{celebrity_intro}\n\n{selling_points}\n\n{experience}\n\n{closing}",
        ],
    }

    # 标签库
    TAGS_POOL = {
        "brand": ["林清轩黑金霜", "林清轩黑金面霜", "林清轩", "林清轩面霜"],
        "function": ["抗老面霜", "抗老", "法令纹", "法令纹淡化", "熟龄肌护肤", "抗皱", "淡纹", "紧致"],
        "audience": ["干敏皮抗老", "秋冬护肤", "30+护肤", "25+抗老", "熬夜护肤"],
        "ingredient": ["细胞能量因子", "NAD+", "胶原蛋白", "抗老成分", "6重小分子肽", "III型胶原蛋白"],
        "celebrity": ["温峥嵘同款", "明星同款"],
        "safety": ["敏肌可用", "0添加", "天然成分"],
    }

    # 抖音脚本模板
    DOUYIN_SCRIPTS = {
        "experience": {
            "hook_templates": [
                "熬夜垮脸的姐妹停一下！这瓶面霜真的救了我",
                "30+还在纠结抗老面霜的，看完这条就够了",
                "用了一个月林清轩黑金霜，法令纹真的淡了",
                "堪比热玛吉？21天法令纹淡了60%，实测不骗人",
            ],
            "structure": "hook → 痛点共鸣 → 产品展示 → 成分讲解 → 使用展示 → 效果对比 → 行动号召",
        },
        "science": {
            "hook_templates": [
                "NAD+是什么？为什么抗老都在说它",
                "细胞能量因子VS玻色因，谁更强？数据说话",
                "6重小分子肽+III型胶原蛋白，这配方什么水平",
                "促生9大蛋白是什么概念？这瓶面霜有点猛",
            ],
            "structure": "悬念引入 → 科普NAD+ → 产品成分拆解 → 实验数据 → 质地展示 → 总结推荐",
        },
        "unboxing": {
            "hook_templates": [
                "林清轩黑金霜2.0开箱！黑金瓶身+贵妇按摩棒",
                "贵妇面霜开箱｜林清轩黑金霜值不值",
                "双十一囤的面霜到了！林清轩黑金霜2.0开箱",
            ],
            "structure": "包装展示 → 开箱过程 → 质地特写 → 上手试涂 → 初体验感受 → 总结",
        },
        "comparison": {
            "hook_templates": [
                "林清轩黑金霜 VS 雅诗兰黛，谁更抗老",
                "同价位面霜横评，林清轩能打吗",
                "国货VS大牌，抗老面霜到底选哪个",
                "细胞能量因子VS玻色因，促胶原数据对比",
            ],
            "structure": "对比引入 → 两款产品展示 → 成分对比 → 质地对比 → 上脸对比 → 结论推荐",
        },
    }

    def generate_xhs_content(
        self,
        topic: str = "林清轩黑金霜",
        angle: str = "anti_aging",
        tone: str = "professional_friendly",
        target_audience: str = "25-35岁女性",
        extra_info: str = "",
    ) -> dict:
        """生成小红书种草文案"""

        title = self._generate_title(topic, angle)
        body = self._generate_body(topic, angle, tone, target_audience, extra_info)
        tags = self._generate_tags(angle)
        tips = self._generate_xhs_tips(angle, target_audience)

        return {
            "platform": "xiaohongshu",
            "topic": topic,
            "angle": angle,
            "target_audience": target_audience,
            "title": title,
            "body": body,
            "tags": tags,
            "tags_str": " ".join(f"#{t}" for t in tags),
            "tips": tips,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def generate_douyin_content(
        self,
        topic: str = "林清轩黑金霜",
        video_type: str = "experience",
        duration: str = "30-60s",
        target_audience: str = "25-35岁女性",
        extra_info: str = "",
    ) -> dict:
        """生成抖音短视频脚本"""

        script_template = self.DOUYIN_SCRIPTS.get(video_type, self.DOUYIN_SCRIPTS["experience"])
        hook = random.choice(script_template["hook_templates"])
        script = self._generate_douyin_script(topic, video_type, duration, target_audience, extra_info)

        tags = self._generate_tags("anti_aging")
        if video_type == "science":
            tags = [t for t in tags if t not in self.TAGS_POOL["celebrity"]]
            tags = self.TAGS_POOL["ingredient"][:3] + self.TAGS_POOL["brand"][:2] + ["护肤科普", "成分党"]

        return {
            "platform": "douyin",
            "topic": topic,
            "video_type": video_type,
            "duration": duration,
            "target_audience": target_audience,
            "hook": hook,
            "script": script,
            "structure": script_template["structure"],
            "tags": tags,
            "tags_str": " ".join(f"#{t}" for t in tags),
            "music_suggestion": self._suggest_music(video_type),
            "shooting_tips": self._generate_shooting_tips(video_type),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def generate_titles(self, topic: str, angle: str, count: int = 10) -> list:
        """生成标题选项"""
        templates = self.TITLE_TEMPLATES.get(angle, self.TITLE_TEMPLATES["anti_aging"])
        titles = []
        for t in templates[:count]:
            title = t.format(
                product=topic,
                age=random.choice(["25", "30", "35"]),
                income=random.choice(["4w", "5W", "3w"]),
                celebrity=random.choice(["温峥嵘", "金巧巧"]),
            )
            titles.append(title)
        random.shuffle(titles)
        return titles[:count]

    def _generate_title(self, topic: str, angle: str) -> str:
        templates = self.TITLE_TEMPLATES.get(angle, self.TITLE_TEMPLATES["anti_aging"])
        template = random.choice(templates)
        return template.format(
            product=topic,
            age=random.choice(["25", "30", "35"]),
            income=random.choice(["4w", "5W", "3w"]),
            celebrity=random.choice(["温峥嵘", "金巧巧"]),
        )

    def _generate_body(self, topic, angle, tone, target_audience, extra_info) -> str:
        """生成正文"""
        pain_point = random.choice(self.PAIN_POINTS.get(angle, self.PAIN_POINTS["anti_aging"]))

        science_explanation = (
            "简单来说，随着年龄增加，体内NAD+水平下降，细胞线粒体供能不足，"
            "没有力气补充新的胶原，也没力气去修护受损的胶原，"
            "新的没有补充，旧的又被破坏，所以胶原严重缺失，"
            "这时候各种纹路、松弛、暗沉的问题也就出现了。"
        )

        selling_points = (
            f"通过{self.SELLING_POINTS['core_tech']}组合形成的细胞能量因子，"
            f"48H激活NAD+ 120.95%，促生ATP +128.25%，给细胞加油蓄能，"
            f"促生胶原蛋白+157.24%，远超玻色因！\n\n"
            f"并且复配了{self.SELLING_POINTS['peptides']}和{self.SELLING_POINTS['collagen']}，"
            f"促生9大年轻关键蛋白，内外协同撑起皮肤。\n\n"
            f"更绝的是搭载{self.SELLING_POINTS['absorption']}，"
            f"加上{self.SELLING_POINTS['brightening']}，"
            f"在皮肤抗老的同时减少自由基，让皮肤边抗老边提亮。"
        )

        product_analysis = (
            f"{topic}的核心竞争力在于「细胞能量抗皱」这个理念。"
            f"它不是简单的外部补充胶原，而是从细胞内部激活NAD+和ATP，"
            f"让皮肤自己「支棱」起来。促生9大年轻关键蛋白，"
            f"从屏障修护到胶原层全面覆盖。"
        )

        ingredient_breakdown = (
            f"核心成分拆解：\n"
            f"• 细胞能量因子（4重红山茶精萃+3重能量精萃）→ 激活NAD+ 120.95%、ATP +128.25%\n"
            f"• 6重黄金小分子肽 → 淡纹紧致，促生胶原\n"
            f"• 专利III型胶原蛋白（100%人同源）→ 直补胶原\n"
            f"• 专利抗温度老化原料 → 24H保护胶原不流失（4℃+63.90%，42℃+49.09%）\n"
            f"• 院线级传明酸+98%麦角硫因+96%四氢姜黄素 → 焕亮抗氧\n"
            f"• 纳米囊泡透皮吸收技术 → 毛孔千分之一大小，2.3倍渗透力\n"
            f"• 促生9大年轻关键蛋白 → 屏障+基底膜+胶原层三维充盈"
        )

        experience = (
            "坚持用了快一个月，最直观的变化就是脸不垮了！"
            "就连熬夜后，皮肤也不会又黄又松，反而透着自然的光泽。"
            "之前卡粉的法令纹像被慢慢填平似的，苹果肌也饱满了一些。"
            f"最让我惊喜的是，{self.EFFICACY_DATA['21day_wrinkle']}，"
            f"而且{self.EFFICACY_DATA['28day_firm']}。"
        )

        texture_desc = (
            f"{self.SELLING_POINTS['texture']}。"
            f"现在有经典版（滋润型，干皮&混合皮挚爱）和轻盈版（油皮挚爱）两个版本，"
            f"敏肌都可用，还有环保替换装。"
        )

        usage_method = (
            "分享我的使用方法：\n"
            "1️⃣ 洁面爽肤后，先用爽肤水打开吸收通道\n"
            "2️⃣ 取适量精华涂抹面部\n"
            "3️⃣ 取珍珠大小的面霜于掌心，均匀涂抹\n"
            "4️⃣ 从下颌线推至耳后，再从嘴角提向太阳穴，轻轻提拉按摩\n"
            "5️⃣ 搭配定制黑金贵妇按摩能量棒，至臻呵护肌肤\n"
            "6️⃣ 第二天醒来能感觉到轮廓明显收紧"
        )

        closing_options = [
            f"干敏皮姐妹要是想找温和不刺激、淡纹还自然的抗皱面霜，闭眼冲{topic}就对了！",
            f"三十岁之后越来越觉得，与其在各种平价里试错，不如把预算集中在一瓶真正有底气的面霜上。",
            f"毕竟这张脸，是每天要见的职场名片，把钱用在刀刃上，总归是值得的。",
            f"堪比热玛吉级的抗皱效果，10大专利背书，{self.SAFETY['0_add']}，这瓶真的不是智商税。",
        ]
        closing = random.choice(closing_options)

        celebrity_intro = (
            "跟着温峥嵘护肤真的不容易出错！作为干敏皮+熟龄肌，"
            "我之前最头疼的就是秋冬抗老，结果刷峥嵘姐姐视频被种草了林清轩黑金霜2.0，"
            "加上我早就用过他家山茶花油巨好用，果断入坑。"
        )

        if extra_info:
            closing += f"\n\n{extra_info}"

        template = self.BODY_TEMPLATES.get(angle, self.BODY_TEMPLATES["anti_aging"])[0]
        return template.format(
            pain_point=pain_point,
            science_explanation=science_explanation,
            selling_points=selling_points,
            product=topic,
            experience=experience,
            texture_desc=texture_desc,
            usage_method=usage_method,
            closing=closing,
            product_analysis=product_analysis,
            ingredient_breakdown=ingredient_breakdown,
            celebrity_intro=celebrity_intro,
        )

    def _generate_tags(self, angle: str) -> list:
        """生成标签组合"""
        tags = []
        tags.extend(self.TAGS_POOL["brand"][:2])
        tags.extend(random.sample(self.TAGS_POOL["function"], 3))
        tags.extend(random.sample(self.TAGS_POOL["audience"], 2))
        if angle == "ingredient":
            tags.extend(self.TAGS_POOL["ingredient"][:2])
        if angle == "gift":
            tags.extend(self.TAGS_POOL["celebrity"][:1])
        seen = set()
        unique_tags = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                unique_tags.append(t)
        return unique_tags[:8]

    def _generate_xhs_tips(self, angle: str, audience: str) -> list:
        """生成小红书发布建议"""
        tips = [
            "建议配 5-8 张图片，第一张为封面图（文字+产品图）",
            "发布时间建议：工作日 12:00-13:00 或 20:00-22:00",
            "正文前 3 行决定是否被点开，痛点要够痛、够共鸣",
            "评论区主动互动，引导用户提问「在哪买」「多少钱」",
        ]
        if angle == "anti_aging":
            tips.append("封面建议用「使用前后对比」或「手持产品+文字标语」")
        elif angle == "ingredient":
            tips.append("封面建议用「成分表特写」或「手绘成分拆解图」")
        elif angle == "lifestyle":
            tips.append("封面建议用「生活场景+产品融入」，不要太硬广")
        elif angle == "gift":
            tips.append("封面建议用「礼盒包装」或「送礼场景」")
        return tips

    def _generate_douyin_script(self, topic, video_type, duration, audience, extra_info) -> str:
        """生成抖音脚本"""
        if video_type == "experience":
            return self._douyin_experience_script(topic, duration, extra_info)
        elif video_type == "science":
            return self._douyin_science_script(topic, duration, extra_info)
        elif video_type == "unboxing":
            return self._douyin_unboxing_script(topic, duration, extra_info)
        elif video_type == "comparison":
            return self._douyin_comparison_script(topic, duration, extra_info)
        return self._douyin_experience_script(topic, duration, extra_info)

    def _douyin_experience_script(self, topic, duration, extra_info) -> str:
        return f"""【场景1 - 痛点引入】(0-5s)
画面：素颜对镜，特写法令纹、眼角纹
口播：「过了25+，法令纹越来越深，一熬夜整张脸都垮了...」

【场景2 - 产品亮相】(5-10s)
画面：从包装盒取出{topic}，特写黑金瓶身
口播：「直到我遇到这瓶{topic}2.0，才真正理解什么叫细胞能量抗皱」

【场景3 - 成分讲解】(10-25s)
画面：手持产品+文字标注核心成分
口播：「核心是细胞能量因子，48H激活NAD+ 120.95%！ATP+128.25%！
相当于给皮肤细胞充电。还促生胶原蛋白+157.24%，远超玻色因！
复配6重黄金小分子肽和100%人同源III型胶原蛋白，促生9大年轻关键蛋白」

【场景4 - 质地展示】(25-35s)
画面：手背涂抹展示质地
口播：「丰盈乳霜质地，像融化的冰淇淋，推开就吸收，润而不油」

【场景5 - 使用方法】(35-45s)
画面：上脸涂抹+黑金按摩棒提拉
口播：「从下颌线推至耳后，再从嘴角提向太阳穴，
搭配定制黑金贵妇按摩能量棒，至臻呵护肌肤」

【场景6 - 效果展示】(45-55s)
画面：使用前后对比，标注实测数据
口播：「21天实测：法令纹-60%！抬头纹-41.65%！
28天下颌线清晰1.11度！堪比热玛吉级抗皱效果！」

【场景7 - 行动号召】(55-60s)
画面：手持产品+笑容
口播：「6大0添加，88%天然成分，敏肌安心用。脸垮有纹的姐妹，试试这瓶{topic}」"""

    def _douyin_science_script(self, topic, duration, extra_info) -> str:
        return f"""【场景1 - 悬念引入】(0-5s)
画面：白板/iPad展示「NAD+」
口播：「为什么所有大牌都在说NAD+？它到底是什么？」

【场景2 - 科普NAD+】(5-15s)
画面：动画图解细胞能量
口播：「简单说，NAD+是细胞的能量货币。年龄越大，NAD+越少，
线粒体供能不足，细胞没力气补充胶原，皱纹就来了」

【场景3 - 产品成分拆解】(15-30s)
画面：产品特写+成分标注
口播：「{topic}2.0的核心就是细胞能量因子，
4重高山红山茶精萃+3重能量精萃（腺苷、浮游生物GP4G、依克多因）
48H激活NAD+ 120.95%，促生ATP +128.25%！
促生胶原蛋白+157.24%，远超玻色因！
还有6重黄金小分子肽+专利III型胶原蛋白」

【场景4 - 数据支撑】(30-45s)
画面：实验数据图表对比
口播：「不是智商税，是有科学依据的。
促生9大年轻关键蛋白，三维充盈。
纳米囊泡透皮吸收技术，毛孔千分之一大小，2.3倍渗透力
30min渗透角质层，8小时到肌肤底层」

【场景5 - 质地展示】(45-50s)
画面：手背涂抹
口播：「丰盈乳霜质地，像冰淇淋一样化开，润而不腻。
还有轻盈版给油皮选择」

【场景6 - 总结】(50-60s)
画面：手持产品
口播：「抗老不是表面功夫，要从细胞能量开始。
10大专利背书，{topic}2.0，值得一试」"""

    def _douyin_unboxing_script(self, topic, duration, extra_info) -> str:
        return f"""【场景1 - 开箱预告】(0-3s)
画面：手拍包装盒
口播：「林清轩黑金霜2.0开箱！黑金瓶身+贵妇按摩棒，太高级了」

【场景2 - 开箱过程】(3-15s)
画面：拆包装、展示黑金瓶身细节、按摩棒
口播：「金色瓶身质感满满，拿在手里沉甸甸的，贵妇感拉满。
还配了定制黑金贵妇按摩能量棒，1棒双享」

【场景3 - 质地特写】(15-25s)
画面：打开瓶盖，挖取面霜特写
口播：「丰盈乳霜质地，像融化的冰淇淋，看着就想摸。
还有轻盈版给油皮选择」

【场景4 - 上手试涂】(25-35s)
画面：手背涂抹延展性展示
口播：「推开非常丝滑，搭载纳米囊泡透皮吸收技术，
2.3倍渗透力，一下子就吸收了，完全不油腻」

【场景5 - 成分速览】(35-45s)
画面：文字标注核心成分
口播：「细胞能量因子，激活NAD+ 120.95%
6重黄金小分子肽+专利III型胶原蛋白
院线级传明酸+98%麦角硫因+96%四氢姜黄素
配方真的很能打」

【场景6 - 初体验感受】(45-55s)
画面：上脸涂抹
口播：「第一次用就感觉皮肤被喂饱了，10分钟光泽度+29.55%
第二天醒来脸很透亮」

【场景7 - 总结】(55-60s)
画面：手持产品+满意表情
口播：「开箱就很有仪式感，10大专利背书，6大0添加，
想抗老的姐妹可以冲」"""

    def _douyin_comparison_script(self, topic, duration, extra_info) -> str:
        return f"""【场景1 - 对比引入】(0-5s)
画面：两款产品并排
口播：「细胞能量因子VS玻色因，促胶原谁更强？数据说话！」

【场景2 - 两款展示】(5-15s)
画面：分别展示两款产品
口播：「左边{topic}2.0，主打细胞能量因子
右边含玻色因的大牌，来横评一下促胶原能力」

【场景3 - 成分对比】(15-30s)
画面：实验数据图表对比
口播：「{topic}：细胞能量因子促生胶原蛋白+157.24%
I型+21.57%、III型+12.94%、IV型+25.94%、VII型+61.04%、弹性蛋白+41.12%
全部远超玻色因！
还多了6重小分子肽+III型胶原蛋白+纳米囊泡透皮技术」

【场景4 - 质地对比】(30-40s)
画面：两款同时手背涂抹
口播：「{topic}像冰淇淋质地，延展性更好；
大牌偏厚重，需要多按摩一会」

【场景5 - 上脸对比】(40-50s)
画面：左右脸分别试用
口播：「{topic}吸收更快，搭载纳米囊泡技术2.3倍渗透力；
大牌滋润度高但略黏」

【场景6 - 结论】(50-60s)
画面：手持{topic}
口播：「综合来看，{topic}2.0在成分创新和促胶原数据上都更胜一筹，
10大专利背书，6大0添加，性价比也更高。抗老面霜，这瓶值得入」"""

    def _suggest_music(self, video_type: str) -> str:
        """推荐BGM风格"""
        suggestions = {
            "experience": "轻快vlog风 / 温柔治愈系BGM",
            "science": "科技感电子乐 / 知识科普BGM",
            "unboxing": "治愈轻音乐 / 小确幸BGM",
            "comparison": "节奏感强的对比BGM",
        }
        return suggestions.get(video_type, "轻快BGM")

    def _generate_shooting_tips(self, video_type: str) -> list:
        """生成拍摄建议"""
        general_tips = [
            "使用自然光拍摄，避免黄光灯",
            "产品特写用微距镜头或放大拍摄",
            "口播语速适中，每条不超过60秒",
            "字幕必加，很多用户静音刷视频",
        ]
        type_tips = {
            "experience": ["使用前后对比图放在封面", "法令纹区域多给特写", "可标注21天法令纹-60%实测数据"],
            "science": ["准备白板或iPad做图解", "成分标注用动画效果", "促胶原VS玻色因数据对比图"],
            "unboxing": ["开箱过程要慢，有仪式感", "黑金瓶身和按摩棒多给特写"],
            "comparison": ["两款产品同时出现", "对比要公平客观", "促胶原数据用柱状图展示"],
        }
        return general_tips + type_tips.get(video_type, [])
