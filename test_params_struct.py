"""分析参数页面数据结构"""
import json

d = json.load(open("test_params_output.json", "r", encoding="utf-8"))
props = d["rawData"]["properties"]

print(f"Total properties: {len(props)}")

# type=0 是分类标题, type=1 是具体参数
current_group = ""
for i, p in enumerate(props[:50]):
    ptype = p.get("type", -1)
    text = p.get("text", "")
    key = p.get("key", "")
    sub_list = p.get("sub_list") or []

    if ptype == 0:
        current_group = text
        print(f"\n=== [{i}] {text} (key={key}) ===")
    else:
        # 获取值
        values = []
        for sl in sub_list:
            if isinstance(sl, dict):
                v = sl.get("value", "")
                if v:
                    values.append(str(v)[:60])
        val_str = ", ".join(values) if values else "(empty)"
        print(f"  [{i}] {text} (key={key}) = {val_str}")

print("\n\n--- type distribution ---")
from collections import Counter
types = Counter(p.get("type", -1) for p in props)
print(types)
