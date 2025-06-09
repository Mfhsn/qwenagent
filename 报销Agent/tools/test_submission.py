#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试NCC提交功能，验证表单填写是否正常工作
"""

import os
import json
import sys
from ncc_submission import NCCSubmission

# 测试数据
test_form = {
    "报销类型": "差旅费",
    "报销事由": "出差",
    "报销总金额": 2500.50,
    "收款银行名称": "招商银行",
    "收款人卡号": "6225887788990011",
    "分摊原因": "",
    "住宿费超标金额": "0",
    "城市内公务交通车费超标金额": "0",
    "超标说明": "无",
    "费用明细": {
        "交通费": [
            {
                "invoice_type": "火车票",
                "date": "2023-10-15",
                "travel_date": "2023-10-15",
                "amount": 553.5,
                "departure": "上海",
                "destination": "北京",
                "passenger": "张三"
            }
        ],
        "住宿费": [
            {
                "invoice_type": "酒店住宿发票",
                "date": "2023-10-15",
                "check_in_date": "2023-10-15",
                "check_out_date": "2023-10-17",
                "amount": 880,
                "hotel_name": "北京希尔顿酒店",
                "nights": 2,
                "guest_name": "张三"
            }
        ]
    }
}

def main():
    """测试主函数"""
    # 创建测试目录
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建json目录
    json_dir = os.path.join(os.path.dirname(test_dir), "json")
    transportation_dir = os.path.join(json_dir, "transportation")
    hotel_dir = os.path.join(json_dir, "hotel")
    
    # 确保目录存在
    for dir_path in [json_dir, transportation_dir, hotel_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    
    # 创建transportation测试数据
    for i, trans in enumerate(test_form["费用明细"].get("交通费", [])):
        trans_file = os.path.join(transportation_dir, f"transportation_{i+1}.json")
        with open(trans_file, 'w', encoding='utf-8') as f:
            json.dump(trans, f, ensure_ascii=False, indent=2)
        print(f"已创建交通费测试数据: {trans_file}")
    
    # 创建hotel测试数据
    for i, hotel in enumerate(test_form["费用明细"].get("住宿费", [])):
        hotel_file = os.path.join(hotel_dir, f"hotel_{i+1}.json")
        with open(hotel_file, 'w', encoding='utf-8') as f:
            json.dump(hotel, f, ensure_ascii=False, indent=2)
        print(f"已创建住宿费测试数据: {hotel_file}")
    
    print("测试数据准备完成，请确认json目录下的文件：")
    print(f"transportation目录: {os.listdir(transportation_dir)}")
    print(f"hotel目录: {os.listdir(hotel_dir)}")
    
    # 测试提交功能
    try:
        print("\n===== 开始测试NCC提交功能 =====")
        
        # 创建NCCSubmission实例
        ncc_tool = NCCSubmission()
        
        # 验证转换函数
        form_data = ncc_tool._convert_reimbursement_to_form_data(test_form)
        print(f"表单数据转换结果: {form_data}")
        
        # 是否执行RPA（需要慎重，会启动浏览器并进行实际操作）
        do_rpa = False
        
        if do_rpa:
            print("\n警告：即将执行RPA操作，将会启动浏览器并尝试登录NCC系统！")
            confirm = input("是否继续？(y/n): ")
            if confirm.lower() == 'y':
                # 模拟调用
                result = ncc_tool.call(json.dumps({
                    "submission_params": {
                        "reimbursement_form": test_form,
                        "confirm": True,
                        "execute_rpa": True
                    }
                }))
                
                # 输出结果
                print(f"执行结果: {result}")
            else:
                print("已取消RPA测试")
        else:
            print("RPA测试已禁用，不会启动浏览器")
        
        print("\n===== 测试完成 =====")
        
    except Exception as e:
        print(f"测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 