#!/usr/bin/env python3
"""
瓜子二手车本地配置 - 城市代码表 + 缓存管理
本地有缓存则直接读取，无需每次重新获取
"""

import json
import os
from typing import Dict, List, Optional

# 配置文件路径
GUAZI_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "guazi_config_cache.json")

# ================================================================
# 全国城市代码表（从瓜子官网提取，共 300+ 城市）
# 格式：{city_code: city_name}
# ================================================================

CITY_MAP: Dict[str, str] = {
    # A
    "anshan": "鞍山", "anyang": "安阳", "anqing": "安庆", "anshun": "安顺",
    "aba": "阿坝", "ankang": "安康",
    # B
    "bj": "北京", "baoding": "保定", "baotou": "包头", "binzhou": "滨州",
    "bengbu": "蚌埠", "beihai": "北海", "baise": "百色", "benxi": "本溪",
    "baoji": "宝鸡", "bayanchuoer": "巴彦淖尔", "bijie": "毕节", "bozhou": "亳州",
    "baicheng": "白城", "baiyin": "白银", "baoshan": "保山", "baishan": "白山",
    "bazhong": "巴中",
    # C
    "cd": "成都", "cq": "重庆", "cc": "长春", "cs": "长沙",
    "cangzhou": "沧州", "changzhou": "常州", "changzhi": "长治", "chifeng": "赤峰",
    "chuzhou": "滁州", "chengde": "承德", "changde": "常德", "chongzuo": "崇左",
    "chenzhou": "郴州", "chaozhou": "潮州", "chuxiong": "楚雄", "chizhou": "池州",
    "chaoyang": "朝阳",
    # D
    "dg": "东莞", "dl": "大连", "dongying": "东营", "dezhou": "德州",
    "daqing": "大庆", "datong": "大同", "deyang": "德阳", "dandong": "丹东",
    "dazhou": "达州", "dali": "大理", "dehong": "德宏", "dingxi": "定西",
    "daxinganling": "大兴安岭", "diqing": "迪庆",
    # E
    "eerduosi": "鄂尔多斯", "ezhou": "鄂州", "enshi": "恩施",
    # F
    "foshan": "佛山", "fz": "福州", "fushun": "抚顺", "fuyang": "阜阳",
    "fuxin": "阜新", "fangchenggang": "防城港", "fuzhou": "抚州",
    # G
    "gz": "广州", "gy": "贵阳", "ganzhou": "赣州", "guilin": "桂林",
    "guigang": "贵港", "guangan": "广安", "guangyuan": "广元", "guyuanshi": "固原",
    # H
    "hz": "杭州", "hrb": "哈尔滨", "hf": "合肥", "nmg": "呼和浩特",
    "huizhou": "惠州", "handan": "邯郸", "heze": "菏泽", "huaian": "淮安",
    "hengshui": "衡水", "huzhou": "湖州", "huanggang": "黄冈", "hechi": "河池",
    "huainan": "淮南", "huludao": "葫芦岛", "hengyang": "衡阳",
    "hulunbeier": "呼伦贝尔", "huaibei": "淮北", "huangshi": "黄石",
    "huaihua": "怀化", "heyuan": "河源", "hhe": "红河", "hezhou": "贺州",
    "haikou": "海口", "hebi": "鹤壁", "heihe": "黑河", "hanzhong": "汉中",
    "huangshan": "黄山", "hegang": "鹤岗", "haidong": "海东", "hami": "哈密",
    # J
    "jn": "济南", "jinhua": "金华", "jining": "济宁", "jiaxing": "嘉兴",
    "jiangmen": "江门", "jilin": "吉林", "jieyang": "揭阳", "jiamusi": "佳木斯",
    "jinzhong": "晋中", "jinzhou": "锦州", "jiaozuo": "焦作", "jingzhou": "荆州",
    "jiujiang": "九江", "jingdezhen": "景德镇", "jian": "吉安", "jixi": "鸡西",
    "jingmen": "荆门", "jincheng": "晋城", "jiuquan": "酒泉",
    "jiayuguan": "嘉峪关", "jinchang": "金昌", "jiyuanshi": "济源",
    # K
    "km": "昆明", "kaifeng": "开封", "kashi": "喀什", "kekedala": "可克达拉市",
    # L
    "linyi": "临沂", "langfang": "廊坊", "luoyang": "洛阳", "lz": "兰州",
    "liuzhou": "柳州", "lianyungang": "连云港", "linfen": "临汾", "luan": "六安",
    "liaocheng": "聊城", "luzhou": "泸州", "leshan": "乐山", "liaoyang": "辽阳",
    "lvilianga": "吕梁", "longyan": "龙岩", "laibin": "来宾",
    "liangshanceshi": "凉山", "lishui": "丽水", "luohe": "漯河",
    "liupanshui": "六盘水", "loudi": "娄底", "liaoyuan": "辽源",
    "lijiang": "丽江", "lincang": "临沧", "lonnan": "陇南", "linxia": "临夏",
    "laiwu": "莱芜",
    # M
    "mianyang": "绵阳", "maoming": "茂名", "meizhou": "梅州", "meishan": "眉山",
    "mudanjiang": "牡丹江", "maanshan": "马鞍山",
    # N
    "nj": "南京", "nn": "南宁", "nc": "南昌", "nb": "宁波",
    "nantong": "南通", "nanyang": "南阳", "nanchong": "南充", "ningde": "宁德",
    "neijiang": "内江", "nanping": "南平", "nujiang": "怒江",
    # P
    "puyang": "濮阳", "putian": "莆田", "pingdingshan": "平顶山",
    "panjin": "盘锦", "pingxiang": "萍乡", "puer": "普洱",
    "panzhihua": "攀枝花", "pingliang": "平凉",
    # Q
    "qd": "青岛", "quanzhou": "泉州", "qiqihaer": "齐齐哈尔",
    "qinzhou": "钦州", "qingyuan": "清远", "qinhuangdao": "秦皇岛",
    "qujing": "曲靖", "qiannan": "黔南", "quzhou": "衢州",
    "qianxinan": "黔西南", "qiandongnan": "黔东南", "qingyanga": "庆阳",
    "qitaihe": "七台河", "qianjiang": "潜江", "qionghai": "琼海",
    # R
    "rizhao": "日照",
    # S
    "sh": "上海", "sz": "深圳", "sy": "沈阳", "su": "苏州",
    "sjz": "石家庄", "shantou": "汕头", "suqian": "宿迁", "shaoxing": "绍兴",
    "suihua": "绥化", "shangqiu": "商丘", "songyuan": "松原", "shanwei": "汕尾",
    "ahsuzhou": "宿州", "shangrao": "上饶", "siping": "四平", "shaoyang": "邵阳",
    "suining": "遂宁", "shiyan": "十堰", "sanming": "三明", "shaoguan": "韶关",
    "shuangyashan": "双鸭山", "sanmenxia": "三门峡", "shuozhou": "朔州",
    "suizhoushi": "随州", "sanya": "三亚", "shizuishan": "石嘴山",
    "shangluo": "商洛", "shennongjia": "神农架", "shuanghe": "双河市",
    # T
    "tj": "天津", "ty": "太原", "tangshan": "唐山", "taian": "泰安",
    "jstaizhou": "泰州", "zjtaizhou": "台州", "tieling": "铁岭",
    "tongliao": "通辽", "tonghua": "通化", "tianshui": "天水",
    "tongling": "铜陵", "tongren": "铜仁", "tacheng": "塔城",
    "tongchuan": "铜川", "tianmen": "天门", "tiemenguan": "铁门关市",
    # W
    "wh": "武汉", "weifang": "潍坊", "wx": "无锡", "xj": "乌鲁木齐",
    "wenzhou": "温州", "wei": "威海", "wuhu": "芜湖",
    "wulanchabu": "乌兰察布", "weinan": "渭南", "wuzhou": "梧州",
    "wenshan": "文山", "wuzhong": "吴忠", "wuhai": "乌海", "wuwei": "武威",
    # X
    "xa": "西安", "xuzhou": "徐州", "xm": "厦门", "xinxiang": "新乡",
    "xingtai": "邢台", "xiangyang": "襄阳", "xianyang": "咸阳", "xn": "西宁",
    "xuchang": "许昌", "xuancheng": "宣城", "xinyang": "信阳", "xiaogan": "孝感",
    "xinzhou": "忻州", "xiangtan": "湘潭", "xianning": "咸宁", "xinyu": "新余",
    "xishuangbanna": "西双版纳", "xiangxi": "湘西", "xilinguole": "锡林郭勒",
    "xiantao": "仙桃",
    # Y
    "yantai": "烟台", "yangzhou": "扬州", "yancheng": "盐城", "yingkou": "营口",
    "gxyulin": "玉林", "yinchuan": "银川", "yichang": "宜昌", "yibin": "宜宾",
    "yuncheng": "运城", "sxyulin": "榆林", "yueyang": "岳阳", "yangjiang": "阳江",
    "yuxi": "玉溪", "yunfu": "云浮", "yichunshi": "宜春", "yongzhou": "永州",
    "yiyang": "益阳", "yanbianshi": "延边", "yangquan": "阳泉", "yanan": "延安",
    "yinchun": "伊春", "yaan": "雅安", "yingtan": "鹰潭", "yili": "伊犁",
    # Z
    "zz": "郑州", "zhongshan": "中山", "zibo": "淄博", "zhanjiang": "湛江",
    "zhuhai": "珠海", "zhangzhou": "漳州", "zaozhuang": "枣庄", "zunyi": "遵义",
    "zhenjiang": "镇江", "zhaoqing": "肇庆", "zhangjiakou": "张家口",
    "zhumadian": "驻马店", "zhangjiajie": "张家界", "zhoukou": "周口",
    "zigong": "自贡", "zhuzhou": "株洲", "zhaotong": "昭通", "ziyang": "资阳",
    "zhoushan": "舟山", "zhangye": "张掖", "zhongwei": "中卫",
}

