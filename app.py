from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
from dotenv import load_dotenv
from openai import OpenAI
import requests
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import re

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

# Google Custom Search API 配置
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'AIzaSyBwyTp6pR1Xwj_Z5_V0YkY_Q4AY53-bzMc')
GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID', '5299e07176b844ae6')

# 启动时打印配置信息
logger.info(f"Google API配置: API_KEY={GOOGLE_API_KEY[:10]}..., SEARCH_ENGINE_ID={GOOGLE_SEARCH_ENGINE_ID}")
print(f"Google API配置: API_KEY={GOOGLE_API_KEY[:10]}..., SEARCH_ENGINE_ID={GOOGLE_SEARCH_ENGINE_ID}")

def google_search(query, num_results=5):
    """
    使用Google Custom Search API进行搜索
    返回搜索结果列表
    """
    if not GOOGLE_API_KEY:
        logger.warning("警告: 未配置Google API密钥，跳过搜索")
        return []
    
    # 如果没有搜索引擎ID，尝试使用默认的
    if not GOOGLE_SEARCH_ENGINE_ID:
        logger.warning("警告: 未配置Google搜索引擎ID，尝试使用API密钥直接搜索")
        # 注意：Google Custom Search API 需要搜索引擎ID，如果没有则无法搜索
        return []
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_SEARCH_ENGINE_ID,
            'q': query,
            'num': min(num_results, 10)  # Google API最多返回10个结果
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
        
        logger.info(f"Google搜索成功，找到 {len(results)} 个结果")
        print(f"Google搜索成功，找到 {len(results)} 个结果")
        return results
    except Exception as e:
        logger.error(f"Google搜索出错: {str(e)}")
        print(f"Google搜索出错: {str(e)}")
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

def extract_webpage_content(url, max_length=2000):
    """
    从网页URL提取主要内容
    返回网页的文本内容
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or 'utf-8'
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 移除脚本和样式标签
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.decompose()
        
        # 提取主要内容
        # 优先提取article、main、content等标签
        content = None
        for tag in ['article', 'main', '[role="main"]', '.content', '.post', '.entry-content']:
            elements = soup.select(tag)
            if elements:
                content = elements[0]
                break
        
        # 如果没有找到特定标签，使用body
        if not content:
            content = soup.find('body') or soup
        
        # 提取文本
        text = content.get_text(separator='\n', strip=True)
        
        # 清理文本：移除多余空白
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # 限制长度
        if len(text) > max_length:
            text = text[:max_length] + '...'
        
        return text
    except Exception as e:
        logger.warning(f"提取网页内容失败 {url}: {str(e)}")
        return None

def search_destination_info(destination, days, preferences=''):
    """
    搜索目的地的相关信息，并提取网页内容
    返回包含网页内容的搜索结果
    """
    search_queries = [
        f"{destination} {days}天 旅游攻略 景点推荐",
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
    
    if not unique_results:
        logger.warning("没有找到搜索结果")
        return []
    
    # 提取网页内容（最多5个，避免太慢）
    logger.info(f"开始提取 {len(unique_results[:5])} 个网页的内容...")
    print(f"开始提取 {len(unique_results[:5])} 个网页的内容...")
    enriched_results = []
    for i, result in enumerate(unique_results[:5], 1):
        logger.info(f"正在提取网页 {i}/{min(5, len(unique_results))}: {result['link']}")
        print(f"正在提取网页 {i}/{min(5, len(unique_results))}: {result['link']}")
        content = extract_webpage_content(result['link'], max_length=1500)
        if content:
            result['content'] = content
            logger.info(f"成功提取网页内容，长度: {len(content)} 字符")
            print(f"成功提取网页内容，长度: {len(content)} 字符")
            enriched_results.append(result)
        else:
            logger.warning(f"提取网页内容失败，使用摘要: {result.get('snippet', '无摘要')[:100]}")
            print(f"提取网页内容失败，使用摘要")
            # 即使提取失败，也保留搜索结果（至少有用摘要）
            enriched_results.append(result)
    
    logger.info(f"成功提取 {len(enriched_results)} 个网页的内容")
    print(f"成功提取 {len(enriched_results)} 个网页的内容")
    return enriched_results

@app.route('/')
def index():
    """返回主页面"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST', 'OPTIONS'])
