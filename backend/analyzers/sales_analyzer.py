#!/usr/bin/env python3
"""
林清轩线下销售数据分析模块
数据来源: 2025.6-2026.5线下会员数据销售原表.xlsx
功能: 区域分析 / 品类分析 / 月度趋势 / 会员等级 / 产品排行 / 黑金霜专题
"""

import openpyxl
from collections import defaultdict
from pathlib import Path

SALES_FILE = Path("/Users/lily/Desktop/黑金资料/2025.6-2026.5线下会员数据销售原表.xlsx")

# 月份排序
def month_sort(m):
    if not m:
        return ""
    return str(m)

# 金额格式化
def fmt_money(v):
    if v is None:
        return 0
    return round(float(v), 2)

# 数量格式化
def fmt_qty(v):
    if v is None:
        return 0
    return int(float(v))


class SalesAnalyzer:
    """销售数据分析器"""

    def __init__(self, filepath=SALES_FILE):
        self.filepath = filepath
        self._data = None
        self._loaded = False

    def _load(self):
        """加载Excel数据（懒加载，首次调用时读取）"""
        if self._loaded:
            return
        wb = openpyxl.load_workbook(self.filepath, read_only=True, data_only=True)
        ws = wb["Sheet1"]
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue  # 跳过表头
            level, region, month, category, code, name, qty, amt = row
            rows.append({
                "level": level or "",
                "region": region or "",
                "month": str(month) if month else "",
                "category": category or "",
                "code": code or "",
                "name": name or "",
                "qty": fmt_qty(qty),
                "amount": fmt_money(amt),
            })
        wb.close()
        self._data = rows
        self._loaded = True

    def summary(self):
        """总览数据"""
        self._load()
        total_qty = sum(r["qty"] for r in self._data)
        total_amount = sum(r["amount"] for r in self._data)
        months = sorted(set(r["month"] for r in self._data if r["month"]))
        regions = sorted(set(r["region"] for r in self._data if r["region"]))
        categories = sorted(set(r["category"] for r in self._data if r["category"]))
        levels = sorted(set(r["level"] for r in self._data if r["level"]))

        # 黑金霜专项
        hj_qty = sum(r["qty"] for r in self._data if r["category"] == "黑金霜")
        hj_amt = sum(r["amount"] for r in self._data if r["category"] == "黑金霜")

        return {
            "total_qty": total_qty,
            "total_amount": round(total_amount, 2),
            "avg_unit_price": round(total_amount / total_qty, 2) if total_qty else 0,
            "month_range": f"{months[0]}~{months[-1]}" if months else "",
            "months": months,
            "regions": regions,
            "categories": categories,
            "levels": levels,
            "hj_qty": hj_qty,
            "hj_amount": round(hj_amt, 2),
            "hj_pct": round(hj_amt / total_amount * 100, 1) if total_amount else 0,
            "row_count": len(self._data),
        }

    def by_region(self, category=None):
        """按区域分析"""
        self._load()
        result = defaultdict(lambda: {"qty": 0, "amount": 0, "orders": 0})
        for r in self._data:
            if category and r["category"] != category:
                continue
            result[r["region"]]["qty"] += r["qty"]
            result[r["region"]]["amount"] += r["amount"]
            result[r["region"]]["orders"] += 1

        items = []
        for region, v in result.items():
            items.append({
                "region": region,
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
                "orders": v["orders"],
                "avg_price": round(v["amount"] / v["qty"], 2) if v["qty"] else 0,
            })
        items.sort(key=lambda x: x["amount"], reverse=True)
        return items

    def by_category(self):
        """按品类分析"""
        self._load()
        result = defaultdict(lambda: {"qty": 0, "amount": 0, "orders": 0})
        for r in self._data:
            result[r["category"]]["qty"] += r["qty"]
            result[r["category"]]["amount"] += r["amount"]
            result[r["category"]]["orders"] += 1

        items = []
        for cat, v in result.items():
            items.append({
                "category": cat,
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
                "orders": v["orders"],
                "avg_price": round(v["amount"] / v["qty"], 2) if v["qty"] else 0,
            })
        items.sort(key=lambda x: x["amount"], reverse=True)
        return items

    def by_month(self, category=None, region=None):
        """按月度趋势分析"""
        self._load()
        result = defaultdict(lambda: {"qty": 0, "amount": 0})
        for r in self._data:
            if category and r["category"] != category:
                continue
            if region and r["region"] != region:
                continue
            result[r["month"]]["qty"] += r["qty"]
            result[r["month"]]["amount"] += r["amount"]

        items = []
        for month in sorted(result.keys()):
            v = result[month]
            items.append({
                "month": month,
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
            })
        return items

    def by_level(self):
        """按会员等级分析"""
        self._load()
        result = defaultdict(lambda: {"qty": 0, "amount": 0, "orders": 0})
        for r in self._data:
            result[r["level"]]["qty"] += r["qty"]
            result[r["level"]]["amount"] += r["amount"]
            result[r["level"]]["orders"] += 1

        items = []
        for level, v in result.items():
            items.append({
                "level": level,
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
                "orders": v["orders"],
                "avg_order": round(v["amount"] / v["orders"], 2) if v["orders"] else 0,
            })
        items.sort(key=lambda x: x["amount"], reverse=True)
        return items

    def top_products(self, category=None, limit=20):
        """产品销量排行"""
        self._load()
        result = defaultdict(lambda: {"qty": 0, "amount": 0, "orders": 0})
        for r in self._data:
            if category and r["category"] != category:
                continue
            key = r["name"]
            result[key]["qty"] += r["qty"]
            result[key]["amount"] += r["amount"]
            result[key]["orders"] += 1
            result[key]["category"] = r["category"]

        items = []
        for name, v in result.items():
            items.append({
                "name": name,
                "category": v["category"],
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
                "orders": v["orders"],
            })
        items.sort(key=lambda x: x["amount"], reverse=True)
        return items[:limit]

    def region_category_matrix(self):
        """区域×品类交叉分析矩阵"""
        self._load()
        categories = sorted(set(r["category"] for r in self._data if r["category"]))
        regions = sorted(set(r["region"] for r in self._data if r["region"]))

        matrix = {}
        for region in regions:
            matrix[region] = {cat: {"qty": 0, "amount": 0} for cat in categories}

        for r in self._data:
            if r["region"] and r["category"]:
                matrix[r["region"]][r["category"]]["qty"] += r["qty"]
                matrix[r["region"]][r["category"]]["amount"] += r["amount"]

        # 转为列表格式
        rows = []
        for region in regions:
            row = {"region": region}
            total_amt = 0
            for cat in categories:
                amt = round(matrix[region][cat]["amount"], 2)
                row[cat] = amt
                total_amt += amt
            row["total"] = round(total_amt, 2)
            rows.append(row)
        rows.sort(key=lambda x: x["total"], reverse=True)

        return {"categories": categories, "rows": rows}

    def heijin_detail(self):
        """黑金霜专题分析"""
        self._load()
        hj_data = [r for r in self._data if r["category"] == "黑金霜"]

        # 按规格聚合
        spec_result = defaultdict(lambda: {"qty": 0, "amount": 0, "orders": 0})
        for r in hj_data:
            spec_result[r["name"]]["qty"] += r["qty"]
            spec_result[r["name"]]["amount"] += r["amount"]
            spec_result[r["name"]]["orders"] += 1

        specs = []
        for name, v in spec_result.items():
            specs.append({
                "name": name,
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
                "orders": v["orders"],
                "avg_price": round(v["amount"] / v["qty"], 2) if v["qty"] else 0,
            })
        specs.sort(key=lambda x: x["amount"], reverse=True)

        # 区域分布
        region_result = defaultdict(lambda: {"qty": 0, "amount": 0})
        for r in hj_data:
            region_result[r["region"]]["qty"] += r["qty"]
            region_result[r["region"]]["amount"] += r["amount"]

        regions = []
        for region, v in region_result.items():
            regions.append({
                "region": region,
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
            })
        regions.sort(key=lambda x: x["amount"], reverse=True)

        # 月度趋势
        month_result = defaultdict(lambda: {"qty": 0, "amount": 0})
        for r in hj_data:
            month_result[r["month"]]["qty"] += r["qty"]
            month_result[r["month"]]["amount"] += r["amount"]

        months = []
        for month in sorted(month_result.keys()):
            v = month_result[month]
            months.append({
                "month": month,
                "qty": v["qty"],
                "amount": round(v["amount"], 2),
            })

        total_qty = sum(r["qty"] for r in hj_data)
        total_amt = sum(r["amount"] for r in hj_data)

        return {
            "total_qty": total_qty,
            "total_amount": round(total_amt, 2),
            "spec_count": len(specs),
            "top_specs": specs[:10],
            "region_dist": regions,
            "monthly_trend": months,
        }


# 单例
analyzer = SalesAnalyzer()
