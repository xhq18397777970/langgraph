"""
MCP客户端管理模块
提供统一的MCP客户端连接、工具管理和Agent创建功能
"""

import json
import os
import asyncio
from typing import Dict, List, Optional, Any
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent


class MCPClientManager:
    """MCP客户端管理器，负责统一管理MCP连接和Agent实例"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化MCP客户端管理器
        
        Args:
            config_path: 配置文件路径，默认为相对路径
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        self._clients: Dict[str, MultiServerMCPClient] = {}
        self._agents: Dict[str, Any] = {}  # 缓存Agent实例
        self._tools_cache: Dict[str, List[StructuredTool]] = {}  # 缓存工具
        
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, "..", "config", "mcp_config.json")
        
    def _load_config(self) -> Dict[str, Any]:
        """加载MCP配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"🔍 [DEBUG] 成功加载MCP配置: {self.config_path}")
                return config
        except FileNotFoundError:
            print(f"❌ [ERROR] 配置文件未找到: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            print(f"❌ [ERROR] 配置文件格式错误: {e}")
            raise
            
    def create_sync_tool_wrapper(self, async_tool):
        """创建同步工具包装器，将异步 MCP 工具转换为同步工具"""
        
        def sync_func(**kwargs):
            """同步包装函数，使用 asyncio.run 调用异步工具"""
            try:
                # 调用异步工具的 coroutine 函数
                result = asyncio.run(async_tool.coroutine(**kwargs))
                return result
            except Exception as e:
                print(f"🔍 [DEBUG] 同步包装器执行异常: {e}")
                raise e
        
        # 创建新的同步 StructuredTool
        sync_tool = StructuredTool.from_function(
            func=sync_func,
            name=async_tool.name,
            description=async_tool.description,
            args_schema=async_tool.args_schema,
            return_direct=getattr(async_tool, 'return_direct', False)
        )
        
        print(f"🔍 [DEBUG] 创建同步工具包装器: {async_tool.name}")
        return sync_tool

    def convert_async_tools_to_sync(self, async_tools):
        """将异步工具列表转换为同步工具列表"""
        sync_tools = []
        for tool in async_tools:
            if hasattr(tool, 'coroutine') and tool.coroutine is not None:
                # 这是一个异步工具，需要包装
                sync_tool = self.create_sync_tool_wrapper(tool)
                sync_tools.append(sync_tool)
                print(f"🔍 [DEBUG] 转换异步工具: {tool.name} -> 同步工具")
            else:
                # 这已经是同步工具，直接使用
                sync_tools.append(tool)
                print(f"🔍 [DEBUG] 保持同步工具: {tool.name}")
        
        return sync_tools
        
    def create_client(self, server_name: str) -> MultiServerMCPClient:
        """
        创建指定服务器的MCP客户端
        
        Args:
            server_name: 服务器名称（在配置文件中定义）
            
        Returns:
            MultiServerMCPClient实例
        """
        if server_name in self._clients:
            return self._clients[server_name]
            
        if server_name not in self.config["servers"]:
            raise ValueError(f"服务器配置未找到: {server_name}")
            
        server_config = self.config["servers"][server_name]
        
        print(f"🔍 [DEBUG] 创建 {server_name} MCP 客户端...")
        client = MultiServerMCPClient({
            server_name: {
                "url": server_config["url"],
                "transport": server_config["transport"],
            }
        })
        
        self._clients[server_name] = client
        return client
        
    def get_sync_tools(self, server_name: str) -> List[StructuredTool]:
        """
        获取指定服务器的同步工具列表
        
        Args:
            server_name: 服务器名称
            
        Returns:
            同步工具列表
        """
        # 检查缓存
        if server_name in self._tools_cache:
            print(f"🔍 [DEBUG] 使用缓存的 {server_name} 工具")
            return self._tools_cache[server_name]
            
        client = self.create_client(server_name)
        
        print(f"🔍 [DEBUG] 获取 {server_name} MCP 工具...")
        async_tools = asyncio.run(client.get_tools())
        sync_tools = self.convert_async_tools_to_sync(async_tools)
        
        # 缓存工具
        self._tools_cache[server_name] = sync_tools
        return sync_tools
        
    def create_agent(self, server_name: str, model, system_prompt: str = None) -> Any:
        """
        创建并缓存指定服务器的Agent
        
        Args:
            server_name: 服务器名称
            model: 语言模型实例
            system_prompt: 系统提示词
            
        Returns:
            创建的Agent实例
        """
        # 检查缓存
        if server_name in self._agents:
            print(f"🔍 [DEBUG] 使用缓存的 {server_name} Agent")
            return self._agents[server_name]
            
        sync_tools = self.get_sync_tools(server_name)
        
        print(f"🔍 [DEBUG] 创建 {server_name} React Agent...")
        agent = create_react_agent(
            model=model,
            tools=sync_tools,
        )
        
        # 缓存Agent
        self._agents[server_name] = agent
        return agent
        
    def get_cached_agent(self, server_name: str) -> Optional[Any]:
        """
        获取缓存的Agent实例
        
        Args:
            server_name: 服务器名称
            
        Returns:
            缓存的Agent实例，如果不存在返回None
        """
        return self._agents.get(server_name)
        
    def clear_cache(self, server_name: str = None):
        """
        清除缓存
        
        Args:
            server_name: 指定服务器名称，为None时清除所有缓存
        """
        if server_name:
            self._agents.pop(server_name, None)
            self._tools_cache.pop(server_name, None)
            self._clients.pop(server_name, None)
            print(f"🔍 [DEBUG] 清除 {server_name} 缓存")
        else:
            self._agents.clear()
            self._tools_cache.clear()
            self._clients.clear()
            print("🔍 [DEBUG] 清除所有缓存")
            
    def get_server_info(self) -> Dict[str, Any]:
        """获取所有服务器配置信息"""
        return self.config["servers"]
        
    def is_agent_cached(self, server_name: str) -> bool:
        """检查Agent是否已缓存"""
        return server_name in self._agents


# 全局单例实例
_mcp_manager: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    """获取全局MCP管理器单例"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPClientManager()
    return _mcp_manager


def initialize_agents(model):
    """
    初始化所有MCP Agents的兼容性函数
    保持与现有代码的向后兼容性
    
    Args:
        model: 语言模型实例
        
    Returns:
        bool: 初始化是否成功
    """
    try:
        manager = get_mcp_manager()
        
        print("🔍 [DEBUG] 初始化MCP Agents...")
        
        # 初始化domain agent
        manager.create_agent("domain-info-server", model)
        
        # 初始化deeplog agent  
        manager.create_agent("deeplog-ck-server", model)
        
        print("🔍 [DEBUG] MCP Agents 初始化完成")
        return True
        
    except Exception as e:
        print(f"🔍 [DEBUG] MCP Agents 初始化失败: {e}")
        return False


def get_domain_agent():
    """获取domain agent的兼容性函数"""
    manager = get_mcp_manager()
    return manager.get_cached_agent("domain-info-server")


def get_deeplog_agent():
    """获取deeplog agent的兼容性函数"""
    manager = get_mcp_manager()
    return manager.get_cached_agent("deeplog-ck-server")