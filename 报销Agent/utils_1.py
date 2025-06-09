from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import json
import os
import re
import glob  # 添加glob模块导入

# 全局超时设置 - 减少等待时间以加快处理速度
DEFAULT_TIMEOUT = 3  # 默认等待时间
SHORT_TIMEOUT = 1    # 短等待时间

def load_json_data(file_path):
    """
    加载JSON文件中的表单数据
    
    :param file_path: JSON文件路径
    :return: 表单数据字典
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"已成功加载JSON数据: {file_path}")
        return data
    except Exception as e:
        print(f"加载JSON数据出错: {e}")
        # 返回默认表单数据
        return {
            "报销类型": "001/出差北上",
            "收支项目": "差旅费-外勤出差",
            "出发日期": "2020-05-09",
            "到达日期": "2020-05-10",
            "出发地点": "福州",
            "出差天数": "2",
            "到达地点": "深圳",
            "交通工具": "飞机",
            "说明（含同行人员等）": "同行",
            "飞机车船费": "500",
            "出差补贴": "100",
            "特殊事项": "无",
            "税率（%）": "1",
            "其他费用（民航发展基金、行李费等）": "100"
        }

def get_json_files_from_folder(folder_path):
    """
    获取指定文件夹中的所有JSON文件
    
    :param folder_path: 文件夹路径
    :return: JSON文件路径列表
    """
    try:
        # 确保文件夹路径存在
        if not os.path.exists(folder_path):
            print(f"警告: 文件夹不存在: {folder_path}")
            return []
        
        # 获取文件夹中所有的JSON文件
        json_files = glob.glob(os.path.join(folder_path, "*.json"))
        print(f"在 {folder_path} 中找到 {len(json_files)} 个JSON文件")
        
        # 返回排序后的文件列表（按文件名排序）
        return sorted(json_files)
    except Exception as e:
        print(f"获取JSON文件列表时出错: {e}")
        return []

def load_json_files_from_folder(folder_path):
    """
    加载指定文件夹中的所有JSON文件数据
    
    :param folder_path: 文件夹路径
    :return: JSON数据列表，每个元素是一个字典
    """
    try:
        # 获取文件夹中的所有JSON文件
        json_files = get_json_files_from_folder(folder_path)
        
        # 如果没有找到JSON文件，返回空列表
        if not json_files:
            print(f"在 {folder_path} 中未找到JSON文件")
            return []
        
        # 加载每个JSON文件中的数据
        json_data_list = []
        for file_path in json_files:
            try:
                data = load_json_data(file_path)
                json_data_list.append({
                    'file_path': file_path,
                    'data': data
                })
                print(f"已加载文件: {file_path}")
            except Exception as e:
                print(f"加载文件 {file_path} 时出错: {e}")
        
        print(f"共加载了 {len(json_data_list)} 个JSON文件的数据")
        return json_data_list
    except Exception as e:
        print(f"加载文件夹中的JSON文件时出错: {e}")
        return []

def click_expand_button(driver, xpath=None):
    """
    点击展开按钮
    
    :param driver: WebDriver对象
    :param xpath: 展开按钮的XPath (可选)
    :return: 是否成功点击
    """
    try:
        if xpath:
            # 使用提供的XPath
            button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            button.click()
            print(f"已点击指定的展开按钮: {xpath}")
        else:
            # 尝试常见的展开按钮XPath
            possible_xpaths = [
                "//button[contains(text(), '展开')]",
                "//span[contains(text(), '展开')]",
                "//a[contains(text(), '展开')]",
                "//div[contains(@class, 'expand')]",
                "//i[contains(@class, 'expand')]"
            ]
            
            for xpath in possible_xpaths:
                try:
                    button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    button.click()
                    print(f"已点击展开按钮: {xpath}")
                    break
                except:
                    continue
        
        # 等待模态框加载
        # time.sleep(1)
        return True
    except Exception as e:
        print(f"点击展开按钮时出错: {e}")
        return False

def get_modal_container(driver, modal_xpath=None):
    """
    获取模态框容器元素
    
    :param driver: WebDriver对象
    :param modal_xpath: 模态框的XPath (可选)
    :return: 模态框容器元素
    """
    try:
        if not modal_xpath:
            # 默认XPath
            modal_xpath = "//*[@id='tableModal']/div[1]/div/div"
        
        container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, modal_xpath))
        )
        return container
    except Exception as e:
        print(f"获取模态框容器时出错: {e}")
        
        # 尝试通过类名查找
        try:
            container = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.card-table-modal-form-wrap-body"))
            )
            return container
        except:
            print("无法找到模态框容器")
            return None

def find_form_fields(driver, container):
    """
    查找表单字段和输入框
    
    :param driver: WebDriver对象
    :param container: 模态框容器元素
    :return: 标签和输入框的映射字典
    """
    try:
        # 查找所有表单行
        form_fields = {}
        
        # 使用JavaScript查找表单字段，改进查找逻辑以匹配NC财务系统的表单结构
        fields = driver.execute_script("""
            var container = arguments[0];
            var fields = {};
            
            // 查找所有表单项目
            var formItems = container.querySelectorAll('.card-table-modal-form-item, .form-item, .form-group, .row, .form-row');
            
            for (var i = 0; i < formItems.length; i++) {
                var item = formItems[i];
                
                // 查找标签元素
                var labelContainer = item.querySelector('.side-form-label');
                if (!labelContainer) continue;
                
                var label = labelContainer.querySelector('label, .u-label');
                if (!label) continue;
                
                var labelText = '';
                
                // 获取标签的文本内容
                // 先尝试获取直接的文本内容
                var spans = label.querySelectorAll('span');
                if (spans.length > 0) {
                    // 如果有多个span，寻找不含"mark-required"类的span（实际内容span）
                    for (var j = 0; j < spans.length; j++) {
                        if (!spans[j].className.includes('mark-required')) {
                            labelText = spans[j].textContent.trim();
                            break;
                        }
                    }
                    
                    // 如果没找到内容span，使用所有span的内容
                    if (!labelText) {
                        for (var j = 0; j < spans.length; j++) {
                            labelText += spans[j].textContent.trim();
                        }
                    }
                } else {
                    // 没有span，使用整个label的文本
                    labelText = label.textContent.trim();
                }
                
                // 清理标签文本（移除*等特殊字符）
                labelText = labelText.replace(/[*:：]/g, '').trim();
                
                if (!labelText) continue;
                
                // 查找对应的输入控件容器
                var controlContainer = item.querySelector('.side-form-control');
                if (!controlContainer) continue;
                
                // 在控件容器中查找各类输入元素
                var inputElement = controlContainer.querySelector(
                    'input:not([type="hidden"]), select, textarea, ' + 
                    '.refer-input, .nc-input, .u-form-control, ' + 
                    '.u-select-selection-rendered, .u-select, ' + 
                    '.calendar-picker, .datepicker, .date-picker'
                );
                
                if (inputElement) {
                    fields[labelText] = {
                        label: labelText,
                        input: inputElement,
                        formItem: item
                    };
                }
            }
            
            return fields;
        """, container)
        
        if not fields:
            print("未找到表单字段")
        else:
            print(f"找到 {len(fields)} 个表单字段:")
            for label in fields:
                print(f"  - {label}")
        
        return fields
    except Exception as e:
        print(f"查找表单字段时出错: {e}")
        return {}

def handle_refer_input(driver, input_element, value):
    """
    处理第一种类型：带引用的输入框（图一所示）
    
    :param driver: WebDriver对象
    :param input_element: 输入元素
    :param value: 要填写的值
    :return: 是否成功填写
    """
    try:
        print(f"处理refer-input类型输入框，值: {value}")
        
        # 检查是否为报销人字段
        field_name = ""
        try:
            field_name = driver.execute_script("""
                var element = arguments[0];
                var formItem = element.closest('.card-table-modal-form-item');
                if (!formItem) {
                    formItem = element.closest('.form-item');
                }
                if (!formItem) {
                    return "";
                }
                
                var label = formItem.querySelector('label, .u-label');
                if (!label) {
                    return "";
                }
                
                return label.textContent.trim();
            """, input_element) or ""
        except:
            pass

        is_reimbursement_person = "报销人" in field_name
        if is_reimbursement_person:
            print(f"检测到报销人字段，使用增强清除方法")
        
        # 找到真正的输入框
        real_input = driver.execute_script("""
            var container = arguments[0];
            
            // 如果是输入框，直接返回
            if (container.tagName === 'INPUT') {
                return container;
            }
            
            // 查找嵌套的输入框
            var input = container.querySelector('input:not([type="hidden"])');
            if (input) {
                return input;
            }
            
            return container;
        """, input_element)
        
        if not real_input:
            real_input = input_element
        
        # 点击获取焦点
        real_input.click()
        time.sleep(0.5)
        
        # 获取当前值
        current_value = driver.execute_script("return arguments[0].value;", real_input) or ""
        print(f"当前输入框值: '{current_value}'")
        
        # 增强清除功能，特别是对报销人字段
        clearing_methods = [
            # 方法1: 使用clear()方法
            lambda: real_input.clear(),
            
            # 方法2: 使用Ctrl+A和Delete
            lambda: (real_input.send_keys(Keys.CONTROL + "a"), 
                     time.sleep(0.1), 
                     real_input.send_keys(Keys.DELETE)),
                     
            # 方法3: 使用JavaScript清空
            lambda: driver.execute_script("arguments[0].value = '';", real_input),
            
            # 方法4: 逐字符删除
            lambda: (real_input.send_keys(Keys.CONTROL + "a"), 
                     time.sleep(0.1),
                     real_input.send_keys(Keys.HOME),
                     time.sleep(0.1),
                     [real_input.send_keys(Keys.DELETE) for _ in range(len(current_value))])
        ]
        
        # 对报销人字段尝试所有清除方法，对其他字段仅尝试前三种方法
        methods_to_try = clearing_methods if is_reimbursement_person else clearing_methods[:3]
        
        for i, clear_method in enumerate(methods_to_try):
            try:
                print(f"尝试清除方法 {i+1}")
                clear_method()
                time.sleep(0.2)
                
                # 验证清空是否成功
                after_clear = driver.execute_script("return arguments[0].value;", real_input) or ""
                print(f"清除后的值: '{after_clear}'")
                
                if not after_clear:
                    print(f"清除成功，方法 {i+1} 有效")
                    break
            except Exception as e:
                print(f"清除方法 {i+1} 失败: {e}")
        
        # 最终确认输入框是否为空
        current_value = driver.execute_script("return arguments[0].value;", real_input) or ""
        if current_value:
            print(f"警告: 多次尝试后输入框仍未清空，当前值: '{current_value}'")
            # 最后一次尝试，使用JavaScript强制清空
            try:
                driver.execute_script("""
                    arguments[0].value = '';
                    // 触发change事件
                    var event = new Event('change', { bubbles: true });
                    arguments[0].dispatchEvent(event);
                    // 触发input事件
                    var inputEvent = new Event('input', { bubbles: true });
                    arguments[0].dispatchEvent(inputEvent);
                """, real_input)
                time.sleep(0.2)
            except Exception as e:
                print(f"最终JavaScript清空失败: {e}")
        
        # 输入新值
        real_input.send_keys(str(value))
        time.sleep(1)
        
        # 验证输入后的值
        final_value = driver.execute_script("return arguments[0].value;", real_input) or ""
        print(f"输入后的值: '{final_value}'")
        
        # 如果输入后的值不正确，尝试使用JavaScript设置
        if final_value != str(value):
            print(f"输入后的值不正确，尝试使用JavaScript设置")
            driver.execute_script("arguments[0].value = arguments[1];", real_input, str(value))
            
            # 触发变更事件
            driver.execute_script("""
                var event = new Event('change', { bubbles: true });
                arguments[0].dispatchEvent(event);
                var inputEvent = new Event('input', { bubbles: true });
                arguments[0].dispatchEvent(inputEvent);
            """, real_input)
            time.sleep(0.2)
        
        # 按Enter键确认
        real_input.send_keys(Keys.ENTER)
        time.sleep(0.5)
        
        # 处理可能的下拉选项
        try:
            dropdown_items = WebDriverWait(driver, 2).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item"))
            )
            
            if dropdown_items:
                for item in dropdown_items:
                    if str(value).lower() in item.text.lower():
                        item.click()
                        time.sleep(0.5)
                        break
                else:
                    # 如果没有找到匹配的选项，选择第一个
                    dropdown_items[0].click()
                    time.sleep(0.5)
        except:
            # 如果没有下拉选项，按Tab键确认
            real_input.send_keys(Keys.TAB)
        
        return True
    
    except Exception as e:
        print(f"处理refer-input类型输入框出错: {e}")
        return False

def handle_date_input(driver, input_element, value):
    """
    处理日期输入框
    
    :param driver: WebDriver对象
    :param input_element: 输入元素
    :param value: 要填写的值
    :return: 是否成功填写
    """
    try:
        print(f"处理日期类型输入框，值: {value}")
        
        # 获取日期控件的HTML结构以便调试
        html_structure = driver.execute_script("return arguments[0].outerHTML;", input_element)
        print(f"日期控件HTML结构: {html_structure[:200]}...")  # 只打印前200个字符
        
        # 直接根据图示定位日期输入框图标
        calendar_icon = None
        try:
            # 查找日期控件的图标按钮 - 查找同一行的日历图标
            calendar_icon = driver.execute_script("""
                var element = arguments[0];
                var formItem = element.closest('.card-table-modal-form-item') || element.closest('.form-item');
                if (!formItem) return null;
                
                // 查找日历图标
                return formItem.querySelector('.u-form-control-icon, .calendar-icon, .uf-calendar, .u-date-cell-outer, [class*="calendar"], [class*="date"]');
            """, input_element)
            
            if calendar_icon:
                print("找到日历图标，点击打开日期选择器")
                calendar_icon.click()
                time.sleep(1)
        except Exception as e:
            print(f"查找日历图标失败: {e}")
        
        # 如果没有找到日历图标，尝试点击输入框本身
        if not calendar_icon:
            try:
                # 尝试点击日期输入框
                input_element.click()
                time.sleep(1)
                print("已点击日期输入框")
            except Exception as e:
                print(f"点击日期输入框失败: {e}")
        
        # 查找弹出的日期选择器面板
        date_picker_panel = None
        try:
            # 查找各种可能的日期选择器面板
            date_picker_panel = driver.find_element(By.CSS_SELECTOR, 
                ".u-date-panel, .rc-calendar, .date-picker-container, .datepicker, .u-date-panel-visible")
            print("找到日期选择器面板")
        except Exception as e:
            print(f"未找到日期选择器面板: {e}")
        
        # 处理日期值
        date_value = str(value)
        # 确保日期格式正确（YYYY-MM-DD）
        if not (re.match(r'^\d{4}-\d{2}-\d{2}$', date_value) or 
                re.match(r'^\d{4}/\d{2}/\d{2}$', date_value)):
            # 如果格式不正确，尝试转换
            try:
                if re.match(r'^\d{8}$', date_value):  # 如果是YYYYMMDD格式
                    date_value = f"{date_value[:4]}-{date_value[4:6]}-{date_value[6:8]}"
                elif re.match(r'^\d{2}/\d{2}/\d{4}$', date_value):  # 如果是MM/DD/YYYY格式
                    parts = date_value.split('/')
                    date_value = f"{parts[2]}-{parts[0]}-{parts[1]}"
            except:
                pass  # 如果转换失败，保持原样
        
        # 分解日期
        try:
            year, month, day = date_value.replace('/', '-').split('-')
            # 去除前导零
            month = str(int(month))  # 例如 "08" -> "8"
            day = str(int(day))      # 例如 "09" -> "9"
            print(f"分解日期: 年={year}, 月={month}, 日={day}")
        except Exception as e:
            print(f"分解日期失败: {e}")
            year, month, day = "", "", ""
        
        # 方法1: 使用日期选择器面板
        # if date_picker_panel:
        #     try:
        #         # 尝试在日期选择器面板中填写日期
                
        #         # 先选择年份
        #         year_dropdown = driver.find_element(By.CSS_SELECTOR, 
        #             ".rc-calendar-year-select, .u-year-select, .year-select")
        #         year_dropdown.click()
        #         time.sleep(0.5)
                
        #         # 选择具体年份
        #         year_option = driver.find_element(By.XPATH, 
        #             f"//div[contains(@class, 'rc-calendar-year-panel-cell') and contains(text(), '{year}')]")
        #         year_option.click()
        #         time.sleep(0.5)
                
        #         # 选择月份
        #         month_dropdown = driver.find_element(By.CSS_SELECTOR, 
        #             ".rc-calendar-month-select, .u-month-select, .month-select")
        #         month_dropdown.click()
        #         time.sleep(0.5)
                
        #         # 选择具体月份
        #         month_option = driver.find_element(By.XPATH, 
        #             f"//div[contains(@class, 'rc-calendar-month-panel-cell') and contains(text(), '{month}月')]")
        #         month_option.click()
        #         time.sleep(0.5)
                
        #         # 选择日期
        #         day_option = driver.find_element(By.XPATH, 
        #             f"//div[contains(@class, 'rc-calendar-date') and contains(text(), '{day}')]")
        #         day_option.click()
        #         time.sleep(0.5)
                
        #         print("通过日期选择器面板成功选择日期")
        #         return True
        #     except Exception as e:
        #         print(f"使用日期选择器面板选择日期失败: {e}")
        
        # 方法2: 尝试查找日期输入框直接输入
        date_input = None
        try:
            # 查找可能的日期输入框
            date_inputs = driver.find_elements(By.CSS_SELECTOR, 
                "input.rc-calendar-input, .u-form-control[placeholder*='YYYY'], .datepicker-input, input[placeholder*='日期']")
            
            if date_inputs:
                date_input = date_inputs[0]
                print("找到日期输入框")
                
                # 清除现有内容 - 使用全选后清除
                try:
                    # 先点击获取焦点
                    date_input.click()
                    time.sleep(0.2)
                    
                    # 全选现有内容
                    date_input.send_keys(Keys.CONTROL + "a")
                    time.sleep(0.1)
                    
                    # 删除所选内容
                    date_input.send_keys(Keys.DELETE)
                    time.sleep(0.1)
                    
                    # 检查是否清空
                    if driver.execute_script("return arguments[0].value;", date_input):
                        # 如果未清空，尝试JavaScript清空
                        driver.execute_script("arguments[0].value = '';", date_input)
                        time.sleep(0.1)
                except Exception as e:
                    print(f"清空日期输入框失败: {e}")
                    # 尝试使用JavaScript清空
                    driver.execute_script("arguments[0].value = '';", date_input)
                    time.sleep(0.1)
                
                # 输入新日期
                date_input.send_keys(date_value)
                time.sleep(1)
                
                # 按Enter确认
                date_input.send_keys(Keys.ENTER)
                time.sleep(0.5)
                
                print("通过直接输入成功填写日期")
                return True
            else:
                print("未找到日期输入框")
        except Exception as e:
            print(f"直接输入日期失败: {e}")
        
        # 方法3: 使用JavaScript直接设置值
        try:
            result = driver.execute_script("""
                var element = arguments[0];
                var dateValue = arguments[1];
                
                // 查找表单项
                var formItem = element.closest('.card-table-modal-form-item') || element.closest('.form-item');
                if (!formItem) return 'Cannot find form item';
                
                // 查找所有可能的输入元素
                var inputs = formItem.querySelectorAll('input');
                if (inputs.length === 0) return 'No input found';
                
                // 尝试为每个输入框设置值
                var success = false;
                for (var i = 0; i < inputs.length; i++) {
                    try {
                        var input = inputs[i];
                        // 设置值
                        input.value = dateValue;
                        
                        // 触发change事件
                        var event = new Event('change', { bubbles: true });
                        input.dispatchEvent(event);
                        
                        // 触发input事件
                        var inputEvent = new Event('input', { bubbles: true });
                        input.dispatchEvent(inputEvent);
                        
                        success = true;
                    } catch (err) {
                        console.error('Error setting input ' + i + ': ' + err);
                    }
                }
                
                // 尝试设置显示元素的文本
                try {
                    var displayEl = formItem.querySelector('.u-form-control, .rc-calendar-input');
                    if (displayEl) {
                        displayEl.textContent = dateValue;
                    }
                } catch (err) {
                    console.error('Error setting display text: ' + err);
                }
                
                return success ? 'Successfully set date value' : 'Failed to set date value';
            """, input_element, date_value)
            
            print(f"JavaScript设置日期结果: {result}")
            
            # 点击页面其他位置关闭可能的日期选择器
            actions = ActionChains(driver)
            actions.move_by_offset(10, 10).click().perform()
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            print(f"JavaScript设置日期失败: {e}")
        
        # 方法4: 尝试使用键盘事件填写日期
        try:
            # 再次点击输入框
            input_element.click()
            time.sleep(0.5)
            
            # 使用ActionChains模拟键盘输入
            actions = ActionChains(driver)
            
            # 输入日期值
            actions.send_keys(date_value)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(0.5)
            
            print("通过键盘事件填写日期")
            return True
            
        except Exception as e:
            print(f"使用键盘事件填写日期失败: {e}")
            
        # 如果所有方法都失败，返回失败
        return False
    
    except Exception as e:
        print(f"处理日期类型输入框出错: {e}")
        return False

def handle_dropdown_input(driver, input_element, value):
    """
    处理第三种类型：下拉选择输入框（图三所示）
    
    :param driver: WebDriver对象
    :param input_element: 输入元素
    :param value: 要填写的值
    :return: 是否成功填写
    """
    try:
        print(f"处理下拉选择类型输入框，值: {value}")
        
        # 获取字段名，检查是否为交通工具
        field_name = ""
        try:
            field_name = driver.execute_script("""
                var element = arguments[0];
                var formItem = element.closest('.card-table-modal-form-item');
                if (!formItem) {
                    formItem = element.closest('.form-item');
                }
                if (!formItem) {
                    return "";
                }
                
                var label = formItem.querySelector('label, .u-label');
                if (!label) {
                    return "";
                }
                
                return label.textContent.trim();
            """, input_element) or ""
        except:
            pass
        
        # 增强对交通工具字段的识别 - 使用更宽松的条件
        is_transport_field = "交通工具" in field_name or "工具" in field_name
        print(f"字段名: '{field_name}', 是否为交通工具: {is_transport_field}")
        
        # 对于交通工具字段，使用特殊的强化处理
        if is_transport_field:
            return handle_transport_field(driver, input_element, value)
        
        # 检查当前是否已有下拉菜单显示
        dropdown_visible = False
        try:
            dropdown = driver.find_element(By.CSS_SELECTOR, ".u-select-dropdown:not([style*='display: none'])")
            if dropdown.is_displayed():
                dropdown_visible = True
                print("检测到下拉菜单已经显示")
        except:
            dropdown_visible = False
        
        # 如果下拉菜单未显示，点击打开
        if not dropdown_visible:
            print("下拉菜单未显示，点击打开")
            input_element.click()
            time.sleep(0.8)
        
        # 查找下拉选项
        options = WebDriverWait(driver, 3).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
            "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item, .u-select-selection-rendered"))
        )
        
        # 无选项时，重试点击
        if not options:
            print("未找到下拉选项，重试点击")
            input_element.click()
            time.sleep(1)
            
            # 再次查找下拉选项
            options = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item, .u-select-selection-rendered"))
            )
        
        print(f"找到 {len(options)} 个下拉选项")
        
        # 打印所有选项的文本，便于调试
        for i, option in enumerate(options):
            option_text = option.text.strip()
            print(f"选项 {i+1}: '{option_text}'")
        
        # 选择匹配的选项
        found_match = False
        exact_match = None
        partial_match = None
        str_value = str(value).lower()
        
        # 先搜索完全匹配，然后是包含匹配
        for option in options:
            option_text = option.text.strip().lower()
            
            # 检查完全匹配
            if option_text == str_value:
                exact_match = option
                print(f"找到完全匹配选项: '{option_text}'")
                break
            
            # 检查包含匹配 (仅在没有完全匹配时使用)
            if str_value in option_text or option_text in str_value:
                partial_match = option
                print(f"找到部分匹配选项: '{option_text}'")
        
        # 优先使用完全匹配的选项
        if exact_match:
            print(f"点击完全匹配选项: '{exact_match.text}'")
            # 使用JavaScript点击以避免可能的元素不可点击问题
            driver.execute_script("arguments[0].click();", exact_match)
            found_match = True
            time.sleep(0.5)
        # 其次使用部分匹配的选项
        elif partial_match:
            print(f"点击部分匹配选项: '{partial_match.text}'")
            # 使用JavaScript点击
            driver.execute_script("arguments[0].click();", partial_match)
            found_match = True
            time.sleep(0.5)
        # 如果没有找到匹配的选项，选择第一个
        elif options:
            print(f"未找到匹配项，选择第一个选项: '{options[0].text}'")
            # 使用JavaScript点击
            driver.execute_script("arguments[0].click();", options[0])
            found_match = True
            time.sleep(0.5)
        else:
            print("未找到任何选项")
        
        # 如果未找到或点击选项，尝试输入值并按Enter
        if not found_match:
            print(f"尝试直接输入值: {value}")
            # 尝试查找输入框
            try:
                input_field = driver.execute_script("""
                    var element = arguments[0];
                    // 查找嵌套的输入框
                    var input = element.querySelector('input');
                    if (!input) {
                        // 如果本身就是输入框
                        if (element.tagName === 'INPUT') {
                            return element;
                        }
                        // 查找相邻的输入框
                        var parent = element.parentElement;
                        if (parent) {
                            return parent.querySelector('input');
                        }
                    }
                    return input;
                """, input_element)
                
                if input_field:
                    # 清空输入框
                    input_field.clear()
                    # 输入值
                    input_field.send_keys(str(value))
                    # 按Enter确认
                    input_field.send_keys(Keys.ENTER)
                    time.sleep(0.5)
                    print(f"已输入值并按Enter")
            except Exception as e:
                print(f"直接输入值失败: {e}")
        
        # 确保下拉框已关闭
        try:
            dropdown_container = driver.find_element(By.CSS_SELECTOR, ".u-select-dropdown:not([style*='display: none'])")
            if dropdown_container.is_displayed():
                # 点击外部区域来关闭下拉框
                actions = ActionChains(driver)
                actions.move_by_offset(0, 0).click().perform()
                time.sleep(0.5)
        except:
            pass
        
        return True
    
    except Exception as e:
        print(f"处理下拉选择类型输入框出错: {e}")
        return False

def handle_transport_field(driver, input_element, value):
    """
    专门处理交通工具字段的函数
    
    :param driver: WebDriver对象
    :param input_element: 输入元素
    :param value: 要填写的值
    :return: 是否成功填写
    """
    try:
        print(f"使用专门的交通工具处理函数，值: {value}")
        
        # 常见交通工具列表
        transport_types = ["高速公路", "飞机", "火车", "出租车", "公交车", "城铁", "长途汽车", "商务车", "其他"]
        
        # 第一步：根据HTML结构找到下拉框控制元素
        dropdown_control = driver.execute_script("""
            var element = arguments[0];
            // 找到u-select-selection-rendered元素
            var formItem = element.closest('.card-table-modal-form-item') || element.closest('.form-item');
            if (!formItem) return null;
            
            // 查找下拉控件
            var ncSelect = formItem.querySelector('.nc-select, .u-select');
            if (ncSelect) return ncSelect;
            
            // 查找下拉框选择元素
            var selectRendered = formItem.querySelector('.u-select-selection-rendered');
            if (selectRendered) return selectRendered.parentElement;
            
            return element;
        """, input_element)
        
        if not dropdown_control:
            print("未找到下拉控件，使用原始元素")
            dropdown_control = input_element
        
        # 第二步：检查下拉框的状态
        is_expanded = driver.execute_script("""
            var element = arguments[0];
            var selection = element.querySelector('.u-select-selection') || element;
            return selection.getAttribute('aria-expanded') === 'true';
        """, dropdown_control)
        
        print(f"下拉框当前状态: {'已展开' if is_expanded else '未展开'}")
        
        # 如果下拉框未展开，点击展开它
        if not is_expanded:
            print("点击展开下拉框")
            driver.execute_script("""
                var element = arguments[0];
                // 尝试点击箭头
                var arrow = element.querySelector('.u-select-arrow');
                if (arrow) {
                    arrow.click();
                } else {
                    // 点击整个选择框
                    element.click();
                }
            """, dropdown_control)
            time.sleep(1)
            
            # 再次检查是否展开
            is_expanded = driver.execute_script("""
                var element = arguments[0];
                var selection = element.querySelector('.u-select-selection') || element;
                return selection.getAttribute('aria-expanded') === 'true';
            """, dropdown_control)
            
            if not is_expanded:
                print("尝试直接点击元素")
                try:
                    driver.execute_script("arguments[0].click();", dropdown_control)
                    time.sleep(1)
                except Exception as e:
                    print(f"点击下拉控件失败: {e}")
        
        # 第三步：查找下拉选项
        dropdown_items = []
        try:
            # 查找展开的下拉菜单中的选项
            dropdown_items = driver.execute_script("""
                // 查找所有可见的下拉选项
                var items = document.querySelectorAll('.u-select-dropdown-menu-item:not([style*="display: none"])');
                return Array.from(items);
            """)
            
            if not dropdown_items:
                # 尝试通过WebDriverWait查找
                dropdown_items = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                    ".u-select-dropdown-menu-item:not(.u-select-dropdown-menu-item-disabled)"))
                )
            
            print(f"找到 {len(dropdown_items)} 个交通工具选项")
            
            # 打印所有选项文本
            for i, item in enumerate(dropdown_items):
                item_text = item.text.strip()
                print(f"选项 {i+1}: '{item_text}'")
            
            # 第四步：匹配并选择选项
            matched_item = None
            
            # 优先精确匹配
            for item in dropdown_items:
                if item.text.strip() == str(value):
                    matched_item = item
                    print(f"找到精确匹配的交通工具: '{item.text}'")
                    break
            
            # 如果没有精确匹配，尝试部分匹配
            if not matched_item:
                for item in dropdown_items:
                    item_text = item.text.strip().lower()
                    value_lower = str(value).lower()
                    if value_lower in item_text or item_text in value_lower:
                        matched_item = item
                        print(f"找到部分匹配的交通工具: '{item.text}'")
                        break
            
            # 如果找到匹配项，点击它
            if matched_item:
                print(f"点击匹配的选项: '{matched_item.text}'")
                # 确保元素可见
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", matched_item)
                time.sleep(0.5)
                # 使用JavaScript点击
                driver.execute_script("arguments[0].click();", matched_item)
                time.sleep(0.5)
                print("成功选择交通工具")
                return True
            elif dropdown_items:
                # 如果没有匹配项，选择第一个选项
                print(f"未找到匹配项，选择第一个选项: '{dropdown_items[0].text}'")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_items[0])
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", dropdown_items[0])
                time.sleep(0.5)
                print("已选择第一个交通工具选项")
                return True
            
        except Exception as e:
            print(f"处理下拉选项时出错: {e}")
        
        # 第五步：备用方法 - 通过直接设置值
        try:
            print("尝试通过直接设置值的方式处理")
            # 查找选择框中的显示值元素
            result = driver.execute_script("""
                var element = arguments[0];
                var value = arguments[1];
                
                // 找到表单项
                var formItem = element.closest('.card-table-modal-form-item') || element.closest('.form-item');
                if (!formItem) return "未找到表单项";
                
                // 找到显示值的元素
                var valueElement = formItem.querySelector('.u-select-selection-selected-value');
                if (valueElement) {
                    valueElement.textContent = value;
                    valueElement.title = value;
                    
                    // 触发change事件
                    var event = new Event('change', { bubbles: true });
                    valueElement.dispatchEvent(event);
                    return "已设置显示值";
                }
                
                // 查找所有输入元素并设置值
                var inputs = formItem.querySelectorAll('input:not([type="hidden"])');
                if (inputs.length > 0) {
                    for (var i = 0; i < inputs.length; i++) {
                        inputs[i].value = value;
                        
                        // 触发change事件
                        var event = new Event('change', { bubbles: true });
                        inputs[i].dispatchEvent(event);
                    }
                    return "已设置输入框值";
                }
                
                return "未找到可设置的元素";
            """, dropdown_control, str(value))
            
            print(f"直接设置值结果: {result}")
            
            # 关闭可能打开的下拉框
            actions = ActionChains(driver)
            actions.move_by_offset(10, 10).click().perform()
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            print(f"直接设置值失败: {e}")
        
        # 最后尝试：使用键盘事件
        try:
            print("尝试使用键盘事件处理")
            # 点击下拉控件
            dropdown_control.click()
            time.sleep(0.5)
            
            # 清除现有文本
            actions = ActionChains(driver)
            actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL)
            actions.send_keys(Keys.DELETE)
            actions.send_keys(str(value))
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(0.5)
            
            print("已通过键盘事件处理")
            return True
            
        except Exception as e:
            print(f"键盘事件处理失败: {e}")
        
        print("所有方法都失败，交通工具设置失败")
        return False
        
    except Exception as e:
        print(f"处理交通工具字段出错: {e}")
        return False

def fill_input_field(driver, input_element, value):
    """
    填写输入字段
    
    :param driver: WebDriver对象
    :param input_element: 输入元素
    :param value: 要填写的值
    :return: 是否成功填写
    """
    try:
        # 获取元素类型
        tag_name = input_element.tag_name.lower()
        element_class = input_element.get_attribute("class") or ""
        element_type = input_element.get_attribute("type") or ""
        placeholder = input_element.get_attribute("placeholder") or ""
        
        # 改进类型识别逻辑，根据实际字段名和属性进行更精确的判断
        field_name = ""
        try:
            # 尝试获取关联的字段名
            field_name = driver.execute_script("""
                var element = arguments[0];
                var formItem = element.closest('.card-table-modal-form-item');
                if (!formItem) {
                    formItem = element.closest('.form-item');
                }
                if (!formItem) {
                    return "";
                }
                
                var label = formItem.querySelector('label, .u-label');
                if (!label) {
                    return "";
                }
                
                return label.textContent.trim();
            """, input_element) or ""
        except:
            pass
        
        print(f"字段名: '{field_name}', 元素类: '{element_class}', 类型: '{element_type}', 标签: '{tag_name}'")
        
        # 处理hidden-input类型的元素
        if "hidden-input" in element_class:
            print(f"检测到hidden-input类型的元素，使用特殊处理")
            return handle_hidden_input(driver, input_element, value, field_name)
            
        # 特定字段名强制类型判断
        if "交通工具" in field_name:
            print(f"特殊处理交通工具字段")
            return handle_dropdown_input(driver, input_element, value)
            
        # 日期字段判断: 包含日期关键词或匹配日期格式
        is_date_field = (
            "日期" in field_name or
            "时间" in field_name or
            "date" in element_class.lower() or
            "calendar" in element_class.lower() or
            "datepicker" in element_class.lower()
        )
        
        # 引用型字段判断: 包含特定类名
        is_refer_field = (
            "refer-input" in element_class or
            "nc-input" in element_class or
            "itemtype" in input_element.get_attribute("outerHTML") and "refer" in input_element.get_attribute("outerHTML")
        )
        
        # 下拉选择框判断 - 增强判断条件
        is_dropdown_field = (
            tag_name == "div" and "u-select-selection-rendered" in element_class or
            tag_name == "select" or
            "u-select" in element_class or
            "工具" in field_name or  # 针对"交通工具"等
            "类型" in field_name or  # 针对各种"类型"下拉框
            "项目" in field_name     # 针对"收支项目"等下拉框
        )
        
        # 根据判断结果调用对应的处理函数
        if is_date_field:
            print(f"处理日期输入字段: {field_name}")
            return handle_date_input(driver, input_element, value)
        elif is_dropdown_field:
            print(f"处理下拉选择字段: {field_name}")
            return handle_dropdown_input(driver, input_element, value)
        elif is_refer_field:
            print(f"处理引用字段: {field_name}")
            return handle_refer_input(driver, input_element, value)
        else:
            # 处理普通输入框
            print(f"处理普通输入字段: {field_name}")
            
            # 获取当前值
            current_value = driver.execute_script("return arguments[0].value;", input_element) or ""
            print(f"当前输入框值: '{current_value}'")
            
            # 点击获取焦点
            input_element.click()
            time.sleep(0.2)
            
            # 增强清除功能，特别是对报销人字段
            is_reimbursement_person = "报销人" in field_name
            if is_reimbursement_person:
                print(f"检测到报销人字段，使用增强清除方法")
            
            # 清除现有内容 - 使用多种方法确保内容被清除
            clearing_methods = [
                # 方法1: 使用clear()方法
                lambda: input_element.clear(),
                
                # 方法2: 使用Ctrl+A和Delete
                lambda: (input_element.send_keys(Keys.CONTROL + "a"), 
                         time.sleep(0.1), 
                         input_element.send_keys(Keys.DELETE)),
                         
                # 方法3: 使用JavaScript清空
                lambda: driver.execute_script("arguments[0].value = '';", input_element),
                
                # 方法4: 逐字符删除
                lambda: (input_element.send_keys(Keys.CONTROL + "a"), 
                         time.sleep(0.1),
                         input_element.send_keys(Keys.HOME),
                         time.sleep(0.1),
                         [input_element.send_keys(Keys.DELETE) for _ in range(len(current_value))])
            ]
            
            # 对报销人字段尝试所有清除方法，对其他字段仅尝试前三种方法
            methods_to_try = clearing_methods if is_reimbursement_person else clearing_methods[:3]
            
            for i, clear_method in enumerate(methods_to_try):
                try:
                    print(f"尝试清除方法 {i+1}")
                    clear_method()
                    time.sleep(0.2)
                    
                    # 验证清空是否成功
                    after_clear = driver.execute_script("return arguments[0].value;", input_element) or ""
                    print(f"清除后的值: '{after_clear}'")
                    
                    if not after_clear:
                        print(f"清除成功，方法 {i+1} 有效")
                        break
                except Exception as e:
                    print(f"清除方法 {i+1} 失败: {e}")
            
            # 最终确认输入框是否为空
            current_value = driver.execute_script("return arguments[0].value;", input_element) or ""
            if current_value:
                print(f"警告: 多次尝试后输入框仍未清空，当前值: '{current_value}'")
                # 最后一次尝试，使用JavaScript强制清空
                try:
                    driver.execute_script("""
                        arguments[0].value = '';
                        // 触发change事件
                        var event = new Event('change', { bubbles: true });
                        arguments[0].dispatchEvent(event);
                        // 触发input事件
                        var inputEvent = new Event('input', { bubbles: true });
                        arguments[0].dispatchEvent(inputEvent);
                    """, input_element)
                    time.sleep(0.2)
                except Exception as e:
                    print(f"最终JavaScript清空失败: {e}")
            
            # 输入新值
            input_element.send_keys(str(value))
            time.sleep(0.5)
            
            # 验证输入后的值
            final_value = driver.execute_script("return arguments[0].value;", input_element) or ""
            print(f"输入后的值: '{final_value}'")
            
            # 如果输入后的值不正确（如可能是值被附加而不是替换），尝试重新设置
            if final_value != str(value):
                print(f"输入后的值不正确，尝试使用JavaScript设置")
                driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                
                # 触发变更事件
                driver.execute_script("""
                    var event = new Event('change', { bubbles: true });
                    arguments[0].dispatchEvent(event);
                    var inputEvent = new Event('input', { bubbles: true });
                    arguments[0].dispatchEvent(inputEvent);
                """, input_element)
                
                # 再次验证
                final_value = driver.execute_script("return arguments[0].value;", input_element) or ""
                print(f"JavaScript设置后的值: '{final_value}'")
            
            # 按Tab键移动到下一个字段
            input_element.send_keys(Keys.TAB)
            time.sleep(0.2)
            
            # 点击页面空白处确保焦点移除
            actions = ActionChains(driver)
            actions.move_by_offset(10, 10).click().perform()
            time.sleep(0.2)
        
        return True
    
    except Exception as e:
        print(f"填写字段时出错: {e}")
        
        # 尝试使用JavaScript设置值
        try:
            driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
            print(f"通过JavaScript设置值成功")
            return True
        except Exception as js_error:
            print(f"通过JavaScript设置值失败: {js_error}")
            return False

def handle_hidden_input(driver, input_element, value, field_name=""):
    """
    处理hidden-input类型的元素，这类元素通常是被其他元素遮挡的只读输入框
    
    :param driver: WebDriver对象
    :param input_element: 输入元素
    :param value: 要填写的值
    :param field_name: 字段名称
    :return: 是否成功填写
    """
    try:
        print(f"处理hidden-input类型的元素，字段: {field_name}, 值: {value}")
        
        # 检查是否为报销人字段
        is_reimbursement_person = "报销人" in field_name
        if is_reimbursement_person:
            print(f"检测到报销人字段，使用增强清除方法")
        
        # 1. 首先尝试寻找同一表单项中的真实输入框
        real_input = driver.execute_script("""
            var hiddenInput = arguments[0];
            var formItem = hiddenInput.closest('.form-item') || hiddenInput.closest('.card-table-modal-form-item');
            if (!formItem) return null;
            
            // 查找可能的真实输入框
            var realInputs = formItem.querySelectorAll('input:not([type="hidden"]):not(.hidden-input), .nc-input, .refer-input');
            if (realInputs.length > 0) return realInputs[0];
            
            // 查找可能的下拉框
            var selects = formItem.querySelectorAll('select, .u-select, .u-select-selection-rendered');
            if (selects.length > 0) return selects[0];
            
            return null;
        """, input_element)
        
        if real_input:
            print(f"找到hidden-input关联的真实输入元素")
            
            # 查看真实输入框的类型和类
            real_class = real_input.get_attribute("class") or ""
            print(f"真实输入框类: {real_class}")
            
            # 处理报销类型和其他需要输入后选择下拉框第一项的字段
            if "报销类型" in field_name or "收支项目" in field_name or "refer-input" in real_class or "nc-input" in real_class or is_reimbursement_person:
                print(f"检测到需要输入后选择下拉框第一项的字段")
                
                # 点击获取焦点
                driver.execute_script("arguments[0].click();", real_input)
                time.sleep(0.5)
                
                # 获取当前值
                current_value = driver.execute_script("return arguments[0].value;", real_input) or ""
                print(f"当前输入框值: '{current_value}'")
                
                # 增强清除功能，特别是对报销人字段
                clearing_methods = [
                    # 方法1: 使用clear()方法
                    lambda: real_input.clear(),
                    
                    # 方法2: 使用Ctrl+A和Delete
                    lambda: (real_input.send_keys(Keys.CONTROL + "a"), 
                             time.sleep(0.1), 
                             real_input.send_keys(Keys.DELETE)),
                             
                    # 方法3: 使用JavaScript清空
                    lambda: driver.execute_script("arguments[0].value = '';", real_input),
                    
                    # 方法4: 逐字符删除
                    lambda: (real_input.send_keys(Keys.CONTROL + "a"), 
                             time.sleep(0.1),
                             real_input.send_keys(Keys.HOME),
                             time.sleep(0.1),
                             [real_input.send_keys(Keys.DELETE) for _ in range(len(current_value))])
                ]
                
                # 对报销人字段尝试所有清除方法，对其他字段仅尝试前三种方法
                methods_to_try = clearing_methods if is_reimbursement_person else clearing_methods[:3]
                
                for i, clear_method in enumerate(methods_to_try):
                    try:
                        print(f"尝试清除方法 {i+1}")
                        clear_method()
                        time.sleep(0.2)
                        
                        # 验证清空是否成功
                        after_clear = driver.execute_script("return arguments[0].value;", real_input) or ""
                        print(f"清除后的值: '{after_clear}'")
                        
                        if not after_clear:
                            print(f"清除成功，方法 {i+1} 有效")
                            break
                    except Exception as e:
                        print(f"清除方法 {i+1} 失败: {e}")
                
                # 最终确认输入框是否为空
                current_value = driver.execute_script("return arguments[0].value;", real_input) or ""
                if current_value:
                    print(f"警告: 多次尝试后输入框仍未清空，当前值: '{current_value}'")
                    # 最后一次尝试，使用JavaScript强制清空
                    try:
                        driver.execute_script("""
                            arguments[0].value = '';
                            // 触发change事件
                            var event = new Event('change', { bubbles: true });
                            arguments[0].dispatchEvent(event);
                            // 触发input事件
                            var inputEvent = new Event('input', { bubbles: true });
                            arguments[0].dispatchEvent(inputEvent);
                        """, real_input)
                        time.sleep(0.2)
                    except Exception as e:
                        print(f"最终JavaScript清空失败: {e}")
                
                # 输入新值
                real_input.send_keys(str(value))
                time.sleep(1)
                
                # 验证输入后的值
                final_value = driver.execute_script("return arguments[0].value;", real_input) or ""
                print(f"输入后的值: '{final_value}'")
                
                # 如果输入后的值不正确，尝试使用JavaScript设置
                if final_value != str(value):
                    print(f"输入后的值不正确，尝试使用JavaScript设置")
                    driver.execute_script("arguments[0].value = arguments[1];", real_input, str(value))
                    
                    # 触发变更事件
                    driver.execute_script("""
                        var event = new Event('change', { bubbles: true });
                        arguments[0].dispatchEvent(event);
                        var inputEvent = new Event('input', { bubbles: true });
                        arguments[0].dispatchEvent(inputEvent);
                    """, real_input)
                    time.sleep(0.2)
                
                # 检查是否有下拉框显示
                try:
                    # 查找下拉列表项
                    dropdown_items = WebDriverWait(driver, 3).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                        "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item, .refer-item-result"))
                    )
                    
                    if dropdown_items:
                        print(f"找到 {len(dropdown_items)} 个下拉选项")
                        for i, item in enumerate(dropdown_items):
                            print(f"选项 {i+1}: {item.text}")
                        
                        # 查找匹配的选项
                        matched_item = None
                        for item in dropdown_items:
                            if str(value).lower() in item.text.lower():
                                matched_item = item
                                break
                        
                        # 点击匹配的选项或第一个选项
                        if matched_item:
                            print(f"点击匹配的选项: {matched_item.text}")
                            driver.execute_script("arguments[0].click();", matched_item)
                        else:
                            print(f"点击第一个选项: {dropdown_items[0].text}")
                            driver.execute_script("arguments[0].click();", dropdown_items[0])
                        time.sleep(0.5)
                        return True
                    else:
                        print("未找到下拉选项")
                        
                        # 如果没有找到下拉选项，尝试按Enter键
                        real_input.send_keys(Keys.ENTER)
                        time.sleep(0.5)
                except Exception as e:
                    print(f"查找或点击下拉选项失败: {e}")
                    
                    # 尝试按Enter键确认
                    real_input.send_keys(Keys.ENTER)
                    time.sleep(0.5)
                
                return True
            
            # 根据真实输入框的类型决定处理方式
            elif "u-select" in real_class or "select" in real_class.lower():
                print(f"检测到下拉选择框")
                return handle_dropdown_input(driver, real_input, value)
            else:
                # 普通输入框
                print(f"检测到普通输入框")
                # 点击获取焦点
                driver.execute_script("arguments[0].click();", real_input)
                time.sleep(0.2)
                
                # 获取当前值
                current_value = driver.execute_script("return arguments[0].value;", real_input) or ""
                print(f"当前输入框值: '{current_value}'")
                
                # 增强清除功能
                clearing_methods = [
                    # 方法1: 使用clear()方法
                    lambda: real_input.clear(),
                    
                    # 方法2: 使用Ctrl+A和Delete
                    lambda: (real_input.send_keys(Keys.CONTROL + "a"), 
                             time.sleep(0.1), 
                             real_input.send_keys(Keys.DELETE)),
                             
                    # 方法3: 使用JavaScript清空
                    lambda: driver.execute_script("arguments[0].value = '';", real_input)
                ]
                
                for i, clear_method in enumerate(clearing_methods):
                    try:
                        print(f"尝试清除方法 {i+1}")
                        clear_method()
                        time.sleep(0.2)
                        
                        # 验证清空是否成功
                        after_clear = driver.execute_script("return arguments[0].value;", real_input) or ""
                        print(f"清除后的值: '{after_clear}'")
                        
                        if not after_clear:
                            print(f"清除成功，方法 {i+1} 有效")
                            break
                    except Exception as e:
                        print(f"清除方法 {i+1} 失败: {e}")
                
                # 输入新值
                real_input.send_keys(str(value))
                time.sleep(1)
                
                # 验证输入后的值
                final_value = driver.execute_script("return arguments[0].value;", real_input) or ""
                print(f"输入后的值: '{final_value}'")
                
                # 如果输入后的值不正确，尝试使用JavaScript设置
                if final_value != str(value):
                    print(f"输入后的值不正确，尝试使用JavaScript设置")
                    driver.execute_script("arguments[0].value = arguments[1];", real_input, str(value))
                    
                    # 触发变更事件
                    driver.execute_script("""
                        var event = new Event('change', { bubbles: true });
                        arguments[0].dispatchEvent(event);
                        var inputEvent = new Event('input', { bubbles: true });
                        arguments[0].dispatchEvent(inputEvent);
                    """, real_input)
                    time.sleep(0.2)
                
                # 按Tab键确认
                real_input.send_keys(Keys.TAB)
                time.sleep(0.2)
                
                return True
        
        # 2. 如果找不到真实输入框，尝试找到搜索输入框
        search_input = driver.execute_script("""
            var formItem = arguments[0].closest('.form-item') || arguments[0].closest('.card-table-modal-form-item');
            if (!formItem) return null;
            
            // 查找所有输入框，特别是可能的搜索框
            var inputs = formItem.querySelectorAll('input[placeholder], input.refer-input, input.nc-input');
            for (var i = 0; i < inputs.length; i++) {
                // 返回第一个非隐藏的输入框
                if (inputs[i].offsetParent !== null) {
                    return inputs[i];
                }
            }
            return null;
        """, input_element)
        
        if search_input:
            print("找到搜索输入框")
            
            # 点击获取焦点
            driver.execute_script("arguments[0].click();", search_input)
            time.sleep(0.5)
            
            # 获取当前值
            current_value = driver.execute_script("return arguments[0].value;", search_input) or ""
            print(f"当前输入框值: '{current_value}'")
            
            # 增强清除功能
            clearing_methods = [
                # 方法1: 使用clear()方法
                lambda: search_input.clear(),
                
                # 方法2: 使用Ctrl+A和Delete
                lambda: (search_input.send_keys(Keys.CONTROL + "a"), 
                         time.sleep(0.1), 
                         search_input.send_keys(Keys.DELETE)),
                         
                # 方法3: 使用JavaScript清空
                lambda: driver.execute_script("arguments[0].value = '';", search_input)
            ]
            
            for i, clear_method in enumerate(clearing_methods):
                try:
                    print(f"尝试清除方法 {i+1}")
                    clear_method()
                    time.sleep(0.2)
                    
                    # 验证清空是否成功
                    after_clear = driver.execute_script("return arguments[0].value;", search_input) or ""
                    print(f"清除后的值: '{after_clear}'")
                    
                    if not after_clear:
                        print(f"清除成功，方法 {i+1} 有效")
                        break
                except Exception as e:
                    print(f"清除方法 {i+1} 失败: {e}")
            
            # 输入搜索值
            search_input.send_keys(str(value))
            time.sleep(1)
            
            # 验证输入后的值
            final_value = driver.execute_script("return arguments[0].value;", search_input) or ""
            print(f"输入后的值: '{final_value}'")
            
            # 如果输入后的值不正确，尝试使用JavaScript设置
            if final_value != str(value):
                print(f"输入后的值不正确，尝试使用JavaScript设置")
                driver.execute_script("arguments[0].value = arguments[1];", search_input, str(value))
                
                # 触发变更事件
                driver.execute_script("""
                    var event = new Event('change', { bubbles: true });
                    arguments[0].dispatchEvent(event);
                    var inputEvent = new Event('input', { bubbles: true });
                    arguments[0].dispatchEvent(inputEvent);
                """, search_input)
                time.sleep(0.2)
            
            # 查找下拉列表项
            try:
                dropdown_items = WebDriverWait(driver, 3).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                    "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item"))
                )
                
                if dropdown_items:
                    print(f"找到 {len(dropdown_items)} 个下拉选项")
                    
                    # 查找匹配的选项
                    matched_item = None
                    for item in dropdown_items:
                        if str(value).lower() in item.text.lower():
                            matched_item = item
                            break
                    
                    # 点击匹配的选项或第一个选项
                    if matched_item:
                        print(f"点击匹配的选项: {matched_item.text}")
                        driver.execute_script("arguments[0].click();", matched_item)
                    else:
                        print(f"点击第一个选项: {dropdown_items[0].text}")
                        driver.execute_script("arguments[0].click();", dropdown_items[0])
                    time.sleep(0.5)
                    return True
                else:
                    print("未找到下拉选项")
                    
                    # 如果没有找到下拉选项，尝试按Enter键
                    search_input.send_keys(Keys.ENTER)
                    time.sleep(0.5)
            except Exception as e:
                print(f"查找或点击下拉选项失败: {e}")
                
                # 尝试按Enter键确认
                search_input.send_keys(Keys.ENTER)
                time.sleep(0.5)
            
            return True
        
        # 3. 如果找不到搜索输入框，尝试使用父元素作为触发点
        parent_element = driver.execute_script("""
            var element = arguments[0];
            return element.parentElement;
        """, input_element)
        
        if parent_element:
            print(f"尝试点击父元素")
            # 使用JavaScript点击
            driver.execute_script("arguments[0].click();", parent_element)
            time.sleep(0.5)
            
            # 查找可能出现的输入框
            try:
                search_input = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 
                    "input[placeholder], input.refer-input, input.nc-input"))
                )
                
                if search_input:
                    print("点击父元素后找到输入框")
                    
                    # 获取当前值
                    current_value = driver.execute_script("return arguments[0].value;", search_input) or ""
                    print(f"当前输入框值: '{current_value}'")
                    
                    # 增强清除功能
                    clearing_methods = [
                        # 方法1: 使用clear()方法
                        lambda: search_input.clear(),
                        
                        # 方法2: 使用Ctrl+A和Delete
                        lambda: (search_input.send_keys(Keys.CONTROL + "a"), 
                                 time.sleep(0.1), 
                                 search_input.send_keys(Keys.DELETE)),
                                 
                        # 方法3: 使用JavaScript清空
                        lambda: driver.execute_script("arguments[0].value = '';", search_input)
                    ]
                    
                    for i, clear_method in enumerate(clearing_methods):
                        try:
                            print(f"尝试清除方法 {i+1}")
                            clear_method()
                            time.sleep(0.2)
                            
                            # 验证清空是否成功
                            after_clear = driver.execute_script("return arguments[0].value;", search_input) or ""
                            print(f"清除后的值: '{after_clear}'")
                            
                            if not after_clear:
                                print(f"清除成功，方法 {i+1} 有效")
                                break
                        except Exception as e:
                            print(f"清除方法 {i+1} 失败: {e}")
                    
                    # 输入值
                    search_input.send_keys(str(value))
                    time.sleep(1)
                    
                    # 验证输入后的值
                    final_value = driver.execute_script("return arguments[0].value;", search_input) or ""
                    print(f"输入后的值: '{final_value}'")
                    
                    # 如果输入后的值不正确，尝试使用JavaScript设置
                    if final_value != str(value):
                        print(f"输入后的值不正确，尝试使用JavaScript设置")
                        driver.execute_script("arguments[0].value = arguments[1];", search_input, str(value))
                        
                        # 触发变更事件
                        driver.execute_script("""
                            var event = new Event('change', { bubbles: true });
                            arguments[0].dispatchEvent(event);
                            var inputEvent = new Event('input', { bubbles: true });
                            arguments[0].dispatchEvent(inputEvent);
                        """, search_input)
                        time.sleep(0.2)
                    
                    # 查找下拉选项
                    dropdown_items = WebDriverWait(driver, 2).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                        "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item"))
                    )
                    
                    if dropdown_items:
                        print(f"找到 {len(dropdown_items)} 个下拉选项")
                        
                        # 查找匹配的选项
                        matched_item = None
                        for item in dropdown_items:
                            if str(value).lower() in item.text.lower():
                                matched_item = item
                                break
                        
                        # 点击匹配的选项或第一个选项
                        if matched_item:
                            print(f"点击匹配的选项: {matched_item.text}")
                            driver.execute_script("arguments[0].click();", matched_item)
                        else:
                            print(f"点击第一个选项: {dropdown_items[0].text}")
                            driver.execute_script("arguments[0].click();", dropdown_items[0])
                        time.sleep(0.5)
                        return True
            except Exception as e:
                print(f"在父元素中查找输入框或下拉选项失败: {e}")
        
        # 4. 特殊处理特定字段类型
        if "报销类型" in field_name or "报销人" in field_name:
            print(f"特殊处理{field_name}字段")
            try:
                # 查找表单中所有可能的输入框
                inputs = driver.find_elements(By.CSS_SELECTOR, 
                    "input[type='text']:not([readonly]), input:not([type='hidden']), input.refer-input, input.nc-input")
                
                # 遍历所有输入框，尝试找到正确的一个
                for input_field in inputs:
                    try:
                        # 尝试点击输入框
                        driver.execute_script("arguments[0].click();", input_field)
                        time.sleep(0.5)
                        
                        # 获取当前值
                        current_value = driver.execute_script("return arguments[0].value;", input_field) or ""
                        print(f"当前输入框值: '{current_value}'")
                        
                        # 增强清除功能
                        clearing_methods = [
                            # 方法1: 使用clear()方法
                            lambda: input_field.clear(),
                            
                            # 方法2: 使用Ctrl+A和Delete
                            lambda: (input_field.send_keys(Keys.CONTROL + "a"), 
                                     time.sleep(0.1), 
                                     input_field.send_keys(Keys.DELETE)),
                                     
                            # 方法3: 使用JavaScript清空
                            lambda: driver.execute_script("arguments[0].value = '';", input_field)
                        ]
                        
                        for i, clear_method in enumerate(clearing_methods):
                            try:
                                print(f"尝试清除方法 {i+1}")
                                clear_method()
                                time.sleep(0.2)
                                
                                # 验证清空是否成功
                                after_clear = driver.execute_script("return arguments[0].value;", input_field) or ""
                                print(f"清除后的值: '{after_clear}'")
                                
                                if not after_clear:
                                    print(f"清除成功，方法 {i+1} 有效")
                                    break
                            except Exception as e:
                                print(f"清除方法 {i+1} 失败: {e}")
                        
                        # 输入值
                        input_field.send_keys(str(value))
                        time.sleep(1)
                        
                        # 验证输入后的值
                        final_value = driver.execute_script("return arguments[0].value;", input_field) or ""
                        print(f"输入后的值: '{final_value}'")
                        
                        # 如果输入后的值不正确，尝试使用JavaScript设置
                        if final_value != str(value):
                            print(f"输入后的值不正确，尝试使用JavaScript设置")
                            driver.execute_script("arguments[0].value = arguments[1];", input_field, str(value))
                            
                            # 触发变更事件
                            driver.execute_script("""
                                var event = new Event('change', { bubbles: true });
                                arguments[0].dispatchEvent(event);
                                var inputEvent = new Event('input', { bubbles: true });
                                arguments[0].dispatchEvent(inputEvent);
                            """, input_field)
                            time.sleep(0.2)
                        
                        # 检查是否有下拉框显示
                        try:
                            dropdown_items = WebDriverWait(driver, 2).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                                "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item"))
                            )
                            
                            if dropdown_items:
                                print(f"找到 {len(dropdown_items)} 个下拉选项")
                                
                                # 查找匹配的选项
                                matched_item = None
                                for item in dropdown_items:
                                    if str(value).lower() in item.text.lower():
                                        matched_item = item
                                        break
                                
                                # 点击匹配的选项或第一个选项
                                if matched_item:
                                    print(f"点击匹配的选项: {matched_item.text}")
                                    driver.execute_script("arguments[0].click();", matched_item)
                                else:
                                    print(f"点击第一个选项: {dropdown_items[0].text}")
                                    driver.execute_script("arguments[0].click();", dropdown_items[0])
                                time.sleep(0.5)
                                return True
                        except:
                            # 尝试按Enter键
                            input_field.send_keys(Keys.ENTER)
                            time.sleep(0.5)
                    except:
                        continue
            except Exception as e:
                print(f"特殊处理{field_name}失败: {e}")
        
        # 5. 尝试直接设置hidden-input的值
        print(f"尝试直接设置hidden-input的值")
        try:
            driver.execute_script("""
                arguments[0].value = arguments[1];
                
                // 触发变化事件
                var event = new Event('change', { bubbles: true });
                arguments[0].dispatchEvent(event);
                
                // 触发输入事件
                var inputEvent = new Event('input', { bubbles: true });
                arguments[0].dispatchEvent(inputEvent);
            """, input_element, str(value))
            
            print(f"直接设置hidden-input值成功")
            return True
        except Exception as e:
            print(f"直接设置hidden-input值失败: {e}")
        
        # 所有方法都失败，返回失败
        print(f"所有方法都无法处理hidden-input，填写失败")
        return False
    
    except Exception as e:
        print(f"处理hidden-input类型的元素时出错: {e}")
        return False

def handle_checkbox(driver, checkbox_element, value):
    """
    处理复选框元素
    
    :param driver: WebDriver对象
    :param checkbox_element: 复选框元素
    :param value: 要设置的值（"是"则选中，其他值则不选中）
    :return: 是否成功处理
    """
    try:
        # 获取复选框当前状态
        is_checked = driver.execute_script("""
            var element = arguments[0];
            // 通过属性或父元素的类来判断复选框状态
            if (element.checked !== undefined) {
                return element.checked;
            }
            var parent = element.closest('.u-checkbox');
            if (parent) {
                return parent.classList.contains('is-checked') || 
                       parent.querySelector('input').checked;
            }
            return false;
        """, checkbox_element)
        
        print(f"复选框当前状态: {'已选中' if is_checked else '未选中'}")
        
        # 确定是否需要点击复选框
        should_check = (value == "是" or value == "true" or value is True)
        
        # 如果当前状态与期望状态不一致，点击复选框
        if (should_check and not is_checked) or (not should_check and is_checked):
            print(f"点击复选框，将状态改为: {'选中' if should_check else '取消选中'}")
            
            # 尝试直接点击
            try:
                checkbox_element.click()
                time.sleep(0.5)
            except Exception as e:
                print(f"直接点击失败: {e}，尝试使用JavaScript点击")
                driver.execute_script("arguments[0].click();", checkbox_element)
                time.sleep(0.5)
                
            # 再次检查复选框状态是否改变
            is_checked_after = driver.execute_script("""
                var element = arguments[0];
                if (element.checked !== undefined) {
                    return element.checked;
                }
                var parent = element.closest('.u-checkbox');
                if (parent) {
                    return parent.classList.contains('is-checked') ||
                           parent.querySelector('input').checked;
                }
                return false;
            """, checkbox_element)
            
            print(f"点击后复选框状态: {'已选中' if is_checked_after else '未选中'}")
            
            # 如果状态仍不符合预期，尝试找到复选框的父元素并点击
            if (should_check and not is_checked_after) or (not should_check and is_checked_after):
                print("尝试点击复选框父元素")
                checkbox_parent = driver.execute_script("""
                    return arguments[0].closest('.u-checkbox') || 
                           arguments[0].parentElement;
                """, checkbox_element)
                
                if checkbox_parent:
                    driver.execute_script("arguments[0].click();", checkbox_parent)
                    time.sleep(0.5)
        else:
            print(f"复选框状态已经是期望的: {'选中' if should_check else '未选中'}，无需点击")
        
        return True
    except Exception as e:
        print(f"处理复选框时出错: {e}")
        return False

def handle_reimbursement_person(driver, input_element, value):
    """
    专门处理报销人字段的函数
    
    :param driver: WebDriver对象
    :param input_element: 输入元素
    :param value: 要填写的值
    :return: 是否成功处理
    """
    try:
        print(f"使用专门的报销人处理函数，值: {value}")
        
        # 1. 首先尝试常规点击
        try:
            input_element.click()
        except:
            try:
                driver.execute_script("arguments[0].click();", input_element)
            except:
                pass
        time.sleep(1)
        
        # 2. 检查是否有下拉选择器按钮，并点击它
        try:
            dropdown_button = driver.execute_script("""
                var input = arguments[0];
                var parent = input.parentElement;
                // 查找下拉按钮（通常是输入框右侧的图标）
                var button = parent.querySelector('i.uf-symlist, i.uf-treelist, i.uf-grid, button, .u-form-control-icon');
                return button;
            """, input_element)
            
            if dropdown_button:
                print("找到报销人字段的下拉按钮，点击它")
                driver.execute_script("arguments[0].click();", dropdown_button)
                time.sleep(1)
        except Exception as e:
            print(f"寻找下拉按钮失败: {e}")
        
        # 3. 获取当前值
        current_value = driver.execute_script("return arguments[0].value;", input_element) or ""
        print(f"当前报销人输入框值: '{current_value}'")
        
        # 4. 使用多种方法彻底清除当前值
        clearing_methods = [
            # 方法1: 连续多次使用clear()方法
            lambda: [input_element.clear() for _ in range(3)],
            
            # 方法2: 使用Ctrl+A和Delete
            lambda: (input_element.send_keys(Keys.CONTROL + "a"), 
                     time.sleep(0.5), 
                     input_element.send_keys(Keys.DELETE),
                     time.sleep(0.5)),
                     
            # 方法3: 使用JavaScript清空
            lambda: driver.execute_script("""
                arguments[0].value = '';
                // 触发change事件
                var event = new Event('change', { bubbles: true });
                arguments[0].dispatchEvent(event);
                // 触发input事件
                var inputEvent = new Event('input', { bubbles: true });
                arguments[0].dispatchEvent(inputEvent);
            """, input_element),
            
            # 方法4: 使用多个退格键
            lambda: (input_element.send_keys(Keys.CONTROL + "a"), 
                     time.sleep(0.5),
                     [input_element.send_keys(Keys.BACKSPACE) for _ in range(len(current_value) + 5)]),
                     
            # 方法5: 使用JavaScript设置属性并触发事件
            lambda: driver.execute_script("""
                arguments[0].setAttribute('value', '');
                arguments[0].value = '';
                arguments[0].innerText = '';
                arguments[0].innerHTML = '';
                
                // 触发所有可能的事件
                ['change', 'input', 'keyup', 'keydown', 'keypress', 'blur', 'focus'].forEach(function(eventName) {
                    var event = new Event(eventName, { bubbles: true });
                    arguments[0].dispatchEvent(event);
                });
            """, input_element),
            
            # 方法6: 使用ActionChains
            lambda: (ActionChains(driver)
                    .click(input_element)
                    .key_down(Keys.CONTROL)
                    .send_keys('a')
                    .key_up(Keys.CONTROL)
                    .send_keys(Keys.DELETE)
                    .perform())
        ]
        
        for i, clear_method in enumerate(clearing_methods):
            try:
                print(f"尝试报销人清除方法 {i+1}")
                clear_method()
                time.sleep(0.5)
                
                # 验证清空是否成功
                after_clear = driver.execute_script("return arguments[0].value;", input_element) or ""
                print(f"清除后的值: '{after_clear}'")
                
                if not after_clear:
                    print(f"清除成功，方法 {i+1} 有效")
                    break
            except Exception as e:
                print(f"清除方法 {i+1} 失败: {e}")
        
        # 5. 最终确认输入框是否为空
        current_value = driver.execute_script("return arguments[0].value;", input_element) or ""
        if current_value:
            print(f"警告: 多次尝试后报销人输入框仍未清空，当前值: '{current_value}'")
            # 最后一次尝试，使用JavaScript替换DOM元素内容
            try:
                driver.execute_script("""
                    var input = arguments[0];
                    var parent = input.parentElement;
                    
                    // 记录原始input的属性
                    var attrs = {};
                    for (var i = 0; i < input.attributes.length; i++) {
                        var attr = input.attributes[i];
                        attrs[attr.name] = attr.value;
                    }
                    
                    // 创建新的input元素
                    var newInput = document.createElement('input');
                    
                    // 复制属性
                    for (var name in attrs) {
                        newInput.setAttribute(name, attrs[name]);
                    }
                    
                    // 替换元素
                    if (parent) {
                        parent.replaceChild(newInput, input);
                        return "已替换输入元素";
                    }
                    return "未找到父元素，无法替换";
                """, input_element)
                time.sleep(0.5)
                print("已尝试替换DOM元素")
                
                # 重新获取元素
                input_element = driver.execute_script("""
                    var label = document.querySelector('label:contains("报销人")');
                    if (label) {
                        var formItem = label.closest('.form-item');
                        if (formItem) {
                            return formItem.querySelector('input');
                        }
                    }
                    return arguments[0];
                """, input_element)
            except Exception as e:
                print(f"替换DOM元素失败: {e}")
        
        # 6. 输入新值
        print(f"开始输入报销人值: {value}")
        try:
            # 先尝试常规输入
            input_element.send_keys(str(value))
        except:
            # 备用: 使用JavaScript设置值
            driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
        time.sleep(1)
        
        # 验证输入后的值
        final_value = driver.execute_script("return arguments[0].value;", input_element) or ""
        print(f"输入后的报销人值: '{final_value}'")
        
        # 如果输入的值不正确或包含原始值，尝试使用JavaScript完全替换
        if final_value != str(value):
            print(f"输入后的值不正确，使用JavaScript设置")
            driver.execute_script("""
                arguments[0].value = arguments[1];
                // 触发所有可能的事件
                ['change', 'input', 'keyup', 'blur'].forEach(function(eventName) {
                    var event = new Event(eventName, { bubbles: true });
                    arguments[0].dispatchEvent(event);
                });
            """, input_element, str(value))
            time.sleep(0.5)
            
            # 再次验证
            final_value = driver.execute_script("return arguments[0].value;", input_element) or ""
            print(f"JavaScript设置后的报销人值: '{final_value}'")
        
        # 7. 处理可能的下拉选项
        try:
            dropdown_items = WebDriverWait(driver, 3).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                "li.u-select-dropdown-menu-item, .u-select-dropdown-menu-item, .refer-item"))
            )
            
            if dropdown_items:
                print(f"找到 {len(dropdown_items)} 个报销人下拉选项")
                
                # 查找匹配的选项
                matched_item = None
                for item in dropdown_items:
                    if str(value).lower() in item.text.lower():
                        matched_item = item
                        print(f"找到匹配的报销人选项: {item.text}")
                        break
                
                # 点击匹配的选项或第一个选项
                if matched_item:
                    print(f"点击匹配的报销人选项: {matched_item.text}")
                    driver.execute_script("arguments[0].click();", matched_item)
                else:
                    print(f"点击第一个报销人选项: {dropdown_items[0].text}")
                    driver.execute_script("arguments[0].click();", dropdown_items[0])
                time.sleep(0.5)
        except Exception as e:
            print(f"处理报销人下拉选项失败: {e}")
            # 如果没有下拉选项或处理失败，尝试按Enter键确认
            try:
                input_element.send_keys(Keys.ENTER)
                time.sleep(0.5)
            except:
                pass
        
        # 8. 点击页面其他位置，确保焦点移出
        try:
            actions = ActionChains(driver)
            actions.move_by_offset(50, 50).click().perform()
            time.sleep(0.5)
        except Exception as e:
            print(f"点击页面其他位置失败: {e}")
        
        return True
    
    except Exception as e:
        print(f"处理报销人字段时出错: {e}")
        return False

def find_form_fields_with_js(driver):
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
            
            // 检查是否是复选框
            var checkbox = controlDiv.querySelector('input[type="checkbox"], .u-checkbox');
            if (checkbox) {
                result.push({
                    labelText: cleanLabelText,
                    element: checkbox,
                    isCheckbox: true
                });
                continue;
            }
            
            // 检查是否包含隐藏输入框和显示输入框的特殊结构
            var hiddenInput = controlDiv.querySelector('input.hidden-input');
            var referInput = controlDiv.querySelector('.nc-input, .refer-input, .u-form-control');
            
            // 特殊情况处理：hidden-input + refer-input 结构
            if (hiddenInput && referInput) {
                result.push({
                    labelText: cleanLabelText,
                    element: referInput,  // 使用可见输入框
                    hiddenElement: hiddenInput,  // 保存隐藏输入框引用
                    isSpecialField: true,
                    isCheckbox: false
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
                // 特殊处理：标记报销人字段
                var isReimbursementPerson = cleanLabelText === '报销人';
                
                result.push({
                    labelText: cleanLabelText,
                    element: inputElement,
                    isSpecialField: false,
                    isCheckbox: false,
                    isReimbursementPerson: isReimbursementPerson  // 添加报销人标记
                });
            }
        }
        
        return result;
    """
    
    return driver.execute_script(script)

