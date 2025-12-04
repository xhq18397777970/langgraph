
from typing import Annotated, Sequence, List, Literal ,TypedDict
from pydantic import BaseModel, Field 
from langchain_core.messages import HumanMessage,AIMessage,ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command 
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent 
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from langchain_openai import ChatOpenAI
import json
import asyncio
from langchain_core.tools import StructuredTool

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
#配置加载
def get_deepseek_model(temperature=0.2):
    """
    配置并返回 DeepSeek 模型实例
    
    Returns:
        ChatOpenAI: 配置好的 DeepSeek 模型实例
    """
    model = ChatOpenAI(
        model="deepseek-chat",
        api_key="sk-7ce2292c26e546f78aaff58c4bf55fac",
        base_url="https://api.deepseek.com",
        temperature=temperature,
        # model_kwargs={"response_format": None} 
    )
    return model


load_dotenv()



class OverallState(TypedDict):
    messages: Annotated[list, "LangGraph standard messages"]
    domain_node_tool_results: str # 新增字段用于存储domain节点的结果
    deeplog_node_tool_results: str


class SupervisorDecision(BaseModel):
    """
    主管节点的决策模型，用于路由任务。
    """
    next: Literal["domain", "deeplog"] = Field(
        ...,
        description="下一个要执行的专家节点名称，必须是 'domain' 或 'deeplog' 之一。"
    )
    reason: str = Field(
        ...,
        description="简洁的决策依据，说明为什么选择该节点。"
    )
    
class ValidatorDecision(BaseModel):
    """
    验证器节点的决策模型，用于判断任务是否完成。
    """
    next: Literal["supervisor", "__end__"] = Field(
        ...,
        description="下一个要执行的动作，'supervisor' 表示继续任务，'__end__' 表示结束流程。"
    )
    reason: str = Field(
        ...,
        description="用一句话说明任务完成或未完成的核心事实。"
    )
def supervisor_node(state: OverallState) -> Command[Literal["domain", "deeplog"]]:
    
    llm = get_deepseek_model(temperature=0.4)
    
    # --- 关键修改：在 Prompt 中明确指定 JSON Schema ---
    # 我们将 Pydantic 模型的 JSON Schema 直接嵌入到 Prompt 中
    supervisor_system_prompt = f'''
    你是一个工作流调度器，负责将用户任务分配给合适的专家节点。
 
    **你的唯一职责是返回一个符合以下JSON Schema的有效JSON对象**：
    ```json
    {SupervisorDecision.model_json_schema()}
    ```
 
    **各节点职责**:
    - `domain`: 处理域名元数据(注册状态、管理者)相关的查询请求。
    - `deeplog`: 处理指定时间段的历史指标数据查询请求。
    
    **路由规则**:
    1.  检查对话历史，找出尚未完成的用户子任务。
    2.  根据子任务类型，从上述节点中选择一个进行调度。
            -   如果存在域名查询子任务，则选择 `domain`。
            -   如果域名任务已完成，但存在指标数据查询子任务，则选择 `deeplog`。
    
    **输出要求**:
    - 你的**完整输出**必须是一个可以被 Python 的 `json.loads()` 解析的 JSON 对象。
    - 不要在JSON对象前后添加任何解释性文字、代码块标记（如 ```json）或任何其他内容。
    
    **输出示例**:
    {{"next": "domain", "reason": "用户请求查询域名信息。"}}
    '''
    
    messages = [
        {"role": "system", "content": supervisor_system_prompt}, 
    ] + state["messages"] 
 
    # --- 关键修改：恢复常规调用，不再使用 with_structured_output ---
    response = llm.invoke(messages)
    content = response.content.strip()
    
    print(f"🤖 [SUPERVISOR RAW] 模型原始输出:\n{response.content}\n" + "="*40)
    # --- 关键修改：使用 Pydantic 进行安全解析和验证 ---
    try:
        # Pydantic 的 model_validate_json 会解析字符串并进行校验
        decision = SupervisorDecision.model_validate_json(content)
        
        goto = decision.next
        reason = decision.reason
        
        print(f"supervisor 结果为  [{goto}]")
        print(f"supervisor 理由为  [{reason}")
        
        print(f"--- 工作流转移: Supervisor → {goto.upper()} ---")
        
        return Command(
            update={
                "messages": [
                    AIMessage(content=reason, name="supervisor")
                ]
            },
            goto=goto,  
        )
    except Exception as e:
        # 如果 Pydantic 解析失败，说明格式或内容不对
        print("--- supervisor 输出解析失败 ---")
        print(f"模型原始回复: {content}")
        print(f"Pydantic 校验错误: {e}")
        # 抛出异常，让整个流程失败，或者可以添加回退逻辑，比如重新调度
        raise ValueError(f"Supervisor 未能返回有效的JSON格式决策。错误: {e}") from e


