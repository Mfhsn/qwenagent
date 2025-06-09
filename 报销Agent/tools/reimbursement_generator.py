import json
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
            '报销人': {'type': 'string', 'description': '报销人姓名'},
            '报销事由': {'type': 'string', 'description': '报销事由'},
            '收款银行名称': {'type': 'string', 'description': '收款银行名称'},
            '收款人卡号': {'type': 'string', 'description': '收款人卡号'},
            '分摊': {'type': 'string', 'description': '是否分摊费用，"是"或"否"'},
            '分摊原因': {'type': 'string', 'description': '分摊原因'},
            '住宿费超标金额': {'type': 'string', 'description': '住宿费超标金额'},
            '城市内公务交通车费超标金额': {'type': 'string', 'description': '城市内公务交通车费超标金额'},
            '超标说明': {'type': 'string', 'description': '超标说明'}
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
            confirmed = generation_data.get('confirmed', False)  # 新增参数，指示用户是否已确认表单
            
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
            
            # 只有在未确认状态下才执行验证
            validation_results = {
                'is_valid': True,
                'issues': [],
                'warnings': []
            }
            
            if not confirmed:
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
            
            # 如果有验证问题且未确认，添加警告信息
            if not confirmed and not validation_results['is_valid']:
                result['status'] = 'warning'
                result['message'] = '报销单已生成，但存在以下问题需要注意: ' + '; '.join(validation_results['issues'])
            
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'报销单生成失败: {str(e)}'
            }, ensure_ascii=False)
    
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
        """验证发票是否与行程匹配，使用更加灵活的验证规则"""
        validation_results = {
            'is_valid': True,
            'issues': [],
            'warnings': []  # 增加警告字段，用于展示可能的问题但不阻止提交
        }
        
        # 找出所有交通类发票
        transportation_invoices = [
            inv for inv in invoices 
            if inv.get('invoice_type') in ['火车票', '机票', '汽车票']
        ]
        
        # 调试输出
        print(f"找到{len(transportation_invoices)}张交通票据:")
        for i, inv in enumerate(transportation_invoices):
            print(f"  票据{i+1}: 从{inv.get('departure','')}到{inv.get('destination','')}")
        
        # 检查每个行程的往返票
        for i, trip in enumerate(trips):
            departure = trip.get('departure_place', '')
            arrival = trip.get('arrival_place', '')
            round_trip = trip.get('round_trip', True)
            
            if not departure or not arrival:
                validation_results['warnings'].append(f"行程 #{i+1} 缺少出发地或目的地信息")
                continue
            
            print(f"检查行程{i+1}: 从{departure}到{arrival}, 是否往返: {round_trip}")
            
            # 检查去程票 - 使用改进的地点匹配算法
            matching_outbound = []
            for inv in transportation_invoices:
                if (self._is_place_match(inv.get('departure', ''), departure) and 
                    self._is_place_match(inv.get('destination', ''), arrival)):
                    matching_outbound.append(inv)
                    
            has_outbound = len(matching_outbound) > 0
            
            if not has_outbound:
                print(f"  未找到从{departure}到{arrival}的去程票据")
                # 在没有找到确切匹配的情况下，再尝试模糊匹配
                for inv in transportation_invoices:
                    inv_dep = inv.get('departure', '')
                    inv_dest = inv.get('destination', '')
                    print(f"  比较: '{inv_dep}'-'{inv_dest}' vs '{departure}'-'{arrival}'")
                
                # 改为警告而不是错误，允许用户继续提交
                validation_results['warnings'].append(f"可能缺少从 {departure} 到 {arrival} 的去程票据")
            else:
                print(f"  找到{len(matching_outbound)}张从{departure}到{arrival}的去程票据")
            
            # 检查回程票（如果是往返行程）
            if round_trip:
                matching_return = []
                for inv in transportation_invoices:
                    if (self._is_place_match(inv.get('departure', ''), arrival) and 
                        self._is_place_match(inv.get('destination', ''), departure)):
                        matching_return.append(inv)
                        
                has_return = len(matching_return) > 0
                
                if not has_return:
                    print(f"  未找到从{arrival}到{departure}的回程票据")
                    # 在没有找到确切匹配的情况下，再尝试模糊匹配
                    for inv in transportation_invoices:
                        inv_dep = inv.get('departure', '')
                        inv_dest = inv.get('destination', '')
                        print(f"  比较: '{inv_dep}'-'{inv_dest}' vs '{arrival}'-'{departure}'")
                    
                    # 改为警告而不是错误，允许用户继续提交
                    validation_results['warnings'].append(f"可能缺少从 {arrival} 到 {departure} 的回程票据")
                else:
                    print(f"  找到{len(matching_return)}张从{arrival}到{departure}的回程票据")
        
        # 检查酒店住宿发票
        hotel_invoices = [inv for inv in invoices if inv.get('invoice_type') == '酒店住宿发票']
        print(f"找到{len(hotel_invoices)}张酒店住宿发票")
        
        for trip in trips:
            departure_date = trip.get('departure_date')
            arrival_date = trip.get('arrival_date')
            days = trip.get('days', 1)
            
            if not departure_date or not arrival_date:
                continue
                
            print(f"检查行程: 从{departure_date}到{arrival_date}, 共{days}天")
            
            # 检查是否有覆盖整个行程的酒店发票
            covered_nights = 0
            for inv in hotel_invoices:
                check_in = inv.get('check_in_date')
                check_out = inv.get('check_out_date')
                nights = inv.get('nights', 1)  # 默认至少1晚
                
                print(f"  酒店发票: 入住{check_in}至{check_out}, {nights}晚")
                
                # 放宽匹配条件，只要日期有重叠就算有效
                if check_in and check_out:
                    # 检查是否与行程日期有重叠
                    if not (check_out < departure_date or check_in > arrival_date):
                        covered_nights += nights
                        print(f"  匹配成功，累计住宿{covered_nights}晚")
            
            # 根据行程天数计算预期住宿晚数
            expected_nights = max(0, days - 1)  # 出差天数减1为需要住宿的晚数，至少为0
            
            if covered_nights < expected_nights:
                print(f"  酒店发票覆盖不完整: 需要{expected_nights}晚，实际只有{covered_nights}晚")
                # 改为警告而不是错误，允许用户继续提交
                validation_results['warnings'].append(f"酒店住宿发票可能覆盖不完整，出差{days}天但只有{covered_nights}晚的住宿记录")
            else:
                print(f"  酒店发票覆盖完整: 需要{expected_nights}晚，实际有{covered_nights}晚")
        
        # 如果只有警告但没有错误，仍然允许生成报销单
        if validation_results['warnings'] and not validation_results['issues']:
            validation_results['is_valid'] = True
            
        return validation_results
    
    def _is_place_match(self, station_name: str, city_name: str) -> bool:
        """检查站名是否与城市名匹配，使用通用灵活的匹配规则
        
        Args:
            station_name: 车站/机场名称
            city_name: 城市名称
            
        Returns:
            bool: 如果站名匹配城市名则返回True
        """
        if not station_name or not city_name:
            return False
            
        # 标准化处理，去除空格并转为小写
        station = station_name.strip().lower()
        city = city_name.strip().lower()
        
        # 1. 直接包含关系
        if city in station:
            return True
            
        # 2. 处理常见车站/机场名称格式
        common_suffixes = ["站", "东站", "西站", "南站", "北站", "机场", "国际机场"]
        for suffix in common_suffixes:
            if f"{city}{suffix}" in station:
                return True
                
        # 3. 两个名称的编辑距离较小，可能是相同地点的不同表达
        # 对于短名称（如"广州"），要求更高的相似度
        if len(city) <= 2:
            # 对于短城市名(1-2个字)，必须包含在站名中
            return city in station
        else:
            # 对于较长城市名，如果站名中包含城市名的大部分字符，视为匹配
            # 例如"福州"和"福州长乐国际机场"
            char_match_count = sum(1 for c in city if c in station)
            if char_match_count >= len(city) * 0.7:  # 至少70%的字符匹配
                return True
        
        # 4. 处理行政区划简称
        # 例如"北京市"和"北京"，"广州市"和"广州"
        if city.endswith("市") or city.endswith("省"):
            short_city = city[:-1]  # 移除"市"或"省"字
            if short_city in station:
                return True
                
        # 5. 处理某些特定的机场与城市关系 (这部分可以通过配置文件加载，而不是硬编码)
        # 例如"虹桥"和"浦东"代表"上海"
        
        # 6. 允许模糊匹配
        # 在生产环境中，此处可以集成更复杂的自然语言处理或模糊匹配算法
        
        return False
    
    def _generate_reimbursement_form(self, trips: List[Dict], invoices: List[Dict], data: Dict) -> Dict:
        """生成报销单"""
        # 确定报销类型
        reimbursement_type = self._determine_reimbursement_type(trips)
        
        # 按收支项目分类发票
        categorized_invoices = self._categorize_invoices(invoices)
        
        # 计算总金额
        total_amount = sum(inv.get('amount', 0) for inv in invoices)
        
        # 计算附件张数（使用发票数量）
        invoice_count = len(invoices)
        
        # 获取用户在web界面中输入的字段值
        form_fields = {
            "报销人": data.get("报销人", ""),
            "报销事由": data.get("报销事由", "出差"),
            "附件张数": str(invoice_count),  # 使用发票数量作为附件张数
            "收款人": data.get("收款人", "涂超"),
            "收款银行名称": data.get("收款银行名称", "招商银行"),
            "收款人卡号": data.get("收款人卡号", ""),
            "分摊": data.get("分摊", "否"),
            "分摊原因": data.get("分摊原因", ""),
            "住宿费超标金额": data.get("住宿费超标金额", "0"),
            "城市内公务交通车费超标金额": data.get("城市内公务交通车费超标金额", "0"),
            "超标说明": data.get("超标说明", "无")
        }
        
        # 生成报销单
        reimbursement_form = {
            '报销类型': reimbursement_type,
            '报销总金额': total_amount,
            '行程信息': trips,
            '费用明细': categorized_invoices
        }
        
        # 添加用户填写的字段
        reimbursement_form.update(form_fields)
        
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