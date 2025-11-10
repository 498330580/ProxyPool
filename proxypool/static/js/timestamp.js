/**
 * 最后刷新时间戳管理
 * 记录最后一次加载数据的时间，而不是当前系统时间
 */

(function() {
    'use strict';

    // 更新最后刷新时间
    function setLastRefreshTime() {
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

    // 全局函数：供其他脚本沙佐使用
    window.updateLastRefreshTime = setLastRefreshTime;

    // 页面加载完成后初始化一次
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setLastRefreshTime();
        });
    } else {
        // 如果脚本在 DOMContentLoaded 之后加载
        setLastRefreshTime();
    }
})();