def handle_special_field(driver, field, value):
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

def fill_form(driver, form_data, expand_xpath=None, modal_xpath=None):
    """
    填写表单
    
    :param driver: WebDriver对象
    :param form_data: 表单数据字典或JSON文件路径
    :param expand_xpath: 展开按钮的XPath (可选)
    :param modal_xpath: 模态框的XPath (可选)
    :return: 是否成功填写表单
    """
    try:
        # 如果form_data是字符串，假定它是JSON文件路径
        if isinstance(form_data, str):
            form_data = load_json_data(form_data)
        
        # 点击展开按钮（如果提供了展开按钮的XPath）
        if expand_xpath:
            click_expand_button(driver, expand_xpath)
        
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
        for json_key, value in form_data.items():
            print(f"尝试填写: {json_key} = {value}")
            
            # 查找匹配的字段
            input_element = None
            matched_label = None
            is_reimbursement_person = False
            
            # 1. 先尝试精确匹配
            if json_key in form_fields:
                input_element = form_fields[json_key]['input']
                matched_label = json_key
                # 检查是否为报销人字段
                is_reimbursement_person = json_key == "报销人"
            else:
                # 2. 尝试模糊匹配
                for field_label, field_info in form_fields.items():
                    # 检查JSON键是否包含在标签中，或标签是否包含在JSON键中
                    if json_key in field_label or field_label in json_key:
                        input_element = field_info['input']
                        matched_label = field_label
                        # 检查是否为报销人字段
                        is_reimbursement_person = "报销人" in field_label
                        break
            
            # 填写字段
            if input_element:
                print(f"找到匹配的标签: '{matched_label}'")
                
                # 特殊处理报销人字段
                if is_reimbursement_person:
                    print("检测到报销人字段，使用专门的处理函数")
                    if handle_reimbursement_person(driver, input_element, value):
                        print(f"成功填写报销人: {json_key} = {value}")
                        success_count += 1
                    else:
                        print(f"填写报销人失败: {json_key}")
                else:
                    # 处理其他字段
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
        print(f"填写表单时出错: {e}")
        return False

