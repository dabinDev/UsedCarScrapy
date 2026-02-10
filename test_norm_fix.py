from ocr_price import _normalize_ocr_text, parse_price_from_ocr_text

# 测试 "新车指导," 修复
t = '1.08万 新车指导,: 8.18万'
norm = _normalize_ocr_text(t)
print(f"原文: {t}")
print(f"修复: {norm}")
r = parse_price_from_ocr_text(t)
print(f"解析: sh={r['sh_price']}, off={r['official_price']}")
print()

# 测试 "新车抬导价" 修复
t2 = '4.20万 新车抬导价:7.88万'
norm2 = _normalize_ocr_text(t2)
print(f"原文: {t2}")
print(f"修复: {norm2}")
r2 = parse_price_from_ocr_text(t2)
print(f"解析: sh={r2['sh_price']}, off={r2['official_price']}")
