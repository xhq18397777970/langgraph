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
# 导入新的MCP管理模块
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mcp'))
from client.mcp_client_manager import get_mcp_manager, initialize_agents, get_domain_agent, get_deeplog_agent
# 定义日志函数
def get_stream_writer():
    """简单的流式输出写入器"""
    def writer(data):
        if isinstance(data, dict):
            print(f"📊 {data}")
        else:
            print(f"🔔 {data}")
    return writer

load_dotenv()

# 修正：nodes 应该与模型返回的类型一致
nodes = ["domain", "other"]
llm = get_deepseek_model()

# 全局Agent缓存变量 - 保持向后兼容性
_domain_agent = None
_deeplog_agent = None
_agent_initialized = False
_initialization_error = None

# 兼容性函数 - 使用新的MCP管理模块
def initialize_agents():
    global _domain_agent, _deeplog_agent, _agent_initialized, _initialization_error
    
    if _agent_initialized:
        return True
    
    try:
        # 使用新的MCP管理模块初始化
        from client.mcp_client_manager import initialize_agents as mcp_initialize_agents
        success = mcp_initialize_agents(llm)
        if success:
            # 更新全局变量以保持向后兼容性
            _domain_agent = get_domain_agent()
            _deeplog_agent = get_deeplog_agent()
            _agent_initialized = True
            _initialization_error = None
        else:
            _agent_initialized = False
            _initialization_error = "MCP服务连接失败"
        return success
        
    except Exception as e:
        print(f"🔍 [DEBUG] MCP Agents 初始化失败: {e}")
        _initialization_error = str(e)
        _agent_initialized = False
        return False


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
        如果是其他的问题，返回other。
        注意：只返回上述两个单词中的一个，不要返回任何其他的内容。
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
    if "type" in state and state["type"] in ["domain", "other"]:
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
    
    # 初始化Agents（如果还没有初始化）
    if not initialize_agents():
        error_msg = f"MCP服务连接失败: {_initialization_error}。请检查domain-info-service (http://127.0.0.1:10025/sse) 是否正常运行。"
        writer({"error": error_msg})
        return {"messages": [AIMessage(content=error_msg)], "type": "domain"}
    
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
        writer({"domain_step": "调用域名查询工具..."})
        
        print("🔍 [DEBUG] 调用缓存的 domain Agent...")
        # 使用缓存的domain agent（保持向后兼容性）
        domain_agent = _domain_agent or get_domain_agent()
        response = domain_agent.invoke({"messages":prompts})
        
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
        print(f"🔍 [DEBUG] domain Agent 调用异常: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"🔍 [DEBUG] 异常堆栈: {traceback.format_exc()}")
        error_msg = f"域名查询过程中出现错误: {str(e)}。这可能是因为MCP服务连接中断或服务重启导致的。"
        writer({"error": error_msg})
        return {"messages": [AIMessage(content=error_msg)], "type": "domain"}


def deeplog_node(state:State):
    print(">>> deeplog_node")
    writer = get_stream_writer()
    writer({"node": "deeplog_node"})
    
    # 初始化Agents（如果还没有初始化）
    if not initialize_agents():
        error_msg = f"MCP服务连接失败: {_initialization_error}。请检查deeplog-ck-server (http://127.0.0.1:10026/sse) 是否正常运行。"
        writer({"error": error_msg})
        return {"messages": [AIMessage(content=error_msg)], "type": "deeplog"}
    
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
    
    try:
        writer({"deeplog_step": "调用日志分析工具..."})
        
        print("🔍 [DEBUG] 调用缓存的 deeplog Agent...")
        # 使用缓存的deeplog agent（保持向后兼容性）
        deeplog_agent = _deeplog_agent or get_deeplog_agent()
        response = deeplog_agent.invoke({"messages":messages})
        
        # 修正：正确提取响应内容
        if response and "messages" in response and response["messages"]:
            last_message = response["messages"][-1]
            if hasattr(last_message, 'content'):
                result_content = last_message.content
            else:
                result_content = str(last_message)
        else:
            result_content = "日志分析完成"
            
        writer({"deeplog_result": result_content})
        
        #拿到大模型思考结果后，更新state状态
        #必须要HumanMessage方式返回，不可以直接返回字符串
        #langchain中有不同消息类型：
        return {"messages": [AIMessage(content=result_content)], "type": "deeplog"}
        
    except Exception as e:
        print(f"🔍 [DEBUG] deeplog Agent 调用异常: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"🔍 [DEBUG] 异常堆栈: {traceback.format_exc()}")
        error_msg = f"日志分析过程中出现错误: {str(e)}。这可能是因为MCP服务连接中断或服务重启导致的。"
        writer({"error": error_msg})
        return {"messages": [AIMessage(content=error_msg)], "type": "deeplog"}


def other_node(state: State):
    print(">>> other_node")
    writer = get_stream_writer()
    writer({"node": "other_node"})
    other_response = "我主要擅长域名相关问题的处理，您的问题暂时无法回答。"
    return {"messages": [HumanMessage(content=other_response)], "type": "other"}

def routing_func(state: State):
    print(f"路由函数接收到类型: {state['type']}")
    
    if state["type"] == "domain":
        return "domain_node"
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
builder.add_node("other_node", other_node)

# 设置流程
builder.add_edge(START, "supervisor_node")

# 条件路由，langgraph执行引擎
builder.add_conditional_edges(
    "supervisor_node",
    routing_func,
    {
        "domain_node": "domain_node",
        "other_node": "other_node",
        END: END
    }
)

# 各个处理节点完成后回到 supervisor_node 进行结果确认
builder.add_edge("domain_node", "supervisor_node")
builder.add_edge("other_node", "supervisor_node")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

