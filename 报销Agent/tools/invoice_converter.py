import json
import os
import datetime
import sys
import glob

# 导入报销类型地区映射
try:
    # 尝试从当前目录的上一级目录导入config
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import REIMBURSEMENT_TYPE_MAPPING
    print("成功导入config中的REIMBURSEMENT_TYPE_MAPPING")
except ImportError:
    # 定义一个默认的映射表
    print("无法导入config.py中的REIMBURSEMENT_TYPE_MAPPING，使用默认值")
    REIMBURSEMENT_TYPE_MAPPING = {
        '出差北上': ['北京', '上海'],
        '出差广深': ['广州', '深圳'],
        '出差杭厦': ['杭州', '厦门'],
        '出差港澳台': ['香港', '澳门', '台湾'],
        '出差境内其他地市': []  # 默认类型
    }

# 导入报销类型匹配函数
try:
    # 尝试从tools目录导入
    from tools.utils import get_reimbursement_type_by_keyword
except ImportError:
    try:
        # 尝试直接从utils导入
        from utils import get_reimbursement_type_by_keyword
    except ImportError:
        # 如果导入失败，提供一个简单的默认实现
        def get_reimbursement_type_by_keyword(keyword):
            """导入失败时的默认实现"""
            return "001/出差北上"  # 默认返回

def get_reimbursement_type_by_location(location):
    """
    根据地点匹配报销类型编码
    
    :param location: 地点名称
    :return: 匹配的报销类型编码
    """
    if not location:
        return "001"  # 默认为出差北上
    
    location = location.strip()
    
    # 遍历REIMBURSEMENT_TYPE_MAPPING寻找匹配的地区
    for type_key, locations in REIMBURSEMENT_TYPE_MAPPING.items():
        for mapped_location in locations:
            if mapped_location in location or location in mapped_location:
                # 根据映射规则返回对应的编码
                if type_key == '出差北上':
                    return "001"
                elif type_key == '出差广深':
                    return "00101"
                elif type_key == '出差杭厦':
                    return "00102"
                elif type_key == '出差港澳台':
                    return "002"
                elif type_key == '出差境内其他地市':
                    return "003"
    
    # 如果没有匹配的地区，根据城市名尝试进一步匹配
    if any(city in location for city in ['北京', '上海']):
        return "001"  # 出差北上
    elif any(city in location for city in ['广州', '深圳']):
        return "00101"  # 出差广深
    elif any(city in location for city in ['杭州', '厦门']):
        return "00102"  # 出差杭厦
    elif any(city in location for city in ['香港', '澳门', '台湾']):
        return "002"  # 出差港澳台
    elif any(city in location for city in ['美国', '欧洲', '亚洲']):
        return "00202"  # 出差海外欧美亚高消费区
    elif any(city in location for city in ['海外', '国外']):
        return "00201"  # 出差海外-普通消费区
    
    # 默认为境内其他城市
    return "003"

def convert_date_format(date_str):
    """
    将中文日期格式转换为YYYYMMDD格式
    例如: "2025年04月23日" -> "20250423"
    """
    if not date_str:
        return ""
    
    # 处理"4-23"这样的短格式
    if "-" in date_str and len(date_str) <= 5:
        # 假设当前年份为发票上的年份
        current_year = "2025"  # 从发票中提取
        month, day = date_str.split("-")
        return f"{current_year}{month.zfill(2)}{day.zfill(2)}"
    
    # 处理标准中文日期格式
    try:
        if "年" in date_str and "月" in date_str and "日" in date_str:
            year = date_str.split("年")[0]
            month = date_str.split("年")[1].split("月")[0]
            day = date_str.split("月")[1].split("日")[0]
            return f"{year}{month.zfill(2)}{day.zfill(2)}"
    except:
        pass
    
    return date_str

def calculate_trip_days(departure_date, return_date):
    """
    计算出差天数
    """
    if not departure_date or not return_date:
        return ""
    
    try:
        # 将日期字符串转换为日期对象
        departure = datetime.datetime.strptime(departure_date, "%Y%m%d")
        return_day = datetime.datetime.strptime(return_date, "%Y%m%d")
        
        # 计算相差的天数
        delta = (return_day - departure).days + 1  # 包含首尾日期
        
        return str(delta)
    except Exception as e:
        print(f"计算出差天数时出错: {e}")
        return ""

