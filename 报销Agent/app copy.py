import os
import json
import tempfile
import base64
import streamlit as st
from datetime import datetime
import pandas as pd

# 导入配置
from config import (
    LLM_CONFIG, 
    SYSTEM_INSTRUCTION, 
    TOOLS,
    INVOICE_TYPES
)

# 导入工具类
from tools.trip_recorder import TripRecorder
from tools.invoice_processor import InvoiceProcessor
from tools.reimbursement_generator import ReimbursementGenerator
from tools.ncc_submission import NCCSubmission
from tools.invoice_image_processor import InvoiceImageProcessor
from tools.mm_invoice_processor import MMInvoiceProcessor

# 导入辅助函数
from utils.helpers import (
    generate_markdown_table,
    validate_date_format,
    load_help_document,
    group_invoices_by_type,
    summarize_invoices,
    validate_pdf_file
)

# 从Qwen-Agent导入Assistant
from qwen_agent.agents import Assistant
from qwen_agent.utils.output_beautify import typewriter_print

# 设置页面标题和图标
st.set_page_config(
    page_title="智能报销助手",
    page_icon="📋",
    layout="wide"
)

# 创建会话状态
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'bot' not in st.session_state:
    # 创建临时帮助文件
    help_doc = load_help_document()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.md') as f:
        f.write(help_doc.encode('utf-8'))
        help_doc_path = f.name
        
    # 创建Agent实例
    st.session_state.bot = Assistant(
        llm=LLM_CONFIG,
        system_message=SYSTEM_INSTRUCTION,
        function_list=TOOLS,
        files=[help_doc_path]
    )
    st.session_state.help_doc_path = help_doc_path

if 'current_step' not in st.session_state:
    st.session_state.current_step = "开始"

if 'trips' not in st.session_state:
    st.session_state.trips = []

if 'invoices' not in st.session_state:
    st.session_state.invoices = []

if 'reimbursement_form' not in st.session_state:
    st.session_state.reimbursement_form = None

# 添加文件上传状态管理
if 'need_clear_uploads' not in st.session_state:
    st.session_state.need_clear_uploads = False

# 添加文件上传控件的动态key
if 'upload_widget_key' not in st.session_state:
    st.session_state.upload_widget_key = "chat_file_uploader"

# 添加已处理文件跟踪
if 'all_processed_files' not in st.session_state:
    st.session_state.all_processed_files = []

# 添加系统状态追踪
if 'has_processed_files' not in st.session_state:
    st.session_state.has_processed_files = False

# 添加原始文件内容存储
if 'original_file_contents' not in st.session_state:
    st.session_state.original_file_contents = {}

# 定义页面布局
def render_header():
    """渲染页面头部"""
    st.title("📋 智能报销助手")
    st.markdown("基于大模型的智能报销流程助手，帮您快速完成差旅报销")
    
    # 水平分割线
    st.markdown("---")

def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("报销进度")
        steps = ["开始", "行程录入", "发票上传", "报销单生成", "提交NCC"]
        
        # 显示当前步骤
        for i, step in enumerate(steps):
            if step == st.session_state.current_step:
                st.markdown(f"**→ {i+1}. {step}**")
            else:
                st.markdown(f"{i+1}. {step}")
        
        st.markdown("---")
        
        # 显示汇总信息
        st.subheader("当前汇总")
        st.markdown(f"**行程数量**: {len(st.session_state.trips)}")
        st.markdown(f"**发票数量**: {len(st.session_state.invoices)}")
        
        if st.session_state.invoices:
            total_amount = sum(invoice.get('amount', 0) for invoice in st.session_state.invoices)
            st.markdown(f"**总金额**: ¥{total_amount:.2f}")
        
        st.markdown("---")
        
        # 文件处理状态重置按钮
        if st.button("清除已处理文件记录"):
            st.session_state.all_processed_files = []
            st.session_state.original_file_contents = {}
            st.success("已清除所有已处理文件记录！可以重新上传并处理文件了。")
            st.rerun()
        
        # 重置按钮
        if st.button("重置所有数据"):
            st.session_state.messages = []
            st.session_state.trips = []
            st.session_state.invoices = []
            st.session_state.reimbursement_form = None
            st.session_state.current_step = "开始"
            # 同时清除文件处理状态
            st.session_state.all_processed_files = []
            st.session_state.original_file_contents = {}
            st.rerun()

