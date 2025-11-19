"""
RAG工具模块：处理文本、生成PDF、向量化存储和检索
"""
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
import json

# PDF生成
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

# 向量数据库和嵌入
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("Chromadb或sentence-transformers未安装，RAG功能将受限")

logger = logging.getLogger(__name__)

# 全局变量
vector_db = None
embedding_model = None
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), 'chroma_db')
PDF_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'pdf_storage')

# 确保目录存在
os.makedirs(CHROMA_DB_PATH, exist_ok=True)
os.makedirs(PDF_STORAGE_PATH, exist_ok=True)


def init_rag_system():
    """初始化RAG系统（向量数据库和嵌入模型）"""
    global vector_db, embedding_model
    
    if not CHROMADB_AVAILABLE:
        logger.warning("RAG系统不可用：缺少必要的依赖包")
        return False
    
    try:
        # 初始化向量数据库
        vector_db = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 获取或创建集合
        try:
            collection = vector_db.get_collection(name="travel_guides")
        except:
            collection = vector_db.create_collection(name="travel_guides")
        
        # 初始化嵌入模型（使用中文友好的模型）
        try:
            # 使用multilingual模型支持中文
            embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            logger.info("RAG系统初始化成功")
            return True
        except Exception as e:
            logger.error(f"加载嵌入模型失败: {str(e)}")
            # 尝试使用默认模型
            try:
                embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("使用默认嵌入模型")
                return True
            except Exception as e2:
                logger.error(f"加载默认嵌入模型也失败: {str(e2)}")
                return False
                
    except Exception as e:
        logger.error(f"初始化RAG系统失败: {str(e)}")
        return False


def clean_text(text: str) -> str:
    """清理和规范化文本（保留格式和主要内容）"""
    if not text:
        return ""
    
    # 保留换行符，只清理多余的空格（但保留换行）
    # 将多个连续空格替换为单个空格，但保留换行
    text = re.sub(r'[ \t]+', ' ', text)  # 只替换空格和制表符，保留换行
    # 规范化多个连续换行（保留最多2个换行）
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 移除或替换emoji（可选：保留文本内容）
    # 这里我们保留emoji的文本描述，但移除emoji符号本身
    # 常见的emoji模式
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)  # 移除emoji，但保留文本
    
    # 保留中文、英文、数字、基本标点和常见符号
    # 不删除太多内容，只移除真正无用的特殊字符
    # text = re.sub(r'[^\w\s\u4e00-\u9fff，。！？、；：""''（）【】《》\n]', '', text)
    # 上面这行太激进了，我们改为只移除控制字符和特殊空白字符
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)  # 移除控制字符
    
    return text.strip()


def split_text_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """将文本分割成块，用于向量化"""
    if not text:
        return []
    
    # 先按段落分割
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 如果当前块加上新段落不超过chunk_size，就添加
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            # 保存当前块
            if current_chunk:
                chunks.append(current_chunk)
            
            # 如果段落本身很长，需要进一步分割
            if len(para) > chunk_size:
                words = para.split()
                temp_chunk = ""
                for word in words:
                    if len(temp_chunk) + len(word) + 1 <= chunk_size:
                        temp_chunk += " " + word if temp_chunk else word
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk)
                        temp_chunk = word
                if temp_chunk:
                    current_chunk = temp_chunk
            else:
                current_chunk = para
    
    # 添加最后一个块
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def process_xiaohongshu_guide(text: str, title: str = "小红书攻略") -> Dict:
    """
    处理小红书攻略文本
    返回处理后的文本和元数据
    """
    # 清理文本
    cleaned_text = clean_text(text)
    
    # 提取关键信息（使用简单规则）
    destination = ""
    days = ""
    
    # 尝试提取目的地（常见模式）
    destination_patterns = [
        r'去(.+?)(?:旅游|旅行|游玩|攻略)',
        r'(.+?)(?:旅游|旅行|游玩|攻略)',
        r'目的地[：:]\s*(.+)',
        r'地点[：:]\s*(.+)',
    ]
    
    for pattern in destination_patterns:
        match = re.search(pattern, cleaned_text[:500])
        if match:
            destination = match.group(1).strip()
            break
    
    # 尝试提取天数
    days_match = re.search(r'(\d+)\s*天', cleaned_text[:500])
    if days_match:
        days = days_match.group(1)
    
    # 分割文本块
    chunks = split_text_into_chunks(cleaned_text)
    
    return {
        'text': cleaned_text,
        'chunks': chunks,
        'title': title,
        'destination': destination or "未知",
        'days': days or "未知",
        'chunk_count': len(chunks),
        'processed_at': datetime.now().isoformat()
    }


