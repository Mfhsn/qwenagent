import json
import os
import base64
import tempfile
from typing import Dict, List, Any
import pandas as pd
from qwen_agent.tools.base import BaseTool, register_tool
from config import INVOICE_TYPES, OCR_CONFIG

@register_tool('invoice_processor')
class InvoiceProcessor(BaseTool):
    """发票处理工具，用于上传、识别和管理各类发票"""
    
    description = '发票上传和识别工具，用于上传各种类型的发票(包含火车票、机票、汽车票、打车票、酒店住宿发票、餐票、高速通行票等)，并通过OCR或文件解析提取关键信息。'
    parameters = [{
        'name': 'invoice_data',
        'type': 'object',
        'description': '发票数据对象',
        'properties': {
            'invoice_type': {'type': 'string', 'description': '发票类型，如火车票、机票、酒店住宿发票等'},
            'file_type': {'type': 'string', 'description': '文件类型，如pdf、ofd、xml或image(图片)'},
            'file_content': {'type': 'string', 'description': '文件的Base64编码内容，或模拟示例内容'},
            'user_name': {'type': 'string', 'description': '当前用户姓名，用于校验发票信息是否属于该用户'}
        },
        'required': ['invoice_type', 'file_type']
    }]
    
    def __init__(self, tool_cfg=None):
        super().__init__(tool_cfg)
        self.invoices = []
    
    def call(self, params: str, **kwargs) -> str:
        """处理发票上传和识别请求"""
        try:
            invoice_data = json.loads(params)['invoice_data']
            invoice_type = invoice_data.get('invoice_type', '其他')
            
            # 验证发票类型
            if invoice_type not in INVOICE_TYPES:
                return json.dumps({
                    'status': 'error',
                    'message': f'不支持的发票类型: {invoice_type}，支持的类型有: {", ".join(INVOICE_TYPES)}'
                }, ensure_ascii=False)
            
            # 模拟发票识别过程，提取关键信息
            extracted_info = self._extract_invoice_info(invoice_data)
            
            # 添加到发票列表
            self.invoices.append(extracted_info)
            
            # 构建表格形式的发票信息
            if self.invoices:
                df = pd.DataFrame(self.invoices)
                invoice_table = df.to_markdown(index=False)
            else:
                invoice_table = "暂无发票信息"
            
            return json.dumps({
                'status': 'success',
                'message': '发票已成功上传并识别',
                'invoice_info': extracted_info,
                'invoice_table': invoice_table,
                'invoice_count': len(self.invoices)
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'发票处理失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _extract_invoice_info(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取发票信息（根据不同类型的发票提取不同字段）"""
        invoice_type = invoice_data.get('invoice_type', '其他')
        file_type = invoice_data.get('file_type', '')
        user_name = invoice_data.get('user_name', '')
        
        # 在真实环境中，这里会调用OCR服务或PDF解析服务
        # 这里使用模拟数据以便示例
        
        # 根据发票类型生成不同的模拟数据
        if invoice_type in ['火车票', '机票', '汽车票']:
            return {
                'invoice_type': invoice_type,
                'invoice_id': f'T{invoice_type[0]}{self._generate_id()}',
                'date': '2023-06-15',
                'departure': '上海',
                'destination': '北京',
                'amount': 550.00,
                'passenger': user_name or '张三',
                'file_type': file_type
            }
        elif invoice_type == '酒店住宿发票':
            return {
                'invoice_type': invoice_type,
                'invoice_id': f'H{self._generate_id()}',
                'hotel_name': '如家酒店',
                'check_in_date': '2023-06-15',
                'check_out_date': '2023-06-17',
                'nights': 2,
                'amount': 398.00,
                'guest_name': user_name or '张三',
                'file_type': file_type
            }
        elif invoice_type == '打车票':
            return {
                'invoice_type': invoice_type,
                'invoice_id': f'TX{self._generate_id()}',
                'date': '2023-06-16',
                'amount': 45.50,
                'start_location': '上海火车站',
                'end_location': '上海浦东国际机场',
                'passenger': user_name or '张三',
                'file_type': file_type
            }
        elif invoice_type == '餐票':
            return {
                'invoice_type': invoice_type,
                'invoice_id': f'M{self._generate_id()}',
                'date': '2023-06-16',
                'amount': 120.00,
                'restaurant': '全聚德烤鸭店',
                'file_type': file_type
            }
        elif invoice_type == '高速通行票':
            return {
                'invoice_type': invoice_type,
                'invoice_id': f'HW{self._generate_id()}',
                'date': '2023-06-16',
                'amount': 75.00,
                'entry_station': '上海站',
                'exit_station': '南京站',
                'file_type': file_type
            }
        else:
            return {
                'invoice_type': invoice_type,
                'invoice_id': f'O{self._generate_id()}',
                'date': '2023-06-16',
                'amount': 120.00,
                'details': '其他费用',
                'file_type': file_type
            }
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        import random
        return ''.join([str(random.randint(0, 9)) for _ in range(8)])
    
    def _save_file(self, file_content, file_type):
        """保存上传的文件（实际应用中会调用）"""
        try:
            if not file_content:
                return None
                
            # 创建临时文件保存上传内容
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_type}') as temp_file:
                if file_type in ['pdf', 'ofd', 'xml']:
                    # 解码Base64内容
                    file_bytes = base64.b64decode(file_content)
                    temp_file.write(file_bytes)
                elif file_type in ['jpg', 'jpeg', 'png']:
                    # 解码Base64图片
                    file_bytes = base64.b64decode(file_content)
                    temp_file.write(file_bytes)
                else:
                    return None
                    
                return temp_file.name
        except Exception as e:
            print(f"保存文件失败: {e}")
            return None
    
    def get_invoices(self):
        """获取所有已上传的发票"""
        return self.invoices
    
    def clear_invoices(self):
        """清空所有发票记录"""
        self.invoices = []
        return json.dumps({
            'status': 'success',
            'message': '所有发票记录已清空'
        }, ensure_ascii=False)
    
    def delete_invoice(self, index):
        """删除指定发票"""
        if 0 <= index < len(self.invoices):
            deleted_invoice = self.invoices.pop(index)
            return json.dumps({
                'status': 'success',
                'message': f'已删除第{index+1}张发票',
                'deleted_invoice': deleted_invoice
            }, ensure_ascii=False)
        else:
            return json.dumps({
                'status': 'error',
                'message': f'发票索引{index}不存在'
            }, ensure_ascii=False)
    
    def update_invoice(self, index, updated_info):
        """更新指定发票信息"""
        if 0 <= index < len(self.invoices):
            self.invoices[index].update(updated_info)
            return json.dumps({
                'status': 'success',
                'message': f'已更新第{index+1}张发票信息',
                'updated_invoice': self.invoices[index]
            }, ensure_ascii=False)
        else:
            return json.dumps({
                'status': 'error',
                'message': f'发票索引{index}不存在'
            }, ensure_ascii=False) 