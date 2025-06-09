from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import os
import json
import sys
import argparse
from selenium.webdriver.chrome.options import Options

# 全局超时设置（降低以加快速度）
TIMEOUT = 5  # 减少默认等待时间

# 解析命令行参数
def parse_arguments():
    parser = argparse.ArgumentParser(description='RPA自动化报销流程')
    parser.add_argument('--transport-dir', '-t', 
                      help='交通发票JSON文件所在目录路径，默认为transportation目录')
    parser.add_argument('--hotel-dir',
                      help='酒店发票JSON文件所在目录路径，默认为hotel目录')
    return parser.parse_args()

# 获取命令行参数
args = parse_arguments()

# 添加当前目录到sys.path，确保能正确导入utils模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import fill_form, load_json_data, get_json_files_from_folder


# 设置Chrome选项以连接到已有的Chrome浏览器实例
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

# 连接到已有的Chrome浏览器实例
try:
    driver = webdriver.Chrome(options=chrome_options)
    print("成功连接到已打开的Chrome浏览器")
except Exception as e:
    print(f"连接到已有浏览器失败: {e}")
    print("请确保已经使用以下命令启动Chrome浏览器:")
    print(r'"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222')
    print("如果Chrome安装在其他位置，请调整路径")
    # 尝试自动启动Chrome浏览器
    print("\n正在尝试自动启动Chrome浏览器...")
    try:
        import subprocess
        subprocess.Popen(r'C:\Program Files\Google\Chrome\Application\chrome.exe --remote-debugging-port=9222')
        print("Chrome浏览器已启动，请手动完成登录步骤，然后重新运行此脚本")
    except Exception as launch_error:
        print(f"自动启动Chrome浏览器失败: {launch_error}")
    sys.exit(1)

# 获取当前窗口句柄
print(f"Current tabs: {len(driver.window_handles)}")
print("Current URL:", driver.current_url)