def generate_pdf_from_text(text: str, title: str = "旅游攻略", output_path: Optional[str] = None, use_cleaned_text: bool = False) -> BytesIO:
    """
    从文本生成PDF文件
    返回BytesIO对象
    
    Args:
        text: 原始文本内容
        title: PDF标题
        output_path: 可选的文件保存路径
        use_cleaned_text: 是否使用清理后的文本（默认False，使用原始文本以保留格式）
    """
    buffer = BytesIO()
    
    # 如果不需要清理文本，直接使用原始文本（保留格式）
    # 只做最小限度的处理：移除emoji但保留文本结构
    if not use_cleaned_text:
        # 只移除emoji，保留所有格式和换行
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
            "]+", flags=re.UNICODE)
        text = emoji_pattern.sub('', text)  # 移除emoji
        # 规范化多个连续换行
        text = re.sub(r'\n{3,}', '\n\n', text)
    else:
        # 使用清理后的文本
        text = clean_text(text)
    
    try:
        # 注册中文字体
        # Windows系统常见中文字体路径
        chinese_font_name = 'SimSun'  # 宋体
        font_registered = False
        
        # 尝试注册Windows系统中文字体
        # 优先使用.ttf格式，因为.ttc格式可能需要特殊处理
        windows_font_paths = [
            (r'C:\Windows\Fonts\simhei.ttf', 'SimHei'),   # 黑体
            (r'C:\Windows\Fonts\simsun.ttf', 'SimSun'),   # 宋体（.ttf格式）
            (r'C:\Windows\Fonts\msyh.ttf', 'MicrosoftYaHei'),  # 微软雅黑（.ttf格式）
            (r'C:\Windows\Fonts\simsun.ttc', 'SimSun'),   # 宋体（.ttc格式，备用）
            (r'C:\Windows\Fonts\msyh.ttc', 'MicrosoftYaHei'),  # 微软雅黑（.ttc格式，备用）
        ]
        
        for font_path, font_name in windows_font_paths:
            if os.path.exists(font_path):
                try:
                    # 对于.ttc文件，需要指定字体索引（通常是0）
                    if font_path.endswith('.ttc'):
                        # TTC文件可能需要特殊处理，先尝试直接加载
                        try:
                            pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=0))
                        except:
                            # 如果subfontIndex不支持，尝试不使用索引
                            pdfmetrics.registerFont(TTFont(font_name, font_path))
                    else:
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                    
                    chinese_font_name = font_name
                    font_registered = True
                    logger.info(f"成功注册中文字体: {font_path} (名称: {font_name})")
                    break
                except Exception as e:
                    logger.warning(f"注册字体失败 {font_path}: {str(e)}")
                    continue
        
        # 如果Windows字体都不可用，尝试使用ReportLab内置字体
        if not font_registered:
            try:
                # 使用ReportLab内置的字体（虽然可能不支持中文，但至少不会报错）
                chinese_font_name = 'Helvetica'
                logger.warning("未找到中文字体，使用默认字体（可能无法正确显示中文）")
            except Exception as e:
                logger.error(f"字体注册失败: {str(e)}")
                chinese_font_name = 'Helvetica'
        
        # 创建PDF文档
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # 获取样式
        styles = getSampleStyleSheet()
        
        # 创建自定义样式（支持中文）
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=chinese_font_name,
            fontSize=18,
            textColor='#1459CF',
            spaceAfter=30,
            alignment=1  # 居中
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=chinese_font_name,
            fontSize=14,
            textColor='#1D4C50',
            spaceAfter=12,
            spaceBefore=12
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontName=chinese_font_name,
            fontSize=11,
            leading=16,
            spaceAfter=12
        )
        
        # 构建PDF内容
        story = []
        
        # 标题
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # 生成时间（使用支持中文的样式）
        time_style = ParagraphStyle(
            'TimeStyle',
            parent=styles['Normal'],
            fontName=chinese_font_name,
            fontSize=10
        )
        story.append(Paragraph(
            f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}",
            time_style
        ))
        story.append(Spacer(1, 0.3*inch))
        
        # 处理文本内容
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.1*inch))
                continue
            
            # 判断是否是标题（简单规则）
            if line.startswith('#') or (len(line) < 50 and not line.endswith('。') and not line.endswith('！') and not line.endswith('？')):
                # 可能是标题
                clean_line = line.lstrip('#').strip()
                story.append(Paragraph(clean_line, heading_style))
            else:
                # 普通段落
                story.append(Paragraph(line, body_style))
        
        # 构建PDF
        doc.build(story)
        buffer.seek(0)
        
        # 如果指定了输出路径，也保存到文件
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(buffer.getvalue())
            buffer.seek(0)  # 重置指针
        
        logger.info(f"成功生成PDF: {title}")
        return buffer
        
    except Exception as e:
        logger.error(f"生成PDF失败: {str(e)}")
        raise


