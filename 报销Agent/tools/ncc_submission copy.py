import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from qwen_agent.tools.base import BaseTool, register_tool
from config import NCC_CONFIG
import time
import random
import os
import subprocess
import signal
import atexit
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
import json
import sys
import re

# 导入utils中的工具函数（现在在tools目录下）
try:
    # 确保当前目录在导入路径中
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    
    # 直接导入utils模块
    import utils
    from utils import (
        fill_form, 
        load_json_data, 
        get_json_files_from_folder, 
        click_expand_button,
        find_form_fields,
        process_json_folder_for_forms,
        get_modal_container
    )
    UTILS_IMPORTED = True
    print("成功导入utils模块")
except ImportError as e:
    print(f"警告：无法导入utils模块: {e}")
    print("将使用内置的填表功能")
    UTILS_IMPORTED = False

# 添加报销类型映射表，根据截图内容
REIMBURSEMENT_TYPES = [
    {"code": "001", "name": "出差北上"},
    {"code": "00101", "name": "出差广深"},
    {"code": "00102", "name": "出差杭厦(明明日)"},
    {"code": "002", "name": "出差港澳台"},
    {"code": "00201", "name": "出差海外-普通消费区通用"},
    {"code": "00202", "name": "出差海外欧美亚高消费区-科技"},
    {"code": "003", "name": "出差境内其他城市"},
    {"code": "004", "name": "市内交通费"},
    {"code": "005", "name": "通讯费"},
    {"code": "006", "name": "业务招待费+非三项费用"}
]

def get_reimbursement_type_by_keyword(keyword: str) -> str:
    """
    根据关键字匹配报销类型编码
    
    :param keyword: 关键字或报销描述
    :return: 匹配的报销类型编码和名称，如"001/出差北上"，若无匹配则返回默认值
    """
    if not keyword:
        return "001/出差北上"  # 默认值
        
    keyword = keyword.lower()
    
    # 精确匹配
    for item in REIMBURSEMENT_TYPES:
        if keyword == item["name"].lower():
            return f"{item['code']}/{item['name']}"
    
    # 关键字匹配
    matches = []
    for item in REIMBURSEMENT_TYPES:
        if keyword in item["name"].lower():
            matches.append(item)
            
    # 如果找到多个匹配项，返回编码最短的（通常是主类别）
    if matches:
        matches.sort(key=lambda x: len(x["code"]))
        return f"{matches[0]['code']}/{matches[0]['name']}"
    
    # 更广泛的关键字匹配
    for item in REIMBURSEMENT_TYPES:
        for word in keyword.split():
            if word in item["name"].lower() and len(word) > 1:  # 避免单字符误匹配
                return f"{item['code']}/{item['name']}"
    
    return "001/出差北上"  # 默认值