def validator_node(state: OverallState) -> Command[Literal["supervisor", "__end__"]]:
 
    llm = get_deepseek_model(temperature=0.4)
    
    # --- 关键修改：在 Prompt 中明确指定 JSON Schema ---
    validator_system_prompt = f'''
    你是一个工作流程验证器，你的唯一职责是判断用户的原始任务是否已经完全完成。
 
    **你的唯一职责是返回一个符合以下JSON Schema的有效JSON对象**：
    ```json
    {ValidatorDecision.model_json_schema()}
    ```
 
    **判断规则**：
    1.  仔细识别用户最初的、完整的请求。
    2.  检查对话历史，确认所有请求的子任务是否都已由相关专家执行并返回了结果。
    3.  如果所有子任务都有明确的执行记录和结果输出，则任务完成（"__end__"）。
    4.  如果仍有任何子任务未被处理或处理失败，则任务未完成（"supervisor"）。
    
    **输出示例**:
    {{"next": "__end__", "reason": "所有任务均完成。"}}
    '''
    
    messages = [
        {"role": "system", "content": validator_system_prompt}
    ] + state["messages"]
 
    # --- 关键修改：恢复常规调用 ---
    response = llm.invoke(messages)
    content = response.content.strip()
    print(f"🤖 [VALIDATOR RAW] 模型原始输出:\n{response.content}\n" + "="*40)
    # --- 关键修改：使用 Pydantic 进行安全解析和验证 ---
    try:
        decision = ValidatorDecision.model_validate_json(content)
        
        goto = decision.next
        reason = decision.reason
        
        print(f"validator 结果为  [ {goto}]")
        print(f"validator 理由为  [ {reason}]")
        
        if goto == "__end__":
            print(" --- Transitioning to END ---")
        else:
            print(f"--- 工作流转移: validator → supervisor ---")
            
        return Command(
            update={
                "messages": [
                    AIMessage(content=reason, name="validator")
                ]
            },
            goto=goto,  
        )
    except Exception as e:
        # 如果 Pydantic 解析失败
        print("--- validator 输出解析失败 ---")
        print(f"模型原始回复: {content}")
        print(f"Pydantic 校验错误: {e}")
        raise ValueError(f"Validator 未能返回有效的JSON格式决策。错误: {e}") from e
    
@tool
def domain_user_info(domain):

    """
    查询指定域名的管理人信息。
    输入：域名
    输出：域名的管理者
    Args:
        domain (str): 需要查询的完整域名。请提供一个不含协议（如http://）和路径（如/path）的纯净域名，例如 'google.com' 或 'github.com'。
    """
    print("[domain_info]工具被调用")
    return f"域名 {domain} 的管理者为：谢晗琦"

@tool
def domain_register_info(domain):
    """
    查询指定域名的注册状态，只有"未注册","已注册"两种结果
    输入：域名
    输出：域名的注册状态
    Args:
        domain (str): 需要查询的完整域名。请提供一个不含协议（如http://）和路径（如/path）的纯净域名，例如 'google.com' 或 'github.com'。
    """
    print("[domain_info]工具被调用")
    return f"域名 {domain} 的注册状态为：已注册"

@tool
def history_info(time):

    """
    根据指定的时间范围，检索域名的QPS数据
    输入：时间段
    输出：域名指定时间段，QPS
    Args:
        time (str):如"2023-10-1-00:00:00至2023-10-1-00:05:00"
    """
    print("[history_info]工具被调用")
    return f"在该时间段：{time}，QPS平均值是：1.2"

class DomainExecutionResult(BaseModel):
    """
    域名专家节点执行结果的模型。
    """
    tool_name: str = Field(
        ...,
        description="被调用的工具的精确名称"
    )
    tool_result: str = Field(
        ...,
        description="工具返回的原始结果字符串。"
    )
    summary: str = Field(
        ...,
        description="对工具执行结果的总结思考与趋势分析"
    )
    
