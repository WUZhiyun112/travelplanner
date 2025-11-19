#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试DeepSeek API是否正常工作
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
try:
    load_dotenv()
except Exception as e:
    print(f"警告: 加载.env文件时出错: {e}")

# 初始化客户端
api_key = os.getenv('DEEPSEEK_API_KEY', 'sk-9ed593627cf943108c5ebc6541459ad9')
print(f"使用API密钥: {api_key[:10]}...")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

print("\n正在测试API连接...")
print("=" * 50)

try:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": "你好，请回复'API测试成功'"
            }
        ],
        max_tokens=50,
        timeout=30
    )
    
    if response and response.choices:
        result = response.choices[0].message.content
        print("[成功] API测试成功！")
        print(f"回复: {result}")
    else:
        print("[错误] API返回数据格式错误")
        
except Exception as e:
    print(f"[失败] API测试失败！")
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {str(e)}")
    
    # 详细错误信息
    import traceback
    print("\n详细错误堆栈:")
    print(traceback.format_exc())

print("=" * 50)

