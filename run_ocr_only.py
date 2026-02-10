"""本地OCR全量测试（WinOCR 异步）"""
import asyncio
import os
import time
from ocr_price import LocalOCR, parse_price_from_ocr_text

SHOT_DIR = "client_output/screenshots"


async def main():
    files = sorted([f for f in os.listdir(SHOT_DIR) if f.endswith(".png")])
    print(f"截图: {len(files)} 张")

    ocr = LocalOCR()
    print("引擎: EasyOCR")

    success = 0
    fail_list = []
    t0 = time.time()

    for i, f in enumerate(files, 1):
        path = os.path.join(SHOT_DIR, f)
        full_text, crop_text = await ocr.recognize_file_twpass_async(path)
        result = parse_price_from_ocr_text(full_text, crop_text) if full_text else None
        sh = result.get("sh_price") if result else None
        off = result.get("official_price") if result else None

        if sh or off:
            success += 1
        else:
            fail_list.append(f)

        if i <= 5 or i % 100 == 0 or i == len(files):
            elapsed = time.time() - t0
            speed = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(files)}] {f}: sh={sh}, off={off}  ({speed:.1f}张/秒)")

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"总计: {len(files)} 张")
    print(f"成功: {success} ({success*100//max(len(files),1)}%)")
    print(f"失败: {len(fail_list)}")
    print(f"耗时: {elapsed:.1f}秒 ({elapsed/max(len(files),1):.2f}秒/张, {len(files)/max(elapsed,0.1):.1f}张/秒)")
    if fail_list[:10]:
        print(f"失败样本: {fail_list[:10]}")


if __name__ == "__main__":
    asyncio.run(main())
