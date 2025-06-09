import json
from datetime import datetime
import pandas as pd
from qwen_agent.tools.base import BaseTool, register_tool

@register_tool('trip_recorder')
class TripRecorder(BaseTool):
    """行程录入工具，用于记录和管理用户出差行程信息"""
    
    description = '行程录入工具，用于记录用户的出差行程信息，包含出发日期、到达日期、出差天数、出发地点、到达地点、交通工具、出差事由等信息。'
    parameters = [{
        'name': 'trip_info',
        'type': 'object',
        'description': '包含行程信息的对象',
        'properties': {
            'departure_date': {'type': 'string', 'description': '出发日期，格式为YYYY-MM-DD'},
            'arrival_date': {'type': 'string', 'description': '到达日期，格式为YYYY-MM-DD'},
            'days': {'type': 'integer', 'description': '出差天数'},
            'departure_place': {'type': 'string', 'description': '出发地点'},
            'arrival_place': {'type': 'string', 'description': '到达地点'},
            'transportation': {'type': 'string', 'description': '交通工具，如飞机、火车、汽车等'},
            'trip_purpose': {'type': 'string', 'description': '出差事由'},
            'round_trip': {'type': 'boolean', 'description': '是否往返行程，默认为true'}
        },
        'required': ['departure_date', 'arrival_date', 'departure_place', 'arrival_place', 'trip_purpose']
    }]
    
    def __init__(self, tool_cfg=None):
        super().__init__(tool_cfg)
        self.trips = []
    
    def call(self, params: str, **kwargs) -> str:
        """处理行程录入请求"""
        trip_info = json.loads(params)['trip_info']
        
        # 设置往返行程默认值
        if 'round_trip' not in trip_info:
            trip_info['round_trip'] = True
        
        # 计算出差天数（如果未提供）
        if 'days' not in trip_info or not trip_info['days']:
            try:
                d1 = datetime.strptime(trip_info['departure_date'], '%Y-%m-%d')
                d2 = datetime.strptime(trip_info['arrival_date'], '%Y-%m-%d')
                trip_info['days'] = (d2 - d1).days + 1
            except:
                trip_info['days'] = 1
        
        # 添加到行程列表
        self.trips.append(trip_info)
        
        # 构建表格形式的行程信息
        if self.trips:
            df = pd.DataFrame(self.trips)
            trip_table = df.to_markdown(index=False)
        else:
            trip_table = "暂无行程信息"
        
        return json.dumps({
            'status': 'success',
            'message': '行程已成功记录',
            'trip_table': trip_table,
            'trips': self.trips
        }, ensure_ascii=False)
    
    def get_trips(self):
        """获取所有已记录的行程"""
        return self.trips
    
    def clear_trips(self):
        """清空所有行程记录"""
        self.trips = []
        return json.dumps({
            'status': 'success',
            'message': '所有行程记录已清空'
        }, ensure_ascii=False)
    
    def update_trip(self, index, updated_info):
        """更新指定行程信息"""
        if 0 <= index < len(self.trips):
            self.trips[index].update(updated_info)
            return json.dumps({
                'status': 'success',
                'message': f'已更新第{index+1}条行程信息',
                'updated_trip': self.trips[index]
            }, ensure_ascii=False)
        else:
            return json.dumps({
                'status': 'error',
                'message': f'行程索引{index}不存在'
            }, ensure_ascii=False)
    
    def delete_trip(self, index):
        """删除指定行程"""
        if 0 <= index < len(self.trips):
            deleted_trip = self.trips.pop(index)
            return json.dumps({
                'status': 'success',
                'message': f'已删除第{index+1}条行程信息',
                'deleted_trip': deleted_trip
            }, ensure_ascii=False)
        else:
            return json.dumps({
                'status': 'error',
                'message': f'行程索引{index}不存在'
            }, ensure_ascii=False) 