def render_chat_interface():
    """渲染聊天界面"""
    # 显示聊天历史
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        
        if role == "user":
            st.chat_message("user").write(content)
            # 如果消息中包含文件信息，显示文件预览
            if "files" in message:
                for file_info in message["files"]:
                    with st.expander(f"文件: {file_info['filename']}"):
                        st.write(f"类型: {file_info['file_type']}")
                        
                        # 获取文件内容，优先从会话状态中获取
                        file_content = None
                        file_id = file_info.get("file_id")
                        if file_id and file_id in st.session_state.get("original_file_contents", {}):
                            file_content = st.session_state.original_file_contents[file_id]["content"]
                        else:
                            file_content = file_info.get("content", "")
                        
                        if file_info['file_type'].lower() in ['jpg', 'jpeg', 'png']:
                            try:
                                # 解码base64为字节
                                if file_content and len(file_content) > 100:  # 确保是有效内容
                                    file_bytes = base64.b64decode(file_content)
                                    st.image(file_bytes, caption=file_info['filename'])
                                else:
                                    st.warning("无法显示图片: 内容无效或不完整")
                            except Exception as e:
                                st.error(f"无法显示图片: {str(e)}")
                        elif file_info['file_type'].lower() == 'pdf':
                            st.write("PDF文件（已上传，待处理）")
                        else:
                            st.write(f"已上传{file_info['file_type']}文件")
        else:
            st.chat_message("assistant").write(content)
    
    # 显示工具区域（根据当前步骤）
    if st.session_state.current_step == "行程录入":
        render_trip_input_form()
    elif st.session_state.current_step == "发票上传":
        render_invoice_upload_form()
    elif st.session_state.current_step == "报销单生成":
        render_reimbursement_form()
    elif st.session_state.current_step == "提交NCC":
        render_ncc_submission_form()

    # 添加多文件上传区域在聊天输入框上方
    uploaded_files = st.file_uploader("上传发票文件（支持多文件）", 
                                     type=["pdf", "jpg", "jpeg", "png", "ofd", "xml"],
                                     accept_multiple_files=True,
                                     key=st.session_state.upload_widget_key)

    # 检查是否需要清除上传控件状态
    if st.session_state.get('need_clear_uploads', False):
        # 通过设置一个新的key来强制重新加载上传控件
        st.session_state.need_clear_uploads = False
        st.session_state.upload_widget_key = f"chat_uploader_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        print(f"重置上传控件，新的key: {st.session_state.upload_widget_key}")
        st.rerun()

    # 聊天输入框
    if prompt := st.chat_input("输入您的问题或请求..."):
        user_message = {"role": "user", "content": prompt}
        
        # 如果上传了文件，处理文件并添加到消息中
        if uploaded_files:
            # 调试日志：打印当前处理过的文件列表
            print("="*50)
            print(f"当前已处理文件列表: {st.session_state.all_processed_files}")
            print("="*50)
            
            files_info = []
            
            # 保存原始文件内容到会话状态中，用于后续处理
            if 'original_file_contents' not in st.session_state:
                st.session_state.original_file_contents = {}
                
            for uploaded_file in uploaded_files:
                try:
                    # 读取文件内容
                    file_bytes = uploaded_file.read()
                    file_content = base64.b64encode(file_bytes).decode('utf-8')
                    # 确保Base64编码正确
                    file_content = fix_base64_padding(file_content)
                    file_type = uploaded_file.name.split('.')[-1].lower()
                    
                    # 创建一个更可靠的文件ID
                    file_id = f"{uploaded_file.name}-{len(file_bytes)}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    # 保存原始文件内容到会话状态
                    st.session_state.original_file_contents[file_id] = {
                        "content": file_content,
                        "file_type": file_type
                    }
                    
                    # 只在消息中保存文件引用，不包含实际内容
                    files_info.append({
                        "filename": uploaded_file.name,
                        "file_type": file_type,
                        "file_id": file_id,
                        # 包含一个安全的内容预览，不是实际内容
                        "content_preview": "[已保存原始文件内容，文件ID: " + file_id + "]"
                    })
                except Exception as e:
                    st.error(f"处理文件 {uploaded_file.name} 时出错: {str(e)}")
                    
            if files_info:
                user_message["files"] = files_info
                user_message["already_processed"] = False  # 初始化为未处理状态
                prompt += f"\n[用户上传了{len(files_info)}个文件]"
                
                # 设置需要清除上传状态的标志
                st.session_state.need_clear_uploads = True
                
                # 设置已处理文件的标志
                st.session_state.has_processed_files = True
                
        # 添加用户消息到历史
        st.session_state.messages.append(user_message)
        st.chat_message("user").write(prompt)
        
        if "files" in user_message:
            for file_info in user_message["files"]:
                with st.expander(f"文件: {file_info['filename']}"):
                    st.write(f"类型: {file_info['file_type']}")
                    
                    # 获取文件内容，优先从会话状态中获取
                    file_content = None
                    file_id = file_info.get("file_id")
                    if file_id and file_id in st.session_state.get("original_file_contents", {}):
                        file_content = st.session_state.original_file_contents[file_id]["content"]
                    else:
                        file_content = file_info.get("content", "")
                    
                    if file_info['file_type'].lower() in ['jpg', 'jpeg', 'png']:
                        try:
                            # 解码base64为字节
                            if file_content and len(file_content) > 100:  # 确保是有效内容
                                file_bytes = base64.b64decode(file_content)
                                st.image(file_bytes, caption=file_info['filename'])
                            else:
                                st.warning("无法显示图片: 内容无效或不完整")
                        except Exception as e:
                            st.error(f"无法显示图片: {str(e)}")
                    elif file_info['file_type'].lower() == 'pdf':
                        st.write("PDF文件（已上传，待处理）")
                    else:
                        st.write(f"已上传{file_info['file_type']}文件")
            
            # 不再立即将文件标记为已处理，而是等到实际处理完成后再标记为已处理
            print("文件已上传但尚未处理，等待实际处理完成后再标记为已处理")
        
        # 显示助手思考指示器
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                # 调用Agent处理用户输入
                messages_to_agent = []
                
                # 初始化处理标志
                should_process = False
                
                # 如果之前处理过文件，添加系统消息提醒Agent
                if st.session_state.get('has_processed_files', False):
                    # 将system消息改为user消息，避免多个system消息的错误
                    initial_note_message = "注意：用户之前已经上传并处理了文件，当前会话基于这些文件进行。请不要再要求用户上传文件。"
                    messages_to_agent.append({
                        "role": "user",  # 从system改为user
                        "content": initial_note_message
                    })
                
                # 构建消息历史
                for msg in st.session_state.messages:
                    if msg["role"] == "user":
                        agent_msg = {"role": "user", "content": msg["content"]}
                        # 如果包含文件信息，添加到消息中
                        if "files" in msg:
                            # 复制文件信息，确保内容正确
                            agent_files = []
                            for file_info in msg["files"]:
                                # 创建文件信息的深拷贝
                                new_file = {
                                    "filename": file_info["filename"],
                                    "file_type": file_info["file_type"]
                                }
                                
                                # 获取文件内容，优先从会话状态中获取
                                file_content = None
                                file_id = file_info.get("file_id")
                                if file_id and file_id in st.session_state.get("original_file_contents", {}):
                                    # 从会话状态获取原始文件内容
                                    file_content = st.session_state.original_file_contents[file_id]["content"]
                                    print(f"从会话状态获取原始文件内容用于发送给Agent，文件ID: {file_id}, 内容长度: {len(file_content)}")
                                else:
                                    # 尝试从file_info获取内容（兼容旧代码）
                                    file_content = file_info.get("content", "")
                                
                                # 确保内容有效
                                if file_content and len(file_content) > 100 and not file_content.startswith("[已保存"):
                                    new_file["content"] = file_content
                                    print(f"成功添加文件内容到Agent消息中，文件: {file_info['filename']}, 内容长度: {len(file_content)}")
                                else:
                                    print(f"警告: 无法获取有效的文件内容或内容无效，文件ID: {file_id}")
                                
                                agent_files.append(new_file)
                            
                            if agent_files:
                                agent_msg["files"] = agent_files
                        
                        # 如果消息已被处理过，添加标志
                        if msg.get("already_processed", False):
                            agent_msg["already_processed"] = True
                        
                        messages_to_agent.append(agent_msg)
                    else:
                        messages_to_agent.append({"role": "assistant", "content": msg["content"]})
                
                # 如果当前消息包含文件，处理文件上传，解析发票信息
                current_message = messages_to_agent[-1] if messages_to_agent else {"role": "user", "content": ""}
                
                # 增强判断逻辑，确保不会重复处理文件
                if "files" in current_message and not current_message.get("already_processed", False):
                    should_process = True
                else:
                    should_process = False
                
                # 检查文件是否已经在处理过的文件列表中
                if should_process and "files" in current_message:
                    print("\n"+"="*50)
                    print("开始检查文件处理状态:")
                    print(f"当前会话中所有已处理文件: {st.session_state.all_processed_files}")
                    
                    for file_info in current_message["files"]:
                        # 尝试使用file_id作为跟踪标识符（更可靠）
                        file_id = file_info.get("file_id", "")
                        print(f"检查文件ID: {file_id}")
                        
                        if file_id and file_id in st.session_state.get("all_processed_files", []):
                            # 如果文件已经处理过，标记消息为已处理
                            print(f"文件ID {file_id} 已在处理过的列表中，跳过处理")
                            should_process = False
                            current_message["already_processed"] = True
                            break
                            
                        # 兼容旧方式，使用文件名和类型组合
                        filename_type_id = f"{file_info.get('filename', '')}-{file_info.get('file_type', '')}"
                        print(f"检查文件名类型ID: {filename_type_id}")
                        
                        if filename_type_id in st.session_state.all_processed_files:
                            print(f"文件 {filename_type_id} 已在处理过的列表中，跳过处理")
                            should_process = False
                            current_message["already_processed"] = True
                            break
                    
                    print("="*50+"\n")
                
                # 如果已经上传过文件并处理过，但仍存在文件引用，添加提示但不再处理
                if "files" in current_message and current_message.get("already_processed", False):
                    print("检测到文件但已经处理过，跳过重复处理")
                
                # 如果成功处理了发票，添加到发票列表
                if should_process:
                    print("检测到文件上传，准备调用多模态发票处理器...")
                    # 创建处理工具实例
                    image_processor = InvoiceImageProcessor()
                    mm_processor = MMInvoiceProcessor()
                    processed_invoices = []
                    
                    with st.spinner("正在处理上传的文件..."):
                        for file_info in current_message["files"]:
                            try:
                                # 获取文件信息
                                filename = file_info["filename"]
                                file_type = file_info["file_type"]
                                
                                # 获取文件ID，优先使用file_info中的file_id
                                file_id = file_info.get("file_id")
                                
                                # 尝试从会话状态获取原始文件内容
                                file_content = None
                                if file_id and file_id in st.session_state.get("original_file_contents", {}):
                                    # 从会话状态获取原始文件内容
                                    original_file_data = st.session_state.original_file_contents[file_id]
                                    file_content = original_file_data["content"]
                                    print(f"从会话状态获取到原始文件内容，文件ID: {file_id}, 内容长度: {len(file_content)}")
                                elif "content" in file_info and len(file_info["content"]) > 100:
                                    # 直接从file_info获取内容（兼容旧代码）
                                    file_content = file_info["content"]
                                    print(f"从file_info获取文件内容，长度: {len(file_content)}")
                                
                                # 检查文件内容是否有效
                                if not file_content or len(file_content) < 100 or file_content.startswith("[已保存") or file_content.startswith("base64_encoded_content"):
                                    st.error(f"无法获取文件 {filename} 的有效内容，跳过处理")
                                    print(f"错误: 无法获取有效的文件内容，内容无效或不完整")
                                    continue
                                
                                # 调试文件内容
                                content_excerpt = file_content[:20] + "..." if len(file_content) > 20 else file_content
                                print(f"DEBUG - 文件内容信息:")
                                print(f"  文件名: {filename}")
                                print(f"  内容类型: {type(file_content)}")
                                print(f"  内容长度: {len(file_content)}")
                                print(f"  内容摘要: {content_excerpt}")
                                
                                st.write(f"正在处理: {filename}")
                                print(f"处理文件: {filename}, 类型: {file_type}")
                                
                                # 根据文件类型处理
                                if file_type.lower() == 'pdf':
                                    # 转换PDF为图像
                                    print(f"开始处理PDF文件: {filename}")
                                    
                                    try:
                                        result = json.loads(image_processor.call(json.dumps({
                                            'image_params': {
                                                'operation': 'pdf_to_image',
                                                'image_data': file_content
                                            }
                                        })))
                                        
                                        print(f"PDF处理结果: {result.get('status')}")
                                        
                                        if result.get('status') == 'success':
                                            st.success(f"成功将PDF {filename} 转换为{len(result.get('images', []))}张图像")
                                            
                                            # 使用第一张图片进行信息提取
                                            if result.get('images'):
                                                file_content = result['images'][0]
                                                file_type = 'jpg'  # PDF转图片后为jpg格式
                                                print(f"成功提取PDF第一页作为图像，进行后续处理")
                                            else:
                                                st.error(f"{filename}: PDF转换成功但未返回任何图像")
                                                print(f"PDF转换成功但未返回任何图像")
                                                # 尝试直接将文件作为图片处理
                                                st.info("尝试直接将文件作为图片处理...")
                                                continue
                                        else:
                                            error_message = result.get('message', 'PDF转换失败')
                                            st.error(f"{filename}: {error_message}")
                                            print(f"PDF转换失败: {error_message}")
                                            
                                            # 添加问题解决建议
                                            st.info("""可能的解决方法:
                                            1. 确保PDF文件内容有效且未加密
                                            2. 尝试使用其他PDF查看器打开文件以验证其完整性
                                            3. 尝试将PDF转换为图片后再上传
                                            4. 如果问题持续存在，请尝试上传JPEG或PNG格式的文件""")
                                            continue
                                    except Exception as pdf_err:
                                        error_msg = str(pdf_err)
                                        st.error(f"处理PDF {filename} 时发生错误: {error_msg}")
                                        print(f"处理PDF文件时发生异常: {error_msg}")
                                        
                                        # 如果是Base64 padding错误，尝试直接用文件二进制内容
                                        if "Incorrect padding" in error_msg:
                                            st.warning("检测到Base64编码问题，尝试使用替代方法...")
                                            try:
                                                # 重新读取文件
                                                uploaded_file.seek(0)
                                                file_bytes = uploaded_file.read()
                                                
                                                # 创建临时PDF文件
                                                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                                                    temp_pdf.write(file_bytes)
                                                    pdf_path = temp_pdf.name
                                                
                                                st.info(f"正在尝试直接处理文件: {pdf_path}")
                                                
                                                # 验证PDF文件是否有效
                                                if validate_pdf_file(pdf_path):
                                                    st.success("PDF文件有效，继续处理...")
                                                    # 处理逻辑...
                                                else:
                                                    st.error("PDF文件无效或损坏")
                                                
                                                # 清理临时文件
                                                os.unlink(pdf_path)
                                            except Exception as recover_err:
                                                st.error(f"尝试恢复处理失败: {str(recover_err)}")
                                        
                                        # 添加问题解决建议
                                        st.info("""可能的解决方法:
                                        1. 请检查PDF文件是否完整且未损坏
                                        2. 确认系统已安装PyMuPDF和pdf2image库
                                        3. 尝试使用其他格式的文件（如JPEG或PNG）
                                        4. 如果问题持续存在，请联系系统管理员""")
                                        
                                        import traceback
                                        traceback.print_exc()
                                        continue
                                
                                # 打印部分文件内容用于调试
                                content_preview = file_content[:20] + "..." if len(file_content) > 20 else file_content
                                print(f"文件内容预览: {content_preview}")
                                
                                # 检查文件内容是否是占位符文本
                                if file_content.startswith("base64_encoded_content_of_file"):
                                    print("错误: 检测到占位符文本而不是实际的Base64编码内容")
                                    st.error(f"文件 {filename} 内容无效，无法处理")
                                    continue
                                
                                # 判断可能的票据类型
                                possible_invoice_type = None
                                for type_name in INVOICE_TYPES:
                                    if type_name in filename:
                                        possible_invoice_type = type_name
                                        break
                                
                                # 显式调用多模态发票处理器，不管什么类型的文件都尝试提取信息
                                print(f"强制调用多模态发票处理器提取信息: {filename}")
                                
                                # 打印部分文件内容用于调试（不包含完整内容）
                                content_preview = file_content[:20] + "..." if len(file_content) > 20 else file_content
                                print(f"文件内容预览: {content_preview}")
                                
                                # 检查文件内容是否是占位符文本
                                if file_content.startswith("base64_encoded_content_of_file"):
                                    print("错误: 检测到占位符文本而不是实际的Base64编码内容")
                                    st.error(f"文件 {filename} 内容无效，无法处理")
                                    continue
                                
                                # 调用多模态发票处理器
                                try:
                                    print(f"准备mm_invoice_processor参数: file_type={file_type}, invoice_type={possible_invoice_type}")
                                    
                                    # 检查文件内容的有效性
                                    if not file_content or len(file_content) < 100:
                                        print(f"警告: 文件内容可能不完整，长度: {len(file_content) if file_content else 0}")
                                        if not file_content:
                                            st.error(f"文件 {filename} 内容为空，无法处理")
                                            continue
                                    
                                    # 检查并修复base64编码
                                    file_content = fix_base64_padding(file_content)
                                    
                                    # 打印部分文件内容用于调试
                                    content_preview = file_content[:20] + "..." if len(file_content) > 20 else file_content
                                    print(f"文件内容预览: {content_preview}")
                                    
                                    # 准备请求参数
                                    mm_params = {
                                        'process_params': {
                                            'operation': 'extract_info',
                                            'image_data': file_content,
                                            'file_type': file_type,
                                            'invoice_type': possible_invoice_type
                                        }
                                    }
                                    
                                    # 检查最终的image_data是否有效
                                    image_data = mm_params['process_params']['image_data']
                                    if not image_data or len(image_data) < 100:
                                        st.error(f"文件 {filename} 的Base64编码数据无效，无法处理")
                                        print(f"错误: image_data无效或太短 (长度: {len(image_data) if image_data else 0})")
                                        continue
                                    
                                    # 不要打印完整参数，只打印结构
                                    print(f"调用mm_invoice_processor.call，参数结构: {json.dumps({k: '...' for k in mm_params.keys()})}")
                                    
                                    # 调用处理器
                                    mm_result = mm_processor.call(json.dumps(mm_params))
                                    result_preview = mm_result[:100] + "..." if len(mm_result) > 100 else mm_result
                                    print(f"mm_invoice_processor返回结果: {result_preview}")
                                    
                                    # 解析结果
                                    result = json.loads(mm_result)
                                    
                                    if result.get('status') == 'success':
                                        invoice_data = result.get('invoice_info', {})
                                        if invoice_data:
                                            invoice_data['filename'] = filename
                                            invoice_data['file_type'] = file_type
                                            invoice_data['original_content'] = file_content
                                            
                                            detected_type = invoice_data.get('invoice_type', '其他')
                                            st.success(f"成功从{filename}中提取{detected_type}信息")
                                            print(f"成功提取{detected_type}信息: {json.dumps(invoice_data, ensure_ascii=False)[:200]}...")
                                            processed_invoices.append(invoice_data)
                                        else:
                                            st.warning(f"无法从{filename}中提取有效信息")
                                            print(f"无法从{filename}中提取有效信息，返回的invoice_info为空")
                                    else:
                                        error_msg = result.get('message', '未知错误')
                                        st.warning(f"处理{filename}失败: {error_msg}")
                                        print(f"多模态处理失败: {error_msg}")
                                        
                                        # 即使处理失败，也创建一个基本的发票结构
                                        basic_invoice = {
                                            'invoice_type': possible_invoice_type or '其他',
                                            'date': datetime.now().strftime('%Y-%m-%d'),
                                            'amount': 0.0,
                                            'invoice_id': f"AUTO{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                            'filename': filename,
                                            'file_type': file_type,
                                            'original_content': file_content,
                                            'needs_manual_input': True,
                                            'error_message': error_msg
                                        }
                                        
                                        # 根据发票类型添加特定字段
                                        if possible_invoice_type in ["火车票", "机票", "汽车票"]:
                                            basic_invoice.update({
                                                'departure': '',
                                                'destination': '',
                                                'passenger': '',
                                                'travel_date': ''  # 只在交通票据中添加
                                            })
                                        elif possible_invoice_type == "酒店住宿发票":
                                            basic_invoice.update({
                                                'hotel_name': '',
                                                'check_in_date': '',
                                                'check_out_date': '',
                                                'nights': 1,
                                                'guest_name': '',
                                                'hotel_address': '',
                                                'room_number': ''
                                            })
                                        elif possible_invoice_type == "打车票":
                                            basic_invoice.update({
                                                'start_location': '',
                                                'end_location': '',
                                                'taxi_number': ''
                                            })
                                            
                                        st.info(f"已为{filename}创建基本发票结构，请在后续步骤中手动填写信息")
                                        processed_invoices.append(basic_invoice)
                                
                                except Exception as extract_err:
                                    st.error(f"处理文件{filename}时发生异常: {str(extract_err)}")
                                    print(f"提取信息过程中发生异常: {str(extract_err)}")
                                    import traceback
                                    traceback.print_exc()
                            
                            except Exception as e:
                                st.error(f"处理文件{filename}时出错: {str(e)}")
                                print(f"处理文件总体失败: {str(e)}")
                                import traceback
                                traceback.print_exc()
                    
                    # 如果成功处理了发票，添加到发票列表
                    if processed_invoices:
                        for invoice in processed_invoices:
                            # 提取基本信息并标准化
                            std_invoice = {
                                "invoice_type": invoice.get('invoice_type', '其他'),
                                "date": invoice.get('date', datetime.now().strftime('%Y-%m-%d')),
                                "amount": float(invoice.get('amount', 0)),
                                "invoice_id": invoice.get('invoice_id', f"AUTO{datetime.now().strftime('%Y%m%d%H%M%S')}"),
                                "file_type": invoice.get('file_type', 'jpg'),
                                "filename": invoice.get('filename', '')
                            }
                            
                            # 根据发票类型添加特定字段
                            if std_invoice["invoice_type"] in ["火车票", "机票", "汽车票"]:
                                std_invoice.update({
                                    "departure": invoice.get('departure', ''),
                                    "destination": invoice.get('destination', ''),
                                    "passenger": invoice.get('passenger', ''),
                                    "travel_date": invoice.get('travel_date', '')  # 添加travel_date字段
                                })
                                # 打印调试信息
                                print(f"添加交通票据到session - travel_date: {std_invoice.get('travel_date', '无')}")
                            elif std_invoice["invoice_type"] == "酒店住宿发票":
                                std_invoice.update({
                                    "hotel_name": invoice.get('hotel_name', ''),
                                    "check_in_date": invoice.get('check_in_date', ''),
                                    "check_out_date": invoice.get('check_out_date', ''),
                                    "nights": invoice.get('nights', 1),
                                    "guest_name": invoice.get('guest_name', ''),
                                    "hotel_address": invoice.get('hotel_address', ''),
                                    "room_number": invoice.get('room_number', '')
                                })
                            elif std_invoice["invoice_type"] == "打车票":
                                std_invoice.update({
                                    "start_location": invoice.get('start_location', ''),
                                    "end_location": invoice.get('end_location', '')
                                })
                            
                            # 保存原始提取信息
                            if 'raw_extracted_info' in invoice:
                                std_invoice['raw_extracted_info'] = invoice['raw_extracted_info']
                            
                            # 保存所有原始提取信息，确保不丢失任何字段
                            std_invoice['extracted_info'] = invoice
                            
                            # 打印完整的标准化发票信息
                            print(f"标准化后的发票信息: {json.dumps(std_invoice, ensure_ascii=False)[:500]}...")
                            
                            # 添加到session state
                            st.session_state.invoices.append(std_invoice)
                        
                        # 自动保存提取的信息到JSON文件
                        try:
                            # 创建json目录（如果不存在）
                            json_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "json")
                            if not os.path.exists(json_dir):
                                os.makedirs(json_dir)
                                
                            # 准备JSON数据
                            extracted_data = []
                            for idx, inv in enumerate(st.session_state.invoices):
                                # 尝试从不同位置获取raw_extracted_info
                                if 'raw_extracted_info' in inv and inv['raw_extracted_info']:
                                    extracted_data.append({
                                        'invoice_id': inv.get('invoice_id', f'发票{idx+1}'),
                                        'invoice_type': inv.get('invoice_type', '未知类型'),
                                        'raw_extracted_info': inv['raw_extracted_info']
                                    })
                                elif 'extracted_info' in inv and isinstance(inv['extracted_info'], dict) and 'raw_extracted_info' in inv['extracted_info']:
                                    extracted_data.append({
                                        'invoice_id': inv.get('invoice_id', f'发票{idx+1}'),
                                        'invoice_type': inv.get('invoice_type', '未知类型'),
                                        'raw_extracted_info': inv['extracted_info']['raw_extracted_info']
                                    })
                            
                            # 生成带时间戳的文件名
                            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                            json_file_path = os.path.join(json_dir, f"invoice_data_{timestamp}.json")
                            
                            # 写入JSON文件
                            with open(json_file_path, 'w', encoding='utf-8') as f:
                                json.dump(extracted_data, f, ensure_ascii=False, indent=2)
                                
                            print(f"已自动保存发票提取数据到: {json_file_path}")
                            
                            # 自动调用invoice_converter.py处理保存的JSON文件
                            try:
                                converter_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "invoice_converter.py")
                                if os.path.exists(converter_script):
                                    print(f"开始自动调用转换脚本: {converter_script}")
                                    # 使用subprocess调用脚本
                                    import subprocess
                                    result = subprocess.run(
                                        ["python", converter_script], 
                                        capture_output=True, 
                                        text=True
                                    )
                                    
                                    # 打印执行结果
                                    print(f"转换脚本执行结果: {result.returncode}")
                                    if result.stdout:
                                        print(f"转换脚本输出: {result.stdout}")
                                    if result.stderr:
                                        print(f"转换脚本错误: {result.stderr}")
                                    
                                    # 在Streamlit界面上显示转换结果
                                    if result.returncode == 0:
                                        st.success("✅ 发票数据已成功转换并保存到相应目录")
                                        
                                        # 显示转换结果摘要
                                        if result.stdout:
                                            with st.expander("查看转换详情", expanded=False):
                                                st.code(result.stdout, language="text")
                                    else:
                                        st.warning("⚠️ 发票数据转换过程中出现警告或错误")
                                        with st.expander("查看转换日志", expanded=True):
                                            st.code(f"错误代码: {result.returncode}\n\n标准输出:\n{result.stdout}\n\n错误输出:\n{result.stderr}", language="text")
                                else:
                                    print(f"警告: 未找到转换脚本 {converter_script}")
                                    st.warning(f"未找到转换脚本 {converter_script}")
                            except Exception as converter_error:
                                print(f"调用转换脚本时出错: {str(converter_error)}")
                                st.error(f"调用转换脚本时出错: {str(converter_error)}")
                            
                        except Exception as e:
                            print(f"自动保存发票数据失败: {str(e)}")
                        
                        st.success(f"已成功添加{len(processed_invoices)}张发票到系统")
                        print(f"成功添加{len(processed_invoices)}张发票到系统")
                        
                        # 设置需要清除上传控件状态的标志
                        st.session_state.need_clear_uploads = True
                        
                        # 设置已处理文件的标志
                        st.session_state.has_processed_files = True
                        
                        # 如果已经有行程信息，切换到报销单生成步骤
                        if len(st.session_state.trips) >= 1:
                            st.session_state.current_step = "报销单生成"
                        
                        # 创建处理结果的信息摘要
                        result_summary = f"\n\n系统已处理上传的文件："
                        
                        if processed_invoices:
                            result_summary += "\n成功处理的文件："
                            for idx, invoice in enumerate(processed_invoices):
                                inv_type = invoice.get('invoice_type', '未知类型')
                                inv_amount = invoice.get('amount', 0)
                                
                                # 优先使用travel_date作为显示日期（对于交通票据）
                                if inv_type in ["火车票", "机票", "汽车票"] and 'travel_date' in invoice and invoice['travel_date']:
                                    inv_date = invoice.get('travel_date', '')
                                    print(f"发票摘要使用travel_date: {inv_date}")
                                else:
                                    inv_date = invoice.get('date', '')
                                
                                result_summary += f"\n- 文件{idx+1}：{inv_type}，金额：￥{inv_amount}，日期：{inv_date}"
                                
                                # 根据发票类型添加特定信息
                                if inv_type in ["火车票", "机票", "汽车票"]:
                                    departure = invoice.get('departure', '')
                                    destination = invoice.get('destination', '')
                                    if departure and destination:
                                        result_summary += f"，行程：{departure} → {destination}"
                        else:
                            result_summary += "\n无法成功处理任何文件。可能的原因包括："
                            result_summary += "\n- 文件格式不支持"
                            result_summary += "\n- 图像质量不佳"
                            result_summary += "\n- 文件内容不是有效的发票"
                            result_summary += "\n请尝试上传清晰的JPG或PNG格式图片，或使用表单直接输入发票信息。"
                        
                        # 将处理结果添加到用户消息中
                        messages_to_agent[-1]["content"] += result_summary
                        
                        # 添加明确告知Agent文件已处理的消息
                        system_message = "注意：用户已成功上传文件并且系统已经自动处理完成。"
                        system_message += "\n\n文件处理概要："
                        
                        if processed_invoices:
                            system_message += f"\n- 成功处理了{len(processed_invoices)}个文件"
                            system_message += f"\n- 已提取的发票类型包括：{', '.join(set([inv.get('invoice_type', '未知') for inv in processed_invoices]))}"
                            total_amount = sum([float(inv.get('amount', 0)) for inv in processed_invoices])
                            system_message += f"\n- 总金额：￥{total_amount:.2f}"
                            
                            # 添加详细发票信息
                            system_message += "\n\n发票详情："
                            for idx, inv in enumerate(processed_invoices):
                                inv_type = inv.get('invoice_type', '未知类型')
                                inv_amount = inv.get('amount', 0)
                                
                                # 优先使用travel_date作为显示日期（对于交通票据）
                                if inv_type in ["火车票", "机票", "汽车票"] and 'travel_date' in inv and inv['travel_date']:
                                    inv_date = inv.get('travel_date', '')
                                else:
                                    inv_date = inv.get('date', '')
                                
                                system_message += f"\n- {inv_type}："
                                system_message += f"\n  金额：￥{inv_amount}"
                                system_message += f"\n  日期：{inv_date}"
                                
                                # 根据发票类型添加特定信息
                                if inv_type in ["火车票", "机票", "汽车票"]:
                                    departure = inv.get('departure', '')
                                    destination = inv.get('destination', '')
                                    if departure and destination:
                                        system_message += f"\n  行程：{departure} → {destination}"
                                    passenger = inv.get('passenger', '')
                                    if passenger:
                                        system_message += f"\n  乘客：{passenger}"
                                elif inv_type == "酒店住宿发票":
                                    hotel_name = inv.get('hotel_name', '')
                                    if hotel_name:
                                        system_message += f"\n  酒店名称：{hotel_name}"
                                    check_in = inv.get('check_in_date', '')
                                    check_out = inv.get('check_out_date', '')
                                    if check_in and check_out:
                                        system_message += f"\n  入住日期：{check_in} 至 {check_out}"
                                    if 'hotel_address' in inv and inv['hotel_address']:
                                        system_message += f"\n  酒店地址：{inv.get('hotel_address', '未知')}"
                                    if 'room_number' in inv and inv['room_number']:
                                        system_message += f"\n  房间号：{inv.get('room_number', '未知')}"
                            
                            # 添加出发地和目的地信息（如果是交通票）
                            transport_info = []
                            for inv in processed_invoices:
                                if inv.get('invoice_type') in ["火车票", "机票", "汽车票"]:
                                    departure = inv.get('departure', '')
                                    destination = inv.get('destination', '')
                                    if departure and destination:
                                        transport_info.append(f"{departure}→{destination}")
                            
                            if transport_info:
                                system_message += f"\n\n- 行程信息：{', '.join(transport_info)}"
                        
                        system_message += "\n\n请直接基于以上已提取的信息为用户提供服务，不要再要求用户上传文件。"
                        system_message += "\n如果用户询问发票详情，请直接从上文提供的信息中回答。"
                        system_message += "\n如需生成报销单，可以指导用户使用报销单生成功能。"
                        
                        messages_to_agent.append({
                            "role": "user",  # 改为user消息而不是system消息
                            "content": system_message
                        })
                        
                        # 标记该消息的文件已经处理过，避免重复处理
                        messages_to_agent[-1]["already_processed"] = True
                        
                        # 同时更新session_state中的消息，标记为已处理
                        for i, msg in enumerate(st.session_state.messages):
                            if msg["role"] == "user" and "files" in msg and not msg.get("already_processed", False):
                                st.session_state.messages[i]["already_processed"] = True
                                # 记录已处理文件
                                if "files" in msg:
                                    for file_info in msg["files"]:
                                        # 优先使用file_id作为跟踪标识符
                                        file_id = file_info.get("file_id", "")
                                        if file_id and file_id not in st.session_state.all_processed_files:
                                            st.session_state.all_processed_files.append(file_id)
                                            print(f"已添加文件ID到处理列表: {file_id}")
                                        
                                        # 兼容旧方式，使用文件名和类型组合
                                        filename_type_id = f"{file_info.get('filename', '')}-{file_info.get('file_type', '')}"
                                        if filename_type_id not in st.session_state.all_processed_files:
                                            st.session_state.all_processed_files.append(filename_type_id)
                                            print(f"已添加文件名类型ID到处理列表: {filename_type_id}")
                                break
                
                # 获取回复
                response_text = ""
                response_container = st.empty()
                
                responses = []
                for response in st.session_state.bot.run(messages=messages_to_agent):
                    responses.extend(response)
                    
                    # 处理工具调用结果
                    for resp in response:
                        if resp["role"] == "assistant":
                            # 直接使用当前响应内容替换整个文本，而不是累加
                            response_text = resp["content"]
                            response_container.markdown(response_text)
                            
                            # 检查并更新当前步骤
                            update_current_step(response_text)
                            
                            # 根据工具调用结果更新状态
                            for msg in responses:
                                if msg["role"] == "function" and "trip_recorder" in msg.get("name", ""):
                                    try:
                                        result = json.loads(msg["content"])
                                        if "trips" in result:
                                            st.session_state.trips = result["trips"]
                                    except:
                                        pass
                                
                                if msg["role"] == "function" and "invoice_processor" in msg.get("name", ""):
                                    try:
                                        result = json.loads(msg["content"])
                                        if "invoices" in result:
                                            st.session_state.invoices = result["invoices"]
                                    except:
                                        pass
                                        
                                if msg["role"] == "function" and "reimbursement_generator" in msg.get("name", ""):
                                    try:
                                        result = json.loads(msg["content"])
                                        if "reimbursement_form" in result:
                                            st.session_state.reimbursement_form = result["reimbursement_form"]
                                    except:
                                        pass
                
                # 获取最后一个助手回复作为完整回复
                final_response = ""
                for msg in responses:
                    if msg["role"] == "assistant":
                        final_response = msg["content"]
                
                # 添加助手回复到历史
                st.session_state.messages.append({"role": "assistant", "content": final_response})
                
                # 如果处理了文件，设置需要清除上传状态的标志
                if uploaded_files and st.session_state.get('need_clear_uploads', False):
                    st.session_state.need_clear_uploads = False
            
                # 重新渲染页面
                st.rerun()

