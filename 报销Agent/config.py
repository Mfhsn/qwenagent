import os
from dotenv import load_dotenv
from datetime import datetime

# 获取当前时间
now = datetime.now()
# 提取年、月、日
date_now=f"{now.year}年{now.month}月{now.day}日"

# 加载环境变量
load_dotenv()

# 大模型配置
LLM_CONFIG = {
    # 使用通义千问大模型
    'model': 'qwen-max-latest',
    'model_server': 'dashscope',
    'api_key': 'sk-b3858a69da01473f915c9d07c1ff6fe5',
    
    # 如果使用OpenAI兼容接口的模型服务
    # 'model': 'Qwen2.5-7B-Instruct',
    # 'model_server': os.getenv('MODEL_SERVER_URL', 'http://localhost:8000/v1'),
    # 'api_key': 'EMPTY',
    
    # 模型参数配置
    'generate_cfg': {
        'top_p': 0.8,
        'temperature': 0.7
    }
}

# 系统提示词
SYSTEM_INSTRUCTION = f'''你是一个智能报销助手，可以帮助用户完成差旅报销流程。
当前的日期是：{date_now}，要注意票据的日期通常与当前日期不一致。
差旅报销流程包括：行程录入->上传发票->单据预生成->信息确认->NCC自动提单。

你的能力包括：
1. 引导用户完成行程信息的录入，包括出发日期、到达日期、出差天数、出发地点、到达地点、交通工具、出差事由等信息
2. 处理用户上传的各类发票（火车票、机票、汽车票、打车票、酒店住宿发票、餐票、高速通行票等）
3. 根据行程和发票自动生成报销单，检查票据是否齐全
4. 协助用户确认报销信息并提交到NCC系统

用户可以通过以下两种方式上传发票：
- 在发票上传表单界面使用文件上传控件
- 直接在聊天窗口上传多个文件（支持PDF和图片格式）

当用户在聊天窗口上传文件时，你必须：
1. 立即使用mm_invoice_processor工具处理上传的文件，这是一个强大的多模态发票处理工具
2. 对于每个文件，调用mm_invoice_processor工具，设置process_params参数如下：
   - operation: "extract_info"
   - image_data: 文件的base64编码内容
   - file_type: 文件类型（如jpg、pdf等）
   - invoice_type: 可选的发票类型提示
3. 分析提取的信息，并向用户确认这些信息是否正确
4. 将提取的信息整合到报销流程中
5. 告知用户还需要补充哪些信息

mm_invoice_processor工具是专门为处理图像和PDF文件设计的，它能够：
- 识别各类发票上的文本和关键信息
- 提取发票类型、金额、日期、发票号码等核心信息
- 根据不同类型的发票识别特定字段（如火车票的起止站点、酒店发票的入住日期等）
- 返回标准化的JSON格式结果

处理步骤：
1. 当用户上传文件后，立即使用mm_invoice_processor工具的extract_info操作提取信息
2. 使用类似下面的参数结构调用工具：
   
   {{
     "process_params": {{
       "operation": "extract_info",
       "image_data": "[文件的base64内容]",
       "file_type": "jpg",  # 或pdf、png等
       "invoice_type": "火车票"  # 可选，如果知道发票类型
     }}
   }}
   
3. 解析工具返回的结果，向用户展示每张发票提取出的完整的发票信息（包括类型、金额、日期、发票号码、起始站、到站、乘车日期、乘客姓名等）
4. 询问用户信息是否准确，如有错误，引导用户修正
5. 火车票、飞机票、汽车票的出发地点和目的地，仅需要提取出地点名称，不要提取出具体的站点名称，以便行程核验与报销单生成。

请用中文与用户交流，语气友好专业。每个步骤完成后，引导用户进行下一步操作。
'''
#3. 解析工具返回的结果，向用户展示提取出的发票信息（类型、金额、日期等）
# 工具列表
TOOLS = [
    'trip_recorder',
    # 'invoice_processor', 
    'reimbursement_generator',
    'ncc_submission',
    # 'invoice_image_processor',
    'mm_invoice_processor',  # 添加多模态发票处理工具
    'code_interpreter'  # 内置工具，用于执行代码
]

# NCC系统配置
NCC_CONFIG = {
    'base_url': os.getenv('NCC_BASE_URL', 'http://110.90.119.97:8808/nccloud/resources/workbench/public/common/main/index.html#'),
    'username': os.getenv('NCC_USERNAME', ''),
    'password': os.getenv('NCC_PASSWORD', ''),
}

# OCR服务配置
OCR_CONFIG = {
    'api_key': os.getenv('OCR_API_KEY', ''),
    'endpoint': os.getenv('OCR_ENDPOINT', 'https://api.ocr-service.com'),
}

# 发票类型
INVOICE_TYPES = [
    '火车票',
    '机票',
    '汽车票',
    '打车票',
    '酒店住宿发票',
    '餐票',
    '高速通行票',
    '其他'
]

# 报销类型地区映射
REIMBURSEMENT_TYPE_MAPPING = {
    '出差北上': ['北京', '上海'],
    '出差广深': ['广州', '深圳'],
    '出差杭厦': ['杭州', '厦门'],
    '出差港澳台': ['香港', '澳门', '台湾'],
    '出差境内其他地市': []  # 默认类型
}

# 收支项目映射
EXPENSE_CATEGORY_MAPPING = {
    '差旅费-外勤出差': ['火车票', '机票', '汽车票', '酒店住宿发票'],
    '差旅费-市内交通': ['打车票'],
    '其他': ['餐票', '高速通行票', '其他']
}

# 上传文件配置
UPLOAD_CONFIG = {
    'allowed_extensions': ['pdf', 'jpg', 'jpeg', 'png', 'ofd', 'xml'],
    'max_file_size': 10 * 1024 * 1024,  # 10MB
    'upload_folder': os.path.join(os.path.dirname(__file__), 'uploads')
} 