from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
import os
import json
import sys


# 添加当前目录到sys.path，确保能正确导入utils模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils_1 import fill_form, load_json_data, get_json_files_from_folder, handle_checkbox, find_form_fields_with_js, handle_special_field, handle_reimbursement_person


service = Service(port=9515)  # 使用不同于默认的端口
driver = webdriver.Chrome(service=service)


# 如果当前有多个标签页，确保使用正确的标签页
if len(driver.window_handles) > 1:
    driver.switch_to.window(driver.window_handles[1])  # 切换到第二个标签页

# 1. 打开网页
driver.get("http://110.90.119.97:8808/nccloud/resources/workbench/public/common/main/index.html#")

# 等待页面加载完成
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "username"))
)

# 2. 输入账号
username_input = driver.find_element(By.ID, "username")
username_input.clear()
username_input.send_keys("T18638")  # 请替换为实际用户名

# 3. 输入密码
password_input = driver.find_element(By.ID, "password")
password_input.clear()
password_input.send_keys("M@fh18524730187")  # 请替换为实际密码

# 4. 点击登录按钮
login_button = driver.find_element(By.ID, "loginBtn")
login_button.click()

# 等待登录完成，使用更长的等待时间
print("登录成功，等待页面加载...")
time.sleep(3)  # 增加等待时间

# 5. 点击应用菜单图标
print("点击应用菜单图标...")
WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "div.nc-workbench-icon[data-step='1']"))
).click()

# 等待菜单加载
time.sleep(1)

# 6. 点击"费用管理"菜单
print("点击费用管理菜单...")
# 等待费用管理菜单可点击
WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'费用管理')]"))
).click()

# 等待子菜单加载
time.sleep(1)

# 7. 点击"员工差旅费报销单"选项
print("点击员工差旅费报销单...")
# 使用XPath定位元素
WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'item-app') and contains(text(),'员工差旅费报销单')]"))
).click()

# 等待新标签页打开
print("等待新标签页打开...")
time.sleep(3)  # 给页面一些时间来打开新标签页

# 获取所有窗口句柄并切换到新标签页
print("切换到新打开的标签页...")
window_handles = driver.window_handles
if len(window_handles) > 1:
    print(f"检测到{len(window_handles)}个标签页，切换到最新打开的标签页")
    driver.switch_to.window(window_handles[-1])  # 切换到最新打开的标签页
else:
    print("未检测到新标签页，保持在当前标签页")

# 等待页面加载
print("正在进入员工差旅费报销单页面...")
time.sleep(2)  # 增加等待时间，确保页面完全加载

# 8. 先将浏览器窗口最大化
print("最大化浏览器窗口...")
driver.maximize_window()
time.sleep(2)  # 增加等待时间

# 9. 加载JSON数据
print("加载表单数据...")
json_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.json")
form_data = load_json_data(json_file_path)
print(f"已加载JSON数据: {form_data}")

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
    
    # 在查找表单字段后，添加打印每个字段的信息，以便调试
    print("打印所有表单字段信息:")
    for i, field in enumerate(form_fields):
        field_type = "复选框" if field.get('isCheckbox') else "普通字段"
        print(f"{i+1}. 标签: '{field['labelText']}', 类型: {field_type}")
    
    # 填写表单
    filled_fields = 0
    for field in form_fields:
        label_text = field['labelText']
        input_element = field['element']
        is_special_field = field.get('isSpecialField', False)
        is_checkbox = field.get('isCheckbox', False)
        is_reimbursement_person = field.get('isReimbursementPerson', False) or label_text == "报销人"
        
        print(f"处理字段: '{label_text}', 是否特殊字段: {is_special_field}, 是否复选框: {is_checkbox}, 是否报销人字段: {is_reimbursement_person}")
        
        # 查找匹配的JSON键
        matched_key = None
        for json_key in form_data.keys():
            if label_text == json_key:
                matched_key = json_key
                break
        
        if matched_key:
            value = form_data[matched_key]
            print(f"找到字段 '{label_text}' 的输入框，填写值: '{value}'")
            
            # 特殊处理报销人字段
            if is_reimbursement_person:
                print(f"使用专门的报销人处理函数处理: {label_text}")
                if handle_reimbursement_person(driver, input_element, value):
                    filled_fields += 1
                    print(f"成功填写报销人字段: {label_text}")
                continue
            
            # 处理复选框
            if is_checkbox:
                print(f"处理复选框: {label_text}")
                if handle_checkbox(driver, input_element, value):
                    filled_fields += 1
                    print(f"成功处理复选框: {label_text}")
                continue
            
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
    # 确保切回主文档
    try:
        driver.switch_to.default_content()
    except:
        pass

