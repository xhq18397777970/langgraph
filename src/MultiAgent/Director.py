from operator import add
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import START, END
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage,AIMessage
from langgraph.checkpoint.memory import MemorySaver
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.model_config import get_deepseek_model
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
from langgraph.prebuilt  import create_react_agent
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from typing import Any, Dict
# 定义日志函数
def get_stream_writer():
    """简单的流式输出写入器"""
    def writer(data):
        if isinstance(data, dict):
            print(f"📊 {data}")
        else:
            print(f"🔔 {data}")
    return writer

def create_sync_tool_wrapper(async_tool):
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

def convert_async_tools_to_sync(async_tools):
    """将异步工具列表转换为同步工具列表"""
    sync_tools = []
    for tool in async_tools:
        if hasattr(tool, 'coroutine') and tool.coroutine is not None:
            # 这是一个异步工具，需要包装
            sync_tool = create_sync_tool_wrapper(tool)
            sync_tools.append(sync_tool)
            print(f"🔍 [DEBUG] 转换异步工具: {tool.name} -> 同步工具")
        else:
            # 这已经是同步工具，直接使用
            sync_tools.append(tool)
            print(f"🔍 [DEBUG] 保持同步工具: {tool.name}")
    
    return sync_tools

load_dotenv()

# 修正：nodes 应该与模型返回的类型一致
nodes = ["domain", "joke", "chinese", "other"]
llm = get_deepseek_model()

#这里的 add 操作符意味着：
#新返回的 messages 会追加到现有的消息列表中
#必须返回标准的消息对象（BaseMessage 对象，如AIMessage、HumanMessage），不能是纯字符串
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add]
    type: str

def supervisor_node(state: State):
    writer = get_stream_writer()
    writer({">>> supervisor_node"})
    
    prompt = """
        你是一个专业的客服助手，负责对用户的问题进行分类，并将任务分给其他Agent执行。
        如果用户的问题是和域名相关的、与日志查询（QPS、带宽历史数据），那就返回domain。
        如果用户的问题是希望讲一个笑话，那就返回joke。
        如果用户的问题是希望进行中文的句子分析，那就返回chinese。
        如果是其他的问题，返回other。
        注意：只返回上述四个单词中的一个，不要返回任何其他的内容。
        """
    
    # 修正：正确处理消息内容
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_content = state["messages"][-1].content
    else:
        user_content = str(state["messages"])
    
    print(f"用户问题: {user_content}")
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content}
    ]
    
    # 如果已有type属性且不是第一次执行，使用大模型判断是否完成
    if "type" in state and state["type"] in ["domain", "joke", "chinese", "other"]:
        # 使用大模型判断任务是否完成
        completion_prompt = f"""
        请判断当前对话是否已经完成用户的任务需求。
        
        用户原始请求：
        {state['messages'][0].content if state['messages'] else '无'}
        
        当前对话历史：
        {[msg.content for msg in state['messages']]}
        
        当前任务类型：{state['type']}
        
        请仔细检查用户原始请求中是否包含多个任务要求，然后回答"完成"或"未完成"：
        - 如果用户的所有任务要求都已经满足，回答"完成"
        - 如果用户还有未完成的任务要求，回答"未完成"
        
        特别注意：用户可能在一个请求中要求多个任务。
        """
        
        completion_messages = [
            {"role": "system", "content": completion_prompt}
        ]
        
        completion_response = llm.invoke(completion_messages)
        completion_result = completion_response.content.strip()
        
        writer({"supervisor_step": f"任务完成状态判断: {completion_result}"})
        
        if "完成" in completion_result:
            writer({"supervisor_step": f"任务已完成，流程结束"})
            return {"type": END}
        else:
            # 判断下一步执行哪个节点
            next_step_prompt = f"""
            根据用户原始请求和当前进展，决定下一步应该执行哪个处理节点。
            
            用户原始请求：
            {state['messages'][0].content if state['messages'] else '无'}
            
            当前对话历史：
            {[msg.content for msg in state['messages']]}
            
            当前已完成的任务：{state['type']}
            可用节点：domain, joke, chinese, other
            
            请分析用户还有哪些任务没有完成，选择最合适的下一个节点。
            只返回节点名称（domain/joke/chinese/other）
            """
            
            next_step_messages = [
                {"role": "system", "content": next_step_prompt}
            ]
            
            next_step_response = llm.invoke(next_step_messages)
            next_node = next_step_response.content.strip().lower()
            
            # 打印信息调试
            writer({"supervisor_step": f"大模型建议的下一个节点: {next_node}"})
            
            # 确保返回的节点在预定义节点中
            if next_node not in nodes:
                # 如果建议的节点不在预定义节点中，重新分析用户原始请求
                original_request = state['messages'][0].content if state['messages'] else user_content
                writer({"supervisor_step": f"重新分析原始请求: {original_request}"})
                
                # 重新分类原始请求
                reclassify_messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": original_request}
                ]
                reclassify_response = llm.invoke(reclassify_messages)
                next_node = reclassify_response.content.strip().lower()
                writer({"supervisor_step": f"重新分类结果: {next_node}"})
            
            # 最终验证节点有效性
            if next_node not in nodes:
                next_node = "other"  # 默认使用 other
            
            writer({"supervisor_step": f"继续执行: {next_node}"})
            return {"type": next_node}  # 这里应该返回节点名称，不是 END
    
    # 首次执行，进行任务分类
    response = llm.invoke(messages)
    typeRes = response.content.strip().lower()
    writer({"supervisor_step": f"问题分类结果: {typeRes}"})
    
    print(f"模型返回类型: '{typeRes}'")
    print(f"预定义节点: {nodes}")
    
    # 修正：检查类型是否在预定义节点中
    if typeRes in nodes:
        print(f"✅ 类型 '{typeRes}' 在预定义节点中")
        return {"type": typeRes}
    else:
        print(f"⚠️  类型 '{typeRes}' 不在预定义节点中，使用 'other'")
        return {"type": "other"}