def update_current_step(response_text):
    """根据回复文本更新当前步骤"""
    response_lower = response_text.lower()
    
    if "行程已记录" in response_lower or "行程信息" in response_lower and "请上传" in response_lower:
        st.session_state.current_step = "发票上传"
    elif "发票已上传" in response_lower or "生成报销单" in response_lower:
        st.session_state.current_step = "报销单生成"
    elif "报销单已生成" in response_lower or "请确认报销单" in response_lower:
        st.session_state.current_step = "提交NCC"
    elif "已提交到ncc" in response_lower:
        st.session_state.current_step = "开始"

def render_trip_input_form():
    """渲染行程录入表单"""
    with st.expander("行程录入表单", expanded=True):
        with st.form("trip_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                departure_date = st.date_input("出发日期")
                departure_place = st.text_input("出发地点")
                transportation = st.selectbox("交通工具", ["飞机", "高铁", "火车", "汽车", "其他"])
            
            with col2:
                arrival_date = st.date_input("到达日期")
                arrival_place = st.text_input("到达地点")
                trip_purpose = st.text_input("出差事由")
            
            round_trip = st.checkbox("往返行程", value=True)
            
            submitted = st.form_submit_button("添加行程")
            
            if submitted:
                if not departure_place or not arrival_place or not trip_purpose:
                    st.error("请填写必要的行程信息！")
                else:
                    # 计算天数
                    days = (arrival_date - departure_date).days + 1
                    
                    # 创建行程信息
                    trip_info = {
                        "departure_date": departure_date.strftime("%Y-%m-%d"),
                        "arrival_date": arrival_date.strftime("%Y-%m-%d"),
                        "days": days,
                        "departure_place": departure_place,
                        "arrival_place": arrival_place,
                        "transportation": transportation,
                        "trip_purpose": trip_purpose,
                        "round_trip": round_trip
                    }
                    
                    # 添加到行程列表
                    st.session_state.trips.append(trip_info)
                    
                    # 调用行程录入工具（可选）
                    trip_recorder = TripRecorder()
                    trip_recorder.trips = st.session_state.trips
                    
                    # 显示添加成功消息
                    st.success("行程添加成功！")
                    
                    # 更新当前步骤
                    st.session_state.current_step = "发票上传"
                    
                    # 重新加载页面
                    st.rerun()
        
        # 显示已添加的行程
        if st.session_state.trips:
            st.subheader("已添加的行程")
            trips_df = pd.DataFrame(st.session_state.trips)
            st.dataframe(trips_df)

def render_invoice_upload_form():
    """渲染发票上传表单"""
    with st.expander("发票上传", expanded=True):
        # 添加提示信息
        st.info("请先选择发票类型，然后上传对应的发票文件（PDF或图片）。系统会自动识别发票信息并填写表单。")
        
        # 单独显示文件上传控件，使其更加明显
        st.subheader("第一步：上传发票文件")
        upload_col1, upload_col2 = st.columns([3, 1])
        with upload_col1:
            uploaded_file = st.file_uploader("选择发票文件", type=["pdf", "jpg", "jpeg", "png", "ofd", "xml"], 
                                            help="支持PDF和图片格式。PDF将自动转换为图片进行处理。")
        with upload_col2:
            file_type = st.selectbox("文件类型", ["pdf", "jpg", "jpeg", "png", "ofd", "xml"])
        
        st.subheader("第二步：填写发票信息")
        
        with st.form("invoice_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                invoice_type = st.selectbox("发票类型", INVOICE_TYPES)
                date = st.date_input("发票日期")
            
            with col2:
                amount = st.number_input("金额", min_value=0.0, format="%.2f")
                st.markdown("<div style='height: 39px;'></div>", unsafe_allow_html=True)  # 填充空间以对齐
            
            # 根据发票类型添加其他输入字段
            if invoice_type in ["火车票", "机票", "汽车票"]:
                col1, col2 = st.columns(2)
                with col1:
                    departure = st.text_input("出发地点")
                with col2:
                    destination = st.text_input("目的地")
                passenger = st.text_input("乘客姓名")
            
            elif invoice_type == "酒店住宿发票":
                col1, col2 = st.columns(2)
                with col1:
                    hotel_name = st.text_input("酒店名称")
                with col2:
                    nights = st.number_input("住宿晚数", min_value=1, value=1)
                
                check_in_date = st.date_input("入住日期")
                check_out_date = st.date_input("退房日期")
                guest_name = st.text_input("客人姓名")
            
            elif invoice_type == "打车票":
                col1, col2 = st.columns(2)
                with col1:
                    start_location = st.text_input("起点")
                with col2:
                    end_location = st.text_input("终点")
            
            submitted = st.form_submit_button("添加发票")
            
            if submitted:
                if amount <= 0:
                    st.error("请输入有效的金额！")
                else:
                    # 基础发票信息
                    invoice_data = {
                        "invoice_type": invoice_type,
                        "date": date.strftime("%Y-%m-%d"),
                        "amount": amount,
                        "file_type": file_type,
                        "invoice_id": f"{invoice_type[0]}{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    }
                    
                    # 根据发票类型添加特定字段
                    if invoice_type in ["火车票", "机票", "汽车票"]:
                        invoice_data.update({
                            "departure": departure,
                            "destination": destination,
                            "passenger": passenger
                        })
                    
                    elif invoice_type == "酒店住宿发票":
                        invoice_data.update({
                            "hotel_name": hotel_name,
                            "check_in_date": check_in_date.strftime("%Y-%m-%d"),
                            "check_out_date": check_out_date.strftime("%Y-%m-%d"),
                            "nights": nights,
                            "guest_name": guest_name
                        })
                    
                    elif invoice_type == "打车票":
                        invoice_data.update({
                            "start_location": start_location,
                            "end_location": end_location
                        })
                    
                    # 如果上传了文件
                    if uploaded_file:
                        try:
                            # 读取文件内容
                            file_bytes = uploaded_file.read()
                            file_content = base64.b64encode(file_bytes).decode('utf-8')
                            # 确保Base64编码正确
                            file_content = fix_base64_padding(file_content)
                            file_type = uploaded_file.name.split('.')[-1].lower()
                            
                            # 创建图像处理工具实例
                            image_processor = InvoiceImageProcessor()
                            
                            # 如果是PDF文件，先转换为图像
                            if file_type.lower() == 'pdf':
                                with st.spinner("正在将PDF转换为图像..."):
                                    result = json.loads(image_processor.call(json.dumps({
                                        'image_params': {
                                            'operation': 'pdf_to_image',
                                            'image_data': file_content
                                        }
                                    })))
                                    
                                    if result.get('status') == 'success':
                                        st.success(f"成功将PDF转换为{len(result.get('images', []))}张图像")
                                        
                                        # 使用第一张图片进行信息提取
                                        if result.get('images'):
                                            file_content = result['images'][0]
                                            file_type = 'jpg'  # PDF转图片后为jpg格式
                                    else:
                                        st.error(result.get('message', 'PDF转换失败'))
                            
                            # 从图像中提取发票信息
                            with st.spinner("正在识别发票信息..."):
                                extract_result = json.loads(image_processor.call(json.dumps({
                                    'image_params': {
                                        'operation': 'extract_info',
                                        'image_data': file_content,
                                        'file_type': file_type,
                                        'invoice_type': invoice_type
                                    }
                                })))
                                
                                if extract_result.get('status') == 'success':
                                    # 如果成功提取到发票信息
                                    extracted_info = extract_result.get('invoice_info', {})
                                    st.success(extract_result.get('message', '成功识别发票信息'))
                                    
                                    # 更新表单值
                                    if invoice_type in ["火车票", "机票", "汽车票"]:
                                        # 更新交通票据信息
                                        invoice_data.update({
                                            'departure': extracted_info.get('departure', departure),
                                            'destination': extracted_info.get('destination', destination),
                                            'passenger': extracted_info.get('passenger', passenger),
                                            'amount': extracted_info.get('amount', amount),
                                            'date': extracted_info.get('date', invoice_data['date']),
                                            'travel_date': extracted_info.get('travel_date', extracted_info.get('trip_date', ''))
                                        })
                                    elif invoice_type == "酒店住宿发票":
                                        # 更新酒店住宿信息
                                        invoice_data.update({
                                            'hotel_name': extracted_info.get('hotel_name', hotel_name),
                                            'check_in_date': extracted_info.get('check_in_date', invoice_data['check_in_date']),
                                            'check_out_date': extracted_info.get('check_out_date', invoice_data['check_out_date']),
                                            'nights': extracted_info.get('nights', nights),
                                            'guest_name': extracted_info.get('guest_name', guest_name),
                                            'hotel_address': extracted_info.get('hotel_address', ''),
                                            'room_number': extracted_info.get('room_number', ''),
                                            'amount': extracted_info.get('amount', amount),
                                            'date': extracted_info.get('date', invoice_data['date'])
                                        })
                                    elif invoice_type == "打车票":
                                        # 更新打车票信息
                                        invoice_data.update({
                                            'start_location': extracted_info.get('start_location', start_location),
                                            'end_location': extracted_info.get('end_location', end_location),
                                            'amount': extracted_info.get('amount', amount),
                                            'date': extracted_info.get('date', invoice_data['date'])
                                        })
                                    else:
                                        # 更新其他发票信息
                                        invoice_data.update({
                                            'amount': extracted_info.get('amount', amount),
                                            'date': extracted_info.get('date', invoice_data['date']),
                                            'details': extracted_info.get('details', '')
                                        })
                                    
                                    # 添加提取的原始信息以供参考
                                    invoice_data['extracted_info'] = extracted_info
                                else:
                                    st.warning(extract_result.get('message', '无法自动识别发票信息，请手动填写'))
                        except Exception as e:
                            st.error(f"处理发票文件时出错: {str(e)}")
                    
                    # 添加到发票列表
                    st.session_state.invoices.append(invoice_data)
                    
                    # 更新会话状态
                    if len(st.session_state.invoices) >= 1 and len(st.session_state.trips) >= 1:
                        # 满足条件进入下一步
                        st.session_state.current_step = "报销单生成"
                    
                    # 显示添加成功消息
                    st.success("发票添加成功！")
                    
                    # 重新加载页面
                    st.rerun()
        
        # 显示已添加的发票
        if st.session_state.invoices:
            st.subheader("已添加的发票")
            
            # 添加显示选项开关
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text("发票列表")
            with col2:
                show_all_fields = st.checkbox("显示所有抽取字段", value=False, help="勾选后将显示大模型抽取的所有字段信息")
            
            # 显示每张发票的详细信息
            for idx, inv in enumerate(st.session_state.invoices):
                with st.expander(f"发票 #{idx+1}: {inv.get('invoice_type', '未知')} - {inv.get('amount', 0)}元"):
                    # 基本信息
                    st.markdown(f"**发票类型**: {inv.get('invoice_type', '未知')}")
                    st.markdown(f"**发票金额**: ¥{inv.get('amount', 0)}")
                    st.markdown(f"**发票ID**: {inv.get('invoice_id', '未知')}")
                    
                    # 日期信息（显示两种日期）
                    st.markdown(f"**发票日期**: {inv.get('date', '未知')}")
                    if inv.get('invoice_type') in ['火车票', '机票', '汽车票'] and 'travel_date' in inv:
                        st.markdown(f"**行程日期**: {inv.get('travel_date', '未知')}")
                    
                    # 根据发票类型显示特定信息
                    if inv.get('invoice_type') in ['火车票', '机票', '汽车票']:
                        st.markdown(f"**出发地**: {inv.get('departure', '未知')}")
                        st.markdown(f"**目的地**: {inv.get('destination', '未知')}")
                        st.markdown(f"**乘客**: {inv.get('passenger', '未知')}")
                        if 'ticket_number' in inv:
                            st.markdown(f"**票号**: {inv.get('ticket_number', '未知')}")
                    elif inv.get('invoice_type') == '酒店住宿发票':
                        st.markdown(f"**酒店名称**: {inv.get('hotel_name', '未知')}")
                        st.markdown(f"**入住日期**: {inv.get('check_in_date', '未知')}")
                        st.markdown(f"**退房日期**: {inv.get('check_out_date', '未知')}")
                        st.markdown(f"**住宿晚数**: {inv.get('nights', '未知')}")
                        st.markdown(f"**客人姓名**: {inv.get('guest_name', '未知')}")
                        if 'hotel_address' in inv and inv['hotel_address']:
                            st.markdown(f"**酒店地址**: {inv.get('hotel_address', '未知')}")
                        if 'room_number' in inv and inv['room_number']:
                            st.markdown(f"**房间号**: {inv.get('room_number', '未知')}")
                    elif inv.get('invoice_type') == '打车票':
                        st.markdown(f"**起点**: {inv.get('start_location', '未知')}")
                        st.markdown(f"**终点**: {inv.get('end_location', '未知')}")
                    
                    # 添加一个更明显的显示完整信息按钮
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button(f"📋 显示完整抽取信息", key=f"full_detail_{idx}"):
                            st.session_state[f"show_full_detail_{idx}"] = not st.session_state.get(f"show_full_detail_{idx}", False)
                    with col_btn2:
                        if st.button(f"查看详细抽取信息", key=f"detail_{idx}"):
                            st.session_state[f"show_detail_{idx}"] = not st.session_state.get(f"show_detail_{idx}", False)
                    
                    # 显示完整抽取信息（新增）
                    if st.session_state.get(f"show_full_detail_{idx}", False):
                        st.markdown("---")
                        st.markdown("### 🎯 大模型完整抽取结果")
                        
                        # 显示完整的发票数据结构
                        st.markdown("**当前发票完整数据：**")
                        full_data = dict(inv)
                        # 处理过长的内容
                        if 'original_content' in full_data:
                            content_len = len(str(full_data['original_content']))
                            full_data['original_content'] = f"[文件内容长度: {content_len} 字符]"
                        st.json(full_data)
                        
                        # 如果有extracted_info，单独详细显示
                        if 'extracted_info' in inv and inv['extracted_info']:
                            st.markdown("**📊 extracted_info 详细内容：**")
                            extracted_info = inv['extracted_info']
                            if isinstance(extracted_info, dict):
                                for key, value in extracted_info.items():
                                    if key == 'original_content':
                                        content_len = len(str(value)) if value else 0
                                        st.markdown(f"**{key}**: [内容长度: {content_len} 字符]")
                                    elif isinstance(value, (dict, list)):
                                        st.markdown(f"**{key}**: {json.dumps(value, ensure_ascii=False, indent=2)}")
                                    else:
                                        st.markdown(f"**{key}**: {value}")
                            else:
                                st.markdown(f"extracted_info 内容: {extracted_info}")
                        
                        # 如果有raw_extracted_info，单独显示
                        if 'raw_extracted_info' in inv and inv['raw_extracted_info']:
                            st.markdown("**🔍 raw_extracted_info 详细内容：**")
                            raw_info = inv['raw_extracted_info']
                            if isinstance(raw_info, dict):
                                for key, value in raw_info.items():
                                    st.markdown(f"**{key}**: {value}")
                            else:
                                st.markdown(f"raw_extracted_info 内容: {raw_info}")
                        
                        st.markdown("---")
                    
                    # 显示调试信息（仅在详细模式下）
                    if show_all_fields or st.session_state.get(f"show_detail_{idx}", False):
                        with st.expander("🔍 调试信息（数据结构）", expanded=False):
                            st.markdown("**发票数据结构：**")
                            st.write(f"发票字典keys: {list(inv.keys())}")
                            if 'extracted_info' in inv:
                                st.write(f"extracted_info type: {type(inv['extracted_info'])}")
                                if isinstance(inv['extracted_info'], dict):
                                    st.write(f"extracted_info keys: {list(inv['extracted_info'].keys())}")
                            if 'raw_extracted_info' in inv:
                                st.write(f"raw_extracted_info type: {type(inv['raw_extracted_info'])}")
                                if isinstance(inv['raw_extracted_info'], dict):
                                    st.write(f"raw_extracted_info keys: {list(inv['raw_extracted_info'].keys())}")
                    
                    # 显示原始提取信息
                    if show_all_fields or st.session_state.get(f"show_detail_{idx}", False):
                        st.markdown("### 原始提取信息")
                        
                        # 显示raw_extracted_info
                        if 'raw_extracted_info' in inv and inv['raw_extracted_info']:
                            raw_info = inv['raw_extracted_info']
                            st.markdown("**直接抽取字段（raw_extracted_info）：**")
                            for key, value in raw_info.items():
                                if value is not None and str(value).strip():  # 只显示非空字段
                                    st.markdown(f"**{key}**: {value}")
                        # 如果没有raw_extracted_info，但extracted_info中有raw_extracted_info
                        elif 'extracted_info' in inv and isinstance(inv['extracted_info'], dict) and 'raw_extracted_info' in inv['extracted_info'] and inv['extracted_info']['raw_extracted_info']:
                            raw_info = inv['extracted_info']['raw_extracted_info']
                            st.markdown("**嵌套抽取字段（extracted_info.raw_extracted_info）：**")
                            for key, value in raw_info.items():
                                if value is not None and str(value).strip():  # 只显示非空字段
                                    st.markdown(f"**{key}**: {value}")
                        
                        # 显示extracted_info的所有字段
                        if 'extracted_info' in inv and inv['extracted_info']:
                            st.markdown("**所有抽取字段（extracted_info）：**")
                            extracted_info = inv['extracted_info']
                            
                            # 处理extracted_info
                            if isinstance(extracted_info, dict):
                                for key, value in extracted_info.items():
                                    # 跳过一些特殊字段
                                    if key in ['original_content', 'filename', 'file_type']:
                                        continue
                                    
                                    # 处理嵌套字典
                                    if isinstance(value, dict):
                                        st.markdown(f"**{key}**: {json.dumps(value, ensure_ascii=False)}")
                                    elif isinstance(value, list):
                                        st.markdown(f"**{key}**: {', '.join(map(str, value))}")
                                    elif value is not None and str(value).strip():
                                        st.markdown(f"**{key}**: {value}")
                            else:
                                st.markdown(f"extracted_info内容: {extracted_info}")
                                    
                        # 额外显示所有extracted_info中的字段（包括嵌套的）- 用JSON格式
                        if 'extracted_info' in inv and inv['extracted_info']:
                            st.markdown("### 完整提取信息（JSON格式）")
                            # 创建一个清理后的版本，移除过大的content字段
                            clean_info = dict(inv['extracted_info'])
                            if 'original_content' in clean_info:
                                content_preview = clean_info['original_content'][:50] + "..." if len(clean_info['original_content']) > 50 else clean_info['original_content']
                                clean_info['original_content'] = f"[内容长度: {len(inv['extracted_info']['original_content'])}] {content_preview}"
                            st.json(clean_info)  # 使用json组件显示完整结构
            
            # 创建一个更简洁的DataFrame用于显示
            display_cols = ["invoice_type", "date", "amount", "invoice_id"]
            simplified_invoices = []
            
            for inv in st.session_state.invoices:
                simplified_inv = {col: inv.get(col, "") for col in display_cols}
                # 如果是交通类发票且有travel_date字段，优先使用travel_date作为显示日期
                if inv.get('invoice_type') in ['火车票', '机票', '汽车票'] and 'travel_date' in inv and inv['travel_date']:
                    simplified_inv['date'] = inv['travel_date']
                    # 打印调试信息
                    print(f"发票列表显示 - 使用travel_date替换date: {inv['travel_date']}")
                simplified_invoices.append(simplified_inv)
            
            # 打印调试信息
            for idx, inv in enumerate(simplified_invoices):
                print(f"发票{idx+1}显示信息: {json.dumps(inv, ensure_ascii=False)}")
                
            invoices_df = pd.DataFrame(simplified_invoices)
            st.dataframe(invoices_df)
            
            # 添加继续按钮
            if st.button("生成报销单"):
                st.session_state.current_step = "报销单生成"
                st.rerun()

def render_reimbursement_form():
    """渲染报销单生成和确认表单"""
    with st.expander("报销单生成", expanded=True):
        # 显示状态信息
        col_status1, col_status2 = st.columns(2)
        with col_status1:
            if not st.session_state.trips:
                st.warning("⚠️ 尚未添加行程信息")
            else:
                st.success(f"✅ 已添加 {len(st.session_state.trips)} 条行程信息")
        
        with col_status2:
            if not st.session_state.invoices:
                st.warning("⚠️ 尚未添加发票信息")
            else:
                st.success(f"✅ 已添加 {len(st.session_state.invoices)} 张发票")
        
        # 始终显示表单，不再使用return提前退出
        # 表单输入区域
        st.subheader("请填写报销单信息")
        
        with st.form("reimbursement_details_form"):
            # 创建两列布局
            col1, col2 = st.columns(2)
            
            with col1:
                # 左侧四个字段
                reimbursement_person = st.text_input("报销人", value="", help="请输入报销人姓名")
                report_reason = st.text_input("报销事由", value="出差")
                bank_name = st.text_input("收款银行名称", value="招商银行")
                receiver_name = st.text_input("收款人", value="")
            
            with col2:
                # 右侧四个字段
                bank_account = st.text_input("收款人卡号", value="")
                hotel_exceed = st.text_input("住宿费超标金额", value="0")
                traffic_exceed = st.text_input("城市内公务交通车费超标金额", value="0")
                # 将分摊选项作为一个单独字段
                share_col1, share_col2 = st.columns([3, 1])
                with share_col1:
                    share_reason = st.text_input("分摊原因", value="")
                with share_col2:
                    is_shared = st.checkbox("是否分摊", value=False)
            
            # 超标说明单独占一行
            exceed_note = st.text_input("超标说明", value="无")
            
            # 提交按钮，在没有行程或发票信息时禁用
            submit_disabled = not st.session_state.trips or not st.session_state.invoices
            submitted = st.form_submit_button("生成报销单", disabled=submit_disabled)
            
            if submit_disabled:
                st.info("请先添加行程和发票信息才能生成报销单")
            
            if submitted:
                # 创建包含用户输入的字典
                user_inputs = {
                    "报销人": reimbursement_person,
                    "报销事由": report_reason,
                    "收款银行名称": bank_name,
                    "收款人": receiver_name,
                    "收款人卡号": bank_account,
                    "分摊": "是" if is_shared else "否",
                    "分摊原因": share_reason if is_shared else "",
                    "住宿费超标金额": hotel_exceed,
                    "城市内公务交通车费超标金额": traffic_exceed,
                    "超标说明": exceed_note
                }
                
                # 调用报销单生成工具
                with st.spinner("生成报销单中..."):
                    reimbursement_tool = ReimbursementGenerator()
                    result = json.loads(reimbursement_tool.call(json.dumps({
                        "generation_params": {
                            "trips": st.session_state.trips,
                            "invoices": st.session_state.invoices,
                            "confirmed": False,  # 初次生成时未确认
                            **user_inputs  # 传递用户输入的字段
                        }
                    })))
                    
                    if result.get("status") in ["success", "warning"]:
                        st.session_state.reimbursement_form = result.get("reimbursement_form")
                        
                        # 如果有验证问题，显示警告
                        if result.get("status") == "warning" and "validation_results" in result:
                            validation_results = result["validation_results"]
                            issues = validation_results.get("issues", [])
                            warnings = validation_results.get("warnings", [])
                            
                            # 保存验证结果到session_state
                            st.session_state.validation_results = validation_results
                            
                            # 显示所有问题和警告
                            with st.expander("注意事项", expanded=True):
                                if issues:
                                    st.markdown("系统提示可能存在以下问题：")
                                    for issue in issues:
                                        st.warning(issue)
                                
                                if warnings:
                                    st.markdown("系统提示可能存在以下问题：")
                                    for warning in warnings:
                                        st.warning(warning)
                    else:
                        st.error(result.get("message", "报销单生成失败"))
                        return
        
        # 如果报销单已经生成，显示报销单
        if st.session_state.reimbursement_form:
            form = st.session_state.reimbursement_form
            
            st.subheader("已生成的报销单")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**报销类型**: {form.get('报销类型', '')}")
                st.markdown(f"**报销人**: {form.get('报销人', '')}")
                st.markdown(f"**报销事由**: {form.get('报销事由', '')}")
                st.markdown(f"**报销总金额**: ¥{form.get('报销总金额', 0):.2f}")
            
            with col2:
                st.markdown(f"**收款银行名称**: {form.get('收款银行名称', '')}")
                st.markdown(f"**收款人**: {form.get('收款人', '')}")
                st.markdown(f"**收款人卡号**: {form.get('收款人卡号', '')}")
                st.markdown(f"**分摊**: {form.get('分摊', '否')}")
            
            # 显示明细表格
            if "expense_details" in form:
                st.subheader("费用明细")
                
                # 将字典列表转换为DataFrame
                expense_details = pd.DataFrame(form["expense_details"])
                st.table(expense_details)
            
            # 显示报销单相关的行程信息
            if "trips" in form:
                st.subheader("行程信息")
                trips_df = pd.DataFrame(form["trips"])
                st.table(trips_df)
            
            # 显示报销单相关的发票信息
            if "invoices" in form:
                st.subheader("发票信息")
                
                # 创建一个简化版本的发票信息
                invoices = form["invoices"]
                if invoices:
                    simplified_invoices = []
                    for inv in invoices:
                        # 确定显示日期：优先使用travel_date（交通票据），其次是date或check_in_date
                        display_date = ""
                        if inv.get('invoice_type') in ['火车票', '机票', '汽车票'] and 'travel_date' in inv and inv['travel_date']:
                            display_date = inv['travel_date']
                        else:
                            display_date = inv.get("date", "") or inv.get("check_in_date", "")
                            
                        simple_inv = {
                            "发票类型": inv.get("invoice_type", ""),
                            "金额": inv.get("amount", 0),
                            "日期": display_date
                        }
                        
                        # 添加出发地和目的地（如果是交通票据）
                        if inv.get('invoice_type') in ['火车票', '机票', '汽车票']:
                            simple_inv["出发地"] = inv.get("departure", "")
                            simple_inv["目的地"] = inv.get("destination", "")
                        
                        simplified_invoices.append(simple_inv)
                    
                    if simplified_invoices:
                        st.table(pd.DataFrame(simplified_invoices))
            
            # 进入下一步按钮
            if st.button("确认并提交到NCC"):
                # 用户确认后，如果需要再次生成报销单，将使用confirmed=True
                if "validation_results" in st.session_state and (
                    st.session_state.validation_results.get("issues") or 
                    st.session_state.validation_results.get("warnings")
                ):
                    # 重新生成报销单，但标记为已确认
                    reimbursement_tool = ReimbursementGenerator()
                    result = json.loads(reimbursement_tool.call(json.dumps({
                        "generation_params": {
                            "trips": st.session_state.trips,
                            "invoices": st.session_state.invoices,
                            "confirmed": True,  # 用户已确认
                            **{k: form.get(k, "") for k in [
                                "报销人", "报销事由", "收款银行名称", "收款人", 
                                "收款人卡号", "分摊", "分摊原因", "住宿费超标金额",
                                "城市内公务交通车费超标金额", "超标说明"
                            ]}
                        }
                    })))
                    
                    if result.get("status") == "success":
                        st.session_state.reimbursement_form = result.get("reimbursement_form")
                
                st.session_state.current_step = "提交NCC"
                st.rerun()

def render_ncc_submission_form():
    """渲染NCC提交表单"""
    with st.expander("提交到NCC", expanded=True):
        if not st.session_state.reimbursement_form:
            st.warning("请先生成报销单")
            return
            
        st.markdown("### 确认提交")
        st.markdown("请确认以下信息无误后提交到NCC系统")
        
        form = st.session_state.reimbursement_form
        st.markdown(f"**报销类型**: {form.get('报销类型', '')}")
        st.markdown(f"**报销人**: {form.get('报销人', '')}")
        st.markdown(f"**报销事由**: {form.get('报销事由', '')}")
        st.markdown(f"**报销总金额**: ¥{form.get('报销总金额', 0):.2f}")
        st.markdown(f"**收款银行**: {form.get('收款银行名称', '')}")
        st.markdown(f"**收款人**: {form.get('收款人', '')}")
        st.markdown(f"**收款人卡号**: {form.get('收款人卡号', '')}")
        
        # 复选框确认
        confirm = st.checkbox("我已确认上述信息无误，同意提交")
        
        # 添加RPA自动化选项
        execute_rpa = st.checkbox("提交后自动执行RPA操作（自动打开NCC系统并填写表单）", value=False)
        
        if execute_rpa:
            st.info("系统将自动启动Chrome浏览器并执行RPA操作，请勿手动关闭浏览器。")
        
        if st.button("提交到NCC系统", disabled=not confirm):
            with st.spinner("提交中..."):
                # 调用NCC提交工具
                ncc_tool = NCCSubmission()
                result = json.loads(ncc_tool.call(json.dumps({
                    "submission_params": {
                        "reimbursement_form": form,
                        "confirm": confirm,
                        "execute_rpa": execute_rpa
                    }
                })))
                
                if result.get("status") == "success":
                    st.success(result.get("message", "提交成功"))
                    st.balloons()
                    
                    # 显示提交结果
                    st.markdown(f"**提交时间**: {result.get('submission_time', '')}")
                    st.markdown(f"**NCC单据ID**: {result.get('ncc_bill_id', '')}")
                    
                    # 显示NCC链接和RPA状态（如果有）
                    if "ncc_url" in result:
                        st.markdown(f"[点击查看NCC系统]({result['ncc_url']})")
                    
                    # 显示RPA执行状态（如果执行了RPA）
                    if execute_rpa:
                        st.markdown("### RPA自动化执行结果")
                        st.markdown(f"**状态**: {result.get('rpa_status', '未知')}")
                        st.markdown(f"**消息**: {result.get('rpa_message', '')}")
                        
                        # 显示是否自动启动了浏览器
                        if result.get('auto_launched', False):
                            st.success("系统已自动启动Chrome浏览器")
                        
                        # 如果有截图，显示截图
                        if "screenshot" in result:
                            try:
                                screenshot_path = result["screenshot"]
                                if os.path.exists(screenshot_path):
                                    st.image(screenshot_path, caption="RPA执行截图")
                                else:
                                    st.warning(f"截图文件不存在: {screenshot_path}")
                            except Exception as e:
                                st.error(f"显示截图时出错: {str(e)}")
                    
                    # 重置报销单
                    st.session_state.reimbursement_form = None
                    
                    # 重置步骤
                    st.session_state.current_step = "开始"
                else:
                    st.error(result.get("message", "提交失败"))

def fix_base64_padding(data: str) -> str:
    """修复Base64编码的padding问题
    
    Base64编码的字符串长度应该是4的倍数，如果不是，需要添加=号作为填充
    """
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)
    return data

# 主函数
def main():
    render_header()
    render_sidebar()
    
    # 🔍 添加调试信息区域
    with st.expander("🔍 系统状态调试信息", expanded=True):
        st.markdown("### 当前系统状态")
        st.write(f"**当前步骤**: {st.session_state.current_step}")
        st.write(f"**行程数量**: {len(st.session_state.trips)}")
        st.write(f"**发票数量**: {len(st.session_state.invoices)}")
        
        if st.session_state.invoices:
            st.markdown("### 📄 发票数据详情")
            for idx, inv in enumerate(st.session_state.invoices):
                # 不使用嵌套expander，改用markdown展示
                st.markdown(f"**发票 #{idx+1}: {inv.get('invoice_type', '未知')} - ¥{inv.get('amount', 0)}**")
                st.write(f"- 所有字段: {list(inv.keys())}")
                st.write(f"- 包含extracted_info: {'extracted_info' in inv}")
                st.write(f"- 包含raw_extracted_info: {'raw_extracted_info' in inv}")
                
                # 显示extracted_info的内容
                if 'extracted_info' in inv and inv['extracted_info']:
                    st.markdown("📊 **extracted_info 内容:**")
                    if isinstance(inv['extracted_info'], dict):
                        for key, value in inv['extracted_info'].items():
                            if key != 'original_content':  # 跳过文件内容
                                st.markdown(f"  - **{key}**: {value}")
                    else:
                        st.write(f"  extracted_info: {inv['extracted_info']}")
                
                # 显示raw_extracted_info的内容
                if 'raw_extracted_info' in inv and inv['raw_extracted_info']:
                    st.markdown("🔍 **raw_extracted_info 内容:**")
                    if isinstance(inv['raw_extracted_info'], dict):
                        for key, value in inv['raw_extracted_info'].items():
                            st.markdown(f"  - **{key}**: {value}")
                    else:
                        st.write(f"  raw_extracted_info: {inv['raw_extracted_info']}")
                
                st.markdown("---")  # 分隔线
        else:
            st.warning("❌ 当前没有发票数据。请先上传发票或使用表单添加发票。")
            st.info("💡 提示：请先点击下方的'转到发票上传'按钮，然后上传发票文件。")
    
    # 添加测试按钮直接切换到发票上传步骤
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("转到行程录入"):
            st.session_state.current_step = "行程录入"
            st.rerun()
    with col2:
        if st.button("转到发票上传"):
            st.session_state.current_step = "发票上传"
            st.rerun()
    with col3:
        if st.button("转到报销单生成"):
            st.session_state.current_step = "报销单生成"
            st.rerun()
    with col4:
        if st.button("转到NCC提交"):
            st.session_state.current_step = "提交NCC"
            st.rerun()
    
    # 显示当前步骤
    st.write(f"当前步骤: **{st.session_state.current_step}**")
    
    render_chat_interface()
    
    # 处理帮助文档清理
    def cleanup():
        if 'help_doc_path' in st.session_state and os.path.exists(st.session_state.help_doc_path):
            os.remove(st.session_state.help_doc_path)
    
    # 注册页面卸载事件处理
    st.on_session_state_change = cleanup

if __name__ == "__main__":
    main() 