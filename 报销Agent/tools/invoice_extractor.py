import os
import base64
import json
import re
import tempfile
from typing import Dict, Any, Optional, Union
from openai import OpenAI
from PIL import Image
import datetime

class InvoiceExtractor:
    def __init__(self, api_key=None):
        self.api_key = api_key or "sk-b3858a69da01473f915c9d07c1ff6fe5"
    
    def encode_image(self, image_path):
        """将图片转换为base64编码"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def encode_image_from_bytes(self, image_bytes):
        """将图片字节数据转换为base64编码"""
        return base64.b64encode(image_bytes).decode("utf-8")

    def extract_json_from_markdown(self, markdown_text):
        """从Markdown文本中提取JSON数据"""
        # 尝试直接解析JSON
        try:
            return json.loads(markdown_text)
        except json.JSONDecodeError:
            pass
        
        # 使用正则表达式匹配```json和```之间的内容
        pattern = r'```(?:json)?\s*(.*?)\s*```'
        # re.DOTALL标志使.能够匹配换行符
        match = re.search(pattern, markdown_text, re.DOTALL)

        if match:
            json_str = match.group(1)  # 提取JSON字符串部分
            try:
                # 解析JSON字符串为Python字典
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError as e:
                return {"error": f"JSON解析错误: {str(e)}", "raw_content": json_str}
        
        # 尝试匹配{}之间的内容
        pattern = r'({.*})'
        match = re.search(pattern, markdown_text, re.DOTALL)
        if match:
            try:
                json_str = match.group(1)
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                pass
        
        return {"error": "未找到JSON数据", "raw_content": markdown_text}

    def extract_info(self, image_path, invoice_type=None):
        """从发票图片中提取信息"""
        try:
            print(f"invoice_extractor.extract_info被调用, 图片路径: {image_path}, 发票类型: {invoice_type}")
            
            # 验证图像文件是否存在且可读
            if not os.path.exists(image_path):
                return {"error": f"图像文件不存在: {image_path}"}
                
            try:
                # 尝试验证图像是否有效
                try:
                    with Image.open(image_path) as img:
                        # 检查图像格式并转换为RGB以确保兼容性
                        if img.mode != 'RGB':
                            rgb_img = img.convert('RGB')
                            # 保存为临时JPEG文件
                            temp_path = image_path + ".jpg"
                            rgb_img.save(temp_path, 'JPEG')
                            print(f"已将图像转换为RGB格式并保存为: {temp_path}")
                            image_path = temp_path
                except Exception as img_err:
                    print(f"图像验证失败: {str(img_err)}")
                    return {"error": f"图像验证失败: {str(img_err)}"}
            except ImportError:
                print("PIL库未安装，跳过图像验证")
            
            # 编码图像为base64
            try:
                base64_image = self.encode_image(image_path)
                print(f"成功将图片编码为base64, 长度: {len(base64_image)}")
                
                # 检查base64编码是否有效
                if len(base64_image) < 100:
                    print(f"警告: base64编码长度过短，可能是空图像或编码错误: {len(base64_image)}")
                    return {"error": "图像编码异常，长度过短"}
            except Exception as encode_err:
                print(f"图像编码失败: {str(encode_err)}")
                return {"error": f"图像编码失败: {str(encode_err)}"}

            # 创建OpenAI客户端
            try:
                client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                )
                print("成功创建OpenAI客户端")
            except Exception as client_err:
                print(f"创建OpenAI客户端失败: {str(client_err)}")
                return {"error": f"创建API客户端失败: {str(client_err)}"}
            
            # 根据发票类型调整提示词
            prompt = """
            提取图片中的发票信息，返回JSON格式。
            如果是交通发票，需要提取的字段为[乘客姓名,发票号码,起始站,到站,燃油费,票价,乘坐日期,电子客票号,开车时间,车次,座号,日期,金额,销售方名称]。
            如果是住宿发票，需要提取的字段为[酒店名称,销售方名称,入住日期,退房日期,住宿天数,票价,发票号码,房间号,开票日期（记为"日期"字段）,金额,税率/征收率,住宿人姓名,住宿地址]。
            如果是餐饮发票，需要提取的字段为[商家名称,销售方名称,消费日期,消费项目,金额,发票号码,就餐人数,消费地址]。
            如果是打车发票，需要提取的字段为[起点,终点,上车时间,下车时间,里程,金额,发票号码,车牌号,出租车公司]。
            
            请识别所有可见的文字信息，包括：
            - 销售方名称（开票方、商家名称、酒店名称等）
            - 购买方信息（如果有）
            - 所有日期信息
            - 金额信息
            - 发票代码、发票号码
            - 税务相关信息
            - 地址信息
            - 其他关键业务信息
            
            确保不遗漏任何可见的字段信息。
            若内容被遮挡或无法识别，请勿将其他字段内容填入。
            请直接以JSON格式返回，不要有任何其他文字说明。
            """
            
            if invoice_type:
                prompt = f"""
                这是一张{invoice_type}，请提取其中的关键信息，以JSON格式返回。
                请识别所有可见的日期信息和金额信息，确保不遗漏任何重要字段。
                请直接以JSON格式返回，不要有任何其他文字说明。
                """
            
            print(f"使用提示词: {prompt}")
            
            # 调用大模型API
            try:
                print("开始调用OpenAI API...")
                
                # 构建图片URL（避免直接在代码中输出完整的base64编码）
                image_url_with_prefix = f"data:image/jpeg;base64,{base64_image}"
                if len(image_url_with_prefix) > 100:
                    display_url = image_url_with_prefix[:50] + "..." + image_url_with_prefix[-20:]
                else:
                    display_url = image_url_with_prefix
                print(f"图片URL(部分): {display_url}")
                
                # 重试机制
                max_retries = 2
                for retry in range(max_retries + 1):
                    try:
                        completion = client.chat.completions.create(
                            model="qwen2.5-vl-72b-instruct",  # 使用通义千问大模型
                            messages=[{"role": "user", "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]}],
                            temperature=0,  # 降低温度以获得更确定性的结果
                            max_tokens=1000  # 限制token数量提高响应速度
                        )
                        break  # 如果成功则跳出重试循环
                    except Exception as api_err:
                        if retry < max_retries:
                            wait_time = (retry + 1) * 2  # 逐渐增加等待时间
                            print(f"API调用失败，第{retry+1}次重试，等待{wait_time}秒: {str(api_err)}")
                            import time
                            time.sleep(wait_time)
                        else:
                            raise  # 最后一次重试仍失败，抛出异常
                
                print(f"API调用成功，开始处理响应...")
                response_str = completion.model_dump_json()
                response_dict = json.loads(response_str)
                content = response_dict["choices"][0]["message"]["content"]
                print(f"获取到响应内容: {content[:100]}...")
                
                # 解析JSON数据
                extracted_info = self.extract_json_from_markdown(content)
                print(f"从响应中提取JSON数据: {extracted_info}")
                
                # 检查是否有错误
                if isinstance(extracted_info, dict) and "error" in extracted_info:
                    return extracted_info
                
                # 增加发票类型识别
                if isinstance(extracted_info, dict):
                    # 交通票据识别：检查是否有明确的交通相关属性
                    is_transport = False
                    
                    # 检查关键字段
                    if extracted_info.get('起始站') and extracted_info.get('到站'):
                        is_transport = True
                    # 检查是否有其他交通相关字段
                    elif any(key in extracted_info for key in ['车次', '乘车日期', '开车时间', '座号', '列车号', '航班号', '车牌号']):
                        is_transport = True
                    # 检查是否有交通相关关键词
                    elif any(keyword in str(extracted_info) for keyword in ['火车', '高铁', '动车', '汽车', '客车', '飞机', '航班', '出租车', '公交']):
                        is_transport = True
                    
                    if is_transport:
                        extracted_info['发票类型'] = '交通票据'
                        # 如果缺少起始站或到站信息，添加警告
                        if not extracted_info.get('起始站'):
                            extracted_info['警告'] = extracted_info.get('警告', [])
                            if isinstance(extracted_info['警告'], list):
                                extracted_info['警告'].append('缺少起始站信息')
                            else:
                                extracted_info['警告'] = ['缺少起始站信息']
                        if not extracted_info.get('到站'):
                            extracted_info['警告'] = extracted_info.get('警告', [])
                            if isinstance(extracted_info['警告'], list):
                                extracted_info['警告'].append('缺少到站信息')
                            else:
                                extracted_info['警告'] = ['缺少到站信息']
                    # 住宿票据识别逻辑
                    elif extracted_info.get('入住日期') or extracted_info.get('退房日期') or (extracted_info.get('日期') and ('酒店' in str(extracted_info) or '住宿' in str(extracted_info))):
                        extracted_info['发票类型'] = '住宿票据'
                        
                        # 确保住宿票据有日期字段
                        if not extracted_info.get('日期') and (extracted_info.get('入住日期') or extracted_info.get('退房日期')):
                            # 如果没有日期字段但有入住日期，将入住日期作为日期
                            extracted_info['日期'] = extracted_info.get('入住日期', '')
                    else:
                        extracted_info['发票类型'] = '其他票据'
                
                # 清理临时文件
                if image_path.endswith(".jpg") and image_path != os.path.splitext(image_path)[0]:
                    try:
                        os.remove(image_path)
                        print(f"已删除临时转换文件: {image_path}")
                    except Exception as del_err:
                        print(f"删除临时文件失败: {str(del_err)}")
                
                return extracted_info
            
            except Exception as api_error:
                print(f"API调用过程中出错: {str(api_error)}")
                import traceback
                traceback.print_exc()
                
                # 尝试使用备用方法提取信息
                try:
                    print("API调用失败，尝试使用本地备用方法提取信息...")
                    
                    # 使用OCR或其他备用方法提取文本
                    # 这里可以实现简单的备用提取逻辑
                    extracted_info = self._backup_extract_info(image_path, invoice_type)
                    if extracted_info:
                        print("成功使用备用方法提取信息")
                        return extracted_info
                except Exception as backup_err:
                    print(f"备用方法也失败: {str(backup_err)}")
                
                return {"error": f"API调用失败: {str(api_error)}"}
            
        except Exception as e:
            print(f"提取信息总体出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": f"提取信息时出错: {str(e)}"}
    
    def _get_prompt_by_invoice_type(self, invoice_type=None):
        """根据发票类型获取对应的提示语
        
        Args:
            invoice_type: 发票类型，如"火车票"、"机票"、"酒店住宿发票"等
            
        Returns:
            str: 提示语
        """
        # 基础提示
        base_prompt = """
        请仔细分析图像中的发票或票据信息，以JSON格式返回关键数据。
        请识别所有可见的日期信息和金额信息，确保不遗漏任何重要字段。
        若内容被遮挡或模糊不清，请勿猜测，将对应字段留空。
        请直接以JSON格式返回，不要有任何其他文字说明。
        """
        
        if not invoice_type or invoice_type in ["火车票", "机票", "汽车票"]:
            return f"""
            {base_prompt}
            这是一张交通票据（可能是火车票/机票/汽车票）。
            请提取以下关键字段：
            - 发票号码/电子客票号
            - 日期（票据开具日期）
            - 乘车/乘机日期
            - 起始站/出发地
            - 到站/目的地
            - 票价/金额
            - 乘客姓名/旅客信息
            - 车次/航班号
            - 座位信息
            - 时间信息（出发时间/到达时间）
            """
        elif invoice_type == "酒店住宿发票":
            return f"""
            {base_prompt}
            这是一张酒店住宿发票。
            请提取以下关键字段：
            - 发票号码
            - 日期（开票日期）
            - 酒店名称
            - 入住日期
            - 退房日期
            - 住宿天数
            - 房间号/房型
            - 住宿人姓名
            - 金额/票价
            """
        elif invoice_type == "打车票":
            return f"""
            {base_prompt}
            这是一张打车票/出租车发票。
            请提取以下关键字段：
            - 发票号码
            - 日期
            - 金额/票价
            - 上车地点/起点
            - 下车地点/终点
            - 车牌号
            - 里程数
            """
        elif invoice_type == "餐票":
            return f"""
            {base_prompt}
            这是一张餐饮发票/餐票。
            请提取以下关键字段：
            - 发票号码
            - 日期
            - 金额/票价
            - 商家名称/餐厅名称
            - 消费项目
            - 人数（如有）
            """
        else:
            return f"""
            {base_prompt}
            请识别这张发票/票据的类型，并提取关键信息，包括但不限于：
            - 发票类型
            - 发票号码
            - 日期
            - 金额/票价
            - 发票内容/项目描述
            - 其他关键信息
            """
    
    def _standardize_invoice_info(self, extracted_info, invoice_type=None):
        """标准化发票信息以符合系统需求
        
        Args:
            extracted_info: 从图片中提取的原始信息
            invoice_type: 发票类型提示
            
        Returns:
            Dict: 标准化后的发票信息
        """
        if not isinstance(extracted_info, dict):
            return {"error": "提取的信息格式不正确"}
            
        # 判断发票类型
        detected_type = self._detect_invoice_type(extracted_info, invoice_type)
        
        # 标准化字段
        standardized = {
            "invoice_type": detected_type,
            "amount": self._extract_amount(extracted_info),
            "date": self._extract_date(extracted_info),
            "invoice_id": extracted_info.get("发票号码", ""),
        }
        
        # 根据不同发票类型添加特定字段
        if detected_type in ["火车票", "机票", "汽车票"]:
            standardized.update({
                "departure": extracted_info.get("起始站", extracted_info.get("出发地", "")),
                "destination": extracted_info.get("到站", extracted_info.get("目的地", "")),
                "passenger": extracted_info.get("乘客姓名", extracted_info.get("旅客信息", "")),
                "ticket_number": extracted_info.get("电子客票号", extracted_info.get("票号", "")),
                "trip_date": extracted_info.get("乘车日期", extracted_info.get("乘机日期", "")),
                "transport_number": extracted_info.get("车次", extracted_info.get("航班号", "")),
                "seat_info": extracted_info.get("座位信息", extracted_info.get("座号", "")),
            })
        elif detected_type == "酒店住宿发票":
            standardized.update({
                "hotel_name": extracted_info.get("酒店名称", ""),
                "check_in_date": extracted_info.get("入住日期", ""),
                "check_out_date": extracted_info.get("退房日期", ""),
                "nights": self._extract_nights(extracted_info),
                "guest_name": extracted_info.get("住宿人姓名", ""),
                "room_info": extracted_info.get("房间号", extracted_info.get("房型", "")),
            })
        elif detected_type == "打车票":
            standardized.update({
                "start_location": extracted_info.get("上车地点", extracted_info.get("起点", "")),
                "end_location": extracted_info.get("下车地点", extracted_info.get("终点", "")),
                "taxi_number": extracted_info.get("车牌号", ""),
                "distance": extracted_info.get("里程数", ""),
            })
        elif detected_type == "餐票":
            standardized.update({
                "restaurant_name": extracted_info.get("商家名称", extracted_info.get("餐厅名称", "")),
                "items": extracted_info.get("消费项目", ""),
                "person_count": extracted_info.get("人数", ""),
            })
            
        # 保存原始提取数据以供参考
        standardized["raw_extracted_info"] = extracted_info
        
        return standardized
    
    def _detect_invoice_type(self, extracted_info, provided_type=None):
        """检测发票类型
        
        Args:
            extracted_info: 提取的信息
            provided_type: 外部提供的类型提示
            
        Returns:
            str: 发票类型
        """
        # 如果提供了类型，优先使用
        if provided_type:
            return provided_type
            
        # 从提取信息中获取类型
        if "发票类型" in extracted_info:
            type_map = {
                "交通票据": "火车票",  # 默认归类为火车票
                "住宿票据": "酒店住宿发票"
            }
            return type_map.get(extracted_info["发票类型"], extracted_info["发票类型"])
            
        # 根据特征判断类型
        if any(key in extracted_info for key in ["起始站", "到站", "车次", "航班号"]):
            if "航班" in str(extracted_info) or "机场" in str(extracted_info):
                return "机票"
            return "火车票"
        elif any(key in extracted_info for key in ["入住日期", "退房日期", "酒店名称"]):
            return "酒店住宿发票"
        elif any(key in extracted_info for key in ["上车地点", "下车地点", "车牌号"]):
            return "打车票"
        elif any(key in extracted_info for key in ["餐厅", "消费项目", "人数"]) or "餐" in str(extracted_info):
            return "餐票"
        elif "高速" in str(extracted_info) or "通行" in str(extracted_info):
            return "高速通行票"
            
        # 默认类型
        return "其他"
    
    def _extract_amount(self, extracted_info):
        """提取金额信息
        
        Args:
            extracted_info: 提取的信息
            
        Returns:
            float: 金额，如果无法提取则返回0
        """
        # 尝试从不同可能的字段中提取金额
        amount_fields = ["金额", "票价", "总金额", "应收金额", "消费金额"]
        
        for field in amount_fields:
            if field in extracted_info:
                try:
                    # 处理可能的字符串格式，如"￥100.00"
                    amount_str = str(extracted_info[field])
                    # 移除非数字字符（保留小数点）
                    amount_str = re.sub(r'[^\d.]', '', amount_str)
                    return float(amount_str)
                except (ValueError, TypeError):
                    continue
                    
        return 0.0
    
    def _extract_date(self, extracted_info):
        """提取日期信息
        
        Args:
            extracted_info: 提取的信息
            
        Returns:
            str: 日期，格式为YYYY-MM-DD，如果无法提取则返回空字符串
        """
        # 尝试从不同可能的字段中提取日期
        date_fields = ["日期", "开票日期", "乘车日期", "乘机日期", "入住日期", "发票日期"]
        
        for field in date_fields:
            if field in extracted_info:
                date_str = str(extracted_info[field])
                
                # 尝试标准化日期格式
                try:
                    # 处理常见的日期格式
                    import datetime
                    
                    # 移除非数字和分隔符
                    date_str = re.sub(r'[^\d-/年月日]', '', date_str)
                    
                    # 处理中文日期格式
                    if any(char in date_str for char in ['年', '月', '日']):
                        date_str = date_str.replace('年', '-').replace('月', '-').replace('日', '')
                    
                    # 处理斜杠分隔符
                    date_str = date_str.replace('/', '-')
                    
                    # 提取数字部分
                    parts = re.findall(r'\d+', date_str)
                    
                    if len(parts) >= 3:
                        year, month, day = parts[0], parts[1], parts[2]
                        
                        # 确保年份为4位数
                        if len(year) == 2:
                            year = '20' + year
                            
                        # 确保月日为两位数
                        month = month.zfill(2)
                        day = day.zfill(2)
                        
                        return f"{year}-{month}-{day}"
                    
                except Exception:
                    continue
                    
        return ""
    
    def _extract_nights(self, extracted_info):
        """提取住宿天数
        
        Args:
            extracted_info: 提取的信息
            
        Returns:
            int: 住宿天数，如果无法提取则返回1
        """
        # 直接提取
        if "住宿天数" in extracted_info:
            try:
                return int(str(extracted_info["住宿天数"]).strip())
            except (ValueError, TypeError):
                pass
                
        # 根据入住和退房日期计算
        if "入住日期" in extracted_info and "退房日期" in extracted_info:
            try:
                import datetime
                
                check_in = self._extract_date({"日期": extracted_info["入住日期"]})
                check_out = self._extract_date({"日期": extracted_info["退房日期"]})
                
                if check_in and check_out:
                    check_in_date = datetime.datetime.strptime(check_in, "%Y-%m-%d")
                    check_out_date = datetime.datetime.strptime(check_out, "%Y-%m-%d")
                    
                    delta = check_out_date - check_in_date
                    return max(1, delta.days)
            except Exception:
                pass
                
        # 默认返回1天
        return 1 

    def _backup_extract_info(self, image_path, invoice_type=None):
        """备用的信息提取方法，当API调用失败时使用"""
        try:
            # 这里可以实现一个简单的备用方法
            # 例如，对常见票据类型返回基本信息结构
            
            if invoice_type == "火车票":
                return {
                    "发票类型": "交通票据",
                    "日期": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "金额": 0.0,
                    "发票号码": "未能识别",
                    "起始站": "未能识别",
                    "到站": "未能识别",
                    "备注": "由备用方法生成，信息不完整"
                }
            elif invoice_type == "酒店住宿发票":
                return {
                    "发票类型": "住宿票据",
                    "日期": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "金额": 0.0,
                    "发票号码": "未能识别",
                    "入住日期": "",
                    "退房日期": "",
                    "备注": "由备用方法生成，信息不完整"
                }
            else:
                # 默认返回最基本的结构
                return {
                    "发票类型": "其他票据",
                    "日期": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "金额": 0.0,
                    "发票号码": "未能识别",
                    "备注": "由备用方法生成，信息不完整"
                }
                
        except Exception as e:
            print(f"备用提取方法出错: {str(e)}")
            return None 