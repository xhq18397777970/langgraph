
from fastmcp import FastMCP
import hashlib
import requests
import time
import json
from langchain_core.tools import tool
# 创建MCP服务器实例
mcp = FastMCP("Domain Info Service", port=10025)

# === 配置参数 ===
DEFAULT_CONFIG = {
    'appCode': 'xhq',
    'erp': 'xiehanqi.jackson',
    'businessId': '6abe3998080d92d648d7ad461bd67f38',
    'api_url': 'http://api-np.jd.local/V1/Dns/domainsInfo'
}
#也可以使用@tool的方式声明工具，为函数起别名，LLM通过名字再找到函数，且工具调用结果直接返回，大语言模型不做思考总结 
# @tool('devide_tool',return_direct=True)
def generate_signature(erp: str, businessId: str, timestamp: str) -> str:
    """生成请求签名"""
    timeStr = time.strftime("%H%M%Y%m%d", time.localtime(int(timestamp)))
    sign_str = f"{erp}#{businessId}NP{timeStr}"
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

def build_headers(appCode: str, erp: str, timestamp: str, sign: str) -> dict:
    """构造请求头"""
    return {
        "Content-type": "application/json",
        "appCode": appCode,
        "erp": erp,
        "timestamp": timestamp,
        "sign": sign
    }

@mcp.tool()
def query_domains_info(domains: list, erp: str = None, businessId: str = None) -> dict:
    """
    查询一个或多个域名的完整详细信息，包括DNS记录、负责人、项目信息等。
    
    适用场景：
    - 当用户询问任何域名相关的信息时（如IP地址、负责人、状态等）
    - 需要验证域名是否存在或状态是否正常时
    - 需要了解域名的技术配置和管理信息时
    
    Args:
        domains: 要查询的域名列表，支持同时查询多个域名。例如：['jd.com', 'graycluster-bind-check.jd.local']
        erp: 操作者的ERP账号，用于权限验证和审计日志。如果不提供，使用系统默认值。
        businessId: 业务标识符，用于区分不同的业务系统。如果不提供，使用系统默认值。
        
    Returns:
        返回包含域名详细信息的JSON格式字符串，包括：
        - 域名基本状态（是否解析、网络类型等）
        - 负责人信息（姓名、邮箱、ERP等）
        - 项目信息（所属项目、环境等）
        - 技术配置（DNS记录、服务类型等）
        
    示例调用：
    >>> query_domains_info(['jd.com'])
    >>> query_domains_info(['example.com', 'test.com'], erp='your_erp')
    """
    print(f"🚀 函数被调用: query_domains_info")
    print(f"📝 参数: domains={domains}, erp={erp}, businessId={businessId}")
    try:
        # 使用传入参数或默认配置
        config = DEFAULT_CONFIG.copy()
        if erp:
            config['erp'] = erp
        if businessId:
            config['businessId'] = businessId
        
        # 生成时间戳和签名
        timestamp = str(int(time.time()))
        sign = generate_signature(config['erp'], config['businessId'], timestamp)
        # 构造请求头
        headers = build_headers(config['appCode'], config['erp'], timestamp, sign)
        # 构造请求体
        post_data = {"domains": domains}
        # 执行请求
        response = requests.post(config['api_url'], headers=headers, json=post_data)
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json(),
                "timestamp": timestamp,
                "domains_count": len(domains)
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
def check_domain_status(domain: str, erp: str = None, businessId: str = None) -> dict:
    """
    检测域名状态，判断域名是否空闲可用。
    
    适用场景：
    - 检查域名是否可以被注册或使用
    - 验证域名当前的使用状态
    - 判断域名是否已被占用
    
    Args:
        domain: 要检查的域名，例如 'example.jd.com'
        erp: 操作者的ERP账号，用于权限验证。如果不提供，使用系统默认值。
        businessId: 业务标识符，用于区分不同的业务系统。如果不提供，使用系统默认值。
        
    Returns:
        返回包含域名状态信息的字典，包括：
        - status: 域名状态码
          -1: 域名不存在（可以申请）
          1: DNS已解析域名（已被使用）
          2: 商家域名
          3: NP系统预留域名
        - msg: 状态描述信息
        - is_available: 域名是否可用（True/False）
        
    状态说明：
    - 状态码为 -1 表示域名空闲，可以申请使用
    - 其他状态码表示域名已被占用或保留
    
    示例调用：
    >>> check_domain_status('test.jd.com')
    >>> check_domain_status('new-domain.jd.local', erp='your_erp')
    """
    print(f"🔍 检查域名状态: {domain}")
    print(f"📝 参数: domain={domain}, erp={erp}, businessId={businessId}")
    
    try:
        # 使用传入参数或默认配置
        config = DEFAULT_CONFIG.copy()
        if erp:
            config['erp'] = erp
        if businessId:
            config['businessId'] = businessId
        
        # 生成时间戳和签名
        timestamp = str(int(time.time()))
        sign = generate_signature(config['erp'], config['businessId'], timestamp)
        
        # 构造请求头
        headers = build_headers(config['appCode'], config['erp'], timestamp, sign)
        
        # 构造请求URL（GET请求）
        api_url = "http://api-np.jd.local/V1/Dns/domainCheck"
        params = {"domain": domain}
        
        # 执行GET请求
        response = requests.get(api_url, headers=headers, params=params)
        
        if response.status_code == 200:
            result = response.json()
            
            # 解析状态信息
            status_code = result.get('data', {}).get('status', 0)
            status_msg = result.get('data', {}).get('msg', '未知状态')
            
            # 判断域名是否可用（状态码-1表示可用）
            is_available = (status_code == -1)
            
            return {
                "success": True,
                "data": {
                    "domain": domain,
                    "status": status_code,
                    "msg": status_msg,
                    "is_available": is_available,
                    "status_description": get_status_description(status_code)
                },
                "timestamp": timestamp
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

def get_status_description(status_code: int) -> str:
    """获取状态码的详细描述"""
    status_descriptions = {
        -1: "域名不存在，可以申请使用",
        1: "DNS已解析域名，已被使用",
        2: "商家域名",
        3: "NP系统预留域名",
        0: "未知状态"
    }
    return status_descriptions.get(status_code, "未知状态码")

if __name__ == "__main__":
    print("🚀 启动域名查询 MCP 服务...")
    print("📡 传输方式: SSE")
    print(f"🔗 服务端口: 10025")
    
    # 使用SSE传输方式启动服务器
    mcp.run(transport="sse")