def search():
    """独立的搜索API端点"""
    # 处理CORS预检请求
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    
    try:
        logger.info(f"收到搜索请求: {request.method}, Content-Type: {request.content_type}")
        
        if not request.is_json:
            logger.warning("请求不是JSON格式")
            return jsonify({
                'success': False,
                'error': '请求格式错误，需要JSON格式'
            }), 400
        
        data = request.json
        if not data:
            logger.warning("请求数据为空")
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400
            
        query = data.get('query', '')
        logger.info(f"搜索关键词: {query}")
        
        if not query:
            return jsonify({
                'success': False,
                'error': '请输入搜索关键词'
            }), 400
        
        # 优先使用Google API，如果没有配置则使用简化版
        has_api = bool(GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID)
        logger.info(f"搜索请求: query={query}, has_api={has_api}, API_KEY={bool(GOOGLE_API_KEY)}, SEARCH_ENGINE_ID={bool(GOOGLE_SEARCH_ENGINE_ID)}")
        
        if has_api:
            logger.info("使用Google Custom Search API进行搜索")
            results = google_search(query, num_results=10)
        else:
            logger.warning("未配置完整Google API，使用简化版搜索")
            # 使用简化版搜索（返回搜索链接）
            results = simple_search(query, num_results=10)
        
        logger.info(f"搜索完成，返回 {len(results)} 个结果")
        return jsonify({
            'success': True,
            'results': results,
            'using_api': has_api
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
        
        search_results = []
        try:
            search_results = search_destination_info(destination, days, preferences)
            logger.info(f"搜索完成，找到 {len(search_results)} 个结果")
            print(f"搜索完成，找到 {len(search_results)} 个结果")
        except Exception as search_error:
            logger.warning(f"搜索过程中出错，继续生成计划: {str(search_error)}")
            print(f"搜索过程中出错，继续生成计划: {str(search_error)}")
        
        # 构建提示词
        prompt = f"""请为我制定一个详细的{days}天旅游计划，目的地是{destination}。

"""
        if budget:
            prompt += f"预算：{budget}\n\n"
        if preferences:
            prompt += f"兴趣偏好：{preferences}\n\n"
        
        # 如果有搜索结果，添加到提示词中
        if search_results and len(search_results) > 0:
            logger.info(f"将 {len(search_results)} 个搜索结果的内容传递给AI进行分析")
            print(f"将 {len(search_results)} 个搜索结果的内容传递给AI进行分析")
            # 统计有多少个成功提取了内容
            content_count = sum(1 for r in search_results if 'content' in r and r['content'])
            logger.info(f"其中 {content_count} 个成功提取了网页内容")
            print(f"其中 {content_count} 个成功提取了网页内容")
            
            prompt += "以下是从网络搜索并提取的实际网页内容，请仔细阅读这些真实信息，然后基于这些内容制定详细的旅游计划：\n\n"
            for i, result in enumerate(search_results, 1):
                prompt += f"=== 信息来源 {i} ===\n"
                prompt += f"标题：{result.get('title', '无标题')}\n"
                prompt += f"来源链接：{result.get('link', '无链接')}\n"
                
                # 如果有提取的网页内容，使用它；否则使用摘要
                if 'content' in result and result['content']:
                    prompt += f"网页实际内容：\n{result['content']}\n\n"
                    logger.info(f"信息来源 {i}: 使用提取的网页内容 ({len(result['content'])} 字符)")
                else:
                    snippet = result.get('snippet', '无摘要')
                    prompt += f"摘要：{snippet}\n\n"
                    logger.info(f"信息来源 {i}: 使用摘要 ({len(snippet)} 字符)")
            
            prompt += "=== 重要提示 ===\n"
            prompt += "请仔细分析以上从真实网页提取的内容，包括：\n"
            prompt += "1. 具体的景点名称、地址和特色\n"
            prompt += "2. 推荐的餐厅和美食\n"
            prompt += "3. 住宿建议和价格信息\n"
            prompt += "4. 交通方式和路线\n"
            prompt += "5. 最佳旅游时间和注意事项\n"
            prompt += "6. 预算建议和实用信息\n\n"
            prompt += "基于这些真实信息，制定一个详细、实用、准确的旅游计划。\n\n"
        else:
            logger.warning("没有搜索结果，将仅基于AI知识库生成计划")
            print("没有搜索结果，将仅基于AI知识库生成计划")
        
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
            
            # 如果有搜索结果，添加参考链接部分
            if search_results and len(search_results) > 0:
                plan += "\n\n---\n\n## 📚 参考资料来源\n\n"
                plan += "本计划基于以下网络资源生成，您可以点击链接查看原文：\n\n"
                for i, result in enumerate(search_results, 1):
                    title = result.get('title', '无标题')
                    link = result.get('link', '')
                    if link:
                        plan += f"{i}. [{title}]({link})\n"
                    else:
                        plan += f"{i}. {title}\n"
                plan += "\n*注：以上链接仅供参考，请以实际情况为准。*\n"
            
            return jsonify({
                'success': True,
                'plan': plan,
                'references': [{'title': r.get('title', ''), 'link': r.get('link', '')} for r in search_results] if search_results else []
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