# 获取更多页面信息
try:
    print("Current page title:", driver.title)
    
    # 检查所有标签页，寻找标题包含"员工差旅费报销单"的标签页
    target_tab_index = -1
    for i, handle in enumerate(driver.window_handles):
        driver.switch_to.window(handle)
        print(f"Tab {i+1} - URL: {driver.current_url}, Title: {driver.title}")
        if "员工差旅费报销单" in driver.title:
            target_tab_index = i
            print(f"Found the target tab (Employee Travel Expense Form) at index {i+1}")
    
    # 如果找到了目标标签页，切换到它
    if target_tab_index >= 0:
        print(f"Switching to the target tab (index {target_tab_index+1})")
        driver.switch_to.window(driver.window_handles[target_tab_index])
        print(f"Now on tab with title: {driver.title}")
    else:
        print("Warning: No tab with '员工差旅费报销单' in title was found")
    
    # 查找可能的iframe
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"Found {len(iframes)} iframes")
    
    # 如果没有找到iframe，尝试等待页面加载更多内容
    if len(iframes) == 0:
        print("No iframes found, waiting for the page to load more content...")
        # time.sleep(3)  # 多等待几秒
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"After waiting, found {len(iframes)} iframes")
        
        # 如果仍然没有找到iframe，尝试点击刷新页面或某些元素以触发iframe加载
        if len(iframes) == 0:
            print("Still no iframes found, trying alternative detection methods...")
            
            # 尝试查找特定于差旅费报销单页面的元素
            try:
                # 查找页面上可能存在的特定元素，如标题栏、按钮等
                specific_elements = driver.find_elements(By.XPATH, "//div[contains(text(), '员工差旅费报销单')]")
                if specific_elements:
                    print(f"Found {len(specific_elements)} elements containing '员工差旅费报销单'")
                
                # 查找页面上的表格或表单元素
                tables = driver.find_elements(By.TAG_NAME, "table")
                print(f"Found {len(tables)} tables on the page")
                
                # 查找表单相关元素
                form_elements = driver.find_elements(By.CSS_SELECTOR, "input, select, textarea")
                print(f"Found {len(form_elements)} form input elements on the page")
                
                # 打印页面结构以帮助调试
                print("Page structure summary:")
                structure = driver.execute_script("""
                    function getElementInfo(element, level) {
                        const tagName = element.tagName.toLowerCase();
                        const id = element.id ? '#' + element.id : '';
                        const className = element.className ? '.' + element.className.replace(/\\s+/g, '.') : '';
                        return '  '.repeat(level) + tagName + id + className;
                    }
                    
                    function scanDOM(element, level, maxLevel) {
                        if (level > maxLevel) return [];
                        let result = [getElementInfo(element, level)];
                        for (let i = 0; i < element.children.length && i < 3; i++) {
                            result = result.concat(scanDOM(element.children[i], level + 1, maxLevel));
                        }
                        return result;
                    }
                    
                    return scanDOM(document.body, 0, 3).join('\\n');
                """)
                print(structure)
            except Exception as e:
                print(f"Error during alternative detection: {e}")
            
    # 检查是否在表单页面上
    is_form_page = False
    
    # 即使没有iframe，也尝试在当前页面上直接查找表单元素
    form_elements = driver.find_elements(By.CSS_SELECTOR, "div.lightapp-component-form")
    if form_elements:
        print("Found form elements directly on the page!")
        is_form_page = True
    else:
        # 尝试查找更多可能的表单元素
        alternative_form_elements = driver.find_elements(By.CSS_SELECTOR, "form, div.form, div[class*='form'], table.form-table")
        if alternative_form_elements:
            print(f"Found {len(alternative_form_elements)} alternative form elements directly on the page!")
            is_form_page = True
        else:
            print("No form elements found directly on the page, checking iframes...")
    
    # 尝试切换到各个iframe检查内容
    if not is_form_page and iframes:
        # 保存当前窗口位置
        current_window = driver.current_window_handle
        
        for i, iframe in enumerate(iframes):
            try:
                print(f"Switching to iframe {i+1}")
                driver.switch_to.frame(iframe)
                
                # 尝试查找表单元素
                form_elements = driver.find_elements(By.CSS_SELECTOR, "div.lightapp-component-form")
                if form_elements:
                    print(f"Found form elements in iframe {i+1}!")
                    is_form_page = True
                    # 不切回主文档，保持在此iframe中
                    break
                
                # 如果没找到表单元素，切回主文档
                driver.switch_to.default_content()
            except Exception as e:
                print(f"Error checking iframe {i+1}: {e}")
                driver.switch_to.default_content()
        
        if not is_form_page:
            # 如果所有iframe都检查完还没找到表单，回到原始窗口
            driver.switch_to.window(current_window)
    
    # 如果仍然没有找到表单，尝试通过检查页面元素来确认是否在表单页面
    if not is_form_page and "员工差旅费报销单" in driver.title:
        print("Page title contains '员工差旅费报销单', assuming we are on the correct page")
        print("Proceeding with form filling even though form elements are not directly detected")
        
        # 尝试检查页面是否有特定的结构或元素，这些可能表明我们在差旅费报销单页面上
        try:
            # 检查是否存在表格或数据网格
            tables = driver.find_elements(By.TAG_NAME, "table")
            grid_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='grid'], [class*='table'], [class*='datagrid']")
            
            if tables or grid_elements:
                print(f"Found potential form-related elements: {len(tables)} tables, {len(grid_elements)} grid elements")
                
                # 尝试查找增行按钮或其他特定按钮
                add_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'add') or contains(text(), '增行') or contains(text(), '添加')]")
                if add_buttons:
                    print(f"Found {len(add_buttons)} potential add row buttons")
                
                # 查找标签或表单部分标题
                section_headers = driver.find_elements(By.XPATH, "//div[contains(text(), '基本信息') or contains(text(), '差旅信息') or contains(text(), '费用明细')]")
                if section_headers:
                    print(f"Found {len(section_headers)} form section headers")
                    for i, header in enumerate(section_headers):
                        print(f"  Section {i+1}: {header.text}")
            
                # 如果找到这些元素，我们可以假设我们在正确的页面上
                if tables or grid_elements or add_buttons or section_headers:
                    print("Found sufficient evidence that we are on the correct form page")
                    is_form_page = True
        except Exception as e:
            print(f"Error during special page structure detection: {e}")
        
        # 无论如何，由于标题包含目标文字，我们假设在正确的页面上
        is_form_page = True
    
    if is_form_page:
        print("Successfully located the form page, can continue with automated filling")
    else:
        print("\nWARNING: Could not find the form page. Please ensure you have manually navigated to the Employee Travel Expense Reimbursement Form page")
        print("You may need to manually complete: Application menu -> Expense Management -> Employee Travel Expense Reimbursement Form")
        
        # 询问用户是否需要帮助导航
        user_input = input("\nDo you need help navigating to the Employee Travel Expense Reimbursement Form? (y/n): ")
        if user_input.lower() == 'y':
            try:
                print("\nAttempting to help navigate to the Employee Travel Expense Reimbursement Form page...")
                # 首先回到主文档
                driver.switch_to.default_content()
                
                # 尝试点击应用菜单图标
                print("Trying to click the application menu icon...")
                try:
                    menu_icon = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.nc-workbench-icon[data-step='1']"))
                    )
                    menu_icon.click()
                    print("Successfully clicked the application menu icon")
                    # time.sleep(1)
                except Exception as e:
                    print(f"Failed to click application menu icon: {e}")
                    print("Please manually click the application menu icon in the top left corner")
                    input("Press Enter after clicking...")
                
                # 尝试点击"费用管理"菜单
                print("Trying to click the Expense Management menu...")
                try:
                    expense_menu = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'费用管理')]"))
                    )
                    expense_menu.click()
                    print("Successfully clicked the Expense Management menu")
                    # time.sleep(1)
                except Exception as e:
                    print(f"Failed to click Expense Management menu: {e}")
                    print("Please manually click the 'Expense Management' menu")
                    input("Press Enter after clicking...")
                
                # 尝试点击"员工差旅费报销单"选项
                print("Trying to click the Employee Travel Expense Reimbursement Form option...")
                try:
                    travel_expense_option = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'item-app') and contains(text(),'员工差旅费报销单')]"))
                    )
                    travel_expense_option.click()
                    print("Successfully clicked the Employee Travel Expense Reimbursement Form option")
                    # time.sleep(3)  # 等待新标签页打开
                    
                    # 获取所有窗口句柄并切换到新标签页
                    window_handles = driver.window_handles
                    if len(window_handles) > 1:
                        print(f"Detected {len(window_handles)} tabs, switching to the most recently opened tab")
                        driver.switch_to.window(window_handles[-1])  # 切换到最新打开的标签页
                        print(f"Switched to tab: {driver.title}")
                    
                    # 再次检查是否进入表单页面
                    print("Waiting for page to load...")
                    # time.sleep(3)
                    
                    # 寻找iframe并检查表单
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        try:
                            driver.switch_to.frame(iframe)
                            form_elements = driver.find_elements(By.CSS_SELECTOR, "div.lightapp-component-form")
                            if form_elements:
                                print("Successfully navigated to the form page!")
                                is_form_page = True
                                break
                            driver.switch_to.default_content()
                        except:
                            driver.switch_to.default_content()
                    
                    if not is_form_page:
                        print("Navigation seems complete, but no form elements were found. Please check if the page loaded correctly.")
                        print("Please confirm if you see the Employee Travel Expense Reimbursement Form page")
                        input("Press Enter after confirming...")
                except Exception as e:
                    print(f"Failed to click Employee Travel Expense Reimbursement Form option: {e}")
                    print("Please manually click the 'Employee Travel Expense Reimbursement Form' option")
                    input("Press Enter after completing navigation...")
            
            except Exception as e:
                print(f"Error during assisted navigation: {e}")
                print("Please manually complete navigation, continue after entering the Employee Travel Expense Reimbursement Form page")
                input("Press Enter after navigation is complete...")
        else:
            print("Please manually complete navigation, continue after entering the Employee Travel Expense Reimbursement Form page")
            input("Press Enter after navigation is complete...")
        