def store_guide_to_vector_db(processed_data: Dict, pdf_buffer: Optional[BytesIO] = None) -> bool:
    """
    将处理后的攻略存储到向量数据库
    """
    global vector_db, embedding_model
    
    if not vector_db or not embedding_model:
        logger.error("RAG系统未初始化")
        return False
    
    try:
        collection = vector_db.get_collection(name="travel_guides")
        
        chunks = processed_data.get('chunks', [])
        if not chunks:
            logger.warning("没有文本块可存储")
            return False
        
        # 生成嵌入向量
        embeddings = embedding_model.encode(chunks, show_progress_bar=False)
        
        # 准备元数据
        metadata_list = []
        ids = []
        
        base_id = f"guide_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        for i, chunk in enumerate(chunks):
            metadata = {
                'title': processed_data.get('title', ''),
                'destination': processed_data.get('destination', ''),
                'days': processed_data.get('days', ''),
                'chunk_index': str(i),
                'processed_at': processed_data.get('processed_at', ''),
                'source': 'xiaohongshu'
            }
            metadata_list.append(metadata)
            ids.append(f"{base_id}_chunk_{i}")
        
        # 存储到向量数据库
        collection.add(
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=metadata_list,
            ids=ids
        )
        
        logger.info(f"成功存储 {len(chunks)} 个文本块到向量数据库")
        return True
        
    except Exception as e:
        logger.error(f"存储到向量数据库失败: {str(e)}")
        return False


def search_similar_content(query: str, n_results: int = 5, destination_filter: Optional[str] = None) -> List[Dict]:
    """
    在向量数据库中搜索相似内容
    """
    global vector_db, embedding_model
    
    if not vector_db or not embedding_model:
        logger.warning("RAG系统未初始化，无法进行检索")
        return []
    
    try:
        collection = vector_db.get_collection(name="travel_guides")
        
        # 生成查询向量
        query_embedding = embedding_model.encode([query], show_progress_bar=False)[0]
        
        # 构建查询
        where_clause = {}
        if destination_filter:
            where_clause['destination'] = destination_filter
        
        # 执行搜索
        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=min(n_results, 10),
            where=where_clause if where_clause else None
        )
        
        # 格式化结果
        formatted_results = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else None
                })
        
        logger.info(f"检索到 {len(formatted_results)} 条相关结果")
        return formatted_results
        
    except Exception as e:
        logger.error(f"向量检索失败: {str(e)}")
        return []


def format_rag_context(search_results: List[Dict]) -> str:
    """
    将检索结果格式化为上下文文本，用于LLM提示词
    """
    if not search_results:
        return ""
    
    context = "=== 参考攻略信息 ===\n\n"
    
    for i, result in enumerate(search_results, 1):
        content = result.get('content', '')
        metadata = result.get('metadata', {})
        title = metadata.get('title', '未知标题')
        destination = metadata.get('destination', '')
        
        context += f"[参考 {i}] 来源: {title}"
        if destination:
            context += f" | 目的地: {destination}"
        context += "\n"
        context += f"{content}\n\n"
    
    context += "=== 以上是参考信息，请基于这些信息生成旅游计划 ===\n\n"
    
    return context