def domain_node(state: State):
    print(">>> domain_node")
    writer = get_stream_writer()
    writer({"node": "domain_node"})
    
    # 修正：正确构建消息格式
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_input = state["messages"][-1].content
    else:
        user_input = str(state["messages"])
    
    system_prompt = """
        你是一个专业的域名、日志数据分析领域专家，根据提供的工具完成域名、日志数据检索和分析相关的功能。
        """
        
    prompts = [
        {"role": "system", "content":system_prompt},
        {"role":"user","content":user_input}
    ]
    
    try:
        #mcp客户端，用于连接mcp服务
        print("🔍 [DEBUG] 创建 MCP 客户端...")
        client = MultiServerMCPClient(
            {
                "domain-info-service": {
                    "url": "http://127.0.0.1:10025/sse",
                    "transport": "sse",
                }
            }
        )
        
        #langgraph整个图是同步的，需要将异步方法转为同步的实现
        print("🔍 [DEBUG] 获取 MCP 工具...")
        async_tools = asyncio.run(client.get_tools())
        
        # 添加诊断日志
        print(f"🔍 [DEBUG] 获取到 {len(async_tools)} 个异步工具")
        for i, tool in enumerate(async_tools):
            print(f"🔍 [DEBUG] 异步工具 {i}: {type(tool).__name__}")
            print(f"🔍 [DEBUG] 工具名称: {getattr(tool, 'name', 'Unknown')}")
            if hasattr(tool, 'coroutine'):
                print(f"🔍 [DEBUG] 工具有 coroutine 属性: {tool.coroutine}")
            if hasattr(tool, 'func'):
                print(f"🔍 [DEBUG] 工具 func 类型: {type(tool.func)}")
        
        # 将异步工具转换为同步工具
        print("🔍 [DEBUG] 转换异步工具为同步工具...")
        sync_tools = convert_async_tools_to_sync(async_tools)
        
        print(f"🔍 [DEBUG] 转换完成，得到 {len(sync_tools)} 个同步工具")
        for i, tool in enumerate(sync_tools):
            print(f"🔍 [DEBUG] 同步工具 {i}: {type(tool).__name__}")
            print(f"🔍 [DEBUG] 工具名称: {getattr(tool, 'name', 'Unknown')}")
            if hasattr(tool, 'func') and tool.func is not None:
                print(f"🔍 [DEBUG] 工具有有效的 func: {type(tool.func)}")
            else:
                print(f"🔍 [DEBUG] 工具 func 为空或无效")
        
        print("🔍 [DEBUG] 创建 React Agent...")
        agent = create_react_agent(
            model=llm,
            tools=sync_tools,
        )
        
        writer({"domain_step": "调用域名查询工具..."})
        
        print("🔍 [DEBUG] 调用 Agent...")
        # 修正：使用正确的输入格式
        response = agent.invoke({"messages":prompts})
        
        # 修正：正确提取响应内容
        if response and "messages" in response and response["messages"]:
            last_message = response["messages"][-1]
            if hasattr(last_message, 'content'):
                result_content = last_message.content
            else:
                result_content = str(last_message)
        else:
            result_content = "域名查询完成"
            
        writer({"domain_result": result_content})
        
        # 修正：返回正确的消息格式
        return {"messages": [AIMessage(content=result_content)], "type": "domain"}
        
    except Exception as e:
        print(f"🔍 [DEBUG] 异常详情: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"🔍 [DEBUG] 异常堆栈: {traceback.format_exc()}")
        writer({"error": f"域名查询失败: {e}"})
        error_msg = f"域名查询过程中出现错误: {str(e)}"
        return {"messages": [AIMessage(content=error_msg)], "type": "domain"}

def joke_node(state: State):

    writer({">>> joke_node"})
    
    # 更详细的提示词
    system_prompt = """你是一个专业的喜剧编剧和笑话生成器。请根据用户的要求创作一个精彩的笑话。
    
    创作指南：
    1. 结构完整：有铺垫、转折和笑点
    2. 语言生动：使用形象的语言和适当的夸张
    3. 贴近生活：从日常生活中寻找灵感
    4. 积极向上：避免低俗、歧视性内容
    5. 适度创新：可以结合时事热点或流行文化
    
    如果用户指定了笑话类型（如冷笑话、相声段子、谐音梗等），请按照要求创作。
    如果用户提到了具体的喜剧演员风格（如郭德纲、周立波等），请模仿相应的风格。
    特别注意：除了生成笑话，不做其他任何推理任务！输入是要求，输出是笑话！
    """
    
    # 获取用户输入
    #state["messages"] 存储了整个对话历史
    #state["messages"][-1] 获取最后一条消息（通常是用户的输入）
    #通过 .content 属性提取消息的文本内容
    
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_input = state["messages"][-1].content
        user_prompt = f"用户请求：{user_input}\n\n请根据以上要求创作一个合适的笑话。"
    else:
        user_prompt = "请创作一个有趣的笑话，主题不限。"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    writer({"joke_generation": "大模型正在创作笑话..."})
    
    try:
        response = llm.invoke(messages)
        joke_content = response.content.strip()
        
        # 确保笑话内容不为空
        if not joke_content:
            joke_content = "为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 == Dec 25！"
            
        writer({"generated_joke": joke_content})
        
    except Exception as e:
        writer({"error": f"笑话生成失败: {e}"})
        # 备用笑话
        joke_content = "听说有个程序员去钓鱼，钓了一天都没钓到。后来他发现，原来他一直在调的是 debug。。。"
    
    #拿到大模型思考结果后，更新state状态
    #必须要HumanMessage方式返回，不可以直接返回字符串
    #langchain中有不同消息类型： 
    return {"messages": [AIMessage(content=joke_content)], "type": "joke"}

def chinese_node(state: State):
    print(">>> analyse_node")
    writer = get_stream_writer()
    writer({"node": "chinese_node"})
    # 实际应该调用对联生成API
    
    system_prompt="""
    你是一个专业的语言大师，用于分析中文句子成分，负责中文的语义分析，输出所有的名词、动词、形容词、副词。
    特别注意：除此之外，不做任何其他的推理工作！
    """
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_input = state["messages"][-1].content
        user_prompt = f"用户请求：{user_input}\n\n请根据以上要求分析中文句子成分。"
    else:
        user_prompt = "请创作一个有趣的对联，主题不限。"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    writer({"chinese_generation": "大模型正在分析句子语意"})
    
    try:
        response = llm.invoke(messages)
        chinese_content = response.content.strip()
        
        # 确保对联内容不为空
        if not chinese_content:
            chinese_content = "默认对联"
            
        writer({"generated_joke": chinese_content})
        
    except Exception as e:
        writer({"error": f"对联生成失败: {e}"})
        # 备用笑话
        chinese_content = "准备好的对联"
    
    #拿到大模型思考结果后，更新state状态
    #必须要HumanMessage方式返回，不可以直接返回字符串
    #langchain中有不同消息类型：
    return {"messages": [AIMessage(content=chinese_content)], "type": "chinese"}

def deeplog_node(state:State):
    print(">>> analyse_node")
    writer = get_stream_writer()
    writer({"node": "deeplog_node"})
    # 实际应该调用对联生成API
    
    system_prompt="""
    你是一个专业的语言大师，用于分析中文句子成分，负责中文的语义分析，输出所有的名词、动词、形容词、副词。
    特别注意：除此之外，不做任何其他的推理工作！
    """
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_input = state["messages"][-1].content
        user_prompt = f"用户请求：{user_input}\n\n请根据以上要求分析中文句子成分。"
    else:
        user_prompt = "请创作一个有趣的对联，主题不限。"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    writer({"deeplog_generation": "大模型正在分析句子语意"})
    
    try:
        response = llm.invoke(messages)
        deeplog_content = response.content.strip()
        
        # 确保对联内容不为空
        if not deeplog_content:
            deeplog_content = "默认对联"
            
        writer({"generated_joke": deeplog_content})
        
    except Exception as e:
        writer({"error": f"对联生成失败: {e}"})
        # 备用笑话
        chinese_content = "准备好的对联"
    
    #拿到大模型思考结果后，更新state状态
    #必须要HumanMessage方式返回，不可以直接返回字符串
    #langchain中有不同消息类型：
    return {"messages": [AIMessage(content=chinese_content)], "type": "chinese"}
def other_node(state: State):
    print(">>> other_node")
    writer = get_stream_writer()
    writer({"node": "other_node"})
    other_response = "我主要擅长旅游规划、讲笑话和对对联，您的问题暂时无法回答。"
    return {"messages": [HumanMessage(content=other_response)], "type": "other"}

def routing_func(state: State):
    print(f"路由函数接收到类型: {state['type']}")
    
    if state["type"] == "domain":
        return "domain_node"
    elif state["type"] == "joke":
        return "joke_node"
    elif state["type"] == "chinese":
        return "chinese_node"
    elif state["type"] == "other":
        return "other_node"
    elif state["type"] == END:
        return END
    else:
        print(f"❌ 未知类型: {state['type']}，路由到 other_node")
        return "other_node"

# 构建图
builder = StateGraph(State)
builder.add_node("supervisor_node", supervisor_node)
builder.add_node("domain_node", domain_node)
builder.add_node("joke_node", joke_node)
builder.add_node("chinese_node", chinese_node)
builder.add_node("other_node", other_node)

# 设置流程
builder.add_edge(START, "supervisor_node")

# 条件路由，langgraph执行引擎，如果返回值为joke_node则下一个执行任务的是joke_node
builder.add_conditional_edges(
    "supervisor_node",
    routing_func,
    {
        "domain_node": "domain_node",
        "joke_node": "joke_node", 
        "chinese_node": "chinese_node",
        "other_node": "other_node",
        END: END
    }
)

# 各个处理节点完成后回到 supervisor_node 进行结果确认
builder.add_edge("domain_node", "supervisor_node")
builder.add_edge("joke_node", "supervisor_node") 
builder.add_edge("chinese_node", "supervisor_node")
builder.add_edge("other_node", "supervisor_node")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

