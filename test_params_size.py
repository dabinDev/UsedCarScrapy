import json
from dongchedi_api import DongchediAPI

d = json.load(open("test_params_output.json", "r", encoding="utf-8"))
api = DongchediAPI()
parsed = api._parse_param_groups(d["rawData"])
s = json.dumps(parsed, ensure_ascii=False)
print(f"parsed JSON size: {len(s)} bytes ({len(s)/1024:.1f} KB)")
print(f"groups: {len(parsed)}, total params: {sum(len(g['params']) for g in parsed)}")

# raw_data 太大，不存
rd = json.dumps(d["rawData"], ensure_ascii=False)
print(f"raw_data JSON size: {len(rd)} bytes ({len(rd)/1024:.1f} KB)")
