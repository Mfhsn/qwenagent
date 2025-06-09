#!/usr/bin/env python
# -*- coding: utf-8 -*-

print("开始测试导入...")

try:
    # 直接导入
    import utils
    print("成功直接导入utils模块")
except ImportError as e:
    print(f"直接导入失败: {e}")

try:
    # 相对导入
    from . import utils
    print("成功相对导入utils模块")
except ImportError as e:
    print(f"相对导入失败: {e}")
    print("相对导入通常只能在包内使用，而不能在主模块中使用")

try:
    # 修改导入路径
    import sys
    import os
    
    # 添加当前目录到路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(current_dir)
    
    # 尝试导入
    import utils
    print(f"成功通过路径导入utils模块，版本: {getattr(utils, '__version__', '未知')}")
    
    # 打印utils模块中的函数
    functions = [name for name in dir(utils) if callable(getattr(utils, name)) and not name.startswith('_')]
    print(f"utils模块中的函数: {', '.join(functions[:10])}...")
    
    # 检查特定函数是否存在
    required_funcs = ['fill_form', 'load_json_data', 'get_json_files_from_folder', 
                      'click_expand_button', 'find_form_fields', 'handle_special_field',
                      'process_json_folder_for_forms']
    
    for func in required_funcs:
        if hasattr(utils, func) and callable(getattr(utils, func)):
            print(f"✓ 找到函数: {func}")
        else:
            print(f"✗ 未找到函数: {func}")
            
    # 检查process_json_folder_for_forms的源代码
    if hasattr(utils, 'process_json_folder_for_forms') and callable(getattr(utils, 'process_json_folder_for_forms')):
        import inspect
        print("\nprocess_json_folder_for_forms函数源代码:")
        print(inspect.getsource(utils.process_json_folder_for_forms))
    
except ImportError as e:
    print(f"路径导入失败: {e}")
except Exception as e:
    print(f"检查函数时出错: {e}")
    import traceback
    traceback.print_exc()

print("测试完成") 