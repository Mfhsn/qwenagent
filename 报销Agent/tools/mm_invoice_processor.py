import json
import base64
import tempfile
import os
from typing import Dict, List, Any, Optional, Union
from qwen_agent.tools.base import BaseTool, register_tool
from tools.invoice_extractor import InvoiceExtractor

@register_tool('mm_invoice_processor')
class MMInvoiceProcessor(BaseTool):
    """多模态发票处理工具，基于大模型的发票识别和信息提取"""
    
    description = '使用多模态大模型处理票据图像，识别并提取发票信息，支持火车票、机票、汽车票、酒店住宿发票、打车票等类型。'
    parameters = [{
        'name': 'process_params',
        'type': 'object',
        'description': '发票处理参数',
        'properties': {
            'image_data': {'type': 'string', 'description': '图像的Base64编码数据'},
            'file_type': {'type': 'string', 'description': '文件类型，如jpg、jpeg、png'},
            'invoice_type': {'type': 'string', 'description': '发票类型提示，如火车票、机票、酒店住宿发票等'},
            'operation': {'type': 'string', 'description': '要执行的操作，如extract_info'}
        },
        'required': ['image_data', 'operation']
    }]
    
    def __init__(self, tool_cfg=None):
        super().__init__(tool_cfg)
        self.invoice_extractor = InvoiceExtractor()
    
    def call(self, params: str, **kwargs) -> str:
        """处理发票图像，提取信息"""
        try:
            # 不打印整个参数，而是打印简短摘要
            print(f"mm_invoice_processor被调用，正在处理参数...")
            
            # 解析参数
            process_params = json.loads(params)['process_params']
            operation = process_params.get('operation', '')
            image_data = process_params.get('image_data', '')
            file_type = process_params.get('file_type', 'jpg')
            invoice_type = process_params.get('invoice_type', None)
            
            # 打印图像数据长度而不是内容
            image_data_length = len(image_data) if image_data else 0
            print(f"操作: {operation}, 文件类型: {file_type}, 发票类型提示: {invoice_type}, 图像数据长度: {image_data_length}字节")
            
            if not operation:
                print("错误: 未指定处理操作")
                return json.dumps({
                    'status': 'error',
                    'message': '未指定处理操作'
                }, ensure_ascii=False)
                
            if not image_data:
                print("错误: 未提供图像数据")
                return json.dumps({
                    'status': 'error',
                    'message': '未提供图像数据'
                }, ensure_ascii=False)
            
            # 验证base64数据的有效性
            if image_data.startswith("[") and image_data.endswith("]"):
                print("错误: 收到的似乎是描述文本而不是实际的base64数据")
                return json.dumps({
                    'status': 'error',
                    'message': '图像数据无效，收到的是描述性文本而非base64编码'
                }, ensure_ascii=False)
                
            # 检查是否包含有效的base64字符
            import re
            if not re.match(r'^[A-Za-z0-9+/=,]+$', image_data):
                print("警告: 图像数据包含非标准base64字符")
                # 打印一些字符用于调试
                if len(image_data) > 20:
                    print(f"数据前20个字符: {image_data[:20]}")
                else:
                    print(f"数据内容: {image_data}")
                
                return json.dumps({
                    'status': 'error',
                    'message': '图像数据包含非标准base64字符，请提供有效的base64编码字符串'
                }, ensure_ascii=False)
            
            # 执行对应操作
            if operation == 'extract_info':
                result = self._extract_invoice_info(image_data, file_type, invoice_type)
                print(f"提取结果状态: {json.loads(result).get('status', 'unknown')}")
                return result
            else:
                print(f"错误: 不支持的操作: {operation}")
                return json.dumps({
                    'status': 'error',
                    'message': f'不支持的操作：{operation}'
                }, ensure_ascii=False)
                
        except Exception as e:
            print(f"处理发票图像失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return json.dumps({
                'status': 'error',
                'message': f'处理发票图像失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _extract_invoice_info(self, image_data: str, file_type: str, invoice_type: Optional[str] = None) -> str:
        """使用多模态模型提取发票信息
        
        Args:
            image_data: 图像的Base64编码
            file_type: 文件类型
            invoice_type: 发票类型提示
            
        Returns:
            包含提取信息的JSON字符串
        """
        temp_path = None
        try:
            print(f"开始提取发票信息，文件类型: {file_type}, 发票类型提示: {invoice_type}")
            
            # 处理输入图像
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_type}') as temp_file:
                # 处理可能包含前缀的base64字符串
                print("开始处理base64图像数据...")
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                    print("已移除base64前缀")
                
                # 修复Base64 padding问题
                missing_padding = len(image_data) % 4
                if missing_padding:
                    image_data += '=' * (4 - missing_padding)
                    print(f"已修复Base64 padding，添加了{4 - missing_padding}个=")
                
                # 解码并保存到临时文件
                try:
                    # 尝试解码前先验证一次
                    if not all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in image_data):
                        invalid_chars = [c for c in image_data[:100] if c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=']
                        print(f"警告: base64字符串包含无效字符: {invalid_chars}")
                    
                    image_bytes = base64.b64decode(image_data)
                    bytes_size = len(image_bytes)
                    print(f"解码后的图像大小: {bytes_size} 字节")
                    
                    # 降低最小大小阈值，并添加更详细的错误信息
                    if bytes_size < 50:  # 降低到50字节
                        print(f"警告: 图像数据非常小 ({bytes_size} 字节)，可能不是有效图像")
                    
                    temp_file.write(image_bytes)
                    temp_path = temp_file.name
                    print(f"已将解码后的图像保存到临时文件: {temp_path}")
                except Exception as decode_err:
                    print(f"Base64解码失败: {str(decode_err)}")
                    print(f"Base64数据长度: {len(image_data)}")
                    print(f"Base64数据前20个字符: {image_data[:20]}")
                    
                    # 尝试读取部分数据
                    try:
                        partial_data = image_data[:100] + "..."
                        partial_bytes = base64.b64decode(partial_data)
                        print(f"部分数据解码成功，大小: {len(partial_bytes)}字节")
                    except:
                        print("部分数据解码也失败")
                    
                    return json.dumps({
                        'status': 'error',
                        'message': f'Base64解码失败: {str(decode_err)}'
                    }, ensure_ascii=False)
            
            # 验证和处理图像格式
            # try:
            #     from PIL import Image
            #     try:
            #         with Image.open(temp_path) as img:
            #             # 检查图像格式并转换为RGB以确保兼容性
            #             if img.mode != 'RGB':
            #                 rgb_img = img.convert('RGB')
            #                 # 保存为临时JPEG文件
            #                 processed_path = temp_path + ".jpg"
            #                 rgb_img.save(processed_path, 'JPEG')
            #                 print(f"已将图像转换为RGB格式并保存为: {processed_path}")
            #
            #                 # 使用处理后的图像路径
            #                 if os.path.exists(processed_path) and os.path.getsize(processed_path) > 0:
            #                     # 删除原始临时文件
            #                     os.unlink(temp_path)
            #                     temp_path = processed_path
            #                     print(f"将使用处理后的图像: {temp_path}")
            #     except Exception as img_err:
            #         print(f"图像验证/处理失败，继续使用原始图像: {str(img_err)}")
            # except ImportError:
            #     print("PIL库未安装，跳过图像验证和处理")
            
            # 使用多模态抽取器提取信息
            try:
                print(f"调用invoice_extractor.extract_info处理: {temp_path}")
                extracted_info = self.invoice_extractor.extract_info(temp_path, invoice_type)
                print(f"提取信息完成，结果: {extracted_info}")
                
                # 删除临时文件
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                    print(f"已删除临时文件: {temp_path}")
                
                # 检查是否成功提取信息
                if 'error' in extracted_info:
                    print(f"提取过程中发生错误: {extracted_info['error']}")
                    # 如果有错误但仍然有一些基本信息，尝试使用这些信息
                    if invoice_type and len(extracted_info) > 1:
                        print("尽管有错误，但仍尝试使用部分提取的信息")
                        # 继续处理部分信息
                    else:
                        return json.dumps({
                            'status': 'error',
                            'message': extracted_info['error']
                        }, ensure_ascii=False)
                
                # 将提取的信息转换为系统所需的发票信息格式
                invoice_info = self._convert_to_system_format(extracted_info)
                print(f"已转换为系统格式: {invoice_info}")
                
                return json.dumps({
                    'status': 'success',
                    'message': '成功提取发票信息',
                    'invoice_info': invoice_info
                }, ensure_ascii=False)
                
            except Exception as extract_err:
                print(f"提取信息过程中发生异常: {str(extract_err)}")
                import traceback
                traceback.print_exc()
                
                # 确保删除临时文件
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                        print(f"已删除临时文件: {temp_path}")
                    except:
                        pass
                
                # 提供备用基本信息
                if invoice_type:
                    basic_info = self._generate_basic_invoice_info(invoice_type)
                    if basic_info:
                        print("提供备用的基本发票信息")
                        return json.dumps({
                            'status': 'warning',
                            'message': f'无法完全提取发票信息: {str(extract_err)}，提供基本结构',
                            'invoice_info': basic_info
                        }, ensure_ascii=False)
                
                raise extract_err
            
        except Exception as e:
            print(f"提取发票信息总体失败: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    print(f"已删除临时文件: {temp_path}")
                except:
                    pass
            
            return json.dumps({
                'status': 'error',
                'message': f'提取发票信息失败: {str(e)}'
            }, ensure_ascii=False)
            
    def _generate_basic_invoice_info(self, invoice_type: str) -> Dict[str, Any]:
        """根据发票类型生成基本的发票信息结构
        
        Args:
            invoice_type: 发票类型
            
        Returns:
            Dict: 基本的发票信息结构
        """
        import datetime
        
        # 基本发票信息，不再使用当前日期作为默认值
        basic_info = {
            'invoice_type': invoice_type,
            'date': '',  # 留空，等待大模型提取
            'amount': 0.0,
            'invoice_id': f"AUTO{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
            '备注': '需要通过大模型提取正确的发票日期'
        }
        
        # 根据发票类型添加特定字段
        if invoice_type in ["火车票", "机票", "汽车票"]:
            basic_info.update({
                'departure': '',
                'destination': '',
                'passenger': ''
            })
        elif invoice_type == "酒店住宿发票":
            basic_info.update({
                'hotel_name': '',
                'check_in_date': '',  # 不再使用当前日期
                'check_out_date': '',
                'nights': 0,  # 默认为0而不是1
                'guest_name': ''
            })
        elif invoice_type == "打车票":
            basic_info.update({
                'start_location': '',
                'end_location': '',
                'taxi_number': ''
            })
        
        return basic_info
    
    def _convert_to_system_format(self, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
        """将抽取器的输出转换为系统所需的格式
        
        Args:
            extracted_info: 抽取器提取的信息
            
        Returns:
            Dict: 符合系统格式的发票信息
        """
        print(f"开始转换提取信息: {json.dumps(extracted_info, ensure_ascii=False)}")
        
        # 基础信息
        invoice_info = {
            'invoice_type': self._map_invoice_type(extracted_info.get('发票类型', extracted_info.get('invoice_type', '其他'))),
            'invoice_id': extracted_info.get('发票号码', extracted_info.get('invoice_id', f"AUTO{extracted_info.get('日期', '')}")),
            'date': extracted_info.get('日期', extracted_info.get('date', '')),
            'amount': self._extract_amount(extracted_info),
        }
        
        print(f"基础信息转换结果: {json.dumps(invoice_info, ensure_ascii=False)}")
        
        # 根据发票类型添加特定字段
        if invoice_info['invoice_type'] in ["火车票", "机票", "汽车票"]:
            # 更全面的中文字段映射
            departure = None
            for field in ['起始站', '出发地', '始发站', '出发站', '出发', 'departure']:
                if field in extracted_info and extracted_info[field]:
                    departure = extracted_info[field]
                    break
                
            destination = None
            for field in ['到站', '目的地', '终点站', '终点', '到达站', '到达', 'destination']:
                if field in extracted_info and extracted_info[field]:
                    destination = extracted_info[field]
                    break
                
            passenger = None
            for field in ['乘客姓名', '旅客姓名', '旅客信息', '乘客', '旅客', 'passenger']:
                if field in extracted_info and extracted_info[field]:
                    passenger = extracted_info[field]
                    break
                
            ticket_number = None
            for field in ['电子客票号', '票号', '客票号', '车票号', 'ticket_number']:
                if field in extracted_info and extracted_info[field]:
                    ticket_number = extracted_info[field]
                    break
            
            travel_date = None
            for field in ['乘坐日期', '乘车日期', 'travel_date']:
                if field in extracted_info and extracted_info[field]:
                    travel_date = extracted_info[field]
                    break

            invoice_info.update({
                'departure': departure or '',
                'destination': destination or '',
                'passenger': passenger or '',
                'ticket_number': ticket_number or '',
                'travel_date': travel_date or ''
            })
            
            print(f"火车票/机票/汽车票特定字段: departure={departure}, destination={destination}, passenger={passenger}")
            
        elif invoice_info['invoice_type'] == "酒店住宿发票":
            # 酒店住宿发票特定字段
            hotel_name = None
            for field in ['酒店名称', '宾馆名称', '住宿地点', '酒店', '销售方名称', '开票方', '商家名称', '企业名称', 'hotel_name']:
                if field in extracted_info and extracted_info[field]:
                    hotel_name = extracted_info[field]
                    break
                    
            check_in_date = None
            for field in ['入住日期', '入住时间', '开始日期', '入住', 'check_in_date']:
                if field in extracted_info and extracted_info[field]:
                    check_in_date = extracted_info[field]
                    break
                    
            check_out_date = None
            for field in ['退房日期', '退房时间', '结束日期', '退房', 'check_out_date']:
                if field in extracted_info and extracted_info[field]:
                    check_out_date = extracted_info[field]
                    break
                    
            guest_name = None
            for field in ['住宿人姓名', '客人姓名', '入住人', '客人', '住宿人', 'guest_name']:
                if field in extracted_info and extracted_info[field]:
                    guest_name = extracted_info[field]
                    break
            
            # 添加住宿地址字段
            hotel_address = None
            for field in ['住宿地址', '酒店地址', '地址', '详细地址', '开票地址']:
                if field in extracted_info and extracted_info[field]:
                    hotel_address = extracted_info[field]
                    break
            
            # 添加房间号字段
            room_number = None
            for field in ['房间号', '房号', '客房号', '房间']:
                if field in extracted_info and extracted_info[field]:
                    room_number = extracted_info[field]
                    break
            
            invoice_info.update({
                'hotel_name': hotel_name or '',
                'check_in_date': check_in_date or '',
                'check_out_date': check_out_date or '',
                'nights': self._extract_nights(extracted_info),
                'guest_name': guest_name or '',
                'hotel_address': hotel_address or '',
                'room_number': room_number or ''
            })
            
            print(f"酒店住宿发票特定字段: hotel={hotel_name}, check_in={check_in_date}, check_out={check_out_date}, guest={guest_name}, address={hotel_address}, room={room_number}")
            
        elif invoice_info['invoice_type'] == "打车票":
            # 打车票特定字段
            start_location = None
            for field in ['上车地点', '起点', '出发地', '起始地点', '始发地', 'start_location']:
                if field in extracted_info and extracted_info[field]:
                    start_location = extracted_info[field]
                    break
                    
            end_location = None
            for field in ['下车地点', '终点', '目的地', '结束地点', '到达地', 'end_location']:
                if field in extracted_info and extracted_info[field]:
                    end_location = extracted_info[field]
                    break
                    
            taxi_number = None
            for field in ['车牌号', '出租车号', '车辆号码', '车辆编号', 'taxi_number']:
                if field in extracted_info and extracted_info[field]:
                    taxi_number = extracted_info[field]
                    break
            
            invoice_info.update({
                'start_location': start_location or '',
                'end_location': end_location or '',
                'taxi_number': taxi_number or ''
            })
            
            print(f"打车票特定字段: start={start_location}, end={end_location}, taxi={taxi_number}")
        
        # 保存原始提取信息供参考
        invoice_info['raw_extracted_info'] = extracted_info
        
        print(f"最终转换结果: {json.dumps(invoice_info, ensure_ascii=False)}")
        return invoice_info
    
    def _map_invoice_type(self, extracted_type: str) -> str:
        """将抽取器的发票类型映射到系统使用的类型
        
        Args:
            extracted_type: 抽取器识别的发票类型
            
        Returns:
            str: 系统使用的发票类型
        """
        # 类型映射
        type_map = {
            '交通票据': '火车票',  # 默认归类为火车票
            '住宿票据': '酒店住宿发票',
            '出租车票据': '打车票',
            '餐饮票据': '餐票',
            '高速通行费': '高速通行票'
        }
        
        return type_map.get(extracted_type, extracted_type)
    
    def _extract_amount(self, extracted_info: Dict[str, Any]) -> float:
        """提取金额信息
        
        Args:
            extracted_info: 提取的信息
            
        Returns:
            float: 金额，如果无法提取则返回0
        """
        # 尝试直接获取金额字段
        if '金额' in extracted_info:
            try:
                # 处理可能的字符串格式，如"￥100.00"
                amount_str = str(extracted_info['金额'])
                # 移除非数字字符（保留小数点）
                import re
                amount_str = re.sub(r'[^\d.]', '', amount_str)
                return float(amount_str)
            except (ValueError, TypeError):
                pass
                
        # 尝试从票价字段获取
        if '票价' in extracted_info:
            try:
                # 处理可能的字符串格式
                price_str = str(extracted_info['票价'])
                # 移除非数字字符
                import re
                price_str = re.sub(r'[^\d.]', '', price_str)
                return float(price_str)
            except (ValueError, TypeError):
                pass
        
        return 0.0
    
    def _extract_nights(self, extracted_info: Dict[str, Any]) -> int:
        """提取住宿天数
        
        Args:
            extracted_info: 提取的信息
            
        Returns:
            int: 住宿天数，如果无法提取则返回1
        """
        # 直接提取
        if '住宿天数' in extracted_info:
            try:
                return int(str(extracted_info['住宿天数'].replace('天', '').replace('晚', '').replace('日', '').strip()))
            except (ValueError, TypeError):
                pass
                
        # # 尝试计算住宿天数
        # if '入住日期' in extracted_info and '退房日期' in extracted_info:
        #     try:
        #         # 尝试解析日期格式
        #         import datetime
        #         import re
                
        #         # 提取入住日期的数字
        #         check_in_str = extracted_info['入住日期']
        #         check_in_parts = re.findall(r'\d+', check_in_str)
                
        #         # 提取退房日期的数字
        #         check_out_str = extracted_info['退房日期']
        #         check_out_parts = re.findall(r'\d+', check_out_str)
                
        #         if len(check_in_parts) >= 3 and len(check_out_parts) >= 3:
        #             # 尝试构建日期对象
        #             check_in = datetime.datetime(
        #                 int(check_in_parts[0]), 
        #                 int(check_in_parts[1]), 
        #                 int(check_in_parts[2])
        #             )
        #             check_out = datetime.datetime(
        #                 int(check_out_parts[0]), 
        #                 int(check_out_parts[1]), 
        #                 int(check_out_parts[2])
        #             )
                    
        #             # 计算天数差
        #             days = (check_out - check_in).days
        #             return max(1, days)
        #     except Exception:
        #         pass
                
        return 1 