# 热门城市（优先采集）
HOT_CITIES = [
    "bj", "sh", "sz", "gz", "cd", "cq", "wh", "tj", "hz", "xa",
    "zz", "nj", "cs", "su", "dl", "qd", "sy", "sjz", "hf", "km",
    "nn", "nc", "nb", "fz", "xm", "gy", "cc", "hrb", "ty",
]


def get_all_cities() -> Dict[str, str]:
    """获取全部城市代码表"""
    return CITY_MAP.copy()


def get_hot_cities() -> Dict[str, str]:
    """获取热门城市代码表"""
    return {code: CITY_MAP[code] for code in HOT_CITIES if code in CITY_MAP}


# ================================================================
# 本地缓存管理（品牌/车系等运行时数据）
# ================================================================

def load_config_cache() -> Dict:
    """加载本地缓存配置"""
    if os.path.exists(GUAZI_CONFIG_PATH):
        try:
            with open(GUAZI_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config_cache(data: Dict):
    """保存本地缓存配置"""
    with open(GUAZI_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_cached_brands() -> Optional[List[Dict]]:
    """获取缓存的品牌列表"""
    cache = load_config_cache()
    return cache.get("brands")


def set_cached_brands(brands: List[Dict]):
    """缓存品牌列表"""
    cache = load_config_cache()
    cache["brands"] = brands
    save_config_cache(cache)


def get_cached_series() -> Optional[List[Dict]]:
    """获取缓存的车系列表"""
    cache = load_config_cache()
    return cache.get("series")


def set_cached_series(series: List[Dict]):
    """缓存车系列表"""
    cache = load_config_cache()
    cache["series"] = series
    save_config_cache(cache)
