-- ================================================================
-- 二手车数据库建表脚本（兼容懂车帝 + 瓜子）
-- MySQL 8.0+
-- 设计原则：
--   1. sku_id 统一 VARCHAR(50)：懂车帝=纯数字, 瓜子=c+数字，天然不冲突
--   2. brand_id / series_id 统一 VARCHAR(50)：懂车帝=数字ID, 瓜子=slug
--   3. car_overview / car_detail 加 source 字段区分来源
--   4. 所有子表通过 sku_id 关联，无需 source 字段
-- ================================================================

USE `used-car`;

-- 品牌表（懂车帝=数字ID, 瓜子=slug 如 "bmw"）
CREATE TABLE IF NOT EXISTS `brand` (
    `brand_id`   VARCHAR(50)  NOT NULL COMMENT '品牌ID（懂车帝=数字, 瓜子=slug）',
    `brand_name` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '品牌名称',
    `brand_logo` VARCHAR(500) NOT NULL DEFAULT '' COMMENT '品牌Logo URL',
    `pinyin`     VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '拼音首字母/slug',
    `source`     VARCHAR(20)  NOT NULL DEFAULT 'dongchedi' COMMENT '数据来源: dongchedi / guazi',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`brand_id`),
    KEY `idx_source` (`source`)
) ENGINE=InnoDB COMMENT='品牌表（懂车帝+瓜子共用）';

-- 车系表（懂车帝=数字ID, 瓜子=slug 如 "bmw-3xi"）
CREATE TABLE IF NOT EXISTS `series` (
    `series_id`   VARCHAR(50)  NOT NULL COMMENT '车系ID（懂车帝=数字, 瓜子=slug）',
    `brand_id`    VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '所属品牌ID',
    `series_name` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '车系名称',
    `image_url`   VARCHAR(500) NOT NULL DEFAULT '' COMMENT '车系图片',
    `source`      VARCHAR(20)  NOT NULL DEFAULT 'dongchedi' COMMENT '数据来源',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`series_id`),
    KEY `idx_brand_id` (`brand_id`),
    KEY `idx_source` (`source`)
) ENGINE=InnoDB COMMENT='车系表（懂车帝+瓜子共用）';

-- 车辆概览表（列表页数据）
CREATE TABLE IF NOT EXISTS `car_overview` (
    `sku_id`                VARCHAR(50)  NOT NULL COMMENT '车辆ID（懂车帝=纯数字, 瓜子=c+数字）',
    `spu_id`                VARCHAR(50)  DEFAULT NULL COMMENT 'SPU ID',
    `brand_id`              VARCHAR(50)  DEFAULT NULL COMMENT '品牌ID',
    `series_id`             VARCHAR(50)  DEFAULT NULL COMMENT '车系ID',
    `car_id`                VARCHAR(50)  DEFAULT NULL COMMENT '车型ID',
    `title`                 VARCHAR(200) NOT NULL DEFAULT '' COMMENT '标题',
    `car_name`              VARCHAR(100) NOT NULL DEFAULT '' COMMENT '车型名',
    `car_year`              VARCHAR(20)  DEFAULT NULL COMMENT '年款',
    `image`                 VARCHAR(500) NOT NULL DEFAULT '' COMMENT '列表缩略图',
    `sh_price`              DECIMAL(10,2) DEFAULT NULL COMMENT '二手价（万元，列表页可见）',
    `car_source_city`       VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '车源城市',
    `transfer_cnt`          INT          NOT NULL DEFAULT 0 COMMENT '过户次数',
    `mileage`               VARCHAR(30)  NOT NULL DEFAULT '' COMMENT '里程（如 3.2万公里）',
    `shop_id`               VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '商家ID',
    `car_source_type`       VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '车源类型',
    `authentication_method` VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '认证方式',
    `tags`                  JSON         DEFAULT NULL COMMENT '标签',
    `detail_url`            VARCHAR(500) NOT NULL DEFAULT '' COMMENT '详情页URL',
    `source`                VARCHAR(20)  NOT NULL DEFAULT 'dongchedi' COMMENT '数据来源: dongchedi / guazi',
    `collected_at`          DATETIME     DEFAULT NULL COMMENT '采集时间',
    `created_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`),
    KEY `idx_brand_id` (`brand_id`),
    KEY `idx_series_id` (`series_id`),
    KEY `idx_source` (`source`),
    KEY `idx_sh_price` (`sh_price`)
) ENGINE=InnoDB COMMENT='车辆概览表（懂车帝+瓜子共用）';