# 9. 加载transportation文件夹中的JSON数据文件
print("准备处理transportation文件夹中的JSON文件...")
transportation_folder = "C:/Users/97818/Desktop/project/rpa_test/报销Agent_new/报销Agent/json/transportation"
print(f"transportation文件夹路径: {transportation_folder}")

# 使用utils中的函数获取JSON文件列表
from utils_1 import get_json_files_from_folder, load_json_data, fill_form

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
                    time.sleep(1)
                    
                    # 点击增行按钮
                    increase_button.click()
                    print("成功点击增行按钮")
                    time.sleep(2)
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
                        time.sleep(2)
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
                        time.sleep(1)
                        
                        # 点击展开按钮
                        expand_button.click()
                        print("成功点击展开按钮")
                        time.sleep(2)
                    except Exception as e:
                        print(f"点击展开按钮失败: {e}")
                        
                        # 备用方法：尝试通过文本内容找到展开按钮
                        try:
                            print("尝试通过文本内容查找展开按钮...")
                            text_button = driver.find_element(By.XPATH, "//a[text()='展开']")
                            text_button.click()
                            print("通过文本内容成功点击展开按钮")
                            time.sleep(2)
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
                time.sleep(1)
                
                # 点击确认按钮
                confirm_button.click()
                print("成功点击确认按钮")
                time.sleep(2)
            except Exception as e:
                print(f"点击确认按钮失败: {e}")
                
                # 尝试通过文本内容查找确认按钮
                try:
                    print("尝试通过文本内容查找确认按钮...")
                    ok_buttons = driver.find_elements(By.XPATH, "//button[contains(text(),'确定') or contains(text(),'OK') or contains(text(),'保存')]")
                    if ok_buttons:
                        ok_buttons[0].click()
                        print("通过文本内容成功点击确认按钮")
                        time.sleep(2)
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
    
    # 获取hotel文件夹路径
    hotel_folder = "C:/Users/97818/Desktop/project/rpa_test/报销Agent_new/报销Agent/json/hotel"
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
                        time.sleep(1)
                        
                        # 点击增行按钮
                        increase_button.click()
                        print("成功点击hotel增行按钮")
                        time.sleep(2)
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
                            time.sleep(2)
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
                            time.sleep(1)
                            
                            # 点击展开按钮
                            expand_button.click()
                            print("成功点击hotel展开按钮")
                            time.sleep(2)
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
                                time.sleep(2)
                            except Exception as js_error:
                                print(f"JavaScript点击hotel展开按钮失败: {js_error}")
                            
                            # 备用方法：尝试通过文本内容找到展开按钮
                            try:
                                print("尝试通过文本内容查找hotel展开按钮...")
                                text_button = driver.find_element(By.XPATH, "//a[text()='展开']")
                                text_button.click()
                                print("通过文本内容成功点击hotel展开按钮")
                                time.sleep(2)
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
                    time.sleep(1)
                    
                    # 点击确认按钮
                    confirm_button.click()
                    print("成功点击hotel确认按钮")
                    time.sleep(2)
                except Exception as e:
                    print(f"点击hotel确认按钮失败: {e}")
                    
                    # 尝试通过文本内容查找确认按钮
                    try:
                        print("尝试通过文本内容查找hotel确认按钮...")
                        ok_buttons = driver.find_elements(By.XPATH, "//button[contains(text(),'确定') or contains(text(),'OK') or contains(text(),'保存')]")
                        if ok_buttons:
                            ok_buttons[0].click()
                            print("通过文本内容成功点击hotel确认按钮")
                            time.sleep(2)
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