"""
数据库表结构迁移脚本
更新已有表以匹配最新 schema.sql
"""
import asyncio
from db_manager import DBManager

ALTER_STATEMENTS = [
    # car_config: 移除 detail_params_raw, power 改为 TEXT, 更新注释
    "ALTER TABLE `car_config` DROP COLUMN IF EXISTS `detail_params_raw`",
    "ALTER TABLE `car_config` MODIFY COLUMN `power` TEXT DEFAULT NULL COMMENT '动力概览（JSON，来自 car_config_overview.power）'",
    "ALTER TABLE `car_config` MODIFY COLUMN `transmission` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '变速箱概览'",
    "ALTER TABLE `car_config` MODIFY COLUMN `drive_type` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '驱动方式概览'",
    "ALTER TABLE `car_config` MODIFY COLUMN `dimensions` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '尺寸概览'",
    "ALTER TABLE `car_config` MODIFY COLUMN `detail_params` JSON DEFAULT NULL COMMENT '完整参数配置（7组~257项）'",

    # shop: 增加新字段
    "ALTER TABLE `shop` ADD COLUMN IF NOT EXISTS `shop_short_name` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '商家简称' AFTER `shop_name`",
    "ALTER TABLE `shop` ADD COLUMN IF NOT EXISTS `business_time` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '营业时间' AFTER `address`",
    "ALTER TABLE `shop` ADD COLUMN IF NOT EXISTS `sales_range` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '销售范围' AFTER `business_time`",
    "ALTER TABLE `shop` ADD COLUMN IF NOT EXISTS `sales_car_num` INT NOT NULL DEFAULT 0 COMMENT '在售车辆数' AFTER `sales_range`",

    # car_highlight: 增加 updated_at
    "ALTER TABLE `car_highlight` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`",

    # car_report: 增加 updated_at
    "ALTER TABLE `car_report` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`",

    # car_financial: 增加 updated_at
    "ALTER TABLE `car_financial` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`",
]


async def main():
    db = DBManager()
    await db.connect()

    print("📋 开始迁移数据库表结构...")
    success = 0
    fail = 0
    for sql in ALTER_STATEMENTS:
        try:
            await db._execute(sql)
            success += 1
            desc = sql[:80].replace("\n", " ")
            print(f"  ✅ {desc}...")
        except Exception as e:
            fail += 1
            desc = sql[:60].replace("\n", " ")
            print(f"  ⚠️ {desc}... -> {e}")

    await db.close()
    print(f"\n✅ 迁移完成: 成功={success}, 失败={fail}")


if __name__ == "__main__":
    asyncio.run(main())