def domain_node(state: OverallState) -> Command[Literal["__end__"]]:
    
    llm = get_deepseek_model(0.1)
    
    # --- 【修改】新的 Prompt，包含 JSON Schema 指导 ---
    # 这个 Prompt 会在 Agent 调用完工具后，指导其如何进行最终总结
    final_summary_prompt = f"""
    你已经执行了工具调用。现在，请根据你的完整思考过程和工具返回的结果，生成一个最终的JSON摘要。
    
    **你的唯一职责是返回一个符合以下JSON Schema的有效JSON对象**：
    ```json
    {DomainExecutionResult.model_json_schema()}
    ```
    
    **输出要求**:
    - 你的**完整输出**必须是一个可以被 Python 的 `json.loads()` 解析的 JSON 对象。
    - 不要在JSON对象前后添加任何解释性文字、代码块标记（如 ```json）或任何其他内容。
 
    **输出示例**:
    {{
        "tool_name": "domain_register_info",
        "tool_result": "域名 example.com 的注册状态为：已注册",
        "summary": "已成功确认域名 example.com 处于已注册状态。"
    }}
    """
 
    state_with_prompt = state.copy()
    state_with_prompt["messages"] = [
        AIMessage(content=final_summary_prompt, name="system")  # <-- 将精细化的 Prompt 作为系统消息
    ] + state["messages"]
    
    # --- 【修改】使用标准的 LLM 创建 Agent ---
    # 不再使用 with_structured_output
    domain_agent = create_react_agent(
        llm,  
        tools=[domain_user_info, domain_register_info],
        # debug=True  # 保留 debug 以便观察 Agent 行为
    )
    
    result = domain_agent.invoke(state_with_prompt)
    
    print(f"🛠️ [DOMAIN RAW] Agent 最终输出:\n{result['messages'][-1].content}\n" + "="*40)
    # --- 【修改】使用 Pydantic 进行安全解析和验证 ---
    try:
        final_message_content = result["messages"][-1].content.strip()
        
        # 使用 Pydantic 模型来解析和验证 Agent 的最终输出
        execution_output = DomainExecutionResult.model_validate_json(final_message_content)
        
        # 打印格式化后的结果以便调试
        formatted_output = (
            f"{{\n"
            f'  "tool_name": "{execution_output.tool_name}",\n'
            f'  "tool_result": "{execution_output.tool_result}",\n'
            f'  "summary": "{execution_output.summary}"\n'
            f"}}"
        )
        
        # print(f"--- Domain Node 结构化输出结果 ---\n{formatted_output}")
        # print(f"--- 工作流转移: domain → Validator ---")
 
        # --- 【修改】将结构化对象的 JSON 字符串存入状态 ---
        return Command(
            update={
                "messages": [ 
                    AIMessage(
                        content=execution_output.model_dump_json(),  # <-- 将 Pydantic 模型转为 JSON 字符串
                        name="domain_expert"
                    )
                ],
                "domain_node_tool_results":execution_output.tool_result
            },
            goto="__end__", 
        )
    except Exception as e:
        # 如果解析失败，打印错误信息
        print("--- Domain Node 输出解析失败 ---")
        print(f"Agent 原始回复: {result['messages'][-1].content}")
        print(f"Pydantic 校验错误: {e}")
        # 抛出明确的异常
        raise ValueError(f"Domain Agent 未能返回有效的JSON格式决策。错误: {e}") from e

class DeeplogExecutionResult(BaseModel):
    """
    域名专家节点执行结果的模型。
    """
    tool_name: str = Field(
        ...,
        description="被调用的工具的精确名称"
    )
    status: str = Field(
        ...,
        description="工具调用的结果是否成功(success or failed)"
    )


 