except Exception as e:
    print(f"Error while getting page information: {e}")

# 从这里开始执行后续操作
print("Starting to take control of the opened page, executing subsequent operations...")

# 9. 加载JSON数据
print("加载表单数据...")
json_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.json")
form_data = load_json_data(json_file_path)
print(f"已加载JSON数据: {form_data}")

# 定义JavaScript函数来查找表单字段
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

# 处理特殊字段的函数
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
        # time.sleep(0.5)
        
        # 直接在可见输入框中输入值
        element.clear()
        element.send_keys(str(value))
        # time.sleep(0.5)
        
        # 点击一下以确保值被接受
        element.send_keys(Keys.TAB)
        # time.sleep(0.5)
        
        # 检查是否需要选择下拉项
        try:
            # 尝试查找包含该值的下拉项
            dropdown_item = driver.find_element(By.XPATH, f"//li[contains(text(), '{value}')]")
            if dropdown_item.is_displayed():
                print(f"找到下拉项：{value}，点击选择")
                dropdown_item.click()
                # time.sleep(0.5)
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

# 10. 查找并填写表单字段
print("开始填写表单...")

# 查找所有包含form-item-label的元素
try:
    # 确保在正确的文档或iframe中
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if iframes:
        print(f"找到{len(iframes)}个iframe，尝试切换...")
        driver.switch_to.frame(iframes[0])  # 切换到第一个iframe
    
    # 等待表单加载完成
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.lightapp-component-form"))
    )
    print("表单已加载")
    
    # 使用JavaScript查找表单字段
    print("使用JavaScript查找表单字段...")
    form_fields = find_form_fields_with_js(driver)
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
                print(f"使用特殊字段处理方法处理: {label_text}")
                if handle_special_field(driver, field, value):
                    filled_fields += 1
                    print(f"成功填写特殊字段: {label_text}")
                continue
            
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
                    # time.sleep(0.5)
                    
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
                # time.sleep(0.5)
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
                # time.sleep(0.5)
                # 尝试直接设置值
                driver.execute_script("arguments[0].value = arguments[1];", input_element, str(value))
                input_element.send_keys(Keys.TAB)  # 按Tab关闭日期选择器
            elif "refer-input" in element_class or "nc-input" in element_class:
                # 引用输入框处理
                print(f"处理引用输入框: {label_text}")
                input_element.click()
                # time.sleep(0.5)
                input_element.clear()
                input_element.send_keys(str(value))
                input_element.send_keys(Keys.TAB)
                # time.sleep(0.5)
                
                # 检查是否需要从下拉列表选择
                try:
                    dropdown_items = driver.find_elements(By.XPATH, f"//li[contains(text(), '{value}')]")
                    if dropdown_items and dropdown_items[0].is_displayed():
                        dropdown_items[0].click()
                        # time.sleep(0.5)
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
            
            # time.sleep(0.5)  # 等待输入完成
            
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
    # 确保切回主文档
    try:
        driver.switch_to.default_content()
    except:
        pass

