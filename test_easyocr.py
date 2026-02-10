"""测试 EasyOCR 速度和准确率"""
import os
import time

SHOT_DIR = "client_output/screenshots"
samples = ["11247193", "11336054", "12806965", "13693499", "13974050",
           "20676004", "20778969", "22506182"]

print("⏳ 初始化 EasyOCR...")
t0 = time.time()
import easyocr
reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
print(f"✅ 初始化耗时: {time.time()-t0:.1f}s\n")

for s in samples:
    path = os.path.join(SHOT_DIR, f"{s}.png")
    t1 = time.time()
    results = reader.readtext(path, detail=0)
    elapsed = time.time() - t1
    text = " ".join(results)
    print(f"--- {s} ({elapsed:.2f}s) ---")
    print(f"  {text[:150]}")
    print()

# 批量测试前20张速度
files = sorted([f for f in os.listdir(SHOT_DIR) if f.endswith(".png")])[:20]
t0 = time.time()
for f in files:
    reader.readtext(os.path.join(SHOT_DIR, f), detail=0)
elapsed = time.time() - t0
print(f"批量: {len(files)}张, {elapsed:.1f}s, {elapsed/len(files):.2f}s/张, {len(files)/elapsed:.1f}张/秒")
