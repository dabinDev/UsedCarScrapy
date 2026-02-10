"""OCR子进程worker：接收图片列表，输出JSON结果"""
import logging
logging.disable(logging.CRITICAL)

import json
import os
import sys
from ocr_price import LocalOCR, parse_price_from_ocr_text


def main():
    input_file = sys.argv[1]   # 输入：每行一个图片路径
    output_file = sys.argv[2]  # 输出：JSON结果
    worker_id = sys.argv[3] if len(sys.argv) > 3 else "?"  # 可选的worker编号

    with open(input_file, "r") as f:
        paths = [line.strip() for line in f if line.strip()]

    total = len(paths)
    print(f"  [W{worker_id}] 启动, 待处理: {total} 张", flush=True)

    import time
    t0 = time.time()
    ocr = LocalOCR()
    print(f"  [W{worker_id}] 引擎就绪 ({time.time()-t0:.1f}s)", flush=True)

    results = []
    ok = 0

    for i, path in enumerate(paths, 1):
        fname = os.path.basename(path)
        sku_id = fname.replace(".png", "")
        text = ocr.recognize_file(path)
        result = parse_price_from_ocr_text(text) if text else None
        sh = result.get("sh_price") if result else None
        off = result.get("official_price") if result else None
        results.append({"sku_id": sku_id, "sh_price": sh, "official_price": off})
        if sh or off:
            ok += 1

        if i % 10 == 0 or i == total:
            elapsed = time.time() - t0
            speed = i / elapsed if elapsed > 0 else 0
            print(f"  [W{worker_id}] {i}/{total} (成功{ok}, {speed:.1f}张/秒)", flush=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

    elapsed = time.time() - t0
    print(f"  [W{worker_id}] 完成! {total}张, 成功{ok}, 耗时{elapsed:.0f}s", flush=True)


if __name__ == "__main__":
    main()
