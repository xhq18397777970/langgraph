import time
import requests
from datetime import datetime
import json
import hashlib
from typing import List, Dict, Optional, Any, Union
from fastmcp import FastMCP

# 创建MCP服务器实例,port本地测试用
mcp = FastMCP("deep_log 日志数据查询服务", port=10026)

# 配置参数
CONFIG_deeplog_api = {
    'appCode': 'JC_PIDLB',
    'token': '9b78f9ab773774f5b2c4b627ff007152',
    'api_url': 'http://deeplog-lb-api.jd.com/',
}
CONFIG_deeplog_ck = {
    'appCode': 'JC_PIDLB',
    'token': '9b78f9ab773774f5b2c4b627ff007152',
    'api_url': 'http://deeplog-ck.jd.com/rest/api/search',
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
def query_log_info_sum(
    multiresource: List[str],
    timeRange: Dict[str, str],
    match: List[Dict],
    interval: str,
    bizName: str = "lbha"
) -> dict:
    """
    查询Deeplog平台的日志数据,简单求和统计
        查询域名QPS、带宽、查询;LB服务器的QPS
    
    Args:
        bizName: 必填,业务/数据源名称,选填("lbha","nginx","nginx4")默认"lbha"
        multiresource: 必填,字符串列表,可填(count求和表示访问量、bin字段求和表示请求带宽、bout表示响应带宽)
        timeRange: 必填,起止时间(例如从2023年1月1日0点0分0秒到2023年1月2日10点10分10秒{"start": "2023-01-01 00:00:00", "end": "2023-01-02 10:00:00"})
        interval: 必填,时序间隔,为空时取该时间段的总体聚合值,粒度有(10s、5m、1s、1h四种单位,例如:1s、2s、1m、4h)时间范围越大填的粒度越大
        match: 必的,匹配条件对象列表。
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
        
        这只是案例,需要根据用户的问题进行替换
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
    
    headers = get_np_auth_headers(CONFIG_deeplog_api['appCode'], CONFIG_deeplog_api['token'])
    url = f"{CONFIG_deeplog_api['api_url']}v1/search"
    
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


@mcp.tool
def query_log_info_group(
    groupBy:List[str],
    resource: List[str],
    timeRange: Dict[str, str],
    match: List[Dict],
    interval: str,
    algorithm: Dict[str, Any],
    bizName: str = "lbha",
    
) -> dict:
    """
    
    查询Deeplog平台的日志数据,并按条件分组展示,多维数据
        查询某域名在某时段,响应时间大于1s的请求:(1)按vip分组计数(2)按后端服务器计算
        查询域名后端实例(或vip)的指标(QPS、请求带宽、响应带宽)
        查询某域名在某时段状态码分布
        查询lbha,404状态码访问最多的host和url
    
    Args:
        强调resource必须是字符串列表!
        bizName: 必填,业务/数据源名称,选填("lbha","nginx","nginx4")默认"lbha"
        resource: 必填,列表，字符串列表,(如count计数)
        timeRange: 必填,起止时间(例如从2023年1月1日0点0分0秒到2023年1月2日10点10分10秒{"start": "2023-01-01 00:00:00", "end": "2023-01-02 10:00:00"})
        interval: 必填,时序间隔,为空时取该时间段的总体聚合值,粒度有(10s、5m、1s、1h四种单位,例如:1s、2s、1m、4h)时间范围越大填的粒度越大
        match: 必填,匹配条件对象列表。
        match块中定义了查询过滤条件,模块中参数均为选填项,字段间关系均为AND,对OR的关系暂时不做处理
            查询条件包括:eq等于、gte大于等于、gt大于、lte小于等于、lt小于
            可以匹配这些指标: srv_delay(响应耗时 header+body)、total_delay(请求总耗时)、client_network_delay(客户端网络耗时)
            
                match格式示例: 域名等于jd.com ,响应耗时大于1000ms
                [
                    {
                        "eq": {
                            "host": ["jd.com"],
                        },
                        "gt": {
                            "srv_delay": 1000
                        }
                    }
                ]
                域名等于jd.com ,请求总耗时大于5000ms
                [
                    {
                        "eq": {
                            "host": ["re.jd.com"],
                        },
                        "lte": {
                            "total_deay": 5000
                        }
                    }
                ]
                数组间关系为OR,数组内关系为AND,同字段数据内数组关系为OR
        
        groupBy,必填，字符串列表。定义数据如何展示,按照指标分组(可按照:srv_ip后端服务器ip、vip、host、url、http_code分组)。
        
        这只是案例,需要根据用户的问题进行替换
        
        (1)域名后端实例(服务器,即srv_ip)的QPS，bin，bout,时间:2025年11月05日10点0分0秒到2025年11月05日10点01分00秒,时间粒度为10s
            请求参数:
            bizName="lbha"
            resource=["count","bout","bin"]
            timeRange={"start": "2025-11-05 10:00:00", "end": "2025-11-05 10:01:00"}
            interval="10s"
            match=[{"eq": {"host": ["jd.com"]}}]
            groupBy=["srv_ip"]
            
        (2)某域名某时间段内,请求总耗时(total_delay)大于1(gt)的请求数(count),按照VIP分组(或按照srv_ip后端服务器ip分组),时间间隔2m
            请求参数:
            bizName="lbha"
            resource=["count"]
            timeRange={"start": "2025-11-05 10:00:00", "end": "2025-11-05 10:06:00"}
            match=[{"eq": {"host": ["jd.com"]}},"gt": {"total_delay" "1000}"]
            interval="2m"
            groupBy=["srv_ip"]
                若按照vip分组则:groupBy=["vip"]
            
        (3)某域名某时间段内状态码分布，按照http_code分组展示(即：查找域名的状态码分布)
            请求参数:
            bizName="lbha"
            resource=["count"]
            timeRange={"start": "2025-11-05 10:00:00", "end": "2025-11-05 10:06:00"}
            match=[{"eq": {"host": ["jd.com"]}}"]
            interval="2m"
            groupBy=["http_code"]
        (4)查询lbha,404状态码访问最多的host和url
            bizName="lbha"
            resource=["count"]
            timeRange={"start": "2025-11-05 10:00:00", "end": "2025-11-05 10:06:00"}
            match=[{"eq": {"http_code": ["404"]}}"]
            interval="2m"
            groupBy=["host","url"]
        (4)查询服务器'lf-pub-ha1-39.lf.jd.local',QPS,按照host、url分组计数
            bizName="lbha"
            resource=["count"]
            timeRange={"start": "2025-11-05 10:00:00", "end": "2025-11-05 10:06:00"}
            match=[{"eq": {"hostname": ["lf-pub-ha1-39.lf.jd.local"]}}"]
            interval="2m"
            groupBy=["host","url"]
    Returns:
        dict: 日志查询结果
    """
    
    params = {
        "size":15,
        "bizName": bizName,
        "resource": resource,
        "timeRange": timeRange,
        "match": match,
        "interval": interval,
        "algorithm": {
            "algorithmName": "group",
            "groupBy": groupBy,
            "size":10
    }
    }
    
    headers = get_np_auth_headers(CONFIG_deeplog_ck['appCode'], CONFIG_deeplog_ck['token'])
    url = CONFIG_deeplog_ck['api_url']
    
    try:
        response = requests.post(url, headers=headers, json=params, timeout=30)
        print(f"响应状态码: {response.status_code}")
        raw_data = response.json()
        if raw_data["code"]==0:
            return {
                "info":"接口调用成功，并返回了结果",
                "result":raw_data
            }
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
    
    
#  1. 从FastMCP实例中获取底层的FastAPI/ASGI应用,对于sse传输，使用sse_app()
app = mcp.sse_app()