import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from qwen_agent.tools.base import BaseTool, register_tool
from config import REIMBURSEMENT_TYPE_MAPPING, EXPENSE_CATEGORY_MAPPING

@register_tool('reimbursement_generator')
class ReimbursementGenerator(BaseTool):
    """报销单生成工具，用于根据行程和发票信息生成报销单"""
    
    description = '报销单生成工具，根据行程信息和发票信息自动匹配并生成NCC报销单，检查是否有票据缺失等问题。'
    parameters = [{
        'name': 'generation_params',
        'type': 'object',
        'description': '报销单生成参数',
        'properties': {
            'trips': {'type': 'array', 'description': '行程信息数组'},
            'invoices': {'type': 'array', 'description': '发票信息数组'},
            'employee_name': {'type': 'string', 'description': '员工姓名'},
            'department': {'type': 'string', 'description': '部门名称'}
        },
        'required': ['trips', 'invoices']
    }]
    
    def __init__(self, tool_cfg=None):
        super().__init__(tool_cfg)
    
    def call(self, params: str, **kwargs) -> str:
        """处理报销单生成请求"""
        try:
            generation_data = json.loads(params)['generation_params']
            trips = generation_data.get('trips', [])
            invoices = generation_data.get('invoices', [])
            
            if not trips:
                return json.dumps({
                    'status': 'error',
                    'message': '无法生成报销单：没有行程信息'
                }, ensure_ascii=False)
            
            if not invoices:
                return json.dumps({
                    'status': 'error',
                    'message': '无法生成报销单：没有发票信息'
                }, ensure_ascii=False)
            
            # 预处理发票信息，确保交通票据使用travel_date而不是date
            invoices = self._preprocess_invoices(invoices)
            
            # 检查票据是否完整，例如往返票是否齐全
            validation_results = self._validate_invoices_against_trips(trips, invoices)
            
            # 生成报销单
            reimbursement_form = self._generate_reimbursement_form(trips, invoices, generation_data)
            
            # 构建表格展示
            expense_summary = self._generate_expense_summary(reimbursement_form)
            
            result = {
                'status': 'success',
                'message': '报销单已成功生成',
                'validation_results': validation_results,
                'reimbursement_form': reimbursement_form,
                'expense_summary': expense_summary
            }
            
            # 如果有验证问题，添加警告信息
            if not validation_results['is_valid']:
                result['status'] = 'warning'
                result['message'] = '报销单已生成，但存在以下问题需要注意: ' + '; '.join(validation_results['issues'])
            
            # 保存JSON文件到指定目录
            self._save_reimbursement_json(result)
            
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'报销单生成失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _save_reimbursement_json(self, result: Dict) -> None:
        """保存报销单JSON到指定目录"""
        # 指定保存目录
        save_dir = r"C:\Users\97818\Desktop\project\rpa_test\报销Agent\报销Agent\return_json"
        
        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 生成文件名，使用报销单号或时间戳
        if 'reimbursement_form' in result and '报销单号' in result['reimbursement_form']:
            filename = f"{result['reimbursement_form']['报销单号']}.json"
        else:
            filename = f"reimbursement_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        
        # 完整的文件路径
        file_path = os.path.join(save_dir, filename)
        
        # 保存JSON文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        print(f"报销单JSON已保存至: {file_path}")
    
    def _preprocess_invoices(self, invoices: List[Dict]) -> List[Dict]:
        """预处理发票信息，确保交通票据使用travel_date作为显示日期"""
        processed_invoices = []
        
        for invoice in invoices:
            # 创建发票副本，避免修改原始数据
            processed_invoice = invoice.copy()
            
            # 对于交通类发票，优先使用travel_date作为显示日期
            if invoice.get('invoice_type') in ['火车票', '机票', '汽车票']:
                # 如果有travel_date字段，将其用于显示
                if 'travel_date' in invoice and invoice['travel_date']:
                    processed_invoice['display_date'] = invoice['travel_date']
                else:
                    processed_invoice['display_date'] = invoice.get('date', '')
            else:
                # 非交通类发票直接使用date字段
                processed_invoice['display_date'] = invoice.get('date', '')
                
            processed_invoices.append(processed_invoice)
            
        return processed_invoices
    
    def _validate_invoices_against_trips(self, trips: List[Dict], invoices: List[Dict]) -> Dict:
        """验证发票是否与行程匹配"""
        validation_results = {
            'is_valid': True,
            'issues': []
        }
        
        # 找出所有交通类发票
        transportation_invoices = [
            inv for inv in invoices 
            if inv.get('invoice_type') in ['火车票', '机票', '汽车票']
        ]
        
        # 检查每个行程的往返票
        for i, trip in enumerate(trips):
            departure = trip.get('departure_place', '')
            arrival = trip.get('arrival_place', '')
            round_trip = trip.get('round_trip', True)
            
            if not departure or not arrival:
                validation_results['is_valid'] = False
                validation_results['issues'].append(f"行程 #{i+1} 缺少出发地或目的地信息")
                continue
            
            # 检查去程票 - 只需要站名包含城市名称即可
            has_outbound = any(
                self._is_place_match(inv.get('departure', ''), departure) and 
                self._is_place_match(inv.get('destination', ''), arrival)
                for inv in transportation_invoices
            )
            
            if not has_outbound:
                validation_results['is_valid'] = False
                validation_results['issues'].append(f"缺少从 {departure} 到 {arrival} 的去程票据")
            
            # 检查回程票（如果是往返行程）- 只需要站名包含城市名称即可
            if round_trip:
                has_return = any(
                    self._is_place_match(inv.get('departure', ''), arrival) and 
                    self._is_place_match(inv.get('destination', ''), departure)
                    for inv in transportation_invoices
                )
                if not has_return:
                    validation_results['is_valid'] = False
                    validation_results['issues'].append(f"缺少从 {arrival} 到 {departure} 的回程票据")
        
        # 检查酒店住宿发票
        hotel_invoices = [inv for inv in invoices if inv.get('invoice_type') == '酒店住宿发票']
        for trip in trips:
            departure_date = trip.get('departure_date')
            arrival_date = trip.get('arrival_date')
            days = trip.get('days', 1)
            
            if not departure_date or not arrival_date:
                continue
                
            # 检查是否有覆盖整个行程的酒店发票
            covered_nights = 0
            for inv in hotel_invoices:
                check_in = inv.get('check_in_date')
                check_out = inv.get('check_out_date')
                nights = inv.get('nights', 0)
                
                if check_in and check_out and departure_date <= check_in and check_out <= arrival_date:
                    covered_nights += nights
            
            if covered_nights < days - 1:  # 出差天数减1为需要住宿的晚数
                validation_results['is_valid'] = False
                validation_results['issues'].append(f"酒店住宿发票覆盖不完整，出差{days}天但只有{covered_nights}晚的住宿记录")
        
        return validation_results
    
    def _is_place_match(self, station_name: str, city_name: str) -> bool:
        """检查站名是否包含城市名称
        
        Args:
            station_name: 车站/机场名称
            city_name: 城市名称
            
        Returns:
            bool: 如果站名包含城市名则返回True
        """
        if not station_name or not city_name:
            return False
        return city_name in station_name
    
    def _generate_reimbursement_form(self, trips: List[Dict], invoices: List[Dict], data: Dict) -> Dict:
        """生成报销单"""
        employee_name = data.get('employee_name', '员工姓名')
        department = data.get('department', '部门')
        
        # 确定报销类型
        reimbursement_type = self._determine_reimbursement_type(trips)
        
        # 按收支项目分类发票
        categorized_invoices = self._categorize_invoices(invoices)
        
        # 计算总金额
        total_amount = sum(inv.get('amount', 0) for inv in invoices)
        
        # 生成报销单
        reimbursement_form = {
            '报销单号': f'ZX{datetime.now().strftime("%Y%m%d%H%M%S")}',
            '报销人': employee_name,
            '部门': department,
            '报销类型': reimbursement_type,
            '报销总金额': total_amount,
            '行程信息': trips,
            '费用明细': categorized_invoices
        }
        
        return reimbursement_form
    
    def _determine_reimbursement_type(self, trips: List[Dict]) -> str:
        """根据出差地点确定报销类型"""
        for trip in trips:
            destination = trip.get('arrival_place', '')
            
            # 检查目的地是否在特定的分类中
            for reim_type, cities in REIMBURSEMENT_TYPE_MAPPING.items():
                if destination in cities:
                    return reim_type
        
        # 默认为其他地市
        return '境内其他地市'
    
    def _categorize_invoices(self, invoices: List[Dict]) -> Dict[str, List[Dict]]:
        """按收支项目对发票进行分类"""
        categorized = {}
        
        # 初始化分类
        for category in EXPENSE_CATEGORY_MAPPING.keys():
            categorized[category] = []
        
        # 对发票进行分类
        for invoice in invoices:
            invoice_type = invoice.get('invoice_type', '其他')
            
            # 根据预设的映射关系分类
            for category, types in EXPENSE_CATEGORY_MAPPING.items():
                if invoice_type in types:
                    categorized[category].append(invoice)
                    break
        
        return categorized
    
    def _generate_expense_summary(self, reimbursement_form: Dict) -> str:
        """生成费用汇总表格"""
        summary_data = []
        
        # 提取各类别的费用
        for category, invoices in reimbursement_form['费用明细'].items():
            total = sum(inv.get('amount', 0) for inv in invoices)
            count = len(invoices)
            
            if count > 0:
                summary_data.append({
                    '收支项目': category,
                    '发票数量': count,
                    '金额合计': total
                })
        
        # 添加总计行
        summary_data.append({
            '收支项目': '总计',
            '发票数量': sum(item['发票数量'] for item in summary_data),
            '金额合计': reimbursement_form['报销总金额']
        })
        
        # 生成表格
        if summary_data:
            df = pd.DataFrame(summary_data)
            return df.to_markdown(index=False)
        else:
            return "暂无费用汇总信息" 