/**
 * ProxyPool 管理面板 - 仪表盘脚本
 */

class Dashboard {
    constructor() {
        this.refreshInterval = 30000; // 30秒刷新一次
        this.currentPage = 1;
        this.pageSize = 20;
        this.init();
    }

    init() {
        // 动态设置API主机地址
        this.updateApiHostDisplay();
        this.bindEvents();
        // 立即更新一次时间戳（不要需要等待数据加载）
        this.updateTimestamp();
        this.startAutoRefresh();
        this.loadDashboardData();
    }

    // 动态设置API主机地址和端口
    updateApiHostDisplay() {
        const apiHostDisplay = document.getElementById('apiHostDisplay');
        const apiPortDisplay = document.getElementById('apiPortDisplay');
        
        if (apiHostDisplay) {
            // 只取主机名或IP，不包含端口
            const hostname = window.location.hostname; // 不包含端口
            apiHostDisplay.textContent = hostname;
        }
        
        if (apiPortDisplay) {
            // 动态获取当前页面的端口
            const port = window.location.port || (window.location.protocol === 'https:' ? '443' : '80');
            apiPortDisplay.textContent = port;
        }
    }

    bindEvents() {
        // 搜索框事件
        const searchInput = document.getElementById('proxySearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.filterProxies(e.target.value);
                }, 300);
            });
        }

        // 刷新按钮
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDashboardData();
            });
        }

        // 导出按钮
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.exportProxies();
            });
        }

        // 分页按钮
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('page-link')) {
                const page = parseInt(e.target.dataset.page);
                this.goToPage(page);
            }
        });
    }

    // 加载仪表板数据
    async loadDashboardData() {
        try {
            // 加载统计数据
            await this.loadStats();
            // 加载代理列表
            await this.loadProxies();
        } catch (error) {
            console.error('加载仪表板数据失败:', error);
            notifyUtils.error('加载数据失败');
        } finally {
            // 无论是否成功，都要更新最后刷新时间
            if (typeof window.updateLastRefreshTime === 'function') {
                window.updateLastRefreshTime();
            }
        }
    }

    // 加载统计信息
    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            if (!response.ok) throw new Error('加载统计信息失败');
            
            const data = await response.json();
            this.updateStats(data);
        } catch (error) {
            console.error('加载统计信息失败:', error);
        }
    }

    // 更新统计卡片
    updateStats(data) {
        const elements = {
            'proxyCount': data.proxy_count || 0,
            'crawlerCount': data.crawler_count || 0,
            'systemStatus': data.status || '未知',
            'avgScore': data.avg_score || 0
        };

        for (const [elementId, value] of Object.entries(elements)) {
            const elem = document.getElementById(elementId);
            if (elem) {
                elem.textContent = value;
                elem.classList.add('fade-in');
            }
        }
    }

    // 加载代理列表
    async loadProxies() {
        const container = document.getElementById('proxiesTableContainer');
        if (!container) {
            console.error('proxiesTableContainer not found');
            return;
        }
        
        // 确保表格结构存在
        let tbody = document.getElementById('proxiesTableBody');
        if (!tbody) {
            console.warn('proxiesTableBody not found, rebuilding table structure');
            container.innerHTML = '<table class="table table-hover"><thead><tr><th style="width: 50px;">#</th><th>代理地址</th><th style="width: 80px;">分数</th><th style="width: 150px;">最后检查</th></tr></thead><tbody id="proxiesTableBody"><tr><td colspan="4" class="text-center text-muted py-4"><span class="spinner"></span> 加载中...</td></tr></tbody></table>';
            tbody = document.getElementById('proxiesTableBody');
            console.log('Table rebuilt, tbody found:', !!tbody);
        } else {
            // tbody 存在，只更新内容
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4"><span class="spinner"></span> 加载中...</td></tr>';
        }

        try {
            const offset = (this.currentPage - 1) * this.pageSize;
            const response = await fetch(`/api/proxies?limit=${this.pageSize}&offset=${offset}`);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            
            // 验证数据
            if (!data || !Array.isArray(data.proxies)) {
                throw new Error('Invalid response format');
            }
            
            // 重新获取 tbody
            const updatedTbody = document.getElementById('proxiesTableBody');
            if (updatedTbody) {
                this.renderProxiesTable(data.proxies || []);
                this.renderPagination(data.total || 0);
            } else {
                console.error('proxiesTableBody disappeared after fetch');
                throw new Error('表格元素丢失');
            }
        } catch (error) {
            console.error('加载代理列表失败:', error);
            const currentTbody = document.getElementById('proxiesTableBody');
            if (currentTbody) {
                currentTbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-4">加载数据失败，请稍候重试</td></tr>';
            }
        }
    }

    // 渲染代理表格
    renderProxiesTable(proxies) {
        const tbody = document.getElementById('proxiesTableBody');
        if (!tbody) {
            console.error('proxiesTableBody not found for rendering');
            return;
        }

        if (!Array.isArray(proxies) || proxies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">暂无代理</td></tr>';
            return;
        }

        try {
            tbody.innerHTML = proxies.map((proxy, index) => {
                const rowNum = (this.currentPage - 1) * this.pageSize + index + 1;
                const proxyStr = this.escapeHtml(proxy.proxy || 'N/A');
                const score = proxy.score || 0;
                const scoreColor = this.getScoreColor(score);
                const lastChecked = this.escapeHtml(proxy.last_checked || 'N/A');
                
                return `<tr style="height: 32px;">
                    <td style="padding: 0.25rem 0.5rem; vertical-align: middle;">${rowNum}</td>
                    <td style="padding: 0.25rem 0.5rem; vertical-align: middle;">
                        <code style="font-size: 0.8rem;">${proxyStr}</code>
                        <button class="btn btn-sm btn-link" onclick="dashboard.copyProxy('${proxy.proxy}')" title="复制" style="padding: 0; margin-left: 0.2rem; line-height: 1;">
                            <i class="bi bi-clipboard" style="font-size: 0.75rem;"></i>
                        </button>
                    </td>
                    <td style="padding: 0.25rem 0.5rem; vertical-align: middle;">
                        <span class="badge" style="background-color: ${scoreColor}; font-size: 0.75rem; padding: 0.25rem 0.4rem;" data-score="${score}">
                            ${score}分
                        </span>
                    </td>
                    <td style="padding: 0.25rem 0.5rem; vertical-align: middle;"><small style="font-size: 0.75rem;">${lastChecked}</small></td>
                </tr>`;
            }).join('');
        } catch (error) {
            console.error('Failed to render proxies table:', error);
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-4">表格渲染失败</td></tr>';
        }
    }

    // 获取分数对应的颜色
    getScoreColor(score) {
        if (score >= 80) return '#198754'; // 绿色
        if (score >= 60) return '#0dcaf0'; // 蓝色
        if (score >= 40) return '#ffc107'; // 黄色
        return '#dc3545'; // 红色
    }

    // 渲染分页
    renderPagination(total) {
        const paginationContainer = document.getElementById('pagination');
        if (!paginationContainer) return;

        const totalPages = Math.ceil(total / this.pageSize);
        if (totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }

        let html = '<nav><ul class="pagination">';
        
        // 上一页
        html += `<li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${this.currentPage - 1}">上一页</a>
        </li>`;

        // 页码
        for (let i = Math.max(1, this.currentPage - 2); i <= Math.min(totalPages, this.currentPage + 2); i++) {
            html += `<li class="page-item ${i === this.currentPage ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${i}">${i}</a>
            </li>`;
        }

        // 下一页
        html += `<li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${this.currentPage + 1}">下一页</a>
        </li>`;

        html += '</ul></nav>';
        paginationContainer.innerHTML = html;
    }

    // 过滤代理
    filterProxies(keyword) {
        // 这里可以在客户端过滤或者发送请求到服务器
        if (!keyword) {
            this.loadProxies();
            return;
        }

        const rows = document.querySelectorAll('#proxiesTableBody tr');
        let visibleCount = 0;

        rows.forEach(row => {
            const proxyCell = row.querySelector('td:nth-child(2) code');
            if (proxyCell && proxyCell.textContent.includes(keyword)) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        if (visibleCount === 0) {
            notifyUtils.info(`未找到包含 "${keyword}" 的代理`);
        }
    }

    // 复制代理
    copyProxy(proxy) {
        clipboardUtils.copy(proxy).then(success => {
            if (success) {
                notifyUtils.success(`已复制: ${proxy}`);
            }
        });
    }

    // 导出代理
    exportProxies() {
        const proxies = [];
        const rows = document.querySelectorAll('#proxiesTableBody tr');
        
        rows.forEach(row => {
            const proxyCell = row.querySelector('td:nth-child(2) code');
            if (proxyCell && proxyCell.style.display !== 'none') {
                proxies.push({
                    proxy: proxyCell.textContent.trim(),
                    score: row.querySelector('td:nth-child(3)').textContent.trim(),
                    checked: row.querySelector('td:nth-child(4)').textContent.trim()
                });
            }
        });

        if (proxies.length === 0) {
            notifyUtils.warning('没有可导出的代理');
            return;
        }

        const date = formatUtils.formatDate(new Date(), 'YYYY-MM-DD_HH-mm-ss');
        exportUtils.exportTXT(proxies.map(p => p.proxy), `proxies_${date}.txt`);
        notifyUtils.success(`已导出 ${proxies.length} 个代理`);
    }

    // 跳转到指定页
    goToPage(page) {
        if (page > 0) {
            this.currentPage = page;
            this.loadProxies();
            // 滚动到表格
            document.getElementById('proxiesTableContainer')?.scrollIntoView({ behavior: 'smooth' });
        }
    }

    // 更新时间戳
    updateTimestamp() {
        const elem = document.getElementById('lastRefresh');
        if (elem) {
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            const seconds = String(now.getSeconds()).padStart(2, '0');
            const timeStr = `${hours}:${minutes}:${seconds}`;
            elem.textContent = timeStr;
        }
    }

    // 开始自动刷新
    startAutoRefresh() {
        setInterval(() => {
            this.loadDashboardData();
        }, this.refreshInterval);
    }

    // HTML 转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
