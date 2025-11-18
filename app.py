from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from dotenv import load_dotenv
from openai import OpenAI
import requests
import logging
from datetime import datetime

# 加载环境变量
try:
    load_dotenv()
except Exception as e:
    print(f"警告: 加载.env文件时出错: {e}，将使用代码中的默认值")

app = Flask(__name__)
CORS(app)

# 配置日志记录到文件
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)
logger.info("=" * 50)
logger.info("应用启动")
logger.info("=" * 50)

# 初始化DeepSeek客户端（兼容OpenAI SDK）
client = OpenAI(
    api_key=os.getenv('DEEPSEEK_API_KEY', 'sk-9ed593627cf943108c5ebc6541459ad9'),
    base_url="https://api.deepseek.com"
)

# 谷歌搜索配置
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID', '')

def google_search(query, num_results=5):
    """
    使用Google Custom Search API进行搜索
    返回搜索结果列表
    """
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        print("警告: 未配置Google API密钥，跳过搜索")
        return []
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_SEARCH_ENGINE_ID,
            'q': query,
            'num': num_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        if 'items' in data:
            for item in data['items']:
                results.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'link': item.get('link', '')
                })
        
        print(f"谷歌搜索成功，找到 {len(results)} 个结果")
        return results
    except Exception as e:
        print(f"谷歌搜索出错: {str(e)}")
        return []

def simple_search(query, num_results=5):
    """
    简化版搜索：直接返回Google搜索链接（不需要API）
    这是一个备用方案，当没有配置API时使用
    """
    # 生成Google搜索链接
    search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    
    # 返回一个包含搜索链接的结果
    # 注意：这只是一个链接，不是实际的搜索结果
    return [{
        'title': f'在Google中搜索: {query}',
        'snippet': '点击下方链接在Google中查看搜索结果（需要手动访问）',
        'link': search_url,
        'is_link_only': True
    }]

def search_destination_info(destination, days, preferences=''):
    """
    搜索目的地的相关信息
    """
    search_queries = [
        f"{destination} 旅游攻略 景点推荐",
        f"{destination} 美食推荐 餐厅",
        f"{destination} 住宿推荐 酒店"
    ]
    
    if preferences:
        search_queries.append(f"{destination} {preferences}")
    
    all_results = []
    for query in search_queries:
        results = google_search(query, num_results=3)
        all_results.extend(results)
    
    # 去重（基于链接）
    seen_links = set()
    unique_results = []
    for result in all_results:
        if result['link'] not in seen_links:
            seen_links.add(result['link'])
            unique_results.append(result)
    
    return unique_results[:10]  # 返回最多10个结果

@app.route('/')
def index():
    """返回主页面"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search():
    """独立的搜索API端点"""
    try:
        data = request.json
        query = data.get('query', '')
        
        if not query:
            return jsonify({
                'success': False,
                'error': '请输入搜索关键词'
            }), 400
        
        # 优先使用Google API，如果没有配置则使用简化版
        if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
            results = google_search(query, num_results=10)
        else:
            # 使用简化版搜索（返回搜索链接）
            results = simple_search(query, num_results=10)
        
        return jsonify({
            'success': True,
            'results': results,
            'using_api': bool(GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID)
        })
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"搜索错误详情: {error_detail}")
        print(f"搜索错误详情: {error_detail}")
        return jsonify({
            'success': False,
            'error': f'搜索时出错：{str(e)}'
        }), 500

@app.route('/api/generate-plan', methods=['POST'])
def generate_plan():
    """生成旅游计划的API端点"""
    try:
        # 检查请求数据
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': '请求格式错误，需要JSON格式'
            }), 400
        
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400
            
        logger.info(f"收到请求: {data}")  # 调试日志
        print(f"收到请求: {data}")  # 调试日志
        
        days = data.get('days', '')
        destination = data.get('destination', '')
        budget = data.get('budget', '')
        preferences = data.get('preferences', '')
        
        # 验证必填字段
        if not days or not destination:
            return jsonify({
                'success': False,
                'error': '请填写旅游天数和目的地'
            }), 400
        
        # 使用谷歌搜索获取目的地信息
        logger.info(f"正在搜索 {destination} 的相关信息...")
        print(f"正在搜索 {destination} 的相关信息...")
        search_results = search_destination_info(destination, days, preferences)
        
        # 构建提示词
        prompt = f"""请为我制定一个详细的{days}天旅游计划，目的地是{destination}。

