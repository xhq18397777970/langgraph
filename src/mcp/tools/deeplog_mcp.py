import time
import requests
from datetime import datetime
import json
import hashlib
from typing import List, Dict, Optional, Any, Union
from fastmcp import FastMCP

# 创建MCP服务器实例
mcp = FastMCP("deep_log 日志数据查询服务", port=10025)

# 配置参数
CONFIG = {
    'appCode': 'JC_PIDLB',
    'token': '9b78f9ab773774f5b2c4b627ff007152',
    'api_url': 'http://deeplog-lb-api.jd.com/',
}

def get_np_auth_headers(app_code: str, token: str) -> dict:
    now = datetime.now()
    # 修正时间格式:%H%M%Y%m%d (小时分钟年月日)
    time_str = now.strftime("%H%M%Y%m%d")
    timestamp = str(int(time.time() * 1000))
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

@mcp.tool
def query_log_info(
    multiresource: List[str],
    timeRange: Dict[str, str],
    match: List[Dict],
    interval: str,
    bizName: str = "lbha"
) -> dict:
    """
    查询Deeplog平台的日志数据:
    查询域名QPS、带宽、查询LB服务器的QPS、状态码占比、404访问最多地址、后端实例访问统计、客户端QPS、客户端Top10
    
    
    Args:
        bizName: 必填,业务/数据源名称,选填（"lbha","nginx","nginx4"）默认"lbha"
        multiresource: 必填，字符串列表，可填（count求和表示访问量、bin字段求和表示请求带宽、bout表示响应带宽）
        timeRange: 必填,起止时间（例如从2023年1月1日0点0分0秒到2023年1月2日10点10分10秒{"start": "2023-01-01 00:00:00", "end": "2023-01-02 10:00:00"}）
        interval: 必填,时序间隔,为空时取该时间段的总体聚合值,粒度有(10s、5m、1s、1h四种单位,例如:1s、2s、1m、4h)时间范围越大填的粒度越大
        match: 必的，匹配条件对象列表。
        match块中定义了查询过滤条件,模块中参数均为选填项,字段间关系均为AND,对OR的关系暂时不做处理
            match格式示例:
            [
                {
                    "eq": {
                        "host": ["re.jd.com"],
                        "url": ["/favicon.ico"], 
                        "vip": ["172.28.15.52"],
                        "lb-node-name": ["yfb001"],
                        "protocol": ["HTTP"],
                        "srv-ip": ["172.28.15.52"],
                        "isp": ["CUCC"],
                        "area": ["BeiJing"]
                    },
                    "gt": {
                        "bin": 3000
                    }
                }
            ]
            数组间关系为OR,数组内关系为AND,同字段数据内数组关系为OR
            
        例子:
        (1)域名等于jd.com的QPS,则"match":[{"eq":{"host": ["jd.com"]}}]
        (2)请求带宽大于3000的数据,则"match":[{"gt":{"bin":3000}}]
        (3)请求带宽大于3000且域名等于jd.com的数据,则"match":[{"gt":{"bin":3000},"eq":{"host": ["jd.com"]}}]
        (4)请求带宽大于3000且域名等于jd.com或baidu.com的数据,则"match":[{"gt":{"bin":3000},"eq":{"host": ["jd.com","baidu.com"]}}]
        
        这只是案例，需要根据用户的问题进行替换
        (1)查询域名jd.com请求带宽,时间:2025年11月05日0点0分0秒到2025年11月05日10点01分00秒,时间粒度为10s
        请求参数:
        bizName="lbha"
        multiresource=["bin"]
        timeRange={"start": "2025-11-05 10:00:00", "end": "2025-11-05 10:01:00"}
        match=[{"eq": {"host": ["erp.jd.com"]}}]
        interval="60s"
        
        2、查询lbha业务下,vip等于11.189.32.1的请求带宽和响应带宽和QPS数,时间范围为2025年11月05日0点0分0秒到2025年11月05日10点06分00秒,时间粒度为2m
        bizName="lbha"
        multiresource=["bin","bout","count"]
        timeRange={"start": "2025-11-05 10:00:00", "end": "2025-11-05 10:06:00"}
        match=[{"eq": {"vip": ["11.189.32.1"]}}]
        interval="2m"
        
    Returns:
        dict: 日志查询结果
    """
    
    params = {
        "bizName": bizName,
        "multiresource": multiresource,
        "timeRange": timeRange,
        "match": match,
        "interval": interval,
        "algorithm": {
            "algorithmName": "sum"
        }
    }
    
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
    # 运行MCP服务器
    mcp.run(transport="sse")