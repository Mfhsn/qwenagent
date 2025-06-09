import json
import os
import tempfile
import base64
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

def generate_markdown_table(data: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> str:
    """生成Markdown格式的表格"""
    if not data:
        return "暂无数据"
    
    df = pd.DataFrame(data)
    if headers:
        df = df[headers]
    
    return df.to_markdown(index=False)

def validate_date_format(date_str: str) -> bool:
    """验证日期格式是否为YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def calculate_days_between(start_date: str, end_date: str) -> int:
    """计算两个日期之间的天数差"""
    try:
        d1 = datetime.strptime(start_date, '%Y-%m-%d')
        d2 = datetime.strptime(end_date, '%Y-%m-%d')
        return (d2 - d1).days + 1
    except ValueError:
        return 0

def save_base64_to_file(base64_str: str, file_type: str = 'pdf') -> Optional[str]:
    """将Base64编码的内容保存到临时文件，并返回文件路径"""
    try:
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
            
        # 修复Base64 padding
        missing_padding = len(base64_str) % 4
        if missing_padding:
            base64_str += '=' * (4 - missing_padding)
        
        file_bytes = base64.b64decode(base64_str)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_type}') as temp_file:
            temp_file.write(file_bytes)
            return temp_file.name
    except Exception as e:
        print(f"保存文件失败: {e}")
        return None

def format_amount(amount: float) -> str:
    """格式化金额，保留两位小数"""
    return f"{amount:.2f}"

def generate_id(prefix: str = '') -> str:
    """生成唯一ID"""
    import random
    random_part = ''.join([str(random.randint(0, 9)) for _ in range(8)])
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"{prefix}{timestamp}{random_part}"

def merge_invoice_data(existing_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """合并发票数据，新数据优先"""
    result = existing_data.copy()
    for key, value in new_data.items():
        if value is not None:
            result[key] = value
    return result

def load_help_document() -> str:
    """加载帮助文档"""
    help_doc = '''
    # 智能报销使用指南
    
    ## 差旅报销流程
    1. **行程录入**：输入出差信息，包括日期、地点、事由等
    2. **发票上传**：上传票据，系统自动识别关键信息
    3. **报销单预生成**：系统自动匹配行程和票据，生成报销单
    4. **信息确认**：核对报销单信息，可进行修改
    5. **NCC提交**：确认无误后提交到NCC系统
    
    ## 支持的发票类型
    - 火车票/机票/汽车票
    - 打车票
    - 酒店住宿发票
    - 餐票
    - 高速通行票
    
    ## 常见问题
    Q: 如何添加多个行程？
    A: 只需说明要添加新行程，然后输入相关信息即可。
    
    Q: 如何修改已录入的信息？
    A: 在确认步骤前都可以修改，只需说明要修改哪项内容。
    
    Q: 发票上传支持哪些格式？
    A: 支持PDF、OFD、XML以及JPEG/PNG图片格式。
    
    Q: 如何处理缺少发票的情况？
    A: 系统会提示缺少哪些发票，您可以选择补充或说明原因继续提交。
    '''
    return help_doc

def group_invoices_by_type(invoices: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按发票类型对发票进行分组"""
    grouped = {}
    for invoice in invoices:
        invoice_type = invoice.get('invoice_type', '其他')
        if invoice_type not in grouped:
            grouped[invoice_type] = []
        grouped[invoice_type].append(invoice)
    return grouped

def summarize_invoices(invoices: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总发票信息"""
    if not invoices:
        return {"total_amount": 0, "count": 0, "types": []}
    
    total_amount = sum(invoice.get('amount', 0) for invoice in invoices)
    grouped = group_invoices_by_type(invoices)
    
    type_summary = []
    for invoice_type, type_invoices in grouped.items():
        type_amount = sum(invoice.get('amount', 0) for invoice in type_invoices)
        type_summary.append({
            "type": invoice_type,
            "count": len(type_invoices),
            "amount": type_amount
        })
    
    return {
        "total_amount": total_amount,
        "count": len(invoices),
        "types": type_summary
    }

def validate_pdf_file(file_path: str) -> bool:
    """验证PDF文件是否有效
    
    Args:
        file_path: PDF文件路径
        
    Returns:
        bool: 如果PDF文件有效则返回True，否则返回False
    """
    try:
        import fitz  # PyMuPDF
        
        # 尝试打开PDF文件
        doc = fitz.open(file_path)
        
        # 检查页数是否大于0
        is_valid = len(doc) > 0
        
        # 关闭文档
        doc.close()
        
        return is_valid
    except Exception as e:
        print(f"PDF文件验证失败: {str(e)}")
        return False 