-- 懂车帝二手车数据库建表脚本
-- MySQL 8.0+

-- 使用已有数据库
USE `used-car`;

-- 品牌表
CREATE TABLE IF NOT EXISTS `brand` (
    `brand_id`   INT          NOT NULL COMMENT '品牌ID（懂车帝原始ID）',
    `brand_name` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '品牌名称',
    `brand_logo` VARCHAR(500) NOT NULL DEFAULT '' COMMENT '品牌Logo URL',
    `pinyin`     VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '拼音首字母',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`brand_id`)
) ENGINE=InnoDB COMMENT='品牌表';

-- 车系表
CREATE TABLE IF NOT EXISTS `series` (
    `series_id`   INT          NOT NULL COMMENT '车系ID',
    `brand_id`    INT          NOT NULL COMMENT '所属品牌ID',
    `series_name` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '车系名称',
    `image_url`   VARCHAR(500) NOT NULL DEFAULT '' COMMENT '车系图片',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`series_id`),
    KEY `idx_brand_id` (`brand_id`)
) ENGINE=InnoDB COMMENT='车系表';

-- 车辆概览表（列表页数据）
CREATE TABLE IF NOT EXISTS `car_overview` (
    `sku_id`                INT          NOT NULL COMMENT '车辆SKU ID',
    `spu_id`                INT          DEFAULT NULL COMMENT 'SPU ID',
    `brand_id`              INT          NOT NULL COMMENT '品牌ID',
    `series_id`             INT          DEFAULT NULL COMMENT '车系ID',
    `car_id`                INT          DEFAULT NULL COMMENT '车型ID',
    `title`                 VARCHAR(200) NOT NULL DEFAULT '' COMMENT '标题',
    `car_name`              VARCHAR(100) NOT NULL DEFAULT '' COMMENT '车型名',
    `car_year`              INT          DEFAULT NULL COMMENT '年款',
    `image`                 VARCHAR(500) NOT NULL DEFAULT '' COMMENT '列表缩略图',
    `car_source_city`       VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '车源城市',
    `transfer_cnt`          INT          NOT NULL DEFAULT 0 COMMENT '过户次数',
    `shop_id`               VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '商家ID',
    `car_source_type`       VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '车源类型',
    `authentication_method` VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '认证方式',
    `tags`                  JSON         DEFAULT NULL COMMENT '标签',
    `detail_url`            VARCHAR(500) NOT NULL DEFAULT '' COMMENT '详情页URL',
    `collected_at`          DATETIME     DEFAULT NULL COMMENT '采集时间',
    `created_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`),
    KEY `idx_brand_id` (`brand_id`),
    KEY `idx_series_id` (`series_id`),
    KEY `idx_car_id` (`car_id`)
) ENGINE=InnoDB COMMENT='车辆概览表';

-- 车辆详情表
CREATE TABLE IF NOT EXISTS `car_detail` (
    `sku_id`               INT            NOT NULL COMMENT '车辆SKU ID',
    `spu_id`               INT            DEFAULT NULL,
    `title`                VARCHAR(200)   NOT NULL DEFAULT '',
    `important_text`       VARCHAR(500)   NOT NULL DEFAULT '' COMMENT '摘要',
    `sh_price`             DECIMAL(10,2)  DEFAULT NULL COMMENT '二手价（万元）',
    `official_price`       DECIMAL(10,2)  DEFAULT NULL COMMENT '指导价（万元）',
    `include_tax_price`    DECIMAL(10,2)  DEFAULT NULL COMMENT '含税价（万元）',
    `source_sh_price`      BIGINT         DEFAULT NULL COMMENT '原始二手价（分）',
    `source_official_price` BIGINT        DEFAULT NULL COMMENT '原始指导价（分）',
    `brand_id`             INT            DEFAULT NULL,
    `brand_name`           VARCHAR(100)   NOT NULL DEFAULT '',
    `series_id`            INT            DEFAULT NULL,
    `series_name`          VARCHAR(100)   NOT NULL DEFAULT '',
    `car_id`               INT            DEFAULT NULL,
    `car_name`             VARCHAR(100)   NOT NULL DEFAULT '',
    `year`                 INT            DEFAULT NULL COMMENT '年款',
    `body_color`           VARCHAR(50)    NOT NULL DEFAULT '' COMMENT '车身颜色',
    `description`          TEXT           COMMENT '车辆描述',
    `detail_url`           VARCHAR(500)   NOT NULL DEFAULT '',
    `detail_params_url`    VARCHAR(500)   NOT NULL DEFAULT '',
    `collected_at`         DATETIME       DEFAULT NULL,
    `created_at`           DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`           DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`),
    KEY `idx_brand_id` (`brand_id`),
    KEY `idx_series_id` (`series_id`)
) ENGINE=InnoDB COMMENT='车辆详情表';

