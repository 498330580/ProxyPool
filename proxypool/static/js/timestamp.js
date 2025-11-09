/**
 * 通用时间戳更新脚本
 * 在所有页面中自动更新 footer 中的最后刷新时间
 */

(function() {
    'use strict';

    // 更新时间戳的函数
    function updateTimestamp() {
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

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            // 立即更新一次
            updateTimestamp();
            // 每秒更新一次
            setInterval(updateTimestamp, 1000);
        });
    } else {
        // 如果脚本在 DOMContentLoaded 之后加载
        updateTimestamp();
        setInterval(updateTimestamp, 1000);
    }
})();
