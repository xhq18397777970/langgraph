from fastmcp import FastMCP
import hashlib
import requests
import time
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

# 创建MCP服务器实例
mcp = FastMCP("LBHA Traffic Statistics Service")

# === 配置参数 ===
DEFAULT_CONFIG = {
    'appCode': 'JC_PIDLB',
    'token': '9b78f9ab773774f5b2c4b627ff007152',
    'api_url': 'http://deeplog-lb-api.jd.com/',
}

def get_np_auth_headers(app_code: str, token: str) -> dict:
    """
    生成NP接口鉴权header
    
    Args:
        app_code: 应用代码
        token: 认证token
        
    Returns:
        包含认证信息的请求头字典
    """
    now = datetime.now()
    time_str = now.strftime("%H%M%Y%m%d")
    timestamp = str(int(time.time() * 1000))  # 毫秒级时间戳
    
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

def format_response_data(raw_data: dict) -> dict:
    """
    格式化接口返回的数据，将时间戳转为可读时间
    
    Args:
        raw_data: 原始响应数据
        
    Returns:
        格式化后的数据，包含可读时间格式
    """
    if raw_data.get("code") != 0:
        return raw_data
        
    formatted_response = []
    for item in raw_data.get("response", []):
        timestamp_ms = item.get("time")
        
        # 将时间戳转为可读时间
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