# 定义基本的辅助函数，以防utils模块不可用
def load_json_data(file_path):
    """加载JSON数据文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON文件失败: {e}")
        return {}

def get_json_files_from_folder(folder_path):
    """获取文件夹中的所有JSON文件"""
    json_files = []
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        for file in os.listdir(folder_path):
            if file.endswith('.json'):
                json_files.append(os.path.join(folder_path, file))
    return json_files

def fill_form(driver, form_data, find_element_func=None, modal_xpath=None):
    """基本的表单填充函数"""
    try:
        print("开始填写表单数据...")
        
        # 查找模态框容器（如果提供了XPath）
        container = None
        if modal_xpath:
            try:
                container = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, modal_xpath))
                )
                print(f"找到模态框容器: {modal_xpath}")
            except:
                print(f"未找到模态框容器: {modal_xpath}，将使用整个文档")
        
        # 使用JavaScript查找表单字段
        form_fields = driver.execute_script("""
            var result = [];
            
            // 找到容器元素，如果没有指定则使用整个文档
            var container = arguments[0] || document;
            
            // 查找所有表单字段
            var labels = container.querySelectorAll('.form-item-label, label, .side-form-label');
            
            for (var i = 0; i < labels.length; i++) {
                var label = labels[i];
                var labelText = label.textContent.trim().replace(/[*：:]/g, '').trim();
                
                if (!labelText) continue;
                
                // 查找输入元素 - 先查找相邻的控件容器
                var controlContainer = label.parentElement.querySelector('.form-item-control');
                if (!controlContainer) {
                    // 如果没有找到控件容器，尝试其他常见结构
                    controlContainer = label.nextElementSibling;
                    if (!controlContainer) {
                        // 查找同级的控件容器
                        var parent = label.parentElement;
                        controlContainer = parent.querySelector('.form-item-control') || 
                                           parent.querySelector('.input-control') || 
                                           parent.querySelector('.u-form-control') || 
                                           parent;
                    }
                }
                
                if (!controlContainer) continue;
                
                // 在控件容器中查找各种类型的输入元素
                var inputElement = controlContainer.querySelector(
                    'input:not([type="hidden"]), textarea, select, ' +
                    '.nc-input, .refer-input, .u-form-control, ' +
                    '.u-select-selection-rendered, .u-select, ' +
                    '.calendar-picker, .datepicker'
                );
                
                // 特殊情况: 处理隐藏输入框
                var hiddenInput = controlContainer.querySelector('input[type="hidden"], input.hidden-input');
                
                // 组合返回字段信息
                if (inputElement) {
                    result.push({
                        labelText: labelText,
                        element: inputElement,
                        hiddenElement: hiddenInput
                    });
                }
            }
            
            return result;
        """, container)
        
        print(f"找到 {len(form_fields)} 个表单字段")
        
        # 填写表单
        filled_fields = 0
        for field in form_fields:
            label_text = field['labelText']
            input_element = field['element']
            is_special_field = field.get('isSpecialField', False)
            
            print(f"处理字段: '{label_text}', 是否特殊字段: {is_special_field}")
            
            # 查找匹配的JSON键
            matched_key = None
            for json_key in form_data.keys():
                if label_text == json_key:
                    matched_key = json_key
                    break
            
            if matched_key:
                value = form_data[matched_key]
                print(f"找到字段 '{label_text}' 的输入框，填写值: '{value}'")
                
                # 特殊字段处理
                if is_special_field:
                    print(f"发现特殊字段: {label_text}，直接进行处理")
                    try:
                        # 直接设置值
                        driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                        # 触发change事件
                        driver.execute_script("""
                            var event = new Event('change', { bubbles: true });
                            arguments[0].dispatchEvent(event);
                        """, input_element)
                        filled_fields += 1
                        print(f"成功填写特殊字段: {label_text}")
                        continue
                    except Exception as e:
                        print(f"处理特殊字段时出错: {e}，尝试常规方法")
                
                # 获取元素类型信息
                tag_name = driver.execute_script("return arguments[0].tagName.toLowerCase();", input_element)
                element_class = driver.execute_script("return arguments[0].className || '';", input_element)
                element_type = driver.execute_script("return arguments[0].type || '';", input_element)
                
                print(f"元素类型: {tag_name}, 类名: {element_class}, 输入类型: {element_type}")
                
                # 根据字段类型和元素类型选择不同的处理方法
                if "hidden-input" in element_class:
                    print(f"发现hidden-input类型字段: {label_text}")
                    # 查找父元素中的可见输入框
                    try:
                        parent_li = driver.execute_script("return arguments[0].closest('li');", input_element)
                        visible_input = parent_li.find_element(By.CSS_SELECTOR, ".nc-input, .refer-input, .u-form-control")
                        print(f"找到对应的可见输入框，尝试填写")
                        
                        # 点击可见输入框
                        visible_input.click()
                        time.sleep(0.5)
                        
                        # 清除并输入值
                        visible_input.clear()
                        visible_input.send_keys(str(value))
                        visible_input.send_keys(Keys.TAB)
                        
                        # 设置隐藏输入框的值
                        driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                        
                        filled_fields += 1
                        print(f"成功填写hidden-input字段: {label_text}")
                        continue
                    except Exception as e:
                        print(f"处理hidden-input失败: {e}，尝试常规方法")
                
                if label_text == "报销事由":
                    print(f"使用JavaScript直接设置报销事由字段值: '{value}'")
                    # 使用JavaScript直接设置值
                    driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                    # 触发change事件以确保值被正确识别
                    driver.execute_script("""
                        var event = new Event('change', { bubbles: true });
                        arguments[0].dispatchEvent(event);
                    """, input_element)
                elif tag_name == "textarea":
                    # 文本区域处理
                    print(f"处理文本区域: {label_text}")
                    driver.execute_script("arguments[0].value = '';", input_element)
                    input_element.send_keys(str(value))
                elif "select" in element_class.lower() or tag_name == "select":
                    # 下拉菜单处理
                    print(f"处理下拉菜单: {label_text}")
                    input_element.click()
                    time.sleep(0.5)
                    # 尝试查找并点击匹配的选项
                    try:
                        option = driver.find_element(By.XPATH, f"//li[contains(text(), '{value}')]")
                        option.click()
                    except:
                        print(f"未找到下拉选项: {value}，尝试直接设置值")
                        driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                elif "date" in element_class.lower() or "calendar" in element_class.lower():
                    # 日期选择器处理
                    print(f"处理日期字段: {label_text}")
                    input_element.click()  # 点击打开日期选择器
                    time.sleep(0.5)
                    # 尝试直接设置值
                    driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                    input_element.send_keys(Keys.TAB)  # 按Tab关闭日期选择器
                elif "refer-input" in element_class or "nc-input" in element_class:
                    # 引用输入框处理
                    print(f"处理引用输入框: {label_text}")
                    input_element.click()
                    time.sleep(0.5)
                    input_element.clear()
                    input_element.send_keys(str(value))
                    input_element.send_keys(Keys.TAB)
                    time.sleep(0.5)
                    
                    # 检查是否需要从下拉列表选择
                    try:
                        dropdown_items = driver.find_elements(By.XPATH, f"//li[contains(text(), '{value}')]")
                        if dropdown_items and dropdown_items[0].is_displayed():
                            dropdown_items[0].click()
                            time.sleep(0.5)
                    except:
                        # 没有找到下拉项或不可见，继续处理
                        pass
                else:
                    # 普通输入框处理
                    # 清除当前值
                    try:
                        input_element.clear()
                    except:
                        print(f"无法清除字段 '{label_text}' 的值，尝试使用JavaScript直接设置")
                        driver.execute_script("arguments[0].value = '';", input_element)
                    
                    # 输入新值
                    try:
                        input_element.send_keys(str(value))
                    except:
                        print(f"无法使用send_keys填写值，尝试使用JavaScript设置")
                        driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                        # 触发change事件
                        driver.execute_script("""
                            var event = new Event('change', { bubbles: true });
                            arguments[0].dispatchEvent(event);
                        """, input_element)
                
                time.sleep(0.5)  # 等待输入完成
                
                # 按Tab键移动到下一个字段
                try:
                    input_element.send_keys(Keys.TAB)
                except:
                    print(f"无法发送Tab键，尝试点击页面其他位置")
                    actions = ActionChains(driver)
                    actions.move_by_offset(10, 10).click().perform()
                
                filled_fields += 1
            else:
                print(f"JSON数据中未找到与 '{label_text}' 匹配的键")
        
        print(f"表单填写完成，成功填写 {filled_fields}/{len(form_fields)} 个字段")
        
        return True
    except Exception as e:
        print(f"填写表单时出错: {e}")
        import traceback
        traceback.print_exc()
        
        return False

@register_tool('ncc_submission')
class NCCSubmission(BaseTool):
    """NCC提交工具，用于将确认后的报销单据提交到NCC系统并执行RPA自动化操作"""
    
    description = '将确认后的报销单据自动提交到NCC系统，并可选择自动执行RPA流程完成后续操作。'
    parameters = [{
        'name': 'submission_params',
        'type': 'object',
        'description': '提交参数',
        'properties': {
            'reimbursement_form': {'type': 'object', 'description': '确认后的报销单数据'},
            'confirm': {'type': 'boolean', 'description': '是否确认提交'},
            'execute_rpa': {'type': 'boolean', 'description': '是否执行RPA自动化操作', 'default': False}
        },
        'required': ['reimbursement_form', 'confirm']
    }]
    
    def __init__(self, tool_cfg=None):
        super().__init__(tool_cfg)
        self.ncc_url = None
        self.ncc_bill_id = None
        self.submission_time = None
        # 添加交通费和住宿费处理相关的XPath
        self.transportation_xpath = {
            'first_increase_button': "//*[@id=\"js_lightTabs_header_arap_bxbusitem\"]/div[4]/div/span/div/button[1]",
            'subsequent_increase_button': "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[1]/button[2]",
            'expand_button': "//*[@id=\"js_lightTabs_arap_bxbusitem\"]/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]",
            'modal': "//*[@id='tableModal']/div[1]/div/div",
            'confirm_button': "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[2]/span[5]"
        }
        
        self.hotel_xpath = {
            'first_increase_button': "//*[@id=\"js_lightTabs_header_other\"]/div[4]/div/span/div/button[1]",
            'subsequent_increase_button': "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[1]/button[2]", 
            'expand_button': "//*[@id=\"js_lightTabs_other\"]/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]",
            'confirm_button': "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[2]/span[5]"
        }

    def call(self, params: str, **kwargs) -> str:
        """处理NCC提交请求"""
        try:
            submission_data = json.loads(params)['submission_params']
            reimbursement_form = submission_data.get('reimbursement_form', {})
            confirm = submission_data.get('confirm', False)
            execute_rpa = submission_data.get('execute_rpa', False)
            
            if not reimbursement_form:
                return json.dumps({
                    'status': 'error',
                    'message': '无法提交：缺少报销单信息'
                }, ensure_ascii=False)
            
            if not confirm:
                return json.dumps({
                    'status': 'pending',
                    'message': '报销单尚未确认提交，可以继续修改',
                    'reimbursement_form': reimbursement_form
                }, ensure_ascii=False)
            
            # 模拟提交过程
            print("开始提交到NCC系统...")
            time.sleep(1)  # 模拟网络延迟
            
            # 生成模拟NCC单据ID
            self.ncc_bill_id = f"NCC{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
            self.submission_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 设置NCC系统URL
            self.ncc_url = f"http://110.90.119.97:8808/nccloud/resources/workbench/public/common/main/index.html#"
            
            # 构建返回结果
            result = {
                    'status': 'success',
                    'message': '报销单已成功提交到NCC系统',
                'submission_time': self.submission_time,
                'ncc_bill_id': self.ncc_bill_id,
                'ncc_url': self.ncc_url
            }
            
            # 执行RPA自动化操作
            if execute_rpa:
                print(f"用户选择执行RPA自动化操作")
                rpa_result = self.execute_rpa_workflow(reimbursement_form)
                result['rpa_status'] = rpa_result.get('status')
                result['rpa_message'] = rpa_result.get('message')
                if 'screenshot' in rpa_result:
                    result['screenshot'] = rpa_result['screenshot']
            
            return json.dumps(result, ensure_ascii=False)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({
                'status': 'error',
                'message': f'NCC提交处理失败: {str(e)}'
            }, ensure_ascii=False)
    
    def execute_rpa_workflow(self, reimbursement_form: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行RPA工作流，自动在NCC系统中填写报销单据
        
        :param reimbursement_form: 报销表单数据
        :return: 执行结果
        """
        try:
            import subprocess
            import os
            import sys
            
            # 获取项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 确保json目录及子目录存在
            json_dir = os.path.join(base_dir, "json")
            hotel_dir = os.path.join(json_dir, "hotel")
            transportation_dir = os.path.join(json_dir, "transportation")
            
            print(f"准备目录：")
            print(f"- JSON目录: {json_dir}")
            print(f"- 酒店数据目录: {hotel_dir}")
            print(f"- 交通数据目录: {transportation_dir}")
            
            # # 创建目录（如果不存在）
            # os.makedirs(json_dir, exist_ok=True)
            # os.makedirs(hotel_dir, exist_ok=True)
            # os.makedirs(transportation_dir, exist_ok=True)
            
            # # 清空目录中的旧文件
            # for folder in [hotel_dir, transportation_dir]:
            #     for file in os.listdir(folder):
            #         if file.endswith('.json'):
            #             os.remove(os.path.join(folder, file))
            
            # # 保存数据到JSON文件
            # hotel_data = reimbursement_form.get('hotel_data', [])
            # transportation_data = reimbursement_form.get('transportation_data', [])
            
            # print(f"保存 {len(hotel_data)} 条酒店数据")
            # for i, hotel_item in enumerate(hotel_data):
            #     hotel_file = os.path.join(hotel_dir, f"hotel_{i+1}.json")
            #     with open(hotel_file, 'w', encoding='utf-8') as f:
            #         json.dump(hotel_item, f, ensure_ascii=False, indent=4)
            
            # print(f"保存 {len(transportation_data)} 条交通数据")
            # for i, transport_item in enumerate(transportation_data):
            #     transport_file = os.path.join(transportation_dir, f"transport_{i+1}.json")
            #     with open(transport_file, 'w', encoding='utf-8') as f:
            #         json.dump(transport_item, f, ensure_ascii=False, indent=4)
            
            # 保存主表单数据
            main_form_data = self._convert_reimbursement_to_form_data(reimbursement_form)
            main_form_file = os.path.join(base_dir, "test.json")
            with open(main_form_file, 'w', encoding='utf-8') as f:
                json.dump(main_form_data, f, ensure_ascii=False, indent=4)
            
            # 直接运行test3_all.py
            test3_path = os.path.join(base_dir, "test3_all.py")
            print(f"运行RPA脚本: {test3_path}")
            
            # 修复test3_all.py中的路径问题
            try:
                # 读取test3_all.py文件内容
                with open(test3_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 修复可能存在的路径问题
                # 使用正则表达式查找常见的路径模式
                import re
                
                # 转换为安全的路径格式（使用正斜杠）
                hotel_dir_safe = hotel_dir.replace('\\', '/')
                transportation_dir_safe = transportation_dir.replace('\\', '/')
                
                # 替换transportation_folder的定义
                content = re.sub(
                    r'transportation_folder\s*=\s*["\'].*?["\']', 
                    f'transportation_folder = "{transportation_dir_safe}"', 
                    content
                )
                
                # 替换hotel_folder的定义
                content = re.sub(
                    r'hotel_folder\s*=\s*["\'].*?["\']', 
                    f'hotel_folder = "{hotel_dir_safe}"', 
                    content
                )
                
                # 保存修改后的文件
                with open(test3_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"已修复test3_all.py中的路径问题")
                
            except Exception as e:
                print(f"修复test3_all.py路径时出错: {e}")
                # 继续执行，即使修复失败
            
            # 使用Python解释器运行脚本
            cmd = [sys.executable, test3_path]
            print(f"执行命令: {' '.join(cmd)}")
            
            # 启动进程
            process = subprocess.Popen(cmd)
            
            # 不等待进程结束，立即返回成功信息
            return {
                'success': True, 
                'message': '已启动RPA自动化操作，请等待浏览器完成表单填写'
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'执行RPA工作流时出错: {str(e)}'}
    
    def _perform_login(self, driver):
        """执行登录操作"""
        try:
            # 等待用户名输入框加载
            username_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_input.clear()
            username_input.send_keys("T18638")  # 使用实际用户名
            
            # 输入密码
            password_input = driver.find_element(By.ID, "password")
            password_input.clear()
            password_input.send_keys("M@fh18524730187")  # 使用实际密码
            
            # 点击登录按钮
            login_button = driver.find_element(By.ID, "loginBtn")
            login_button.click()
            
            # 等待登录完成，使用更长的等待时间
            print("登录成功，等待页面加载...")
            time.sleep(3)
            return True
        except Exception as e:
            print(f"登录过程中出错: {e}")
            return False
    
    def _navigate_to_expense_form(self, driver):
        """导航到员工差旅费报销单页面"""
        try:
            # 点击应用菜单图标
            print("点击应用菜单图标...")
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.nc-workbench-icon[data-step='1']"))
            ).click()
            
            # 等待菜单加载
            time.sleep(1)
            
            # 点击"费用管理"菜单
            print("点击费用管理菜单...")
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'费用管理')]"))
            ).click()
            
            # 等待子菜单加载
            time.sleep(1)
            
            # 点击"员工差旅费报销单"选项
            print("点击员工差旅费报销单...")
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'item-app') and contains(text(),'员工差旅费报销单')]"))
            ).click()
            
            # 等待新标签页打开
            print("等待新标签页打开...")
            time.sleep(3)
            
            # 获取所有窗口句柄并切换到新标签页
            print("切换到新打开的标签页...")
            window_handles = driver.window_handles
            if len(window_handles) > 1:
                print(f"检测到{len(window_handles)}个标签页，切换到最新打开的标签页")
                driver.switch_to.window(window_handles[-1])
            else:
                print("未检测到新标签页，保持在当前标签页")
            
            # 等待页面加载
            print("正在进入员工差旅费报销单页面...")
            time.sleep(2)
            
            # 将浏览器窗口最大化
            print("最大化浏览器窗口...")
            driver.maximize_window()
            time.sleep(2)
            
            return True
        except Exception as e:
            print(f"导航过程中出错: {e}")
            return False
    
    def _fill_main_form(self, driver, form_data):
        """填写主表单字段"""
        try:
            # 查找iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                print(f"找到{len(iframes)}个iframe，切换到第一个")
                driver.switch_to.frame(iframes[0])
            
            # 等待表单加载完成
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.lightapp-component-form"))
            )
            print("表单已加载")
            
            if UTILS_IMPORTED:
                # 使用utils.py中的find_form_fields_with_js和相关函数
                # 不需要重复导入，之前已经导入了
                print(f"使用utils.py中的fill_form函数填写主表单...")
                if fill_form(driver, form_data):
                    print("主表单填写成功")
                else:
                    print("主表单填写失败")
            else:
                # 使用JavaScript查找表单字段
                print("使用JavaScript查找表单字段...")
                form_fields = self._find_form_fields_with_js(driver)
                print(f"找到{len(form_fields)}个表单字段")
                
                # 填写表单
                filled_fields = 0
                for field in form_fields:
                    label_text = field['labelText']
                    input_element = field['element']
                    is_special_field = field.get('isSpecialField', False)
                    
                    print(f"处理字段: '{label_text}', 是否特殊字段: {is_special_field}")
                    
                    # 查找匹配的JSON键
                    matched_key = None
                    for json_key in form_data.keys():
                        if label_text == json_key:
                            matched_key = json_key
                            break
                    
                    if matched_key:
                        value = form_data[matched_key]
                        print(f"找到字段 '{label_text}' 的输入框，填写值: '{value}'")
                        
                        # 特殊字段处理
                        if is_special_field:
                            print(f"发现特殊字段: {label_text}，直接进行处理")
                            try:
                                # 直接设置值
                                driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                                # 触发change事件
                                driver.execute_script("""
                                    var event = new Event('change', { bubbles: true });
                                    arguments[0].dispatchEvent(event);
                                """, input_element)
                                filled_fields += 1
                                print(f"成功填写特殊字段: {label_text}")
                                continue
                            except Exception as e:
                                print(f"处理特殊字段时出错: {e}，尝试常规方法")
                        
                        # 获取元素类型信息
                        tag_name = driver.execute_script("return arguments[0].tagName.toLowerCase();", input_element)
                        element_class = driver.execute_script("return arguments[0].className || '';", input_element)
                        element_type = driver.execute_script("return arguments[0].type || '';", input_element)
                        
                        print(f"元素类型: {tag_name}, 类名: {element_class}, 输入类型: {element_type}")
                        
                        # 根据字段类型和元素类型选择不同的处理方法
                        if "hidden-input" in element_class:
                            print(f"发现hidden-input类型字段: {label_text}")
                            # 查找父元素中的可见输入框
                            try:
                                parent_li = driver.execute_script("return arguments[0].closest('li');", input_element)
                                visible_input = parent_li.find_element(By.CSS_SELECTOR, ".nc-input, .refer-input, .u-form-control")
                                print(f"找到对应的可见输入框，尝试填写")
                                
                                # 点击可见输入框
                                visible_input.click()
                                time.sleep(0.5)
                                
                                # 清除并输入值
                                visible_input.clear()
                                visible_input.send_keys(str(value))
                                visible_input.send_keys(Keys.TAB)
                                
                                # 设置隐藏输入框的值
                                driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                                
                                filled_fields += 1
                                print(f"成功填写hidden-input字段: {label_text}")
                                continue
                            except Exception as e:
                                print(f"处理hidden-input失败: {e}，尝试常规方法")
                        
                        if label_text == "报销事由":
                            print(f"使用JavaScript直接设置报销事由字段值: '{value}'")
                            # 使用JavaScript直接设置值
                            driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                            # 触发change事件以确保值被正确识别
                            driver.execute_script("""
                                var event = new Event('change', { bubbles: true });
                                arguments[0].dispatchEvent(event);
                            """, input_element)
                        elif tag_name == "textarea":
                            # 文本区域处理
                            print(f"处理文本区域: {label_text}")
                            driver.execute_script("arguments[0].value = '';", input_element)
                            input_element.send_keys(str(value))
                        elif "select" in element_class.lower() or tag_name == "select":
                            # 下拉菜单处理
                            print(f"处理下拉菜单: {label_text}")
                            input_element.click()
                            time.sleep(0.5)
                            # 尝试查找并点击匹配的选项
                            try:
                                option = driver.find_element(By.XPATH, f"//li[contains(text(), '{value}')]")
                                option.click()
                            except:
                                print(f"未找到下拉选项: {value}，尝试直接设置值")
                                driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                        elif "date" in element_class.lower() or "calendar" in element_class.lower():
                            # 日期选择器处理
                            print(f"处理日期字段: {label_text}")
                            input_element.click()  # 点击打开日期选择器
                            time.sleep(0.5)
                            # 尝试直接设置值
                            driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                            input_element.send_keys(Keys.TAB)  # 按Tab关闭日期选择器
                        elif "refer-input" in element_class or "nc-input" in element_class:
                            # 引用输入框处理
                            print(f"处理引用输入框: {label_text}")
                            input_element.click()
                            time.sleep(0.5)
                            input_element.clear()
                            input_element.send_keys(str(value))
                            input_element.send_keys(Keys.TAB)
                            time.sleep(0.5)
                            
                            # 检查是否需要从下拉列表选择
                            try:
                                dropdown_items = driver.find_elements(By.XPATH, f"//li[contains(text(), '{value}')]")
                                if dropdown_items and dropdown_items[0].is_displayed():
                                    dropdown_items[0].click()
                                    time.sleep(0.5)
                            except:
                                # 没有找到下拉项或不可见，继续处理
                                pass
                        else:
                            # 普通输入框处理
                            # 清除当前值
                            try:
                                input_element.clear()
                            except:
                                print(f"无法清除字段 '{label_text}' 的值，尝试使用JavaScript直接设置")
                                driver.execute_script("arguments[0].value = '';", input_element)
                            
                            # 输入新值
                            try:
                                input_element.send_keys(str(value))
                            except:
                                print(f"无法使用send_keys填写值，尝试使用JavaScript设置")
                                driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                                # 触发change事件
                                driver.execute_script("""
                                    var event = new Event('change', { bubbles: true });
                                    arguments[0].dispatchEvent(event);
                                """, input_element)
                        
                        time.sleep(0.5)  # 等待输入完成
                        
                        # 按Tab键移动到下一个字段
                        try:
                            input_element.send_keys(Keys.TAB)
                        except:
                            print(f"无法发送Tab键，尝试点击页面其他位置")
                            actions = ActionChains(driver)
                            actions.move_by_offset(10, 10).click().perform()
                        
                        filled_fields += 1
                    else:
                        print(f"JSON数据中未找到与 '{label_text}' 匹配的键")
                
                print(f"表单填写完成，成功填写 {filled_fields}/{len(form_data)} 个字段")
            
            # 如果之前切换到了iframe，切回主文档
            if iframes:
                driver.switch_to.default_content()
                
        except Exception as e:
            print(f"填写表单时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 确保切回主文档
            try:
                driver.switch_to.default_content()
            except:
                pass
    
    def _find_form_fields_with_js(self, driver):
        """
        使用JavaScript查找表单字段和输入框，专门针对图片中所示的HTML结构
        
        :param driver: WebDriver对象
        :return: 表单字段列表，每个字段包含标签文本和对应的输入元素
        """
        script = """
            var result = [];
            
            // 1. 查找lightapp-component-form元素
            var formElement = document.querySelector('div.lightapp-component-form');
            if (!formElement) return result;
            
            // 2. 查找所有span元素
            var spans = formElement.querySelectorAll('span');
            
            for (var i = 0; i < spans.length; i++) {
                var span = spans[i];
                
                // 3. 在每个span中查找form-item-label元素
                var labelDiv = span.querySelector('div.form-item-label');
                if (!labelDiv) continue;
                
                // 获取标签文本
                var labelText = labelDiv.textContent.trim();
                if (!labelText) continue;
                
                // 清理标签文本（去除星号和冒号）
                var cleanLabelText = labelText.replace(/[*：:]/g, '').trim();
                
                // 4. 查找控件容器
                var controlDiv = span.querySelector('div.form-item-control');
                if (!controlDiv) continue;
                
                // 检查是否包含隐藏输入框和显示输入框的特殊结构
                var hiddenInput = controlDiv.querySelector('input.hidden-input');
                var referInput = controlDiv.querySelector('.nc-input, .refer-input, .u-form-control');
                
                // 特殊情况处理：hidden-input + refer-input 结构
                if (hiddenInput && referInput) {
                    result.push({
                        labelText: cleanLabelText,
                        element: referInput,  // 使用可见输入框
                        hiddenElement: hiddenInput,  // 保存隐藏输入框引用
                        isSpecialField: true
                    });
                    continue;
                }
                
                // 5. 在控件容器中查找各类输入元素
                var inputElement = controlDiv.querySelector(
                    'input:not([type="hidden"]), select, textarea, ' + 
                    '.refer-input, .nc-input, .u-form-control, ' + 
                    '.u-select-selection-rendered, .u-select, ' + 
                    '.calendar-picker, .datepicker, .date-picker'
                );
                
                if (inputElement) {
                    result.push({
                        labelText: cleanLabelText,
                        element: inputElement,
                        isSpecialField: false
                    });
                }
            }
            
            return result;
        """
        
        return driver.execute_script(script)
    
    def _handle_special_field(self, driver, field, value):
        """
        处理特殊结构的输入字段，比如hidden-input + refer-input组合
        
        :param driver: WebDriver对象
        :param field: 字段信息
        :param value: 要填写的值
        :return: 是否成功处理
        """
        element = field['element']
        hidden_element = field.get('hiddenElement')
        
        try:
            # 点击可见的输入框，激活它
            element.click()
            time.sleep(0.5)
            
            # 直接在可见输入框中输入值
            element.clear()
            element.send_keys(str(value))
            time.sleep(0.5)
            
            # 点击一下以确保值被接受
            element.send_keys(Keys.TAB)
            time.sleep(0.5)
            
            # 检查是否需要选择下拉项
            try:
                # 尝试查找包含该值的下拉项
                dropdown_item = driver.find_element(By.XPATH, f"//li[contains(text(), '{value}')]")
                if dropdown_item.is_displayed():
                    print(f"找到下拉项：{value}，点击选择")
                    dropdown_item.click()
                    time.sleep(0.5)
            except:
                # 没有找到下拉项或下拉项不可见，继续处理
                pass
            
            # 如果有隐藏输入框，同时设置它的值
            if hidden_element:
                driver.execute_script("arguments[0].value = arguments[1];", hidden_element, str(value))
                # 触发change事件
                driver.execute_script("""
                    var event = new Event('change', { bubbles: true });
                    arguments[0].dispatchEvent(event);
                """, hidden_element)
            
            return True
        except Exception as e:
            print(f"处理特殊字段时出错: {e}")
            return False
    
    def _convert_reimbursement_to_form_data(self, reimbursement_form):
        """将报销单数据转换为表单需要的格式"""
        # 获取报销事由，用于匹配报销类型
        reimbursement_reason = reimbursement_form.get("报销事由", "出差")
        
        # 使用关键字匹配获取报销类型
        reimbursement_type = get_reimbursement_type_by_keyword(reimbursement_reason)
        
        # 直接从报销单中获取字段值
        form_data = {
            "报销事由": reimbursement_form.get("报销事由", "出差"),
            "报销类型": reimbursement_type,  # 使用关键字匹配的报销类型
            "附件张数": reimbursement_form.get("附件张数", "3"),
            "收款人": reimbursement_form.get("收款人", "涂超"),
            "收款银行名称": reimbursement_form.get("收款银行名称", "兴业银行"),
            "收款人卡号": reimbursement_form.get("收款人卡号", ""),
            "分摊原因": reimbursement_form.get("分摊原因", ""),
            "住宿费超标金额": reimbursement_form.get("住宿费超标金额", "0"),
            "城市内公务交通车费超标金额": reimbursement_form.get("城市内公务交通车费超标金额", "0"),
            "超标说明": reimbursement_form.get("超标说明", "无")
        }
        
        print(f"根据报销事由 '{reimbursement_reason}' 匹配到报销类型: {reimbursement_type}")
        print(f"使用的表单数据: {form_data}")
        return form_data

    def _process_transportation_data(self, driver, reimbursement_form):
        """
        处理交通费用数据
        
        :param driver: WebDriver对象
        :param reimbursement_form: 报销表单数据
        :return: 处理结果
        """
        try:
            # 获取交通数据
            transportation_data = reimbursement_form.get('transportation_data', [])
            if not transportation_data:
                print("没有交通费用数据需要处理")
                return {'success': True, 'message': '没有交通费用数据需要处理'}
            
            print(f"开始处理 {len(transportation_data)} 条交通费用数据")
            
            # 定义按钮的XPath
            first_increase_button_xpath = "//*[@id=\"js_lightTabs_header_arap_bxbusitem\"]/div[4]/div/span/div/button[1]"  # 第一次点击的增行按钮
            subsequent_increase_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[1]/button[2]"  # 后续点击的增行按钮
            expand_button_xpath = "//*[@id=\"js_lightTabs_arap_bxbusitem\"]/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]"
            modal_xpath = "//*[@id='tableModal']/div[1]/div/div"
            confirm_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[2]/span[5]"
            
            # 处理所有交通费用数据
            for index, transport_data in enumerate(transportation_data):
                print(f"\n处理第 {index+1}/{len(transportation_data)} 条交通费用数据")
                
                # 处理日期格式 - 将YYYYMMDD转换为YYYY-MM-DD格式
                if 'out_date' in transport_data and len(transport_data['out_date']) == 8:
                    date_str = transport_data['out_date']
                    transport_data['out_date'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                if '出发日期' in transport_data and len(transport_data['出发日期']) == 8:
                    date_str = transport_data['出发日期']
                    transport_data['出发日期'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    
                if '到达日期' in transport_data and len(transport_data['到达日期']) == 8:
                    date_str = transport_data['到达日期']
                    transport_data['到达日期'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                # 1. 点击增行按钮
                if index == 0:
                    # 第一次使用原始增行按钮XPath
                    print("使用第一次的增行按钮XPath")
                    increase_button_xpath = first_increase_button_xpath
                else:
                    # 后续使用新的增行按钮XPath
                    print("使用后续的增行按钮XPath")
                    increase_button_xpath = subsequent_increase_button_xpath
                
                # 点击增行按钮
                self._click_button(driver, increase_button_xpath, "交通费用增行按钮")
                time.sleep(0.8)  # 增加等待时间，确保增行按钮点击生效
                
                # 2. 点击展开按钮 (只在第一次处理时需要)
                if index == 0:
                    self._click_button(driver, expand_button_xpath, "交通费用展开按钮")
                    time.sleep(0.8)  # 增加等待时间，确保展开按钮点击生效
                
                # 3. 填写表单 - 使用自定义的表单填写方法
                print(f"开始填写交通费用表单数据...")
                # 使用自定义的填写表单方法，处理日期字段
                success = self._fill_form_with_date_handling(driver, transport_data, modal_xpath)
                if success:
                    print(f"交通费用表单数据填写成功")
                else:
                    print(f"交通费用表单数据填写失败")
                    continue
                
                print(f"成功处理第 {index+1}/{len(transportation_data)} 条交通费用数据")
                time.sleep(0.8)  # 增加等待时间，确保数据处理完成
            
            # 所有数据处理完毕后，点击确认按钮
            time.sleep(0.8)  # 确保在点击确认按钮前所有操作已完成
            self._click_button(driver, confirm_button_xpath, "交通费用确认按钮")
            
            return {'success': True, 'message': f'成功处理 {len(transportation_data)} 条交通费用数据'}
        
        except Exception as e:
            print(f"处理交通费用数据时出错: {e}")
            import traceback
            traceback.print_exc()
            # 确保切回主文档
            try:
                driver.switch_to.default_content()
            except:
                pass
            return {'success': False, 'message': f'处理交通费用数据时出错: {e}'}

    def _process_hotel_data(self, driver, reimbursement_form):
        """
        处理酒店费用数据
        
        :param driver: WebDriver对象
        :param reimbursement_form: 报销表单数据
        :return: 处理结果
        """
        try:
            # 获取酒店数据
            hotel_data = reimbursement_form.get('hotel_data', [])
            if not hotel_data:
                print("没有酒店费用数据需要处理")
                return {'success': True, 'message': '没有酒店费用数据需要处理'}
            
            print(f"开始处理 {len(hotel_data)} 条酒店费用数据")
            
            # 定义hotel区域的按钮XPath
            hotel_first_increase_button_xpath = "//*[@id=\"js_lightTabs_header_other\"]/div[4]/div/span/div/button[1]"  # 第一次点击的增行按钮
            hotel_expand_button_xpath = "//*[@id=\"js_lightTabs_other\"]/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]"  # 展开按钮
            hotel_subsequent_increase_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[1]/button[2]"  # 后续点击的增行按钮
            hotel_confirm_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[2]/span[5]"  # 确认按钮
            modal_xpath = "//*[@id='tableModal']/div[1]/div/div"
            
            # 处理所有酒店费用数据
            for index, hotel_item in enumerate(hotel_data):
                print(f"\n处理第 {index+1}/{len(hotel_data)} 条酒店费用数据")
                
                # 处理日期格式 - 将YYYYMMDD转换为YYYY-MM-DD格式
                if '入住日期' in hotel_item and len(hotel_item['入住日期']) == 8:
                    date_str = hotel_item['入住日期']
                    hotel_item['入住日期'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    
                if '离店日期' in hotel_item and len(hotel_item['离店日期']) == 8:
                    date_str = hotel_item['离店日期']
                    hotel_item['离店日期'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                # 1. 点击增行按钮
                if index == 0:
                    # 第一次使用原始增行按钮XPath
                    print("使用第一次的hotel增行按钮XPath")
                    increase_button_xpath = hotel_first_increase_button_xpath
                else:
                    # 后续使用新的增行按钮XPath
                    print("使用后续的hotel增行按钮XPath")
                    increase_button_xpath = hotel_subsequent_increase_button_xpath
                
                # 点击增行按钮
                self._click_button(driver, increase_button_xpath, "酒店费用增行按钮")
                time.sleep(0.8)  # 增加等待时间，确保按钮点击生效
                
                # 2. 点击展开按钮 (只在第一次处理时需要)
                if index == 0:
                    # 尝试使用完整XPath
                    try:
                        print(f"尝试点击hotel展开按钮...")
                        self._click_button(driver, hotel_expand_button_xpath, "酒店费用展开按钮")
                        time.sleep(0.8)  # 增加等待时间，确保展开按钮点击生效
                    except Exception as e:
                        print(f"点击hotel展开按钮失败: {e}")
                        
                        # 尝试使用JavaScript直接点击
                        try:
                            print("尝试使用JavaScript直接查找和点击hotel展开按钮...")
                            js_result = driver.execute_script("""
                                var xpath = "//*[@id='js_lightTabs_other']/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]";
                                var element = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (element) {
                                    element.click();
                                    return "成功点击展开按钮";
                                } else {
                                    return "未找到展开按钮";
                                }
                            """)
                            print(f"JavaScript点击结果: {js_result}")
                            time.sleep(0.8)  # JavaScript执行后等待
                        except Exception as js_error:
                            print(f"JavaScript点击hotel展开按钮失败: {js_error}")
                        
                        # 备用方法：尝试通过文本内容找到展开按钮
                        try:
                            print("尝试通过文本内容查找hotel展开按钮...")
                            text_button = driver.find_element(By.XPATH, "//a[text()='展开']")
                            text_button.click()
                            print("通过文本内容成功点击hotel展开按钮")
                            time.sleep(0.8)  # 点击后等待
                        except Exception as text_error:
                            print(f"通过文本内容查找hotel展开按钮失败: {text_error}")
                
                # 3. 填写表单 - 使用自定义的表单填写方法
                print(f"开始填写hotel表单数据...")
                # 使用自定义的填写表单方法，处理日期字段
                success = self._fill_form_with_date_handling(driver, hotel_item, modal_xpath)
                if success:
                    print(f"hotel表单数据填写成功")
                else:
                    print(f"hotel表单数据填写失败")
                    continue
                
                print(f"成功处理第 {index+1}/{len(hotel_data)} 条酒店费用数据")
                time.sleep(0.8)  # 增加等待时间，确保数据处理完成
            
            # 所有hotel文件处理完毕后，点击确认按钮
            time.sleep(0.8)  # 确保在点击确认按钮前所有操作已完成
            self._click_button(driver, hotel_confirm_button_xpath, "酒店费用确认按钮")
            
            return {'success': True, 'message': f'成功处理 {len(hotel_data)} 条酒店费用数据'}
        
        except Exception as e:
            print(f"处理酒店费用数据时出错: {e}")
            import traceback
            traceback.print_exc()
            # 确保切回主文档
            try:
                driver.switch_to.default_content()
            except:
                pass
            return {'success': False, 'message': f'处理酒店费用数据时出错: {e}'}

    def _fill_form_with_date_handling(self, driver, form_data, modal_xpath=None):
        """
        自定义表单填写方法，专门处理日期字段问题
        
        :param driver: WebDriver对象
        :param form_data: 表单数据
        :param modal_xpath: 模态框XPath
        :return: 是否成功填写
        """
        try:
            # 使用utils模块中的函数获取模态框容器和表单字段
            from utils import get_modal_container, find_form_fields
            
            # 获取模态框容器
            container = get_modal_container(driver, modal_xpath)
            if not container:
                print("未找到模态框容器，无法填写表单")
                return False
            
            # 查找表单字段
            form_fields = find_form_fields(driver, container)
            if not form_fields:
                print("未找到表单字段，无法填写表单")
                return False
            
            # 填写表单
            success_count = 0
            date_fields = ['出发日期', '到达日期', '入住日期', '离店日期']  # 日期字段列表
            
            for json_key, value in form_data.items():
                print(f"尝试填写: {json_key} = {value}")
                
                # 查找匹配的字段
                input_element = None
                matched_label = None
                
                # 1. 先尝试精确匹配
                if json_key in form_fields:
                    input_element = form_fields[json_key]['input']
                    matched_label = json_key
                else:
                    # 2. 尝试模糊匹配
                    for field_label, field_info in form_fields.items():
                        # 检查JSON键是否包含在标签中，或标签是否包含在JSON键中
                        if json_key in field_label or field_label in json_key:
                            input_element = field_info['input']
                            matched_label = field_label
                            break
                
                # 填写字段
                if input_element:
                    print(f"找到匹配的标签: '{matched_label}'")
                    
                    # 检查是否是日期字段
                    is_date_field = any(date_field in matched_label for date_field in date_fields)
                    
                    if is_date_field:
                        # 使用JavaScript直接设置日期值
                        print(f"使用JavaScript处理日期字段: {matched_label}")
                        try:
                            # 获取日期控件的类型和信息
                            element_class = input_element.get_attribute("class") or ""
                            tag_name = input_element.tag_name.lower()
                            print(f"日期控件类型: {tag_name}, 类: {element_class}")
                            
                            # 尝试查找真正的日期输入框
                            date_input = driver.execute_script("""
                                var element = arguments[0];
                                var formItem = element.closest('.card-table-modal-form-item') || element.closest('.form-item');
                                if (!formItem) return null;
                                
                                // 查找可能的日期输入框
                                var inputs = formItem.querySelectorAll('input[type="text"], input:not([type]), input.form-control, input.u-form-control');
                                if (inputs.length > 0) return inputs[0];
                                
                                // 如果没找到输入框，尝试查找日期显示元素
                                var dateDisplay = formItem.querySelector('.u-form-control, .date-picker-value, .date-picker');
                                return dateDisplay;
                            """, input_element)
                            
                            if date_input:
                                print(f"找到日期输入元素，尝试设置值: {value}")
                                # 使用JavaScript设置值
                                driver.execute_script("""
                                    arguments[0].value = arguments[1];
                                    
                                    // 触发change事件
                                    var event = new Event('change', { bubbles: true });
                                    arguments[0].dispatchEvent(event);
                                    
                                    // 触发input事件
                                    var inputEvent = new Event('input', { bubbles: true });
                                    arguments[0].dispatchEvent(inputEvent);
                                    
                                    // 触发blur事件
                                    var blurEvent = new Event('blur', { bubbles: true });
                                    arguments[0].dispatchEvent(blurEvent);
                                """, date_input, str(value))
                                time.sleep(0.5)
                                
                                # 尝试点击页面其他位置关闭可能的日期选择器
                                try:
                                    driver.execute_script("document.body.click();")
                                    time.sleep(0.3)
                                except:
                                    pass
                                
                                success_count += 1
                                print(f"成功设置日期字段: {matched_label} = {value}")
                            else:
                                print(f"未找到日期输入元素，尝试使用备用方法")
                                # 尝试直接使用JavaScript修改整个表单项的值
                                result = driver.execute_script("""
                                    var formItem = arguments[0].closest('.card-table-modal-form-item') || arguments[0].closest('.form-item');
                                    if (!formItem) return "未找到表单项";
                                    
                                    try {
                                        // 尝试找到并更新所有可能的日期相关元素
                                        var elements = formItem.querySelectorAll('input, .u-form-control, [class*="date"], [class*="calendar"]');
                                        var updated = false;
                                        
                                        for (var i = 0; i < elements.length; i++) {
                                            var el = elements[i];
                                            // 设置值
                                            if (el.tagName === 'INPUT') {
                                                el.value = arguments[1];
                                                
                                                // 触发事件
                                                var changeEvent = new Event('change', { bubbles: true });
                                                el.dispatchEvent(changeEvent);
                                                
                                                var inputEvent = new Event('input', { bubbles: true });
                                                el.dispatchEvent(inputEvent);
                                                
                                                updated = true;
                                            } else {
                                                // 对于非输入元素，设置文本内容
                                                el.textContent = arguments[1];
                                                updated = true;
                                            }
                                        }
                                        
                                        return updated ? "成功更新日期" : "未找到可更新的元素";
                                    } catch (e) {
                                        return "设置日期时发生错误: " + e;
                                    }
                                """, input_element, str(value))
                                
                                print(f"JavaScript备用方法结果: {result}")
                                if "成功" in result:
                                    success_count += 1
                                    print(f"成功设置日期字段: {matched_label} = {value}")
                                else:
                                    print(f"设置日期字段失败: {matched_label}")
                        except Exception as e:
                            print(f"处理日期字段时出错: {e}")
                            continue
                    else:
                        # 非日期字段，使用utils.py中的fill_input_field函数
                        from utils import fill_input_field
                        if fill_input_field(driver, input_element, value):
                            print(f"成功填写: {json_key} = {value}")
                            success_count += 1
                        else:
                            print(f"填写失败: {json_key}")
                else:
                    print(f"未找到与 '{json_key}' 匹配的标签和输入框")
            
            print(f"表单填写完成，成功填写 {success_count}/{len(form_data)} 个字段")
            return success_count > 0
        except Exception as e:
            print(f"自定义表单填写出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _click_button(self, driver, xpath, button_name):
        """
        点击按钮，支持多种点击方式和错误处理
        
        :param driver: WebDriver对象
        :param xpath: 按钮的XPath
        :param button_name: 按钮名称（用于日志）
        :return: 是否成功点击
        """
        try:
            print(f"尝试点击{button_name}...")
            # 短暂等待确保页面已经准备好
            time.sleep(0.3)
            button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            
            # 确保按钮可见
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(0.3)  # 稍微等待滚动完成
            
            # 点击按钮
            button.click()
            print(f"成功点击{button_name}")
            time.sleep(0.5)  # 点击后等待，确保操作完成
            return True
        except Exception as e:
            print(f"点击{button_name}失败: {e}")
            
            # 尝试使用JavaScript点击
            try:
                # 短暂等待确保页面已经准备好
                time.sleep(0.3)
                result = driver.execute_script(f"""
                    var element = document.evaluate('{xpath}', 
                        document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (element) {{
                        element.click();
                        return "成功点击{button_name}";
                    }} else {{
                        return "未找到{button_name}";
                    }}
                """)
                print(f"JavaScript点击{button_name}结果: {result}")
                time.sleep(0.5)  # JavaScript执行后等待
                return "成功" in result
            except Exception as js_error:
                print(f"JavaScript点击{button_name}失败: {js_error}")
                
                # 如果是确认按钮，尝试通过文本内容查找
                if "确认" in button_name:
                    try:
                        print(f"尝试通过文本内容查找{button_name}...")
                        ok_buttons = driver.find_elements(By.XPATH, "//button[contains(text(),'确定') or contains(text(),'OK') or contains(text(),'保存')]")
                        if ok_buttons:
                            ok_buttons[0].click()
                            print(f"通过文本内容成功点击{button_name}")
                            time.sleep(0.5)  # 点击后等待
                            return True
                        else:
                            print(f"未找到{button_name}")
                    except Exception as text_error:
                        print(f"通过文本内容查找{button_name}失败: {text_error}")
                
                # 如果是展开按钮，尝试通过文本内容查找
                if "展开" in button_name:
                    try:
                        print(f"尝试通过文本内容查找{button_name}...")
                        text_button = driver.find_element(By.XPATH, "//a[text()='展开']")
                        text_button.click()
                        print(f"通过文本内容成功点击{button_name}")
                        time.sleep(0.5)  # 点击后等待
                        return True
                    except Exception as text_error:
                        print(f"通过文本内容查找{button_name}失败: {text_error}")
            
            return False