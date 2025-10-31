import gradio as gr
import random
from Director import graph
from langchain_core.messages import HumanMessage
import os
import sys

# 添加路径以导入模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def chat_with_director(message, history):
    """
    与Director多Agent系统交互的函数
    
    Args:
        message: 用户输入的消息
        history: 对话历史
    
    Returns:
        回复消息和更新后的历史记录
    """
    try:
        # 生成随机线程ID
        config = {
            "configurable": {
                "thread_id": random.randint(1, 10000)
            }
        }
        
        # 构建输入数据
        input_data = {
            "messages": [HumanMessage(content=message)]
        }
        
        # 调用多Agent系统
        result = graph.invoke(
            input_data,
            config=config,
            stream_mode="values"
        )
        
        # 提取最终回复
        if result and "messages" in result and result["messages"]:
            response = result["messages"][-1].content
        else:
            response = "抱歉，系统暂时无法处理您的请求。"
            
        return response
        
    except Exception as e:
        error_msg = f"系统出错：{str(e)}"
        print(f"Error: {error_msg}")
        return error_msg

def create_gradio_interface():
    """创建Gradio界面"""
    
    # 创建聊天界面
    with gr.Blocks(
        title="Director多Agent助手",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 800px !important;
            margin: auto !important;
        }
        .chat-message {
            padding: 10px;
            margin: 5px 0;
            border-radius: 10px;
        }
        """
    ) as demo:
        
        gr.Markdown(
            """
            # 🤖 Director多Agent智能助手
            
            这是一个基于LangGraph构建的多Agent系统，可以帮助您：
            - 🗺️ **旅游规划**：制定旅游路线和建议
            - 😄 **讲笑话**：生成有趣的笑话内容
            - 📝 **对对联**：创作精彩的对联
            - 💬 **其他问题**：处理其他类型的咨询
            
            请在下方输入您的问题，系统会自动识别并分配给合适的专业Agent处理。
            """
        )
        
        # 聊天界面
        chatbot = gr.Chatbot(
            label="对话记录",
            height=400,
            show_label=True,
            container=True,
            bubble_full_width=False
        )
        
        # 输入框
        msg = gr.Textbox(
            label="请输入您的问题",
            placeholder="例如：推荐一个北京旅游路线 / 讲个笑话 / 帮我对个对联",
            lines=2,
            max_lines=5
        )
        
        # 按钮组
        with gr.Row():
            submit_btn = gr.Button("发送", variant="primary", scale=2)
            clear_btn = gr.Button("清空对话", variant="secondary", scale=1)
        
        # 示例问题
        gr.Examples(
            examples=[
                "推荐一个三天的北京旅游路线",
                "讲一个程序员的笑话",
                "帮我对个对联，上联是：春风得意马蹄疾",
                "今天天气怎么样？",
                "你能做什么？"
            ],
            inputs=msg,
            label="示例问题"
        )
        
        # 系统信息
        with gr.Accordion("系统信息", open=False):
            gr.Markdown(
                """
                ### 🔧 系统架构
                - **Supervisor Node**: 负责问题分类和任务调度
                - **Travel Node**: 专门处理旅游相关问题
                - **Joke Node**: 专门生成笑话内容
                - **Couplet Node**: 专门创作对联
                - **Other Node**: 处理其他类型问题
                
                ### 🚀 技术栈
                - **LangGraph**: 多Agent工作流编排
                - **LangChain**: 大语言模型集成
                - **DeepSeek**: 底层语言模型
                - **Gradio**: Web界面框架
                """
            )
        
        def respond(message, chat_history):
            """处理用户输入并更新对话历史"""
            if not message.strip():
                return "", chat_history
            
            # 获取系统回复
            bot_message = chat_with_director(message, chat_history)
            
            # 更新对话历史
            chat_history.append((message, bot_message))
            
            return "", chat_history
        
        def clear_chat():
            """清空对话历史"""
            return None, []
        
        # 绑定事件
        submit_btn.click(
            respond,
            inputs=[msg, chatbot],
            outputs=[msg, chatbot]
        )
        
        msg.submit(
            respond,
            inputs=[msg, chatbot],
            outputs=[msg, chatbot]
        )
        
        clear_btn.click(
            clear_chat,
            outputs=[chatbot, msg]
        )
    
    return demo

if __name__ == "__main__":
    # 检查环境变量
    required_env_vars = ["DEEPSEEK_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  警告：缺少环境变量: {', '.join(missing_vars)}")
        print("请确保已设置相关环境变量，否则系统可能无法正常工作。")
    
    # 创建并启动界面
    demo = create_gradio_interface()
    
    print("🚀 启动Gradio界面...")
    print("📝 支持的功能：旅游规划、讲笑话、对对联、其他问题")
    print("🌐 访问地址：http://localhost:7860")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        quiet=False
    )