"""抽样验证OCR解析结果"""
import asyncio
import os
from ocr_price import LocalOCR, parse_price_from_ocr_text

SHOT_DIR = "client_output/screenshots"
samples = ["14042823", "18440257", "19497311", "20262322", "19693086", "20065945",
           "14754344", "18822534", "19731315", "8686589"]

async def main():
    ocr = LocalOCR()
    for sid in samples:
        path = os.path.join(SHOT_DIR, f"{sid}.png")
        if not os.path.exists(path):
            print(f"  {sid}: 文件不存在")
            continue
        text = await ocr.recognize_file_async(path)
        result = parse_price_from_ocr_text(text) if text else {}
        sh = result.get("sh_price")
        off = result.get("official_price")
        print(f"  {sid}: sh={sh}, off={off}")

asyncio.run(main())
