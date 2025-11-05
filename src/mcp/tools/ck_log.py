from fastmcp import FastMCP
import hashlib
import requests
import time
import json
from typing import List, Dict, Optional, Union
from datetime import datetime
#sample：
#1、查询 erp.jd.com 在1小时内的访问量
#2、查询VIP 106.xx.xx.xx 的带宽消耗
#3、多指标对比分析：同时查看lbha的访问量和带宽
# 创建MCP服务器实例
mcp = FastMCP("LB Traffic Analytics Service", port=10025)

# === 配置参数 ===
DEFAULT_CONFIG = {
    'appCode': 'JC_PIDLB',
    'token': '9b78f9ab773774f5b2c4b627ff007152',
    'api_base_url': 'http://api-np.jd.local'
}

# 支持的资源类型和描述
RESOURCE_TYPES = {
    'count': '访问量计数',
    'bin': '请求带宽',
    'bout': '响应带宽',
    'upstream_bytes_sent': '主机发送数据包',
    'upstream_bytes_received': '主机接收数据包'
}

# 支持的业务数据源
BIZ_TYPES = {
    'lbha': '负载均衡高可用数据',
    'nginx': 'Nginx数据',
    'nginx4': 'Nginx4数据'
}

# 支持的算法类型
ALGORITHM_TYPES = {
    'sum': '求和',
    'avg': '平均值',
    'max': '最大值',
    'min': '最小值'
}

def generate_signature(token: str, timestamp: str) -> str:
    """生成请求签名"""
    timeStr = time.strftime("%H%M%Y%m%d", time.localtime(int(timestamp)))
    sign_str = f"#{token}NP{timeStr}"
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

def build_headers(appCode: str, timestamp: str, sign: str) -> dict:
    """构造请求头"""
    return {
        "Content-Type": "application/json",
        "appCode": appCode,
        "time": timestamp,
        "sign": sign
    }

def convert_to_timestamp(time_str: str) -> int:
    """将时间字符串转换为毫秒时间戳"""
    try:
        if ' ' in time_str:
            # 格式: '2024-01-01 00:00:00'
            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        else:
            # 格式: '2024-01-01'
            dt = datetime.strptime(time_str, '%Y-%m-%d')
        return int(dt.timestamp() * 1000)
    except ValueError as e:
        raise ValueError(f"时间格式错误: {time_str}，请使用 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD' 格式")

