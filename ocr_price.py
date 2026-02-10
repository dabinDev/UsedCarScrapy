"""
OCR价格解析模块
- 支持本地OCR（WinOCR Windows原生 / RapidOCR 备选）和百度云OCR
- 从截图中提取二手车价格和新车指导价
"""

import asyncio
import base64
import logging
import os
import re
import time


class LocalOCR:
    """本地OCR引擎（EasyOCR，准确率高，~1.4s/张）"""

    def __init__(self):
        import warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        import easyocr
        self._reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)

    def recognize_file(self, image_path: str):
        """识别图片文件，返回合并后的文本"""
        try:
            results = self._reader.readtext(image_path, detail=0)
            return " ".join(results) if results else None
        except Exception:
            return None

    async def recognize_file_async(self, image_path: str):
        """异步接口（在线程池中执行，避免阻塞事件循环）"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.recognize_file, image_path)

    async def recognize_file_twpass_async(self, image_path: str):
        """兼容接口：返回 (text, None)，不需要两阶段"""
        text = await self.recognize_file_async(image_path)
        return text, None

    def recognize_image(self, image_data_bytes: bytes):
        """识别图片bytes"""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            tmp.write(image_data_bytes)
            tmp.close()
            return self.recognize_file(tmp.name)
        finally:
            os.unlink(tmp.name)


class BaiduOCR:
    """百度OCR客户端（备选，需要网络）"""

    def __init__(self, app_id="7432271", api_key="VvC2noYSwA3BVXehBsSGzw6f",
                 secret_key="hROkWlBeefuTgtIsnf6m3pH5M99zLfzz"):
        self.app_id = app_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expires_at = 0

    def get_access_token(self):
        """获取百度API访问令牌"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        import requests
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }

        try:
            response = requests.post(url, params=params, timeout=10)
            result = response.json()
            if "access_token" in result:
                self.access_token = result["access_token"]
                self.token_expires_at = time.time() + result.get("expires_in", 2592000) - 60
                return self.access_token
        except Exception:
            pass
        return None

    def recognize_image(self, image_data_bytes: bytes):
        """使用百度通用OCR识别图片（传入bytes）"""
        import requests
        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}"

        try:
            image_b64 = base64.b64encode(image_data_bytes).decode()
            data = {"image": image_b64, "language_type": "CHN_ENG"}
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            response = requests.post(url, headers=headers, data=data, timeout=10)
            result = response.json()

            if "error_code" in result:
                return None

            words_result = result.get("words_result", [])
            text = "\n".join([item["words"] for item in words_result])
            return text
        except Exception:
            return None

    def recognize_file(self, image_path: str):
        """识别图片文件"""
        with open(image_path, "rb") as f:
            return self.recognize_image(f.read())


def _normalize_ocr_text(text: str) -> str:
    """预处理OCR文本：去除字间空格、统一标点、修复常见误识别（适配 winocr 输出）"""
    # 1. 统一全角标点
    text = text.replace("．", ".").replace("：", ":").replace("，", ",")
    text = text.replace("》", "|").replace("《", "|").replace("】", "|").replace("【", "|")
    # 2. 去掉所有空格
    text = re.sub(r' +', '', text)
    # 3. 修复"新车指导价"的各种误识别变体
    #    新车指寻价 / 新车栝价 / 新车指异价 / 新车栝导价 / 新车抬导价 / 新车指导, 等
    text = text.replace("新车抬导价", "新车指导价")
    text = re.sub(r'新车[指栝][导寻栝异]?价', '新车指导价', text)
    # "新车指导," / "新车指导." -> "新车指导价:"（"价"字被误识别为标点）
    text = re.sub(r'新车指导[,.]', '新车指导价:', text)
    # 合并连续冒号 "价::" -> "价:"
    text = re.sub(r'价:+', '价:', text)
    # 4. 修复价格中 L/l -> 1（仅在价格上下文中）
    #    "L58万" -> "1.58万", "L08万" -> "1.08万"
    text = re.sub(r'[Ll](\d{2})万', r'1.\1万', text)
    # 5. 修复 "数字+乱码+万" 的断裂价格
    #    "1"8万" -> 去掉引号尝试拼接
    text = text.replace('"', '').replace('"', '').replace('"', '')
    text = text.replace("'", "").replace("'", "").replace("'", "")
    # 6. 修复末尾 "力" 被误识别（应为万的一部分或小数部分丢失）
    #    "7力" 在价格上下文中无法恢复，但 "数字.数字力" 可以
    return text


