/**
 * ProxyPool 管理面板 - 实用工具
 */

// 数据格式化工具
const formatUtils = {
    // 格式化数字（添加千位分隔符）
    formatNumber(num) {
        return Number(num).toLocaleString('zh-CN');
    },

    // 格式化字节
    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    // 格式化时间
    formatTime(seconds) {
        if (seconds < 60) return Math.floor(seconds) + 's';
        if (seconds < 3600) return Math.floor(seconds / 60) + 'm';
        return Math.floor(seconds / 3600) + 'h';
    },

    // 格式化日期
    formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
        if (typeof date === 'string') date = new Date(date);
        const pad = (n) => n < 10 ? '0' + n : n;
        const map = {
            YYYY: date.getFullYear(),
            MM: pad(date.getMonth() + 1),
            DD: pad(date.getDate()),
            HH: pad(date.getHours()),
            mm: pad(date.getMinutes()),
            ss: pad(date.getSeconds()),
        };
        return format.replace(/YYYY|MM|DD|HH|mm|ss/g, m => map[m]);
    }
};

// UI 通知工具
const notifyUtils = {
    // 显示 Toast 通知
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show`;
        toast.setAttribute('role', 'alert');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            animation: slideIn 0.3s ease-out;
        `;
        toast.innerHTML = `
            <span>${message}</span>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(toast);
        
        if (duration > 0) {
            setTimeout(() => {
                toast.remove();
            }, duration);
        }
        
        return toast;
    },

    // 显示成功消息
    success(message, duration = 3000) {
        return this.showToast(message, 'success', duration);
    },

    // 显示错误消息
    error(message, duration = 4000) {
        return this.showToast(message, 'danger', duration);
    },

    // 显示警告消息
    warning(message, duration = 3000) {
        return this.showToast(message, 'warning', duration);
    },

    // 显示信息消息
    info(message, duration = 3000) {
        return this.showToast(message, 'info', duration);
    }
};

// 复制到剪贴板
const clipboardUtils = {
    copy(text) {
        return navigator.clipboard.writeText(text)
            .then(() => {
                notifyUtils.success('已复制到剪贴板');
                return true;
            })
            .catch(() => {
                notifyUtils.error('复制失败');
                return false;
            });
    },

    // 从剪贴板读取
    paste() {
        return navigator.clipboard.readText()
            .catch(() => {
                notifyUtils.error('无法访问剪贴板');
                return null;
            });
    }
};

// DOM 操作工具
const domUtils = {
    // 显示加载状态
    showLoading(element) {
        if (typeof element === 'string') {
            element = document.querySelector(element);
        }
        element.innerHTML = '<span class="spinner"></span> 加载中...';
        element.disabled = true;
    },

    // 隐藏加载状态
    hideLoading(element, text = '完成') {
        if (typeof element === 'string') {
            element = document.querySelector(element);
        }
        element.textContent = text;
        element.disabled = false;
    },

    // 显示空状态
    showEmpty(container, message = '暂无数据') {
        if (typeof container === 'string') {
            container = document.querySelector(container);
        }
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>${message}</p>
            </div>
        `;
    }
};

// 数据验证工具
const validateUtils = {
    // 检查 IP 地址格式
    isValidIP(ip) {
        const ipv4 = /^(\d{1,3}\.){3}\d{1,3}$/;
        if (!ipv4.test(ip)) return false;
        return ip.split('.').every(part => parseInt(part) <= 255);
    },

    // 检查端口号
    isValidPort(port) {
        port = parseInt(port);
        return port > 0 && port < 65536;
    },

    // 检查代理格式 (IP:PORT)
    isValidProxy(proxy) {
        const parts = proxy.trim().split(':');
        if (parts.length !== 2) return false;
        return this.isValidIP(parts[0]) && this.isValidPort(parts[1]);
    },

    // 检查 URL
    isValidURL(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    }
};

// 数据导出工具
const exportUtils = {
    // 导出为 CSV
    exportCSV(data, filename = 'export.csv') {
        const csv = this._arrayToCSV(data);
        this._downloadFile(csv, filename, 'text/csv;charset=utf-8;');
    },

    // 导出为 JSON
    exportJSON(data, filename = 'export.json') {
        const json = JSON.stringify(data, null, 2);
        this._downloadFile(json, filename, 'application/json;charset=utf-8;');
    },

    // 导出为 TXT
    exportTXT(data, filename = 'export.txt') {
        const text = Array.isArray(data) ? data.join('\n') : data;
        this._downloadFile(text, filename, 'text/plain;charset=utf-8;');
    },

    // 私有方法：数组转 CSV
    _arrayToCSV(data) {
        if (!Array.isArray(data) || data.length === 0) return '';
        
        const headers = Object.keys(data[0]);
        const rows = data.map(item => 
            headers.map(h => {
                const value = item[h];
                if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                    return `"${value.replace(/"/g, '""')}"`;
                }
                return value;
            }).join(',')
        );
        
        return [headers.join(','), ...rows].join('\n');
    },

    // 私有方法：下载文件
    _downloadFile(content, filename, type) {
        const blob = new Blob([content], { type });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
};

// API 请求工具
const apiUtils = {
    // GET 请求
    async get(url, options = {}) {
        return this._request(url, 'GET', null, options);
    },

    // POST 请求
    async post(url, data, options = {}) {
        return this._request(url, 'POST', data, options);
    },

    // PUT 请求
    async put(url, data, options = {}) {
        return this._request(url, 'PUT', data, options);
    },

    // DELETE 请求
    async delete(url, options = {}) {
        return this._request(url, 'DELETE', null, options);
    },

    // 私有方法：发送请求
    async _request(url, method = 'GET', data = null, options = {}) {
        const config = {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            const contentType = response.headers.get('content-type');
            
            let result;
            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
            } else {
                result = await response.text();
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${result.message || result}`);
            }

            return { success: true, data: result };
        } catch (error) {
            console.error('API 请求失败:', error);
            return { success: false, error: error.message };
        }
    }
};

// 性能监控工具
const performanceUtils = {
    // 记录时间
    markStart(label) {
        performance.mark(`${label}-start`);
    },

    markEnd(label) {
        performance.mark(`${label}-end`);
        try {
            performance.measure(label, `${label}-start`, `${label}-end`);
            const measure = performance.getEntriesByName(label)[0];
            console.log(`⏱️ ${label}: ${measure.duration.toFixed(2)}ms`);
        } catch (e) {
            console.warn('Performance API 不可用');
        }
    }
};

// 添加通用的页面加载动画
document.addEventListener('DOMContentLoaded', () => {
    // 为所有需要自动刷新的元素添加类
    const autoRefreshElements = document.querySelectorAll('[data-auto-refresh]');
    autoRefreshElements.forEach(elem => {
        elem.classList.add('fade-in');
    });

    // 添加响应式设计支持
    if (window.matchMedia('(max-width: 768px)').matches) {
        document.body.classList.add('mobile-view');
    }
});