def convert_hotel_invoice(invoice_data, trip_days=""):
    """
    将酒店发票数据转换为目标格式
    """
    raw_data = invoice_data.get("raw_extracted_info", {})
    
    # 提取入住日期和退房日期
    check_in_date = raw_data.get("入住日期", "")
    check_out_date = raw_data.get("退房日期", "")
    
    # 处理可能的日期格式差异
    check_in_date = convert_date_format(check_in_date)
    check_out_date = convert_date_format(check_out_date)
    
    # 如果没有提供出差天数，则尝试从酒店住宿天数计算
    if not trip_days and check_in_date and check_out_date:
        trip_days = calculate_trip_days(check_in_date, check_out_date)
    
    # 从住宿天数中提取数字
    hotel_days = raw_data.get("住宿天数", "").replace("天", "")
    if not hotel_days and check_in_date and check_out_date:
        hotel_days = calculate_trip_days(check_in_date, check_out_date)
    
    # 获取酒店名称和地点信息
    hotel_name = raw_data.get("酒店名称", raw_data.get("销售方名称", ""))
    
    # 根据酒店名称匹配报销类型编码
    reimbursement_type = get_reimbursement_type_by_location(hotel_name)
    
    # 生成报销事由
    reimbursement_reason = f"出差入住{hotel_name}"
    
    # 构建转换后的数据
    converted_data = {
        "报销类型": reimbursement_type,
        "报销事由": reimbursement_reason,
        "入住日期": check_in_date,
        "离店日期": check_out_date,
        "入住酒店": hotel_name,
        "说明（含同行人员等）": "",
        "住宿费": raw_data.get("价税合计(小写)", raw_data.get("金额", "")),
        "特殊事项": "无",
        "税率（%）": raw_data.get("税率/征收率", "").replace("%", ""),
        "住宿天数": hotel_days,
        "税率": raw_data.get("税率/征收率", "").replace("%", "")
    }
    
    return converted_data

def convert_transportation_invoice(invoice_data, trip_days=""):
    """
    将交通发票数据转换为目标格式
    """
    raw_data = invoice_data.get("raw_extracted_info", {})
    
    # 提取出发日期和到达日期（通常交通票据只有一个乘坐日期）
    travel_date = raw_data.get("乘坐日期", "")
    travel_date = convert_date_format(travel_date)
    
    # 提取出发地和到达地
    departure = raw_data.get("起始站", "").replace("站", "")
    destination = raw_data.get("到站", "").replace("站", "")
    
    # 确定交通工具类型
    transport_type = "飞机"
    if invoice_data.get("invoice_type") == "火车票":
        transport_type = "火车"
    elif invoice_data.get("invoice_type") == "出租车发票":
        transport_type = "出租车"
    
    # 根据出发地和目的地匹配报销类型编码
    # 优先使用目的地进行匹配
    reimbursement_type = get_reimbursement_type_by_location(destination)
    
    # 如果目的地没有匹配到特定类型，尝试使用出发地
    if reimbursement_type == "003" and departure:
        departure_type = get_reimbursement_type_by_location(departure)
        if departure_type != "003":
            reimbursement_type = departure_type
    
    # 生成报销事由
    reimbursement_reason = f"出差{departure}至{destination}"
    
    # 构建转换后的数据
    converted_data = {
        "报销类型": reimbursement_type,
        "报销事由": reimbursement_reason,
        "出发日期": travel_date,
        "到达日期": travel_date,
        "出发地点": departure,
        "出差天数": trip_days,  # 使用计算的出差天数
        "到达地点": destination,
        "交通工具": transport_type,
        "说明（含同行人员等）": "",
        "飞机车船费": raw_data.get("票价", raw_data.get("金额", "")),
        "出差补贴": "0",
        "特殊事项": "无",
        "税率（%）": "0",
        "其他费用（民航发展基金、行李费等）": "0"
    }
    
    return converted_data

def generate_filename(invoice_data):
    """
    根据发票数据生成文件名
    """
    invoice_id = invoice_data.get("invoice_id", "")
    raw_data = invoice_data.get("raw_extracted_info", {})
    
    if invoice_data.get("invoice_type") == "酒店住宿发票":
        hotel_name = raw_data.get("酒店名称", raw_data.get("销售方名称", "hotel"))
        return f"{hotel_name}_{invoice_id}.json"
    else:
        departure = raw_data.get("起始站", "").replace("站", "")
        destination = raw_data.get("到站", "").replace("站", "")
        return f"{departure}2{destination}_{invoice_id}.json"

