"""测试裁剪价格行后 EasyOCR 的识别效果和速度"""
import asyncio
import os
import time
from PIL import Image
from ocr_price import LocalOCR, parse_price_from_ocr_text

SHOT_DIR = "client_output/screenshots"
samples = ["11247193", "11336054", "12806965", "13693499", "13974050",
           "20676004", "20778969", "22506182", "14042823", "18440257"]

async def main():
    ocr = LocalOCR()

    print("=== 对比：完整图 vs 裁剪价格行 ===\n")
    for sid in samples:
        path = os.path.join(SHOT_DIR, f"{sid}.png")
        img = Image.open(path)
        w, h = img.size

        # 裁剪底部价格行（约底部15%，模拟只截 dd 元素）
        crop = img.crop((0, int(h * 0.82), w, h))
        crop_path = os.path.join(SHOT_DIR, f"_crop_{sid}.png")
        crop.save(crop_path)

        # OCR 裁剪图
        t1 = time.time()
        crop_text = await ocr.recognize_file_async(crop_path)
        crop_time = time.time() - t1
        crop_result = parse_price_from_ocr_text(crop_text) if crop_text else {}

        # OCR 完整图
        t2 = time.time()
        full_text = await ocr.recognize_file_async(path)
        full_time = time.time() - t2
        full_result = parse_price_from_ocr_text(full_text) if full_text else {}

        # 清理临时文件
        os.remove(crop_path)

        crop_sh = crop_result.get("sh_price")
        crop_off = crop_result.get("official_price")
        full_sh = full_result.get("sh_price")
        full_off = full_result.get("official_price")

        match = "✅" if (crop_sh == full_sh and crop_off == full_off) else "❌"
        print(f"{sid}: {match}")
        print(f"  完整图 ({full_time:.2f}s): sh={full_sh}, off={full_off}")
        print(f"  裁剪图 ({crop_time:.2f}s): sh={crop_sh}, off={crop_off}")
        if crop_text:
            print(f"  裁剪OCR: {crop_text[:80]}")
        print()

asyncio.run(main())
