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
        this.bindEvents();
        this.startAutoRefresh();
        this.loadDashboardData();
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

    // 加载仪表盘数据
    async loadDashboardData() {
        try {
            // 加载统计数据
            await this.loadStats();
            // 加载代理列表
            await this.loadProxies();
            // 更新时间戳
            this.updateTimestamp();
        } catch (error) {
            console.error('加载仪表盘数据失败:', error);
            notifyUtils.error('加载数据失败');
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
        const tbody = document.getElementById('proxiesTableBody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4"><span class="spinner"></span> 加载中...</td></tr>';
        }

        try {
            const offset = (this.currentPage - 1) * this.pageSize;
            const response = await fetch(`/api/proxies?limit=${this.pageSize}&offset=${offset}`);
            
            if (!response.ok) throw new Error('加载代理列表失败');
            
            const data = await response.json();
            this.renderProxiesTable(data.proxies || []);
            this.renderPagination(data.total || 0);
        } catch (error) {
            console.error('加载代理列表失败:', error);
            if (tbody) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger py-4">加载数据失败，请你汀候重试</td></tr>';
            }
        }
    }

    // 渲染代理表格
    renderProxiesTable(proxies) {
        const tbody = document.getElementById('proxiesTableBody');
        if (!tbody) return;

        if (proxies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">暂无代理</td></tr>';
            return;
        }

        tbody.innerHTML = proxies.map((proxy, index) => `
            <tr>
                <td>${(this.currentPage - 1) * this.pageSize + index + 1}</td>
                <td>
                    <code>${this.escapeHtml(proxy.proxy || 'N/A')}</code>
                    <button class="btn btn-sm btn-link" onclick="dashboard.copyProxy('${proxy.proxy}')" title="复制">
                        📋
                    </button>
                </td>
                <td>
                    <span class="badge" style="background-color: ${this.getScoreColor(proxy.score)}">
                        ${proxy.score || 0}分
                    </span>
                </td>
                <td>${proxy.last_checked || 'N/A'}</td>
            </tr>
        `).join('');
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
            elem.textContent = formatUtils.formatDate(new Date(), 'HH:mm:ss');
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