-- 车辆参数表（二手车详情页 other_params 简要参数）
CREATE TABLE IF NOT EXISTS `car_params` (
    `sku_id`         INT         NOT NULL,
    `register_city`  VARCHAR(50) NOT NULL DEFAULT '' COMMENT '上牌地',
    `source_city`    VARCHAR(50) NOT NULL DEFAULT '' COMMENT '车源地',
    `transfer_cnt`   VARCHAR(20) NOT NULL DEFAULT '' COMMENT '过户次数',
    `register_date`  VARCHAR(30) NOT NULL DEFAULT '' COMMENT '上牌时间',
    `displacement`   VARCHAR(30) NOT NULL DEFAULT '' COMMENT '排量',
    `transmission`   VARCHAR(30) NOT NULL DEFAULT '' COMMENT '变速箱',
    `maintenance`    VARCHAR(50) NOT NULL DEFAULT '' COMMENT '保养方式',
    `body_color`     VARCHAR(50) NOT NULL DEFAULT '' COMMENT '车身颜色',
    `interior_color` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '内饰颜色',
    `created_at`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='车辆参数表（二手车页简要参数：上牌地/排量/变速箱等）';

-- 车辆配置表（参数配置页 /auto/params-carIds-{car_id} 完整数据）
CREATE TABLE IF NOT EXISTS `car_config` (
    `sku_id`            INT          NOT NULL,
    `power`             TEXT         DEFAULT NULL COMMENT '动力概览（JSON，来自 car_config_overview.power）',
    `transmission`      VARCHAR(200) NOT NULL DEFAULT '' COMMENT '变速箱概览',
    `drive_type`        VARCHAR(200) NOT NULL DEFAULT '' COMMENT '驱动方式概览',
    `dimensions`        VARCHAR(200) NOT NULL DEFAULT '' COMMENT '尺寸概览',
    `detail_params`     JSON         DEFAULT NULL COMMENT '完整参数配置（7组~257项，结构: [{group,group_key,params:[{key,name,value,icon_type}]}]）',
    `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='车辆配置表（含基本信息/车身/发动机/变速箱/底盘/安全/灯光等完整参数）';

-- 车辆图片表
CREATE TABLE IF NOT EXISTS `car_image` (
    `id`            INT AUTO_INCREMENT NOT NULL,
    `sku_id`        INT          NOT NULL,
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
    `shop_id`        VARCHAR(50)  NOT NULL,
    `shop_name`      VARCHAR(200) NOT NULL DEFAULT '' COMMENT '商家全称',
    `shop_short_name` VARCHAR(200) NOT NULL DEFAULT '' COMMENT '商家简称',
    `city`           VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '城市',
    `address`        VARCHAR(500) NOT NULL DEFAULT '' COMMENT '地址',
    `business_time`  VARCHAR(100) NOT NULL DEFAULT '' COMMENT '营业时间',
    `sales_range`    VARCHAR(100) NOT NULL DEFAULT '' COMMENT '销售范围',
    `sales_car_num`  INT          NOT NULL DEFAULT 0 COMMENT '在售车辆数',
    `created_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`shop_id`)
) ENGINE=InnoDB COMMENT='商家表';

-- 车辆亮点标签表
CREATE TABLE IF NOT EXISTS `car_highlight` (
    `sku_id`     INT      NOT NULL,
    `highlights` JSON     DEFAULT NULL COMMENT '亮点配置列表 [{name,icon}]',
    `tags`       JSON     DEFAULT NULL COMMENT '标签列表 ["懂车帝认证｜3星"]',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='车辆亮点标签表';

-- 检测报告表
CREATE TABLE IF NOT EXISTS `car_report` (
    `sku_id`      INT      NOT NULL,
    `has_report`  TINYINT  NOT NULL DEFAULT 0 COMMENT '是否有检测报告',
    `report_data` JSON     DEFAULT NULL COMMENT '报告详情 {has_report,eva_level,overview}',
    `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='检测报告表';

-- 金融方案表
CREATE TABLE IF NOT EXISTS `car_financial` (
    `sku_id`         INT      NOT NULL,
    `financial_data` JSON     DEFAULT NULL COMMENT '金融方案 {down_payment,month_pay,repayment_cycle}',
    `created_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`sku_id`)
) ENGINE=InnoDB COMMENT='金融方案表';