"""
        if budget:
            prompt += f"预算：{budget}\n\n"
        if preferences:
            prompt += f"兴趣偏好：{preferences}\n\n"
        
        # 如果有搜索结果，添加到提示词中
        if search_results:
            prompt += "以下是从网络搜索到的相关信息，请参考这些信息来制定更准确的计划：\n\n"
            for i, result in enumerate(search_results, 1):
                prompt += f"信息{i}：\n"
                prompt += f"标题：{result['title']}\n"
                prompt += f"内容：{result['snippet']}\n"
                prompt += f"来源：{result['link']}\n\n"
            prompt += "请基于以上搜索到的信息，结合你的专业知识，制定详细的旅游计划。\n\n"
        
        prompt += """请按照以下格式提供详细的旅游计划：

## 旅游计划概览
- 目的地：[目的地名称]
- 旅游天数：[天数]
- 推荐季节：[最佳旅游时间]

## 每日详细行程

### 第1天：[日期/主题]
**上午：**
- [具体活动和时间]
- [景点名称和地址]

**下午：**
- [具体活动和时间]
- [景点名称和地址]

**晚上：**
- [具体活动和时间]
- [餐厅推荐]

**住宿推荐：**
- [酒店/民宿名称和价格范围]

**交通建议：**
- [交通方式和路线]

### 第2天：[日期/主题]
[按照相同格式继续...]

## 实用信息
- **当地交通：** [交通方式建议]
- **美食推荐：** [特色美食和餐厅]
- **注意事项：** [重要提示]
- **预算估算：** [每日/总预算建议]

请确保计划合理、详细，包含具体的景点、餐厅和活动建议。"""

        # 调用DeepSeek API
        logger.info("正在调用DeepSeek API...")
        logger.info(f"API密钥: {client.api_key[:10]}...")  # 只显示前10个字符
        print("正在调用DeepSeek API...")  # 调试日志
        print(f"API密钥: {client.api_key[:10]}...")  # 只显示前10个字符
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的旅游规划师，擅长制定详细、实用的旅游计划。你的回答应该结构清晰、信息准确、建议合理。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000,
                timeout=60  # 设置60秒超时
            )
            
            if not response or not response.choices:
                raise Exception("API返回数据格式错误")
            
            plan = response.choices[0].message.content
            logger.info("API调用成功，返回计划")
            print("API调用成功，返回计划")  # 调试日志
            
            return jsonify({
                'success': True,
                'plan': plan
            })
        except Exception as api_error:
            import traceback
            api_error_detail = traceback.format_exc()
            logger.error(f"API调用错误详情: {api_error_detail}")
            print(f"API调用错误详情: {api_error_detail}")  # 调试日志
            # 不直接抛出，而是返回友好的错误信息
            error_str = str(api_error)
            if '401' in error_str or 'Unauthorized' in error_str:
                return jsonify({
                    'success': False,
                    'error': 'API密钥无效或已过期，请检查您的DeepSeek API密钥配置'
                }), 401
            elif '429' in error_str:
                return jsonify({
                    'success': False,
                    'error': 'API调用频率过高，请稍后再试'
                }), 429
            else:
                raise api_error
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"生成计划错误详情: {error_detail}")
        print(f"错误详情: {error_detail}")  # 调试日志
        
        # 提供更友好的错误信息
        error_message = str(e)
        if '401' in error_message or 'Unauthorized' in error_message:
            error_message = 'API密钥无效，请检查您的DeepSeek API密钥配置'
        elif '429' in error_message or 'rate limit' in error_message.lower():
            error_message = 'API调用频率过高，请稍后再试'
        elif 'timeout' in error_message.lower():
            error_message = '请求超时，请检查网络连接或稍后重试'
        elif 'Connection' in error_message:
            error_message = '网络连接失败，请检查您的网络连接'
        
        return jsonify({
            'success': False,
            'error': f'生成计划时出错：{error_message}',
            'detail': str(e) if app.debug else None
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