@mcp.tool()
def query_traffic_stats(
    resource: str,
    bizName: str,
    start_time: str,
    end_time: str,
    interval: str = "1m",
    hosts: List[str] = None,
    vips: List[str] = None,
    isp: List[str] = None,
    algorithm: str = "sum",
    appCode: str = None,
    token: str = None
) -> dict:
    """
    查询负载均衡流量统计数据（访问量、带宽等）
    
    适用场景：
    - 监控域名或VIP的访问量趋势
    - 分析网络带宽使用情况
    - 排查流量异常问题
    - 生成流量统计报告
    
    Args:
        resource: 资源类型，可选值：
                 'count' - 访问量计数
                 'bin' - 请求带宽  
                 'bout' - 响应带宽
                 'upstream_bytes_sent' - 主机发送数据包
                 'upstream_bytes_received' - 主机接收数据包
        bizName: 数据源类型，可选值：'lbha', 'nginx', 'nginx4'
        start_time: 开始时间，格式：'2024-01-01 00:00:00' 或 '2024-01-01'
        end_time: 结束时间，格式：'2024-01-01 23:59:59' 或 '2024-01-02'
        interval: 时间粒度，可选值：'1s', '10s', '1m', '5m', '1h'等
        hosts: 域名列表，例如：['erp.jd.com', 'www.jd.com']
        vips: VIP地址列表，例如：['106.39.164.213', '106.39.164.214']
        isp: 运营商列表，例如：['ct', 'cm', 'cu']
        algorithm: 聚合算法，默认'sum'，可选：'sum', 'avg', 'max', 'min'
        appCode: 应用代码，如果不提供，使用系统默认值
        token: 认证token，如果不提供，使用系统默认值
        
    Returns:
        返回包含流量统计数据的字典，包括：
        - success: 请求是否成功
        - data: 时间序列数据点列表
        - summary: 数据摘要信息
        - timestamp: 请求时间戳
        
    示例调用：
    >>> query_traffic_stats('count', 'lbha', '2024-01-01 00:00:00', '2024-01-01 01:00:00', hosts=['erp.jd.com'])
    >>> query_traffic_stats('bin', 'nginx', '2024-01-01', '2024-01-02', vips=['106.39.164.213'])
    """
    print(f"📊 查询流量统计: resource={resource}, bizName={bizName}")
    print(f"📝 时间范围: {start_time} 到 {end_time}, 粒度: {interval}")
    
    try:
        # 验证参数
        if resource not in RESOURCE_TYPES:
            return {
                "success": False,
                "error": f"不支持的resource类型: {resource}，可选值: {list(RESOURCE_TYPES.keys())}"
            }
            
        if bizName not in BIZ_TYPES:
            return {
                "success": False,
                "error": f"不支持的bizName类型: {bizName}，可选值: {list(BIZ_TYPES.keys())}"
            }
            
        if algorithm not in ALGORITHM_TYPES:
            return {
                "success": False,
                "error": f"不支持的algorithm类型: {algorithm}，可选值: {list(ALGORITHM_TYPES.keys())}"
            }
        
        # 使用传入参数或默认配置
        config = DEFAULT_CONFIG.copy()
        if appCode:
            config['appCode'] = appCode
        if token:
            config['token'] = token
        
        # 生成时间戳和签名
        timestamp = str(int(time.time()))
        sign = generate_signature(config['token'], timestamp)
        
        # 构造请求头
        headers = build_headers(config['appCode'], timestamp, sign)
        
        # 转换时间格式
        start_ts = convert_to_timestamp(start_time)
        end_ts = convert_to_timestamp(end_time)
        
        # 构造请求体
        post_data = {
            "resource": resource,
            "bizName": bizName,
            "timeRange": {
                "start": start_ts,
                "end": end_ts
            },
            "interval": interval,
            "algorithm": {
                "algorithmName": algorithm
            }
        }
        
        # 添加匹配条件
        match_conditions = []
        if hosts:
            match_conditions.append({"eq": {"host": hosts}})
        if vips:
            match_conditions.append({"eq": {"vip": vips}})
        if isp:
            match_conditions.append({"eq": {"isp": isp}})
            
        if match_conditions:
            post_data["match"] = match_conditions
        
        # 完整的API URL
        api_url = f"{config['api_base_url']}/v1/search"
        
        # 执行POST请求
        response = requests.post(api_url, headers=headers, json=post_data)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('code') == 0:
                data_points = result.get('response', [])
                
                # 计算统计摘要
                total_value = 0
                data_count = 0
                for point in data_points:
                    if isinstance(point.get('value'), (int, float)):
                        total_value += point['value']
                        data_count += 1
                    elif isinstance(point.get('value'), list):
                        # 多字段情况
                        for item in point['value']:
                            if isinstance(item.get('value'), (int, float)):
                                total_value += item['value']
                                data_count += 1
                
                return {
                    "success": True,
                    "data": {
                        "data_points": data_points,
                        "summary": {
                            "total_data_points": len(data_points),
                            "total_value": total_value,
                            "average_value": total_value / data_count if data_count > 0 else 0,
                            "time_range": f"{start_time} 到 {end_time}",
                            "resource_type": RESOURCE_TYPES[resource],
                            "data_source": BIZ_TYPES[bizName]
                        }
                    },
                    "timestamp": timestamp,
                    "query_params": {
                        "resource": resource,
                        "bizName": bizName,
                        "time_range": f"{start_time} - {end_time}",
                        "interval": interval
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"API返回错误: {result.get('message', '未知错误')}",
                    "code": result.get('code'),
                    "details": result
                }
        else:
            return {
                "success": False,
                "error": f"请求失败，状态码: {response.status_code}",
                "details": response.text
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"执行异常: {str(e)}"
        }

@mcp.tool()
def query_multiple_resources(
    resources: List[str],
    bizName: str,
    start_time: str,
    end_time: str,
    interval: str = "1m",
    hosts: List[str] = None,
    vips: List[str] = None,
    isp: List[str] = None,
    algorithm: str = "sum",
    appCode: str = None,
    token: str = None
) -> dict:
    """
    同时查询多个资源的流量统计数据
    
    适用场景：
    - 需要同时获取访问量、带宽等多个指标
    - 对比分析不同资源类型的数据
    - 生成综合流量报告
    
    Args:
        resources: 资源类型列表，例如：['count', 'bin', 'bout']
        bizName: 数据源类型，可选值：'lbha', 'nginx', 'nginx4'
        start_time: 开始时间，格式：'2024-01-01 00:00:00' 或 '2024-01-01'
        end_time: 结束时间，格式：'2024-01-01 23:59:59' 或 '2024-01-02'
        interval: 时间粒度，可选值：'1s', '10s', '1m', '5m', '1h'等
        hosts: 域名列表
        vips: VIP地址列表
        isp: 运营商列表
        algorithm: 聚合算法，默认'sum'
        appCode: 应用代码
        token: 认证token
        
    Returns:
        返回包含多个资源统计数据的字典
        
    示例调用：
    >>> query_multiple_resources(['count', 'bin'], 'lbha', '2024-01-01', '2024-01-02')
    """
    print(f"📈 查询多资源统计: resources={resources}, bizName={bizName}")
    
    try:
        # 验证资源类型
        for resource in resources:
            if resource not in RESOURCE_TYPES:
                return {
                    "success": False,
                    "error": f"不支持的resource类型: {resource}，可选值: {list(RESOURCE_TYPES.keys())}"
                }
        
        # 使用传入参数或默认配置
        config = DEFAULT_CONFIG.copy()
        if appCode:
            config['appCode'] = appCode
        if token:
            config['token'] = token
        
        # 生成时间戳和签名
        timestamp = str(int(time.time()))
        sign = generate_signature(config['token'], timestamp)
        
        # 构造请求头
        headers = build_headers(config['appCode'], timestamp, sign)
        
        # 转换时间格式
        start_ts = convert_to_timestamp(start_time)
        end_ts = convert_to_timestamp(end_time)
        
        # 构造请求体（使用multiresource字段）
        post_data = {
            "multiresource": resources,
            "bizName": bizName,
            "timeRange": {
                "start": start_ts,
                "end": end_ts
            },
            "interval": interval,
            "algorithm": {
                "algorithmName": algorithm
            }
        }
        
        # 添加匹配条件
        match_conditions = []
        if hosts:
            match_conditions.append({"eq": {"host": hosts}})
        if vips:
            match_conditions.append({"eq": {"vip": vips}})
        if isp:
            match_conditions.append({"eq": {"isp": isp}})
            
        if match_conditions:
            post_data["match"] = match_conditions
        
        # 完整的API URL
        api_url = f"{config['api_base_url']}/v1/search"
        
        # 执行POST请求
        response = requests.post(api_url, headers=headers, json=post_data)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('code') == 0:
                data_points = result.get('response', [])
                
                # 按资源类型汇总数据
                resource_summary = {}
                for resource in resources:
                    resource_summary[resource] = {
                        'name': RESOURCE_TYPES[resource],
                        'total_value': 0,
                        'data_points': 0
                    }
                
                # 计算每个资源的总值
                for point in data_points:
                    if isinstance(point.get('value'), list):
                        for item in point['value']:
                            resource_key = item.get('key')
                            value = item.get('value', 0)
                            if resource_key in resource_summary and isinstance(value, (int, float)):
                                resource_summary[resource_key]['total_value'] += value
                                resource_summary[resource_key]['data_points'] += 1
                
                return {
                    "success": True,
                    "data": {
                        "data_points": data_points,
                        "resource_summary": resource_summary,
                        "summary": {
                            "total_data_points": len(data_points),
                            "resources_count": len(resources),
                            "time_range": f"{start_time} 到 {end_time}",
                            "data_source": BIZ_TYPES[bizName]
                        }
                    },
                    "timestamp": timestamp
                }
            else:
                return {
                    "success": False,
                    "error": f"API返回错误: {result.get('message', '未知错误')}",
                    "code": result.get('code'),
                    "details": result
                }
        else:
            return {
                "success": False,
                "error": f"请求失败，状态码: {response.status_code}",
                "details": response.text
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"执行异常: {str(e)}"
        }

@mcp.tool()
def get_supported_config() -> dict:
    """
    获取支持的配置选项和参数说明
    
    Returns:
        返回包含所有支持的资源类型、数据源、算法等的字典
    """
    return {
        "success": True,
        "data": {
            "resource_types": RESOURCE_TYPES,
            "biz_types": BIZ_TYPES,
            "algorithm_types": ALGORITHM_TYPES,
            "time_intervals": ["1s", "10s", "30s", "1m", "5m", "10m", "1h"],
            "common_isp": ["ct", "cm", "cu", "other"],
            "note": "时间格式支持: 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'"
        }
    }

if __name__ == "__main__":
    print("🚀 启动LB流量分析 MCP 服务...")
    print("📡 传输方式: SSE")
    print(f"🔗 服务端口: 10026")
    print("📊 支持的功能:")
    print("  - 单资源流量统计查询")
    print("  - 多资源同时查询")
    print("  - 访问量、带宽、数据包统计")
    print("  - 域名、VIP、运营商条件过滤")
    
    # 使用SSE传输方式启动服务器
    mcp.run(transport="sse")