def _extract_price_near_keyword(text: str, keyword: str):
    """在 keyword 附近提取价格（万为单位），容错更强"""
    idx = text.find(keyword)
    if idx < 0:
        return None, None

    before = text[:idx]
    after = text[idx:]

    # 从 keyword 之后提取新车指导价
    official = None
    m = re.search(r'新车指导价:(\d+\.?\d*)万', after)
    if m:
        official = float(m.group(1))
    else:
        # 尝试匹配 "新车指导价:数字万" (数字可能没有小数点)
        m = re.search(r'新车指导价:(\d+)万', after)
        if m:
            official = float(m.group(1))

    # 从 keyword 之前提取二手车价格（最后一个 X.XX万 或 X万）
    used = None
    prices_before = re.findall(r'(\d+\.?\d*)万', before)
    if prices_before:
        used = float(prices_before[-1])

    return used, official


def parse_price_from_ocr_text(text: str, crop_text: str = None):
    """
    从OCR文本中提取二手车价格和新车指导价
    text: 全图OCR文本（用于提取二手价）
    crop_text: 裁剪底部放大后的OCR文本（用于提取新车指导价，可选）
    返回: {"sh_price": float|None, "official_price": float|None, "ocr_text": str}
    """
    if not text:
        return {"sh_price": None, "official_price": None, "ocr_text": ""}

    # 预处理：去空格、统一标点、修复误识别
    text = _normalize_ocr_text(text)
    used_price = None
    new_car_price = None

    # ---- 优先从裁剪放大文本提取新车指导价（识别率更高）----
    if crop_text:
        crop_norm = _normalize_ocr_text(crop_text)
        if "新车指导价" in crop_norm:
            _, new_car_price = _extract_price_near_keyword(crop_norm, "新车指导价")
        # 裁剪文本也可以提取二手价（大字，同样清晰）
        if "新车指导价" in crop_norm:
            crop_used, _ = _extract_price_near_keyword(crop_norm, "新车指导价")
            if crop_used:
                used_price = crop_used

    # ---- 从全图文本提取（补充或覆盖）----
    if "新车指导价" in text:
        full_used, full_official = _extract_price_near_keyword(text, "新车指导价")
        if used_price is None and full_used:
            used_price = full_used
        if new_car_price is None and full_official:
            new_car_price = full_official

    # ---- 备选策略：按行解析（兼容 RapidOCR 多行输出）----
    if used_price is None and new_car_price is None:
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if "新车指导价" in line:
                both = re.search(r'(\d+\.?\d*)万\s*新车指导价[：:]\s*(\d+\.?\d*)万', line)
                if both:
                    used_price = float(both.group(1))
                    new_car_price = float(both.group(2))
                    break
                m = re.search(r'新车指导价[：:]\s*(\d+\.?\d*)万', line)
                if m:
                    new_car_price = float(m.group(1))
                    others = re.findall(r'(\d+\.?\d*)万', line)
                    if len(others) >= 2:
                        used_price = float(others[0])
                break

    # ---- 兜底：从全文找二手价 ----
    if used_price is None:
        # 排除"万公里"中的数字
        cleaned = re.sub(r'\d+\.?\d*万公里', '', text)
        # 排除"新车指导价:X万"
        cleaned = re.sub(r'新车指导价:\d+\.?\d*万', '', cleaned)
        # 排除年份
        cleaned = re.sub(r'\d{4}年', '', cleaned)
        # 排除"过户X次"
        cleaned = re.sub(r'过户\d+次', '', cleaned)
        prices = re.findall(r'(\d+\.?\d*)万', cleaned)
        if prices:
            used_price = float(prices[-1])

    return {
        "sh_price": used_price,
        "official_price": new_car_price,
        "ocr_text": text,
    }


async def screenshot_and_ocr_price(page, ocr_client: BaiduOCR):
    """
    对当前页面的价格区域截图并OCR解析
    page: 已导航到详情页的 Playwright page
    返回: {"sh_price": float|None, "official_price": float|None, "ocr_text": str}
    """
    try:
        # 尝试定位价格区域（懂车帝详情页的价格容器）
        selectors = [
            ".detail-price",
            "[class*='price']",
            ".car-price",
            ".price-info",
        ]

        screenshot_bytes = None
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    screenshot_bytes = await el.screenshot(timeout=5000)
                    break
            except Exception:
                continue

        # 如果找不到价格元素，截取页面上半部分
        if not screenshot_bytes:
            screenshot_bytes = await page.screenshot(
                clip={"x": 0, "y": 0, "width": 800, "height": 400}
            )

        if not screenshot_bytes:
            return {"sh_price": None, "official_price": None, "ocr_text": ""}

        text = ocr_client.recognize_image(screenshot_bytes)
        return parse_price_from_ocr_text(text)

    except Exception as e:
        return {"sh_price": None, "official_price": None, "ocr_text": f"error: {e}"}