# 9. 加载transportation文件夹中的JSON数据文件
print("准备处理transportation文件夹中的JSON文件...")
# 使用命令行参数或默认路径
if args.transport_dir:
    transportation_folder = args.transport_dir
else:
    transportation_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transportation")
print(f"transportation文件夹路径: {transportation_folder}")

# 使用utils中的函数获取JSON文件列表
from utils import get_json_files_from_folder, load_json_data, fill_form

# 定义按钮的XPath
first_increase_button_xpath = "//*[@id=\"js_lightTabs_header_arap_bxbusitem\"]/div[4]/div/span/div/button[1]"  # 第一次点击的增行按钮
subsequent_increase_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[1]/button[2]"  # 后续点击的增行按钮
expand_button_xpath = "//*[@id=\"js_lightTabs_arap_bxbusitem\"]/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]"
modal_xpath = "//*[@id='tableModal']/div[1]/div/div"
confirm_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[2]/span[5]"

try:
    # 获取transportation文件夹中的所有JSON文件
    json_files = get_json_files_from_folder(transportation_folder)
    if not json_files:
        print("未找到JSON文件，无法处理")
    else:
        print(f"找到 {len(json_files)} 个JSON文件: {json_files}")
        
        # 确保在正确的iframe中
        driver.switch_to.default_content()
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if len(iframes) > 0:
            print(f"切换到iframe...")
            driver.switch_to.frame(iframes[0])
            
            # 处理所有JSON文件
            for index, json_file in enumerate(json_files):
                print(f"\n处理第 {index+1}/{len(json_files)} 个文件: {os.path.basename(json_file)}")
                
                # 加载JSON数据
                form_data = load_json_data(json_file)
                print(f"已加载数据: {form_data}")
                
                # 1. 点击增行按钮
                if index == 0:
                    # 第一次使用原始增行按钮XPath
                    print("使用第一次的增行按钮XPath")
                    increase_button_xpath = first_increase_button_xpath
                else:
                    # 后续使用新的增行按钮XPath
                    print("使用后续的增行按钮XPath")
                    increase_button_xpath = subsequent_increase_button_xpath
                
                try:
                    print(f"尝试点击增行按钮: {increase_button_xpath}")
                    increase_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, increase_button_xpath))
                    )
                    
                    # 确保按钮可见
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", increase_button)
                    # time.sleep(1)
                    
                    # 点击增行按钮
                    increase_button.click()
                    print("成功点击增行按钮")
                    # time.sleep(1)
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
                        # time.sleep(1)
                    except Exception as js_error:
                        print(f"JavaScript点击增行按钮失败: {js_error}")
                
                # 2. 点击展开按钮 (只在第一次处理时需要)
                if index == 0:
                    try:
                        print(f"尝试点击展开按钮...")
                        expand_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, expand_button_xpath))
                        )
                        
                        # 确保按钮可见
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", expand_button)
                        # time.sleep(1)
                        
                        # 点击展开按钮
                        expand_button.click()
                        print("成功点击展开按钮")
                        # time.sleep(1)
                    except Exception as e:
                        print(f"点击展开按钮失败: {e}")
                        
                        # 备用方法：尝试通过文本内容找到展开按钮
                        try:
                            print("尝试通过文本内容查找展开按钮...")
                            text_button = driver.find_element(By.XPATH, "//a[text()='展开']")
                            text_button.click()
                            print("通过文本内容成功点击展开按钮")
                            # time.sleep(1)
                        except Exception as text_error:
                            print(f"通过文本内容查找展开按钮失败: {text_error}")
                
                # 3. 填写表单
                print(f"开始填写表单数据...")
                if fill_form(driver, form_data, None, modal_xpath):
                    print(f"表单数据填写成功")
                else:
                    print(f"表单数据填写失败")
                    continue
                
                print(f"成功处理第 {index+1}/{len(json_files)} 个文件")
            
            # 所有文件处理完毕后，点击确认按钮
            print("所有文件处理完毕，点击确认按钮...")
            try:
                print(f"尝试点击确认按钮...")
                confirm_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, confirm_button_xpath))
                )
                
                # 确保按钮可见
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_button)
                # time.sleep(1)
                
                # 点击确认按钮
                confirm_button.click()
                print("成功点击确认按钮")
                # time.sleep(1)
            except Exception as e:
                print(f"点击确认按钮失败: {e}")
                
                # 尝试通过文本内容查找确认按钮
                try:
                    print("尝试通过文本内容查找确认按钮...")
                    ok_buttons = driver.find_elements(By.XPATH, "//button[contains(text(),'确定') or contains(text(),'OK') or contains(text(),'保存')]")
                    if ok_buttons:
                        ok_buttons[0].click()
                        print("通过文本内容成功点击确认按钮")
                        # time.sleep(1)
                    else:
                        print("未找到确认按钮")
                except Exception as text_error:
                    print(f"通过文本内容查找确认按钮失败: {text_error}")
            
            # 切回主文档
            driver.switch_to.default_content()
        else:
            print("未找到iframe，无法处理JSON文件")
            
    # 开始处理hotel文件夹
    print("\n\n====== 开始处理hotel文件夹 ======\n")
    
    # 获取hotel文件夹路径 - 使用命令行参数或默认路径
    if args.hotel_dir:
        hotel_folder = args.hotel_dir
    else:
        hotel_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hotel")
    print(f"hotel文件夹路径: {hotel_folder}")
    
    # 定义hotel区域的按钮XPath
    hotel_first_increase_button_xpath = "//*[@id=\"js_lightTabs_header_other\"]/div[4]/div/span/div/button[1]"  # 第一次点击的增行按钮
    hotel_expand_button_xpath = "//*[@id=\"js_lightTabs_other\"]/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]"  # 展开按钮
    hotel_subsequent_increase_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[1]/button[2]"  # 后续点击的增行按钮
    hotel_confirm_button_xpath = "/html/body/section[7]/div[2]/div/div/div[2]/div[2]/div[2]/span[5]"  # 确认按钮
    
    try:
        # 获取hotel文件夹中的所有JSON文件
        hotel_json_files = get_json_files_from_folder(hotel_folder)
        if not hotel_json_files:
            print("未找到hotel JSON文件，无法处理")
        else:
            print(f"找到 {len(hotel_json_files)} 个hotel JSON文件: {hotel_json_files}")
            
            # 确保在正确的iframe中
            driver.switch_to.default_content()
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if len(iframes) > 0:
                print(f"切换到iframe...")
                driver.switch_to.frame(iframes[0])
                
                # 处理所有hotel JSON文件
                for index, json_file in enumerate(hotel_json_files):
                    print(f"\n处理第 {index+1}/{len(hotel_json_files)} 个hotel文件: {os.path.basename(json_file)}")
                    
                    # 加载JSON数据
                    form_data = load_json_data(json_file)
                    print(f"已加载数据: {form_data}")
                    
                    # 1. 点击增行按钮
                    if index == 0:
                        # 第一次使用原始增行按钮XPath
                        print("使用第一次的hotel增行按钮XPath")
                        increase_button_xpath = hotel_first_increase_button_xpath
                    else:
                        # 后续使用新的增行按钮XPath
                        print("使用后续的hotel增行按钮XPath")
                        increase_button_xpath = hotel_subsequent_increase_button_xpath
                    
                    try:
                        print(f"尝试点击hotel增行按钮: {increase_button_xpath}")
                        increase_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, increase_button_xpath))
                        )
                        
                        # 确保按钮可见
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", increase_button)
                        # time.sleep(1)
                        
                        # 点击增行按钮
                        increase_button.click()
                        print("成功点击hotel增行按钮")
                        # time.sleep(1)
                    except Exception as e:
                        print(f"点击hotel增行按钮失败: {e}")
                        
                        # 尝试使用JavaScript点击
                        try:
                            result = driver.execute_script(f"""
                                var element = document.evaluate('{increase_button_xpath}', 
                                    document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (element) {{
                                    element.click();
                                    return "成功点击hotel增行按钮";
                                }} else {{
                                    return "未找到hotel增行按钮";
                                }}
                            """)
                            print(f"JavaScript点击hotel增行按钮结果: {result}")
                            # time.sleep(1)
                        except Exception as js_error:
                            print(f"JavaScript点击hotel增行按钮失败: {js_error}")
                    
                    # 2. 点击展开按钮 (只在第一次处理时需要)
                    if index == 0:
                        try:
                            print(f"尝试点击hotel展开按钮...")
                            # 尝试使用完整XPath而不是变量
                            xpath_to_use = "//*[@id=\"js_lightTabs_other\"]/div/div/div[1]/div[3]/div/div[2]/div/table/tbody/tr/td/div/span/div/a[1]"
                            print(f"使用硬编码XPath: {xpath_to_use}")
                            
                            expand_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, xpath_to_use))
                            )
                            
                            # 确保按钮可见
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", expand_button)
                            # time.sleep(1)
                            
                            # 点击展开按钮
                            expand_button.click()
                            print("成功点击hotel展开按钮")
                            # time.sleep(1)
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
                                # time.sleep(1)
                            except Exception as js_error:
                                print(f"JavaScript点击hotel展开按钮失败: {js_error}")
                            
                            # 备用方法：尝试通过文本内容找到展开按钮
                            try:
                                print("尝试通过文本内容查找hotel展开按钮...")
                                text_button = driver.find_element(By.XPATH, "//a[text()='展开']")
                                text_button.click()
                                print("通过文本内容成功点击hotel展开按钮")
                                # time.sleep(1)
                            except Exception as text_error:
                                print(f"通过文本内容查找hotel展开按钮失败: {text_error}")
                    
                    # 3. 填写表单
                    print(f"开始填写hotel表单数据...")
                    if fill_form(driver, form_data, None, modal_xpath):
                        print(f"hotel表单数据填写成功")
                    else:
                        print(f"hotel表单数据填写失败")
                        continue
                    
                    print(f"成功处理第 {index+1}/{len(hotel_json_files)} 个hotel文件")
                
                # 所有hotel文件处理完毕后，点击确认按钮
                print("所有hotel文件处理完毕，点击确认按钮...")
                try:
                    print(f"尝试点击hotel确认按钮...")
                    confirm_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, hotel_confirm_button_xpath))
                    )
                    
                    # 确保按钮可见
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_button)
                    # time.sleep(1)
                    
                    # 点击确认按钮
                    confirm_button.click()
                    print("成功点击hotel确认按钮")
                    # time.sleep(1)
                except Exception as e:
                    print(f"点击hotel确认按钮失败: {e}")
                    
                    # 尝试通过文本内容查找确认按钮
                    try:
                        print("尝试通过文本内容查找hotel确认按钮...")
                        ok_buttons = driver.find_elements(By.XPATH, "//button[contains(text(),'确定') or contains(text(),'OK') or contains(text(),'保存')]")
                        if ok_buttons:
                            ok_buttons[0].click()
                            print("通过文本内容成功点击hotel确认按钮")
                            # time.sleep(1)
                        else:
                            print("未找到hotel确认按钮")
                    except Exception as text_error:
                        print(f"通过文本内容查找hotel确认按钮失败: {text_error}")
                
                # 切回主文档
                driver.switch_to.default_content()
            else:
                print("未找到iframe，无法处理hotel JSON文件")
                
    except Exception as e:
        print(f"处理hotel文件时出错: {e}")
        # 确保切回主文档
        driver.switch_to.default_content()
            
except Exception as e:
    print(f"处理JSON文件时出错: {e}")
    # 确保切回主文档
    driver.switch_to.default_content()

print("所有操作已完成，您可以在浏览器中进行操作，完成后请手动关闭此程序")

# 使用无限循环保持脚本运行，防止浏览器关闭
try:
    while True:
        time.sleep(10)  # 每10秒检查一次
except Exception as e:
    print(f"自动化过程中出现错误: {e}")
    
    # 发生错误时也保持浏览器打开
    input("按Enter键关闭浏览器并退出程序...")
    
# 最终关闭浏览器（只有在用户中断程序时才会执行）
# driver.quit()