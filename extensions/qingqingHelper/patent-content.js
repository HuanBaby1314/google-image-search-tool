/**
 * Google Patents Content Script
 * 运行在 Isolated World，将 inject.js 注入到页面的 MAIN World
 * 同时负责在 Isolated World 监听 chrome.runtime.onMessage 并转发给 MAIN World
 */
(function () {
    'use strict';

    // 注入 inject.js 到页面上下文
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('inject.js');
    script.onload = function () {
        this.remove(); // 运行完后移除标签保持 DOM 整洁
    };
    (document.head || document.documentElement).appendChild(script);

    // 用于存储从页面获取的 callouts 数据
    let pendingCalloutsResolve = null;

    // 监听来自页面脚本的响应
    window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'PATENT_LABELER_CALLOUTS_RESPONSE') {
            if (pendingCalloutsResolve) {
                pendingCalloutsResolve(event.data.callouts || []);
                pendingCalloutsResolve = null;
            }
        }
    });

    // 从页面获取 callouts 数据（通过 postMessage）
    function fetchCalloutsFromPage() {
        return new Promise((resolve) => {
            pendingCalloutsResolve = resolve;
            window.postMessage({ type: 'PATENT_LABELER_GET_CALLOUTS' }, '*');
            // 超时处理
            setTimeout(() => {
                if (pendingCalloutsResolve) {
                    resolve([]);
                    pendingCalloutsResolve = null;
                }
            }, 3000);
        });
    }

    // 监听来自 popup 的消息
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'toggleOriginal') {
            window.postMessage({
                type: 'PATENT_LABELER_TOGGLE',
                showOriginal: message.showOriginal
            }, '*');
            sendResponse({ success: true });
        } else if (message.action === 'getCallouts') {
            // 从页面获取 callouts 数据
            fetchCalloutsFromPage().then(callouts => {
                sendResponse({ callouts });
            });
            return true; // 异步响应
        } else if (message.action === 'showPatentImage') {
            // 转发显示图片的消息到页面
            window.postMessage({
                type: 'PATENT_LABELER_SHOW_IMAGE',
                filename: message.filename,
                label: message.label
            }, '*');
            sendResponse({ success: true });
        }
    });

    // 读取存储状态并发送给页面
    chrome.storage.local.get(['patentShowOriginal'], (result) => {
        if (result.patentShowOriginal) {
            window.addEventListener('load', () => {
                setTimeout(() => {
                    window.postMessage({
                        type: 'PATENT_LABELER_TOGGLE',
                        showOriginal: true
                    }, '*');
                }, 2000);
            });
        }
    });
})();
