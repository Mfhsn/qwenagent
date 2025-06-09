import os
import tempfile
from qwen_agent.agents import Assistant
from qwen_agent.utils.output_beautify import typewriter_print

# 导入配置
from config import (
    LLM_CONFIG, 
    SYSTEM_INSTRUCTION, 
    TOOLS
)

# 导入工具模块
from tools.trip_recorder import TripRecorder
from tools.invoice_processor import InvoiceProcessor
from tools.reimbursement_generator import ReimbursementGenerator
from tools.ncc_submission import NCCSubmission
from tools.invoice_image_processor import InvoiceImageProcessor

# 导入辅助功能
from utils.helpers import load_help_document

def create_help_file():
    """创建帮助文档临时文件"""
    help_doc = load_help_document()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.md') as f:
        f.write(help_doc.encode('utf-8'))
        return f.name

def main():
    """主程序入口，运行智能报销Agent"""
    print("=" * 50)
    print("智能报销Agent启动中...")
    print("=" * 50)
    
    # 创建帮助文档临时文件
    help_doc_path = create_help_file()
    
    try:
        # 创建Assistant实例
        bot = Assistant(
            llm=LLM_CONFIG,
            system_message=SYSTEM_INSTRUCTION,
            function_list=TOOLS,
            files=[help_doc_path]
        )
        
        # 运行聊天机器人
        messages = []
        print("\n智能报销助手已准备就绪！")
        print("您可以开始进行差旅报销，包括行程录入、发票上传、报销单生成和NCC提交。")
        print("输入'帮助'或'help'查看使用指南，输入'退出'或'exit'结束会话。")
        print("-" * 50)
        
        try:
            while True:
                query = input('\n用户请求: ')
                
                # 检查退出命令
                if query.lower() in ['退出', 'exit', 'quit']:
                    print("智能报销助手已退出，感谢使用！")
                    break
                
                # 将用户请求添加到聊天历史
                messages.append({'role': 'user', 'content': query})
                
                # 显示处理中状态
                print('处理中...')
                
                # 流式输出回应
                response_plain_text = ''
                print('助手回应:')
                
                for response in bot.run(messages=messages):
                    response_plain_text = typewriter_print(response, response_plain_text)
                
                # 将回应添加到聊天历史
                messages.extend(response)
                print("-" * 50)
                
        except KeyboardInterrupt:
            print("\n程序已被用户中断")
            
    except Exception as e:
        print(f"程序运行出错: {e}")
        
    finally:
        # 清理临时文件
        if os.path.exists(help_doc_path):
            os.remove(help_doc_path)
        print("会话已结束")

if __name__ == '__main__':
    main() 