def process_json_folder_for_forms(driver, folder_path, increase_button_xpath=None, expand_button_xpath=None, modal_xpath=None, confirm_button_xpath=None):
    """
    处理文件夹中的所有JSON文件，并使用这些数据填写表单
    
    :param driver: WebDriver对象
    :param folder_path: JSON文件所在的文件夹路径
    :param increase_button_xpath: 增行按钮的XPath (可选)
    :param expand_button_xpath: 展开按钮的XPath (可选)
    :param modal_xpath: 模态框的XPath (可选)
    :param confirm_button_xpath: 确认按钮的XPath (可选)
    :return: 处理成功的JSON文件数量
    """
    try:
        # 加载文件夹中的所有JSON文件数据
        json_data_list = load_json_files_from_folder(folder_path)
        
        if not json_data_list:
            print(f"未找到可处理的JSON数据，跳过表单填写")
            return 0
        
        print(f"\n===== 开始处理 {folder_path} 中的 {len(json_data_list)} 个JSON文件 =====")
        
        success_count = 0
        for index, json_item in enumerate(json_data_list):
            file_path = json_item['file_path']
            form_data = json_item['data']
            
            print(f"\n处理第 {index+1}/{len(json_data_list)} 个JSON文件: {os.path.basename(file_path)}")
            
            # 1. 点击增行按钮
            if increase_button_xpath:
                try:
                    print(f"尝试点击增行按钮...")
                    increase_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, increase_button_xpath))
                    )
                    
                    # 确保按钮可见
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", increase_button)
                    time.sleep(1)
                    
                    # 点击增行按钮
                    increase_button.click()
                    print("成功点击增行按钮")
                    time.sleep(1)
                except Exception as e:
                    print(f"点击增行按钮失败: {e}")
                    
                    # 尝试使用JavaScript点击
                    try:
                        result = driver.execute_script(f"""
                            var element = document.evaluate('{increase_button_xpath}', 
                                document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                            if (element) {{
                                element.click();
                                return "成功点击增行按钮";
                            }} else {{
                                return "未找到增行按钮";
                            }}
                        """)
                        print(f"JavaScript点击增行按钮结果: {result}")
                        time.sleep(1)
                    except Exception as js_error:
                        print(f"JavaScript点击增行按钮失败: {js_error}")
            
            # 2. 点击展开按钮
            if expand_button_xpath:
                try:
                    print(f"尝试点击展开按钮...")
                    expand_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, expand_button_xpath))
                    )
                    
                    # 确保按钮可见
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", expand_button)
                    time.sleep(1)
                    
                    # 点击展开按钮
                    expand_button.click()
                    print("成功点击展开按钮")
                    time.sleep(1)
                except Exception as e:
                    print(f"点击展开按钮失败: {e}")
                    
                    # 备用方法：尝试通过文本内容找到展开按钮
                    try:
                        print("尝试通过文本内容查找展开按钮...")
                        text_button = driver.find_element(By.XPATH, "//a[text()='展开']")
                        text_button.click()
                        print("通过文本内容成功点击展开按钮")
                        time.sleep(1)
                    except Exception as text_error:
                        print(f"通过文本内容查找展开按钮失败: {text_error}")
            
            # 3. 填写表单
            print(f"开始填写表单数据...")
            if fill_form(driver, form_data, None, modal_xpath):
                print(f"表单数据填写成功")
            else:
                print(f"表单数据填写失败")
                continue
            
            # 4. 点击确认按钮
            if confirm_button_xpath:
                try:
                    print(f"尝试点击确认按钮...")
                    confirm_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, confirm_button_xpath))
                    )
                    
                    # 确保按钮可见
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_button)
                    time.sleep(1)
                    
                    # 点击确认按钮
                    confirm_button.click()
                    print("成功点击确认按钮")
                    time.sleep(1)
                except Exception as e:
                    print(f"点击确认按钮失败: {e}")
                    
                    # 尝试通过文本内容查找确认按钮
                    try:
                        print("尝试通过文本内容查找确认按钮...")
                        ok_buttons = driver.find_elements(By.XPATH, "//button[contains(text(),'确定') or contains(text(),'OK') or contains(text(),'保存')]")
                        if ok_buttons:
                            ok_buttons[0].click()
                            print("通过文本内容成功点击确认按钮")
                            time.sleep(1)
                        else:
                            print("未找到确认按钮")
                    except Exception as text_error:
                        print(f"通过文本内容查找确认按钮失败: {text_error}")
            
            success_count += 1
            print(f"成功处理第 {index+1}/{len(json_data_list)} 个JSON文件")
        
        print(f"\n===== 文件夹 {folder_path} 中的JSON文件处理完成，成功处理 {success_count}/{len(json_data_list)} 个文件 =====")
        return success_count
    
    except Exception as e:
        print(f"处理JSON文件夹时出错: {e}")
        return 0