@mcp.tool()
def query_lbha_traffic(
    bizName: str = "lbha",
    multiresource: List[str] = None,
    resource: str = None,
    timeRange: Dict[str, str] = None,
    start: str = None,
    end: str = None,
    interval: str = "10s",
    match: List[Dict] = None,
    algorithm: Dict[str, str] = None,
    app_code: str = None,
    token: str = None
) -> dict:
    """
    查询负载均衡流量统计数据，支持灵活的过滤条件和多维度分析
    
    适用场景：
    - 监控网站/服务的访问量(QPS)、请求带宽、响应带宽
    - 分析不同域名、URL、服务器、地域、运营商的流量分布
    - 排查流量异常或性能问题
    - 生成流量统计报告和趋势分析
    
    参数说明：
    bizName: 业务标识，必填
        - "lbha": LBHA数据源
        - "nginx": Nginx数据源
    
    multiresource: 多资源类型查询（与resource二选一）
        - ["count"]: 访问量/QPS计数
        - ["bin"]: 请求带宽（流入流量）
        - ["bout"]: 响应带宽（流出流量）
        - ["count", "bin", "bout"]: 同时查询多个指标
    
    resource: 单资源类型查询（与multiresource二选一）
        - "count": 访问量/QPS
        - "bin": 请求带宽
        - "bout": 响应带宽
    
    timeRange: 时间范围对象（与start/end参数二选一）
        {
            "start": "2025-11-05 10:00:00",
            "end": "2025-11-05 10:05:00"
        }
    
    start: 开始时间（格式：YYYY-MM-DD HH:MM:SS）
    end: 结束时间（格式：YYYY-MM-DD HH:MM:SS）
    
    interval: 时序间隔粒度
        - "1s": 1秒粒度（适用于短时间范围）
        - "10s": 10秒粒度
        - "5m": 5分钟粒度  
        - "1h": 1小时粒度（适用于长时间范围）
        - "": 空字符串表示取时间段的总体聚合值
    
    match: 查询过滤条件数组，支持复杂的AND/OR逻辑
        数组间关系为 OR，数组内关系为 AND
        
        示例1：单条件过滤
        [
            {
                "eq": {
                    "host": ["erp.jd.com"],
                    "protocol": ["HTTP"]
                }
            }
        ]
        
        示例2：多条件OR关系
        [
            {
                "eq": {
                    "host": ["erp.jd.com"]
                }
            },
            {
                "eq": {
                    "host": ["re.jd.com"] 
                }
            }
        ]
        
        示例3：范围条件
        [
            {
                "eq": {
                    "host": ["erp.jd.com"]
                },
                "gt": {
                    "bin": 3000
                },
                "lt": {
                    "bout": 10000
                }
            }
        ]
    
    algorithm: 聚合算法配置
        {
            "algorithmName": "sum"   # 求和聚合
        }
    
    支持的过滤字段：
    - host: 域名，例如 ["erp.jd.com", "re.jd.com"]
    - url: URL路径，例如 ["/favicon.ico", "/api/v1/users"]
    - vip: 服务器VIP，例如 ["172.28.15.52"]
    - lb-node-name: 负载均衡集群，例如 ["yfb001"]
    - protocol: 协议名称，例如 ["HTTP", "HTTPS"]
    - srv-ip: 业务服务器IP，例如 ["172.28.15.52"]
    - isp: 运营商
        - "CMCC": 中国移动
        - "CUCC": 中国联通
        - "CTCC": 中国电信
    - area: 地域，例如 ["BeiJing", "ShangHai"]
    - bin: 请求流量（数值范围条件）
    - bout: 响应流量（数值范围条件）
    
    范围条件运算符：
    - "eq": 等于
    - "gt": 大于
    - "gte": 大于等于  
    - "lt": 小于
    - "lte": 小于等于
    
    返回结果：
    {
        "code": 0,      # 0表示成功，其他为错误码
        "message": "success",
        "data": [
            {
                "time": "2025-11-05 10:00:10",  # 格式化后的时间
                "value": [1234]                 # 对应的数值
            },
            ...
        ]
    }
    
    错误码说明：
    -1: 失败
    100: 非法操作
    101: Token参数缺失  
    102: 参数缺失
    103: 时间范围有问题
    
    示例调用：
    
    1. 查询单个域名访问量：
    >>> query_lbha_traffic(
    ...     multiresource=["count"],
    ...     timeRange={
    ...         "start": "2025-11-05 10:00:00",
    ...         "end": "2025-11-05 10:05:00"
    ...     },
    ...     match=[{
    ...         "eq": {
    ...             "host": ["erp.jd.com"]
    ...         }
    ...     }],
    ...     interval="10s"
    ... )
    
    2. 查询多个资源类型：
    >>> query_lbha_traffic(
    ...     multiresource=["count", "bin", "bout"],
    ...     start="2025-11-05 10:00:00",
    ...     end="2025-11-05 10:05:00", 
    ...     match=[{
    ...         "eq": {
    ...             "host": ["erp.jd.com"],
    ...             "area": ["BeiJing"]
    ...         }
    ...     }],
    ...     interval="20s"
    ... )
    
    3. 查询带宽超过阈值的数据：
    >>> query_lbha_traffic(
    ...     resource="bin",
    ...     start="2025-11-05 10:00:00",
    ...     end="2025-11-05 10:05:00",
    ...     match=[{
    ...         "eq": {
    ...             "host": ["re.jd.com"]
    ...         },
    ...         "gt": {
    ...             "bin": 5000
    ...         }
    ...     }]
    ... )
    
    4. 获取总体聚合值（无时间间隔）：
    >>> query_lbha_traffic(
    ...     resource="count", 
    ...     start="2025-11-05 10:00:00",
    ...     end="2025-11-05 11:00:00",
    ...     interval="",
    ...     match=[{
    ...         "eq": {
    ...             "host": ["erp.jd.com"]
    ...         }
    ...     }]
    ... )
    """
    print(f"📊 查询LBHA流量统计数据")
    print(f"📝 业务标识: {bizName}")
    print(f"📈 资源类型: {multiresource or resource}")
    
    try:
        # 构造请求参数
        params = {
            "lb":
            "bizName": bizName,
            "interval": interval,
            "algorithm":  {"algorithmName": "sum"}
        }
        
        # 处理资源类型
        if multiresource:
            params["multiresource"] = multiresource
        elif resource:
            params["resource"] = resource
        else:
            # 默认使用count
            params["resource"] = "count"
        
        # 处理时间范围
        if timeRange:
            params["timeRange"] = timeRange
        elif start and end:
            params["timeRange"] = {
                "start": start,
                "end": end
            }
        else:
            return {
                "code": 102,
                "message": "参数缺失：必须提供timeRange或start/end时间参数",
                "success": False
            }
        
        # 处理过滤条件
        if match:
            params["match"] = match
        
        print(f"🔍 查询参数: {json.dumps(params, indent=2, ensure_ascii=False)}")
        
        # 生成认证头
        headers = get_np_auth_headers(config['appCode'], config['token'])
        url = f"{config['api_url']}v1/search"
        
        # 执行请求
        response = requests.post(url, headers=headers, json=params, timeout=30)
        print(f"📡 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            raw_data = response.json()
            formatted_data = format_response_data(raw_data)
            return formatted_data
        else:
            return {
                "code": -1,
                "message": f"请求失败，状态码: {response.status_code}",
                "response_text": response.text,
                "success": False
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "code": -1,
            "message": f"请求失败: {str(e)}",
            "error_type": type(e).__name__,
            "success": False
        }
    except Exception as e:
        return {
            "code": -1,
            "message": f"执行异常: {str(e)}",
            "success": False
        }

if __name__ == "__main__":
    print("🚀 启动LBHA流量统计 MCP 服务...")
    print("📡 传输方式: SSE")
    print("🔗 服务端口: 10025")
    print("📊 核心工具: query_lbha_traffic")
    print("💡 功能特点:")
    print("   - 支持多资源类型同时查询")
    print("   - 灵活的过滤条件配置") 
    print("   - 多种时间粒度选择")
    print("   - 复杂的AND/OR逻辑组合")
    
    # 使用SSE传输方式启动服务器
    mcp.run(transport="sse")