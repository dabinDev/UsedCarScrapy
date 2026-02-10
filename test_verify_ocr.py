"""抽样验证OCR解析结果：对比图片真实值"""
import asyncio
import os
import random
from ocr_price import LocalOCR, parse_price_from_ocr_text

SHOT_DIR = "client_output/screenshots"

async def main():
    files = sorted([f for f in os.listdir(SHOT_DIR) if f.endswith(".png")])
    # 随机抽20张 + 之前已知的样本
    random.seed(42)
    known = ["11247193", "11336054", "12806965", "13693499", "13974050",
             "20676004", "20778969", "22506182"]
    sample_ids = set(known)
    random_picks = random.sample(files, min(12, len(files)))
    for f in random_picks:
        sample_ids.add(f.replace(".png", ""))
    
    ocr = LocalOCR()
    print(f"抽样验证 {len(sample_ids)} 张图片\n")
    
    results = []
    for sid in sorted(sample_ids):
        path = os.path.join(SHOT_DIR, f"{sid}.png")
        if not os.path.exists(path):
            continue
        full_text, crop_text = await ocr.recognize_file_twpass_async(path)
        result = parse_price_from_ocr_text(full_text, crop_text) if full_text else {}
        sh = result.get("sh_price")
        off = result.get("official_price")
        results.append((sid, sh, off, full_text[:100] if full_text else ""))
        print(f"  {sid}: sh={sh}, off={off}")
    
    # 输出汇总表格供人工对比
    print(f"\n{'='*60}")
    print(f"{'SKU_ID':<15} {'二手价(sh)':<12} {'新车指导价(off)':<15}")
    print(f"{'-'*60}")
    for sid, sh, off, _ in results:
        print(f"{sid:<15} {str(sh):<12} {str(off):<15}")
    
    print(f"\n请对照截图图片验证以上价格是否正确。")
    print(f"截图目录: {os.path.abspath(SHOT_DIR)}")

asyncio.run(main())
