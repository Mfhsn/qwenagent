import json
import base64
import tempfile
import os
from typing import Dict, List, Any, Optional, Union
import cv2
import numpy as np
from qwen_agent.tools.base import BaseTool, register_tool
from config import OCR_CONFIG
import fitz  # PyMuPDF
from utils.helpers import validate_pdf_file

@register_tool('invoice_image_processor')
class InvoiceImageProcessor(BaseTool):
    """发票图像处理工具，用于识别和处理发票图像"""
    
    description = '用于处理上传的发票图像，包括OCR识别、图像预处理、旋转校正、PDF转图片等操作。'
    parameters = [{
        'name': 'image_params',
        'type': 'object',
        'description': '图像处理参数',
        'properties': {
            'image_data': {'type': 'string', 'description': '图像的Base64编码或示例图像数据'},
            'file_type': {'type': 'string', 'description': '文件类型，如pdf、jpg、jpeg、png'},
            'invoice_type': {'type': 'string', 'description': '发票类型，如火车票、机票、酒店住宿发票等'},
            'operation': {'type': 'string', 'description': '要执行的操作，如ocr、rotate、enhance、pdf_to_image、extract_info等'}
        },
        'required': ['operation']
    }]
    
    def __init__(self, tool_cfg=None):
        super().__init__(tool_cfg)
    
    def call(self, params: str, **kwargs) -> str:
        """处理发票图像操作请求"""
        try:
            image_params = json.loads(params)['image_params']
            operation = image_params.get('operation', '')
            image_data = image_params.get('image_data', '')
            file_type = image_params.get('file_type', '')
            invoice_type = image_params.get('invoice_type', '')
            
            if not operation:
                return json.dumps({
                    'status': 'error',
                    'message': '未指定图像处理操作'
                }, ensure_ascii=False)
            
            # 根据操作类型执行不同的图像处理
            if operation == 'ocr':
                return self._process_ocr(image_data)
            elif operation == 'rotate':
                return self._process_rotate(image_data, image_params.get('angle', 90))
            elif operation == 'enhance':
                return self._process_enhance(image_data)
            elif operation == 'detect_edges':
                return self._process_detect_edges(image_data)
            elif operation == 'pdf_to_image':
                return self._convert_pdf_to_image(image_data)
            elif operation == 'extract_info':
                return self._extract_invoice_info(image_data, file_type, invoice_type)
            else:
                return json.dumps({
                    'status': 'error',
                    'message': f'不支持的操作：{operation}'
                }, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'图像处理失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _process_ocr(self, image_data: str) -> str:
        """执行OCR识别（模拟实现）"""
        # 在实际应用中，这里会调用OCR服务，如百度OCR、阿里OCR等
        # 以下为模拟实现
        
        if not image_data:
            return json.dumps({
                'status': 'error',
                'message': 'OCR识别失败：未提供图像数据'
            }, ensure_ascii=False)
        
        # 模拟OCR识别结果
        return json.dumps({
            'status': 'success',
            'text': '模拟的OCR识别结果：发票代码：1234567890，发票号码：12345678，金额：298.00元',
            'confidence': 0.95,
            'recognized_fields': {
                'invoice_code': '1234567890',
                'invoice_number': '12345678',
                'amount': '298.00',
                'date': '2023-06-15'
            }
        }, ensure_ascii=False)
    
    def _convert_pdf_to_image(self, pdf_data: str) -> str:
        """将PDF文件转换为图像"""
        if not pdf_data:
            return json.dumps({
                'status': 'error',
                'message': 'PDF转换失败：未提供PDF数据'
            }, ensure_ascii=False)
        
        try:
            # 解码PDF数据
            if ',' in pdf_data:
                pdf_data = pdf_data.split(',')[1]
            
            # 修复Base64 padding问题
            pdf_data = self._fix_base64_padding(pdf_data)
            
            try:
                # 添加错误处理以验证base64数据是否有效
                pdf_bytes = base64.b64decode(pdf_data)
                print(f"成功解码PDF数据，大小: {len(pdf_bytes)} 字节")
            except Exception as decode_err:
                print(f"Base64解码PDF数据失败: {str(decode_err)}")
                return json.dumps({
                    'status': 'error',
                    'message': f'Base64解码PDF数据失败: {str(decode_err)}'
                }, ensure_ascii=False)
            
            # 创建临时PDF文件
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                    temp_pdf.write(pdf_bytes)
                    pdf_path = temp_pdf.name
                print(f"已创建临时PDF文件: {pdf_path}")
            except Exception as temp_err:
                print(f"创建临时PDF文件失败: {str(temp_err)}")
                return json.dumps({
                    'status': 'error',
                    'message': f'创建临时PDF文件失败: {str(temp_err)}'
                }, ensure_ascii=False)
            
            # 验证PDF文件是否有效
            if not validate_pdf_file(pdf_path):
                print(f"无效的PDF文件: {pdf_path}")
                return json.dumps({
                    'status': 'error',
                    'message': '无效的PDF文件，无法转换为图像'
                }, ensure_ascii=False)
            
            # 尝试使用PyMuPDF打开PDF
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)
                print(f"成功打开PDF文件，页数: {page_count}")
                
                images = []
                # 遍历每一页，转换为图像
                for page_num in range(page_count):
                    try:
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 使用2x缩放以获得更好的质量
                        print(f"成功渲染第 {page_num+1} 页，尺寸: {pix.width}x{pix.height}")
                        
                        # 创建临时图像文件
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_img:
                            temp_img_path = temp_img.name
                        
                        # 保存为图像文件
                        pix.save(temp_img_path)
                        print(f"成功保存第 {page_num+1} 页为临时图像: {temp_img_path}")
                        
                        # 读取图像并编码为Base64
                        with open(temp_img_path, 'rb') as f:
                            img_data = f.read()
                            img_base64 = base64.b64encode(img_data).decode('utf-8')
                            image_size = len(img_data)
                            print(f"成功读取并编码图像，大小: {image_size} 字节")
                            images.append(img_base64)
                        
                        # 删除临时图像文件
                        os.unlink(temp_img_path)
                        print(f"已删除临时图像文件: {temp_img_path}")
                        
                    except Exception as page_err:
                        print(f"处理PDF第 {page_num+1} 页失败: {str(page_err)}")
                        continue  # 继续处理下一页
                
                # 关闭PDF文档
                doc.close()
                
                # 如果PyMuPDF方法没有生成任何图像，尝试使用pdf2image作为备选方案
                if not images:
                    print("PyMuPDF未能生成任何图像，尝试使用pdf2image...")
                    images = self._convert_with_pdf2image(pdf_path)
                
                # 删除临时PDF文件
                os.unlink(pdf_path)
                print(f"已删除临时PDF文件: {pdf_path}")
                
                if not images:
                    return json.dumps({
                        'status': 'error',
                        'message': '未能从PDF中提取任何图像'
                    }, ensure_ascii=False)
                
                return json.dumps({
                    'status': 'success',
                    'message': f'成功将PDF转换为{len(images)}张图像',
                    'images': images
                }, ensure_ascii=False)
                
            except Exception as fitz_err:
                print(f"使用PyMuPDF处理PDF失败，尝试使用pdf2image作为备选方案: {str(fitz_err)}")
                
                # 尝试使用pdf2image作为备选方案
                images = self._convert_with_pdf2image(pdf_path)
                
                # 删除临时PDF文件
                os.unlink(pdf_path)
                print(f"已删除临时PDF文件: {pdf_path}")
                
                if not images:
                    return json.dumps({
                        'status': 'error',
                        'message': '未能使用备选方法从PDF中提取任何图像'
                    }, ensure_ascii=False)
                
                return json.dumps({
                    'status': 'success',
                    'message': f'使用备选方法成功将PDF转换为{len(images)}张图像',
                    'images': images
                }, ensure_ascii=False)
            
        except Exception as e:
            print(f"PDF转换为图像的详细错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return json.dumps({
                'status': 'error',
                'message': f'PDF转换为图像失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _convert_with_pdf2image(self, pdf_path: str) -> List[str]:
        """使用pdf2image作为备选方案转换PDF为图像"""
        try:
            from pdf2image import convert_from_path
            
            print(f"使用pdf2image处理: {pdf_path}")
            images = []
            
            # 将PDF转换为PIL图像
            pil_images = convert_from_path(pdf_path, dpi=200)
            print(f"pdf2image成功转换了{len(pil_images)}页")
            
            # 将PIL图像转换为Base64
            for i, pil_image in enumerate(pil_images):
                try:
                    # 创建临时图像文件
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_img:
                        temp_img_path = temp_img.name
                    
                    # 保存PIL图像
                    pil_image.save(temp_img_path, format='PNG')
                    print(f"成功保存第 {i+1} 页为临时图像: {temp_img_path}")
                    
                    # 读取图像并编码为Base64
                    with open(temp_img_path, 'rb') as f:
                        img_data = f.read()
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        image_size = len(img_data)
                        print(f"成功读取并编码图像，大小: {image_size} 字节")
                        images.append(img_base64)
                    
                    # 删除临时图像文件
                    os.unlink(temp_img_path)
                    print(f"已删除临时图像文件: {temp_img_path}")
                    
                except Exception as img_err:
                    print(f"处理pdf2image生成的第 {i+1} 页图像失败: {str(img_err)}")
                    continue
            
            return images
            
        except Exception as e:
            print(f"pdf2image处理失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _extract_invoice_info(self, image_data: str, file_type: str, invoice_type: str) -> str:
        """抽取发票图像中的信息
        
        Args:
            image_data: 图像的Base64编码
            file_type: 文件类型，例如'jpg'、'png'等
            invoice_type: 发票类型，例如'火车票'、'机票'等
            
        Returns:
            包含发票信息的JSON字符串
        """
        if not image_data:
            return json.dumps({
                'status': 'error',
                'message': '信息抽取失败：未提供图像数据'
            }, ensure_ascii=False)
        
        try:
            # 图像预处理
            image = self._decode_image(image_data)
            if image is None:
                return json.dumps({
                    'status': 'error',
                    'message': '图像解码失败'
                }, ensure_ascii=False)
            
            # 图像增强（可选）
            # enhanced_image = self._enhance_image(image)
            
            # 这里需要实现自定义的发票识别逻辑
            # 为不同类型的发票提供不同的信息抽取实现
            if invoice_type in ['火车票', '机票', '汽车票']:
                return self._extract_transport_ticket_info(image, invoice_type)
            elif invoice_type == '酒店住宿发票':
                return self._extract_hotel_invoice_info(image)
            elif invoice_type == '打车票':
                return self._extract_taxi_receipt_info(image)
            else:
                return self._extract_general_invoice_info(image, invoice_type)
                
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'发票信息抽取失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _extract_transport_ticket_info(self, image: np.ndarray, ticket_type: str) -> str:
        """抽取交通票据（火车票、机票、汽车票）信息"""
        # 这里实现具体的交通票据识别逻辑
        # 实际项目中需要接入OCR服务或自己训练模型
        
        # 模拟识别结果
        return json.dumps({
            'status': 'success',
            'message': f'成功识别{ticket_type}信息',
            'invoice_info': {
                'invoice_type': ticket_type,
                'invoice_id': f'T{ticket_type[0]}{self._generate_id()}',
                'date': '2023-09-15',
                'departure': '上海',
                'destination': '北京',
                'amount': 550.00,
                'passenger': '张三',
                'ticket_number': f'E{self._generate_id()}'
            }
        }, ensure_ascii=False)
    
    def _extract_hotel_invoice_info(self, image: np.ndarray) -> str:
        """抽取酒店住宿发票信息"""
        # 模拟识别结果
        return json.dumps({
            'status': 'success',
            'message': '成功识别酒店住宿发票信息',
            'invoice_info': {
                'invoice_type': '酒店住宿发票',
                'invoice_id': f'H{self._generate_id()}',
                'hotel_name': '如家酒店',
                'check_in_date': '2023-09-15',
                'check_out_date': '2023-09-17',
                'nights': 2,
                'amount': 398.00,
                'guest_name': '张三',
                'invoice_code': f'HT{self._generate_id()}'
            }
        }, ensure_ascii=False)
    
    def _extract_taxi_receipt_info(self, image: np.ndarray) -> str:
        """抽取打车票信息"""
        # 模拟识别结果
        return json.dumps({
            'status': 'success',
            'message': '成功识别打车票信息',
            'invoice_info': {
                'invoice_type': '打车票',
                'invoice_id': f'TX{self._generate_id()}',
                'date': '2023-09-16',
                'amount': 45.50,
                'start_location': '上海火车站',
                'end_location': '上海浦东国际机场',
                'taxi_number': f'沪A{self._generate_id()[:5]}'
            }
        }, ensure_ascii=False)
    
    def _extract_general_invoice_info(self, image: np.ndarray, invoice_type: str) -> str:
        """抽取通用发票信息"""
        # 模拟识别结果
        return json.dumps({
            'status': 'success',
            'message': f'成功识别{invoice_type}信息',
            'invoice_info': {
                'invoice_type': invoice_type,
                'invoice_id': f'G{self._generate_id()}',
                'date': '2023-09-16',
                'amount': 120.00,
                'details': f'{invoice_type}相关费用',
                'seller': '某商家',
                'buyer': '某公司'
            }
        }, ensure_ascii=False)
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        import random
        return ''.join([str(random.randint(0, 9)) for _ in range(8)])
    
    def _process_rotate(self, image_data: str, angle: int) -> str:
        """旋转图像"""
        if not image_data:
            return json.dumps({
                'status': 'error',
                'message': '图像旋转失败：未提供图像数据'
            }, ensure_ascii=False)
        
        try:
            image = self._decode_image(image_data)
            if image is None:
                return json.dumps({
                    'status': 'error',
                    'message': '图像解码失败'
                }, ensure_ascii=False)
            
            # 定义旋转方式
            if angle == 90:
                rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            elif angle == 180:
                rotated = cv2.rotate(image, cv2.ROTATE_180)
            elif angle == 270:
                rotated = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                # 对于非90度的倍数，使用更复杂的旋转方法
                h, w = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(image, M, (w, h))
                
            rotated_encoded = self._encode_image(rotated)
            
            return json.dumps({
                'status': 'success',
                'message': f'图像已旋转 {angle} 度',
                'image_data': rotated_encoded
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'图像旋转失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _process_enhance(self, image_data: str) -> str:
        """增强图像质量"""
        if not image_data:
            return json.dumps({
                'status': 'error',
                'message': '图像增强失败：未提供图像数据'
            }, ensure_ascii=False)
        
        try:
            image = self._decode_image(image_data)
            if image is None:
                return json.dumps({
                    'status': 'error',
                    'message': '图像解码失败'
                }, ensure_ascii=False)
            
            enhanced = self._enhance_image(image)
            enhanced_encoded = self._encode_image(enhanced)
            
            return json.dumps({
                'status': 'success',
                'message': '图像增强处理完成，提高了对比度和清晰度',
                'image_data': enhanced_encoded
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'图像增强失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _process_detect_edges(self, image_data: str) -> str:
        """检测图像边缘"""
        if not image_data:
            return json.dumps({
                'status': 'error',
                'message': '边缘检测失败：未提供图像数据'
            }, ensure_ascii=False)
        
        try:
            image = self._decode_image(image_data)
            if image is None:
                return json.dumps({
                    'status': 'error',
                    'message': '图像解码失败'
                }, ensure_ascii=False)
            
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 应用边缘检测
            edges = cv2.Canny(gray, 100, 200)
            
            # 转回彩色以便显示
            edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            edges_encoded = self._encode_image(edges_color)
            
            return json.dumps({
                'status': 'success',
                'message': '图像边缘检测完成，有助于识别发票轮廓',
                'image_data': edges_encoded
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                'status': 'error',
                'message': f'边缘检测失败: {str(e)}'
            }, ensure_ascii=False)
    
    def _decode_image(self, image_data: str) -> Optional[np.ndarray]:
        """解码Base64图像数据"""
        try:
            # 检查输入数据
            if not image_data:
                print("图像解码失败: 未提供图像数据")
                return None
                
            # 移除可能的前缀，如 "data:image/jpeg;base64,"
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            # 修复Base64 padding问题
            image_data = self._fix_base64_padding(image_data)
                
            # 解码Base64
            try:
                image_bytes = base64.b64decode(image_data)
                print(f"成功解码图像数据，大小: {len(image_bytes)} 字节")
            except Exception as decode_err:
                print(f"Base64解码图像数据失败: {str(decode_err)}")
                return None
            
            # 创建临时文件
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(image_bytes)
                    temp_path = temp_file.name
                print(f"已创建临时图像文件: {temp_path}")
            except Exception as temp_err:
                print(f"创建临时图像文件失败: {str(temp_err)}")
                return None
            
            # 检查临时文件是否存在且有效
            if not os.path.exists(temp_path):
                print(f"临时图像文件不存在: {temp_path}")
                return None
                
            file_size = os.path.getsize(temp_path)
            if file_size == 0:
                print(f"临时图像文件为空: {temp_path}")
                os.unlink(temp_path)
                return None
            
            # 读取图像
            try:
                image = cv2.imread(temp_path)
                
                if image is None:
                    print(f"OpenCV无法读取图像文件: {temp_path}")
                    # 打印文件的前几个字节以帮助诊断
                    with open(temp_path, 'rb') as f:
                        header = f.read(20)
                    print(f"文件头部字节: {header}")
                else:
                    print(f"成功读取图像，尺寸: {image.shape}")
            except Exception as cv_err:
                print(f"OpenCV读取图像失败: {str(cv_err)}")
                os.unlink(temp_path)
                return None
            
            # 删除临时文件
            os.unlink(temp_path)
            print(f"已删除临时图像文件: {temp_path}")
            
            return image
        except Exception as e:
            print(f"图像解码过程中发生未知错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _log_base64_debug_info(self, data: str) -> None:
        """打印Base64编码的调试信息，帮助诊断问题"""
        try:
            # 打印长度
            length = len(data)
            print(f"Base64字符串长度: {length}")
            print(f"除以4的余数: {length % 4}")
            
            # 检查是否包含非法字符
            allowed_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
            illegal_chars = set(data) - allowed_chars
            if illegal_chars:
                print(f"发现非法字符: {illegal_chars}")
            
            # 检查填充情况
            padding_count = data.count('=')
            print(f"填充符数量: {padding_count}")
            
            # 打印前20个字符和后20个字符作为参考
            print(f"前20个字符: {data[:20]}")
            print(f"后20个字符: {data[-20:] if len(data) > 20 else data}")
        except Exception as e:
            print(f"打印Base64调试信息时出错: {str(e)}")
            
    def _fix_base64_padding(self, data: str) -> str:
        """修复Base64编码的padding问题
        
        Base64编码的字符串长度应该是4的倍数，如果不是，需要添加=号作为填充
        """
        # 打印调试信息
        self._log_base64_debug_info(data)
        
        # 修复padding
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
            print(f"已添加{4 - missing_padding}个'='字符作为填充")
        return data
    
    def _encode_image(self, image: np.ndarray) -> str:
        """将图像编码为Base64"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                cv2.imwrite(temp_file.name, image)
                temp_path = temp_file.name
                
            # 读取文件并编码为Base64
            with open(temp_path, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
                
            # 删除临时文件
            os.unlink(temp_path)
            
            return encoded
        except Exception as e:
            print(f"图像编码失败: {str(e)}")
            return ""
    
    def _enhance_image(self, image: np.ndarray) -> np.ndarray:
        """增强图像质量"""
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 自适应直方图均衡
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # 去噪
            denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
            
            # 转换回彩色
            result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
            
            return result
        except Exception as e:
            print(f"图像增强失败: {str(e)}")
            return image 