-- 车辆详情表
CREATE TABLE IF NOT EXISTS `car_detail` (
    `sku_id`               VARCHAR(50)    NOT NULL COMMENT '车辆ID',
    `spu_id`               VARCHAR(50)    DEFAULT NULL,
    `title`                VARCHAR(200)   NOT NULL DEFAULT '',
    `important_text`       VARCHAR(500)   NOT NULL DEFAULT '' COMMENT '摘要/副标题',
    `sh_price`             DECIMAL(10,2)  DEFAULT NULL COMMENT '二手价（万元）',
    `official_price`       DECIMAL(10,2)  DEFAULT NULL COMMENT '新车指导价（万元）',
    `include_tax_price`    DECIMAL(10,2)  DEFAULT NULL COMMENT '含税价（万元，仅懂车帝）',
    `source_sh_price`      BIGINT         DEFAULT NULL COMMENT '原始二手价（分，仅懂车帝加密字段）',
    `source_official_price` BIGINT        DEFAULT NULL COMMENT '原始指导价（分，仅懂车帝加密字段）',
    `brand_id`             VARCHAR(50)    DEFAULT NULL,
    `brand_name`           VARCHAR(100)   NOT NULL DEFAULT '',
    `series_id`            VARCHAR(50)    DEFAULT NULL,
    `series_name`          VARCHAR(100)   NOT NULL DEFAULT '',
    `car_id`               VARCHAR(50)    DEFAULT NULL,
    `car_name`             VARCHAR(100)   NOT NULL DEFAULT '',
    `year`                 VARCHAR(20)    DEFAULT NULL COMMENT '年款',
    `body_color`           VARCHAR(50)    NOT NULL DEFAULT '' COMMENT '车身颜色',
    `description`          TEXT           COMMENT '车辆描述/卖家说',
    `detail_url`           VARCHAR(500)   NOT NULL DEFAULT '',
    `detail_params_url`    VARCHAR(500)   NOT NULL DEFAULT '' COMMENT '参数配置页URL（仅懂车帝）',
    `price_source`         VARCHAR(20)    NOT NULL DEFAULT '' COMMENT '价格来源: api / ocr',
    `source`               VARCHAR(20)    NOT NULL DEFAULT 'dongchedi' COMMENT '数据来源: dongchedi / guazi',
    `collected_at`         DATETIME       DEFAULT NULL,
    `created_at`           DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`           DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`),
    KEY `idx_brand_id` (`brand_id`),
    KEY `idx_series_id` (`series_id`),
    KEY `idx_source` (`source`),
    KEY `idx_sh_price` (`sh_price`)
) ENGINE=InnoDB COMMENT='车辆详情表（懂车帝+瓜子共用）';