def deeplog_node(state: OverallState) -> Command[Literal["__end__"]]:
    
    llm = get_deepseek_model(0.3)
    
    final_summary_prompt = f"""
    你是一个负责日志检索的专家。你的任务是：
    1. 理解用户的查询需求。
    2. 从可用工具中选择正确的工具，并提取必要参数进行调用。
    3. 工具调用成功后，你的任务就完成了。
 
    **你的最终输出必须是一个简单的 JSON 对象，只包含两个字段**：
    - `tool_name`: 你调用的工具的名称。
    - `status`: 字符串，固定为 "success"。
 
    **输出格式**:
    不要在JSON前后添加任何解释性文字、代码块标记或任何其他内容。
    你的**完整输出**必须是类似这样的格式：
    {{"tool_name": "npa_analysis_prometheus_core", "status": "success"}}
    """
    
    state_with_prompt = state.copy()
    state_with_prompt["messages"] = [
        AIMessage(content=final_summary_prompt, name="system")
    ] + state["messages"]
 
    print("🔍 [DEBUG] 创建 MCP 客户端...")
    client = MultiServerMCPClient(
        {
            "monitor-service": {
                "url": "http://127.0.0.1:10027/sse",
                "transport": "sse",
            }
        }
    )
    print("🔍 [DEBUG] 获取 MCP 工具...")
    async_tools = asyncio.run(client.get_tools())
    print("🔍 [DEBUG] 转换异步工具为同步工具...")
    sync_tools = convert_async_tools_to_sync(async_tools)
 
    deeplog_agent = create_react_agent(
        llm,
        tools=sync_tools,
    )
 
    result = deeplog_agent.invoke(state_with_prompt)
    
    print(f"🛠️ [DEEPLOG RAW] Agent 最终输出:\n{result['messages'][-1].content}\n" + "="*40)
 
    # --- 【核心修改】更健壮地提取原始工具结果 ---
    raw_tool_result = None
    # 从消息历史中倒序查找，确保找到的是最后一次工具调用的结果
    for message in reversed(result["messages"]):
        if isinstance(message, ToolMessage):
            raw_tool_result = message.content
            break  # 找到后立即退出循环
 
    if not raw_tool_result:
        raise ValueError("Agent 没有成功调用任何工具或未找到工具结果。")
 
    try:
        final_message_content = result["messages"][-1].content.strip()
        agent_output = json.loads(final_message_content)
        
        if agent_output.get("status") != "success":
            raise ValueError("Agent 报告任务失败")
            
        print(f"--- Deeplog Node 执行成功，准备前往 Validator ---")
 
        # --- 【核心修改】返回 Command，将原始数据存入独立字段 ---
        # 不再操作 messages 列表，只更新我们自定义的字段
        return Command(
            update={
                # 将原始工具结果字符串存入一个独立的字段
                "deeplog_node_tool_results": raw_tool_result
            },
            goto="__end__",
        )
    except Exception as e:
        print("--- Deeplog Node 输出解析失败 ---")
        print(f"Agent 原始回复: {result['messages'][-1].content}")
        print(f"Pydantic/JSON 校验错误: {e}")
        raise ValueError(f"Deeplog Agent 未能返回有效的JSON格式决策。错误: {e}") from e



graph = StateGraph(OverallState)

graph.add_node("supervisor", supervisor_node) 
graph.add_node("deeplog", deeplog_node)  
graph.add_node("domain", domain_node) 
# graph.add_node("coder", code_node) 
graph.add_node("validator", validator_node)  

graph.add_edge(START, "supervisor")  
app = graph.compile()

#展示graph图
def draw_graph_image():
    try:
        # 使用 xray=True 显示更多细节
        image_data = app.get_graph(xray=True).draw_mermaid_png()
        
        # 保存到当前文件夹
        filename = "langgraph_workflow.png"
        with open(filename, "wb") as f:
            f.write(image_data)
        
        print(f"✅ LangGraph 流程图已保存到当前文件夹: {filename}")
        
    except Exception as e:
        print(f"⚠️ 无法生成流程图图片: {e}")


import json

def parse_simple(returned_string):
    """
    简化的解析方法，假设格式固定为 ["{...}", null]
    """
    # 去除开头的 [" 和结尾的 ", null]
    if returned_string.startswith('["') and returned_string.endswith('", null]'):
        json_string = returned_string[2:-8]  # 去除 [" 和 ", null]
        # 处理转义字符
        json_string = json_string.replace('\\"', '"')
        return json.loads(json_string)
    return None


if __name__ == "__main__":
    print("--- Agent任务执行 ---")
    
    # 1. 定义要注入到图中的初始状态（测试用例）
    initial_state = {
        "messages": [
            HumanMessage(content="请查询集群lf-lan-ha1在2025-12-03 09:43:14到2025-12-03 10:13:14的CPU指标数据")
        ]
    }
    
    try:
        final_state = app.invoke(initial_state)
        
        print("\n" + "="*20 + " 工作流执行完毕，开始分析结果 " + "="*20)
        
        cpu_data = final_state.get("deeplog_node_tool_results")
        
        
        
        print(parse_simple(cpu_data))
        
    except Exception as e:
        print(f"执行出错: {e}")
    # try:
    #     # 2. 使用 app.invoke() 将状态注入并运行整个图
    #     # 这会启动从 START 开始的完整工作流程
    #     final_state = app.invoke(initial_state)

    #     deeplog_node_tool_results = final_state.get("deeplog_node_tool_results")
        
        
    #     print('='*10,deeplog_node_tool_results)
    #     # # 3. (可选) 打印最终的完整对话历史，以验证结果
    #     # print("\n" + "=" * 20 + " 最终结果 " + "=" * 20)
    #     # for i, message in enumerate(final_state["messages"]):
    #     #     print(f"--- 消息 {i} ---")
    #     #     print(f"[类型]: {type(message).__name__}")
    #     #     if message.name:
    #     #         print(f"[当前执行]: {message.name}")
    #     #     print(f"[内容]: {message.content}\n")
 
    # except Exception as e:
    #     print(f"执行出错: {e}")
    
    # # print('-'*10+domain_node_tool_results)