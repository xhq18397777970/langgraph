import os
from langchain_openai import ChatOpenAI


def get_deepseek_model(temperature=0.2):
    """
    配置并返回 DeepSeek 模型实例
    
    Returns:
        ChatOpenAI: 配置好的 DeepSeek 模型实例
    """
    model = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=temperature,
        model_kwargs={"response_format": None} 
    )
    return model