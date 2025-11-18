document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('travelForm');
    const generateBtn = document.getElementById('generateBtn');
    const btnText = document.querySelector('.btn-text');
    const btnLoader = document.querySelector('.btn-loader');
    const resultContainer = document.getElementById('resultContainer');
    const errorContainer = document.getElementById('errorContainer');
    const planContent = document.getElementById('planContent');
    const copyBtn = document.getElementById('copyBtn');
    
    // 搜索功能
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const searchResults = document.getElementById('searchResults');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // 隐藏之前的结果和错误
        resultContainer.style.display = 'none';
        errorContainer.style.display = 'none';
        
        // 获取表单数据
        const formData = {
            days: document.getElementById('days').value,
            destination: document.getElementById('destination').value,
            budget: document.getElementById('budget').value,
            preferences: document.getElementById('preferences').value
        };
        
        // 显示加载状态
        generateBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoader.style.display = 'inline';
        
        try {
            // 设置超时（60秒）
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000);
            
            const response = await fetch('/api/generate-plan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                // 显示结果
                planContent.textContent = data.plan;
                resultContainer.style.display = 'block';
                
                // 将markdown格式转换为HTML（简单处理）
                planContent.innerHTML = formatPlan(data.plan);
                
                // 滚动到结果区域
                resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                // 显示错误
                let errorMsg = data.error || '生成计划时出错，请稍后重试';
                if (data.detail) {
                    console.error('详细错误信息:', data.detail);
                }
                showError(errorMsg);
            }
        } catch (error) {
            console.error('Error:', error);
            if (error.name === 'AbortError') {
                showError('请求超时，请稍后重试。如果问题持续，请检查网络连接或API配置。');
            } else {
                showError('网络错误，请检查您的连接或API配置。错误详情：' + error.message);
            }
        } finally {
            // 恢复按钮状态
            generateBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    });

    // 搜索功能
    searchBtn.addEventListener('click', async function() {
        const query = searchInput.value.trim();
        if (!query) {
            alert('请输入搜索关键词');
            return;
        }
        
        searchBtn.disabled = true;
        searchBtn.textContent = '搜索中...';
        searchResults.style.display = 'none';
        
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                displaySearchResults(data.results, data.using_api !== false);
                searchResults.style.display = 'block';
                searchResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                alert(data.error || '搜索失败，请稍后重试');
            }
        } catch (error) {
            console.error('搜索错误:', error);
            alert('搜索时出错：' + error.message);
        } finally {
            searchBtn.disabled = false;
            searchBtn.textContent = '搜索';
        }
    });
    
    // 支持回车键搜索
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchBtn.click();
        }
    });
    
    function displaySearchResults(results, usingApi = true) {
        if (results.length === 0) {
            searchResults.innerHTML = '<p style="text-align: center; color: #999; padding: 20px;">未找到相关结果</p>';
            return;
        }
        
        let html = '<h3 style="margin-bottom: 15px; color: #333;">搜索结果：</h3>';
        
        if (!usingApi) {
            html += '<div style="background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 8px; margin-bottom: 20px; color: #856404;">';
            html += '<strong>提示：</strong>未配置Google API，显示的是搜索链接。配置API后可获得更详细的搜索结果。';
            html += '</div>';
        }
        
        results.forEach(result => {
            if (result.is_link_only) {
                html += `
                    <div class="search-result-item">
                        <h3><a href="${result.link}" target="_blank">${result.title}</a></h3>
                        <p>${result.snippet}</p>
                        <div class="result-link"><a href="${result.link}" target="_blank">点击访问Google搜索</a></div>
                    </div>
                `;
            } else {
                html += `
                    <div class="search-result-item">
                        <h3><a href="${result.link}" target="_blank">${result.title}</a></h3>
                        <p>${result.snippet}</p>
                        <div class="result-link"><a href="${result.link}" target="_blank">${result.link}</a></div>
                    </div>
                `;
            }
        });
        searchResults.innerHTML = html;
    }

    // 复制功能
    copyBtn.addEventListener('click', function() {
        const text = planContent.textContent || planContent.innerText;
        navigator.clipboard.writeText(text).then(function() {
            const originalText = copyBtn.textContent;
            copyBtn.textContent = '已复制！';
            copyBtn.style.background = '#28a745';
            setTimeout(function() {
                copyBtn.textContent = originalText;
                copyBtn.style.background = '#6c757d';
            }, 2000);
        }).catch(function(err) {
            console.error('复制失败:', err);
            alert('复制失败，请手动选择文本复制');
        });
    });

    function showError(message) {
        errorContainer.style.display = 'block';
        errorContainer.querySelector('.error-message').textContent = message;
        errorContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function formatPlan(text) {
        // 简单的markdown到HTML转换
        let html = text;
        
        // 标题
        html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
        
        // 粗体
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // 列表项
        html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
        
        // 将连续的列表项包装在ul标签中
        html = html.replace(/(<li>.*<\/li>\n?)+/g, function(match) {
            return '<ul>' + match.replace(/\n/g, '') + '</ul>';
        });
        
        // 换行
        html = html.replace(/\n\n/g, '</p><p>');
        html = '<p>' + html + '</p>';
        
        return html;
    }
});

