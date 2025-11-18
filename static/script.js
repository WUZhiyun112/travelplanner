document.addEventListener('DOMContentLoaded', function() {
    console.log('页面加载完成，初始化脚本...');
    
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
    
    // 调试信息显示
    const debugContainer = document.getElementById('debugContainer');
    const debugContent = document.getElementById('debugContent');
    
    // 调试日志函数
    function debugLog(message, data = null) {
        const timestamp = new Date().toLocaleTimeString();
        let logMessage = `[${timestamp}] ${message}`;
        if (data) {
            logMessage += '\n' + JSON.stringify(data, null, 2);
        }
        
        // 显示在页面上
        if (debugContainer && debugContent) {
            debugContainer.style.display = 'block';
            debugContent.textContent += logMessage + '\n\n';
            debugContent.scrollTop = debugContent.scrollHeight;
        }
        
        // 同时输出到控制台
        console.log(message, data || '');
    }
    
    // 检查元素是否存在
    const elementsCheck = {
        searchInput: !!searchInput,
        searchBtn: !!searchBtn,
        searchResults: !!searchResults
    };
    debugLog('搜索元素检查', elementsCheck);
    
    if (!searchInput || !searchBtn || !searchResults) {
        debugLog('错误: 搜索元素未找到', elementsCheck);
    }

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
        btnLoader.textContent = '正在搜索和提取网页内容，请稍候...';
        
        try {
            debugLog('准备发送生成计划请求', formData);
            
            // 设置超时（120秒，因为需要搜索和提取网页）
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000);
            
            debugLog('发送请求到 /api/generate-plan...');
            const response = await fetch('/api/generate-plan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
                signal: controller.signal,
                credentials: 'same-origin'
            });
            
            clearTimeout(timeoutId);
            
            debugLog('收到服务器响应', { status: response.status, ok: response.ok, statusText: response.statusText });
            
            if (!response.ok) {
                const errorText = await response.text();
                debugLog('服务器返回错误', { status: response.status, error: errorText });
                throw new Error(`HTTP错误: ${response.status} - ${errorText.substring(0, 100)}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                // 显示结果
                planContent.textContent = data.plan;
                resultContainer.style.display = 'block';
                
                // 将markdown格式转换为HTML（简单处理）
                planContent.innerHTML = formatPlan(data.plan);
                
                // 如果有参考链接，在末尾添加
                if (data.references && data.references.length > 0) {
                    let referencesHtml = '<div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #e0e0e0;">';
                    referencesHtml += '<h3 style="color: #667eea; margin-bottom: 15px;">📚 参考资料来源</h3>';
                    referencesHtml += '<p style="color: #666; margin-bottom: 15px;">本计划基于以下网络资源生成，您可以点击链接查看原文：</p>';
                    referencesHtml += '<ul style="list-style: none; padding: 0;">';
                    data.references.forEach((ref, index) => {
                        if (ref.link) {
                            referencesHtml += `<li style="margin-bottom: 10px;"><a href="${ref.link}" target="_blank" style="color: #667eea; text-decoration: none; word-break: break-all;">${index + 1}. ${ref.title || ref.link}</a></li>`;
                        } else {
                            referencesHtml += `<li style="margin-bottom: 10px; color: #666;">${index + 1}. ${ref.title || '无标题'}</li>`;
                        }
                    });
                    referencesHtml += '</ul>';
                    referencesHtml += '<p style="color: #999; font-size: 0.9em; margin-top: 15px; font-style: italic;">*注：以上链接仅供参考，请以实际情况为准。*</p>';
                    referencesHtml += '</div>';
                    planContent.innerHTML += referencesHtml;
                }
                
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
            debugLog('生成计划出错', { 
                name: error.name, 
                message: error.message,
                stack: error.stack 
            });
            
            let errorMsg = '生成计划时出错：';
            if (error.name === 'AbortError') {
                errorMsg = '请求超时（超过120秒）。这可能是正常的，因为需要搜索和提取多个网页内容。请稍后重试。';
            } else if (error.message === 'Failed to fetch') {
                errorMsg = '无法连接到服务器。请检查：\n1. 服务器是否正在运行（运行 python app.py）\n2. 服务器地址是否正确\n3. 网络连接是否正常';
            } else {
                errorMsg += error.message;
            }
            
            showError(errorMsg);
        } finally {
            // 恢复按钮状态
            generateBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
        }
    });

    // 搜索功能
    if (searchBtn) {
        searchBtn.addEventListener('click', async function(e) {
            e.preventDefault(); // 防止默认行为
            debugLog('搜索按钮被点击');
            
            const query = searchInput ? searchInput.value.trim() : '';
            if (!query) {
                alert('请输入搜索关键词');
                debugLog('错误: 搜索关键词为空');
                return;
            }
            
            debugLog('开始搜索', { query: query });
            searchBtn.disabled = true;
            searchBtn.textContent = '搜索中...';
            if (searchResults) {
                searchResults.style.display = 'none';
            }
        
        try {
            debugLog('发送搜索请求到服务器...');
            debugLog('请求URL: /api/search');
            debugLog('请求数据', { query: query });
            
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query }),
                credentials: 'same-origin'  // 确保发送cookie
            });
            
            debugLog('收到服务器响应', { status: response.status, ok: response.ok, statusText: response.statusText });
            
            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }
            
            const data = await response.json();
            debugLog('解析响应数据', { success: data.success, resultsCount: data.results ? data.results.length : 0 });
            
            if (data.success) {
                displaySearchResults(data.results, data.using_api !== false);
                if (searchResults) {
                    searchResults.style.display = 'block';
                    searchResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                debugLog('搜索成功，显示结果');
            } else {
                const errorMsg = data.error || '搜索失败，请稍后重试';
                debugLog('搜索失败', { error: errorMsg });
                alert(errorMsg);
            }
        } catch (error) {
            debugLog('搜索出错', { 
                name: error.name, 
                message: error.message,
                stack: error.stack 
            });
            
            // 提供更友好的错误信息
            let errorMsg = '搜索时出错：';
            if (error.message === 'Failed to fetch') {
                errorMsg = '无法连接到服务器。请检查：\n1. 服务器是否正在运行\n2. 网络连接是否正常\n3. 服务器地址是否正确';
            } else {
                errorMsg += error.message;
            }
            
            alert(errorMsg);
        } finally {
            if (searchBtn) {
                searchBtn.disabled = false;
                searchBtn.textContent = '搜索';
            }
        }
        });
    } else {
        debugLog('错误: 搜索按钮元素未找到，无法绑定事件');
    }
    
    // 支持回车键搜索
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (searchBtn) {
                    searchBtn.click();
                }
            }
        });
    }
    
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

