# 旅游计划生成器

一个智能旅游计划生成软件，可以根据您的输入（天数、地点、预算等）自动生成详细的旅游安排。

## 功能特点

- 📅 根据旅游天数自动规划行程
- 🌍 支持多个目的地
- 💰 考虑预算限制
- 🎯 个性化推荐景点和活动
- 📝 详细的每日行程安排
- 🔍 **谷歌搜索集成** - 自动搜索目的地最新信息，生成更准确的计划
- 🔎 **独立搜索功能** - 可以手动搜索景点、餐厅、酒店等旅游信息

## 安装步骤

1. 安装Python依赖：
```bash
pip install -r requirements.txt
```

2. 配置API密钥：
   - 创建 `.env` 文件
   - 在 `.env` 文件中填入你的 API 密钥：
     ```
     DEEPSEEK_API_KEY=你的DeepSeek API密钥
     GOOGLE_API_KEY=你的Google API密钥（可选，用于搜索功能）
     GOOGLE_SEARCH_ENGINE_ID=你的Google搜索引擎ID（可选，用于搜索功能）
     ```
   
   **注意**：
   - 如果不配置Google API密钥，应用仍可正常使用
   - 搜索功能会降级为简化模式（只提供搜索链接，不显示详细结果）
   - 配置API后可以获得完整的搜索结果和自动搜索功能

3. 运行应用：
```bash
python app.py
```

4. 在浏览器中打开 `http://localhost:5000`

## 使用方法

1. 输入旅游天数
2. 输入目的地（可以是一个或多个城市）
3. 可选：输入预算、兴趣偏好等
4. 点击"生成计划"按钮
5. 等待AI生成详细的旅游计划

## 注意事项

- 需要有效的 DeepSeek API 密钥
- 谷歌搜索功能需要配置 Google Custom Search API（可选）
- 首次使用可能需要一些时间来生成计划
- 建议提供尽可能详细的信息以获得更好的计划
- DeepSeek API 使用 OpenAI 兼容的接口，价格更实惠

## 获取 Google Custom Search API 密钥（可选）

如果您想使用谷歌搜索功能：

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 启用 "Custom Search API"
4. 创建 API 密钥
5. 访问 [Google Custom Search](https://programmablesearchengine.google.com/) 创建搜索引擎
6. 获取搜索引擎 ID (CX)
7. 将 API 密钥和搜索引擎 ID 添加到 `.env` 文件中

