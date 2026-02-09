"""
修复损坏的JSON文件：从details.json重建configs.json和images.json
"""
import json
import os
from datetime import datetime

OUTPUT_DIR = "client_output"


def read_safe(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ⚠️ {path} 损坏: {e}")
        return None


def write_json(path, data_list):
    payload = {
        "metadata": {
            "total": len(data_list),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        "data": data_list,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {path}: {len(data_list)} 条")


def main():
    details_path = os.path.join(OUTPUT_DIR, "details.json")
    details_data = read_safe(details_path)

    if not details_data or not details_data.get("data"):
        print("❌ details.json 无数据，无法修复")
        return

    details = details_data["data"]
    print(f"📋 details.json: {len(details)} 条")

    # 检查每个文件
    for name in ["details", "images", "configs"]:
        path = os.path.join(OUTPUT_DIR, f"{name}.json")
        result = read_safe(path)
        if result and result.get("data"):
            print(f"  ✅ {name}.json: 正常 ({len(result['data'])} 条)")
        else:
            print(f"  ❌ {name}.json: 需要重建")

    # 重建 images.json
    images_list = []
    for d in details:
        sku_id = d.get("sku_id")
        if sku_id:
            images_list.append({"sku_id": sku_id, "images": d.get("images", [])})
    write_json(os.path.join(OUTPUT_DIR, "images.json"), images_list)

    # 重建 configs.json
    configs_list = []
    for d in details:
        sku_id = d.get("sku_id")
        if sku_id:
            configs_list.append({
                "sku_id": sku_id,
                "config": d.get("config"),
                "detail_params": d.get("detail_params"),
                "detail_params_raw": d.get("detail_params_raw"),
            })
    write_json(os.path.join(OUTPUT_DIR, "configs.json"), configs_list)

    print("\n✅ 修复完成!")


if __name__ == "__main__":
    main()