def find_trip_routes(invoices):
    """
    从所有交通发票中查找往返行程，计算出差天数
    """
    # 收集所有交通发票信息
    transportation_invoices = []
    for invoice in invoices:
        if any(transport in invoice.get("invoice_type", "") for transport in ["火车", "飞机", "出租车", "汽车"]):
            transportation_invoices.append(invoice)
    
    # 尝试找到往返行程
    trip_routes = {}
    for invoice in transportation_invoices:
        raw_data = invoice.get("raw_extracted_info", {})
        departure = raw_data.get("起始站", "").replace("站", "")
        destination = raw_data.get("到站", "").replace("站", "")
        travel_date = convert_date_format(raw_data.get("乘坐日期", ""))
        
        if not departure or not destination or not travel_date:
            continue
        
        route_key = f"{departure}-{destination}"
        reverse_route_key = f"{destination}-{departure}"
        
        if route_key not in trip_routes:
            trip_routes[route_key] = {"date": travel_date, "invoice_id": invoice.get("invoice_id")}
        
        # 检查是否有返程
        if reverse_route_key in trip_routes:
            # 找到往返行程，计算出差天数
            outbound_date = trip_routes[reverse_route_key]["date"]
            return_date = travel_date
            
            # 确保出发日期在返程日期之前
            if outbound_date > return_date:
                outbound_date, return_date = return_date, outbound_date
            
            trip_days = calculate_trip_days(outbound_date, return_date)
            
            # 返回包含往返行程信息的字典
            return {
                "outbound_date": outbound_date,
                "return_date": return_date,
                "trip_days": trip_days
            }
    
    # 如果找不到完整的往返行程，尝试从酒店发票中提取信息
    for invoice in invoices:
        if "酒店" in invoice.get("invoice_type", "") or "住宿" in invoice.get("invoice_type", ""):
            raw_data = invoice.get("raw_extracted_info", {})
            check_in_date = convert_date_format(raw_data.get("入住日期", ""))
            check_out_date = convert_date_format(raw_data.get("退房日期", ""))
            
            if check_in_date and check_out_date:
                trip_days = calculate_trip_days(check_in_date, check_out_date)
                return {
                    "outbound_date": check_in_date,
                    "return_date": check_out_date,
                    "trip_days": trip_days
                }
    
    return {"outbound_date": "", "return_date": "", "trip_days": ""}

def main():
    # 获取当前脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 获取项目根目录（假设脚本在 报销Agent_new/报销Agent/tools 目录下）
    project_dir = os.path.abspath(os.path.join(script_dir, '..'))
    
    # 构建绝对路径
    json_dir = os.path.join(project_dir, 'json')
    hotel_dir = os.path.join(json_dir, 'hotel')
    transportation_dir = os.path.join(json_dir, 'transportation')
    
    # 确保输出目录存在
    os.makedirs(hotel_dir, exist_ok=True)
    os.makedirs(transportation_dir, exist_ok=True)
    
    # 查找json目录下的所有json文件
    json_files = glob.glob(os.path.join(json_dir, '*.json'))
    
    if not json_files:
        print(f"错误: 在 {json_dir} 目录下未找到任何JSON文件")
        return
    
    print(f"找到以下JSON文件: {json_files}")
    
    # 收集所有发票数据
    all_invoices = []
    
    # 处理每个JSON文件
    for source_file in json_files:
        print(f"处理文件: {source_file}")
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                
                # 判断文件内容是否为列表
                if isinstance(file_data, list):
                    all_invoices.extend(file_data)
                else:
                    # 单个发票数据，添加到列表
                    all_invoices.append(file_data)
                    
        except Exception as e:
            print(f"处理文件 {source_file} 时出错: {e}")
            continue
    
    if not all_invoices:
        print("未能从任何文件中提取到发票数据")
        return
    
    # 查找往返行程，计算出差天数
    trip_info = find_trip_routes(all_invoices)
    trip_days = trip_info["trip_days"]
    
    print(f"出差信息: 出发日期={trip_info['outbound_date']}, 返回日期={trip_info['return_date']}, 出差天数={trip_days}")
    
    # 处理每个发票
    for invoice in all_invoices:
        invoice_type = invoice.get("invoice_type", "")
        
        if "酒店" in invoice_type or "住宿" in invoice_type:
            # 转换酒店发票
            converted_data = convert_hotel_invoice(invoice, trip_days)
            filename = generate_filename(invoice)
            output_path = os.path.join(hotel_dir, filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(converted_data, f, ensure_ascii=False, indent=4)
            
            print(f"已保存酒店发票: {output_path}")
            
        elif any(transport in invoice_type for transport in ["火车", "飞机", "出租车", "汽车"]):
            # 转换交通发票
            converted_data = convert_transportation_invoice(invoice, trip_days)
            filename = generate_filename(invoice)
            output_path = os.path.join(transportation_dir, filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(converted_data, f, ensure_ascii=False, indent=4)
            
            print(f"已保存交通发票: {output_path}")
        
        else:
            print(f"未知发票类型: {invoice_type}, 跳过处理")

if __name__ == "__main__":
    main()