-- 车辆参数表（简要参数：上牌地/排量/变速箱等）
CREATE TABLE IF NOT EXISTS `car_params` (
    `sku_id`         VARCHAR(50) NOT NULL,
    `register_city`  VARCHAR(50) NOT NULL DEFAULT '' COMMENT '上牌地',
    `source_city`    VARCHAR(50) NOT NULL DEFAULT '' COMMENT '车源地',
    `transfer_cnt`   VARCHAR(20) NOT NULL DEFAULT '' COMMENT '过户次数',
    `register_date`  VARCHAR(30) NOT NULL DEFAULT '' COMMENT '上牌时间',
    `displacement`   VARCHAR(50) NOT NULL DEFAULT '' COMMENT '排量/发动机',
    `transmission`   VARCHAR(50) NOT NULL DEFAULT '' COMMENT '变速箱',
    `emission`       VARCHAR(30) NOT NULL DEFAULT '' COMMENT '排放标准（瓜子）',
    `drive_mode`     VARCHAR(30) NOT NULL DEFAULT '' COMMENT '驱动方式（瓜子）',
    `mileage`        VARCHAR(30) NOT NULL DEFAULT '' COMMENT '里程/车龄（瓜子）',
    `maintenance`    VARCHAR(50) NOT NULL DEFAULT '' COMMENT '保养方式/基础车况',
    `body_color`     VARCHAR(50) NOT NULL DEFAULT '' COMMENT '车身颜色',
    `interior_color` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '内饰颜色',
    `created_at`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='车辆参数表';

-- 车辆配置表
CREATE TABLE IF NOT EXISTS `car_config` (
    `sku_id`            VARCHAR(50)  NOT NULL,
    `power`             TEXT         DEFAULT NULL COMMENT '动力概览',
    `transmission`      VARCHAR(200) NOT NULL DEFAULT '' COMMENT '变速箱概览',
    `drive_type`        VARCHAR(200) NOT NULL DEFAULT '' COMMENT '驱动方式概览',
    `dimensions`        VARCHAR(200) NOT NULL DEFAULT '' COMMENT '尺寸概览',
    `detail_params`     JSON         DEFAULT NULL COMMENT '完整参数配置',
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='车辆配置表';

-- 车辆图片表
CREATE TABLE IF NOT EXISTS `car_image` (
    `id`            INT AUTO_INCREMENT NOT NULL,
    `sku_id`        VARCHAR(50)  NOT NULL,
    `image_url`     VARCHAR(500) NOT NULL DEFAULT '',
    `sort_order`    INT          NOT NULL DEFAULT 0 COMMENT '排序',
    `is_downloaded` TINYINT      NOT NULL DEFAULT 0 COMMENT '是否已下载',
    `local_path`    VARCHAR(500) NOT NULL DEFAULT '' COMMENT '本地路径',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_sku_id` (`sku_id`)
) ENGINE=InnoDB COMMENT='车辆图片表';

-- 商家表
CREATE TABLE IF NOT EXISTS `shop` (
    `shop_id`         VARCHAR(50)  NOT NULL,
    `shop_name`       VARCHAR(200) NOT NULL DEFAULT '' COMMENT '商家全称',
    `shop_short_name` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '商家简称',
    `city`            VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '城市',
    `address`         VARCHAR(500) NOT NULL DEFAULT '' COMMENT '地址',
    `business_time`   VARCHAR(100) NOT NULL DEFAULT '' COMMENT '营业时间',
    `sales_range`     VARCHAR(100) NOT NULL DEFAULT '' COMMENT '销售范围',
    `sales_car_num`   INT          NOT NULL DEFAULT 0 COMMENT '在售车辆数',
    `source`          VARCHAR(20)  NOT NULL DEFAULT 'dongchedi' COMMENT '数据来源',
    `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`shop_id`)
) ENGINE=InnoDB COMMENT='商家表（懂车帝+瓜子共用）';

-- 车辆亮点标签表
CREATE TABLE IF NOT EXISTS `car_highlight` (
    `sku_id`     VARCHAR(50) NOT NULL,
    `highlights` JSON     DEFAULT NULL COMMENT '亮点配置列表 [{name,icon}]',
    `tags`       JSON     DEFAULT NULL COMMENT '标签列表',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='车辆亮点标签表';

-- 检测报告表
CREATE TABLE IF NOT EXISTS `car_report` (
    `sku_id`      VARCHAR(50) NOT NULL,
    `has_report`  TINYINT  NOT NULL DEFAULT 0 COMMENT '是否有检测报告',
    `report_data` JSON     DEFAULT NULL COMMENT '报告详情',
    `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='检测报告表';

-- 金融方案表
CREATE TABLE IF NOT EXISTS `car_financial` (
    `sku_id`         VARCHAR(50) NOT NULL,
    `financial_data` JSON     DEFAULT NULL COMMENT '金融方案',
    `created_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='金融方案表';