def main(url, json_file=None, expand_xpath=None, modal_xpath=None):
    """
    主函数
    
    :param url: 网站URL
    :param json_file: JSON文件路径 (可选)
    :param expand_xpath: 展开按钮的XPath (可选)
    :param modal_xpath: 模态框的XPath (可选)
    """
    # 初始化WebDriver
    driver = webdriver.Chrome()
    
    try:
        # 打开网站
        print(f"打开网站: {url}")
        driver.get(url)
        # time.sleep(3)
        
        # 加载表单数据
        if json_file:
            form_data = load_json_data(json_file)
        else:
            # 使用默认数据
            form_data = {
                "报销类型": "001",
                "收支项目": "差旅费-外勤出差",
                "出发日期": "2020-05-09",
                "到达日期": "2020-05-10",
                "出发地点": "福州",
                "出差天数": "2",
                "交通工具": "火车",
                "说明（含同行人员等）": "同行",
                "飞机车船费": "500",
                "出差补贴": "100",
                "特殊事项": "无",
                "税率（%）": "1",
                "其他费用（民航发展基金、行李费等）": "100"
            }
        
        # 填写表单
        fill_form(driver, form_data, expand_xpath, modal_xpath)
        
        # 等待用户操作
        print("表单填写完成，等待10秒...")
        time.sleep(10)
    
    except Exception as e:
        print(f"执行过程中出错: {e}")
    
    finally:
        # 关闭浏览器
        driver.quit()
        print("浏览器已关闭")

if __name__ == "__main__":
    # 示例用法
    # main("http://您的财务系统网址", "form_data.json")
    pass
