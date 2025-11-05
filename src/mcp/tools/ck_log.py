import time
import requests
from datetime import datetime
import json
import hashlib

# 配置参数
CONFIG = {
    'appCode': 'JC_PIDLB',
    'token': '9b78f9ab773774f5b2c4b627ff007152',
    'api_url': 'http://deeplog-lb-api.jd.com/',
}

def get_np_auth_headers(app_code, token):
    """生成NP接口鉴权header（修正版）"""
    now = datetime.now()
    # 修正时间格式：%H%M%Y%m%d (小时分钟年月日)
    time_str = now.strftime("%H%M%Y%m%d")  # 将 %m 改为 %M
    timestamp = str(int(time.time() * 1000))  # 使用毫秒级时间戳
    # 签名字符串
    sign_str = f"#{token}NP{time_str}"
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    headers = {
        "Content-Type": "application/json;charset=utf-8",  
        "appCode": app_code,
        "sign": sign,
        "time": timestamp,
    }
    return headers


def format_response_data(raw_data):
# 格式化接口返回的数据（格式化接口返回数据中的时间戳，转为便于观察的字符串时间）
    formatted_response = []
    for item in raw_data.get("response", []):
        #将接口返回的时间戳，转为可读的时间
        timestamp_ms = item.get("time")

        human_time = datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

        formatted_item = {
            "time": human_time,
            "value": item.get("value", [])
        }
        formatted_response.append(formatted_item)
    
    return {
        "code": "0",
        "message": "success",
        "data": formatted_response
    }
    
def query_single_field_sum(params):
    """单字段SUM聚合查询"""
    headers = get_np_auth_headers(CONFIG['appCode'], CONFIG['token'])
    url = f"{CONFIG['api_url']}v1/search"
    
    try:
        response = requests.post(url, headers=headers, json=params, timeout=30)
        print(f"响应状态码: {response.status_code}")
        
        raw_data = response.json()
        
        return raw_data
        
        
    except requests.exceptions.RequestException as e:
        error_info = {
            "code": -1,
            "message": f"请求失败: {str(e)}",
            "error_type": type(e).__name__
        }
        if hasattr(e, 'response') and e.response is not None:
            error_info["response_text"] = e.response.text
            error_info["status_code"] = e.response.status_code
        return error_info

# 使用示例
if __name__ == "__main__":
    # 示例1: 查询lbha业务，域数据源查询访问量
    lbha_params = {
    "bizName": "lbha",
    "multiresource": ["count", "bin","bout"],
    "timeRange": {
        "start": "2025-11-05 10:00:00",
        "end": "2025-11-05 10:05:00"
    },
    "match" : [{"eq" : {
        "host" : ["erp.jd.com"],

        }}],
    "interval": "60s",
    "algorithm": {
        "algorithmName": "sum"
    }
}
    
    result = query_single_field_sum(lbha_params)
    print(format_response_data(result))

    # print(result)