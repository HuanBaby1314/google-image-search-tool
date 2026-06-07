/**
 * Google Patents 标号高亮脚本
 * 运行在页面的 MAIN World 中，可访问 search-app 状态
 * 功能：提取 images 中的 callouts label，高亮 Claims 文本中的对应标号
 */
(function () {
    'use strict';

    const HIGHLIGHT_CLASS = 'patent-label-highlight';
    const STYLE_ID = 'patent-label-highlight-style';

    // 保存原始 claims HTML
    let originalClaimsHtml = null;
    // 用户是否明确选择显示原文
    let userWantsOriginal = false;

    // 注入高亮样式
    function injectStyles() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = `
            .${HIGHLIGHT_CLASS} {
                background-color: #fff3cd;
                font-weight: bold;
                padding: 0 2px;
                border-radius: 3px;
                border: 1px solid #ffeba2;
                cursor: pointer;
                transition: all 0.2s;
            }
            .${HIGHLIGHT_CLASS}:hover {
                background-color: #ffecb3;
                border-color: #ffb300;
                box-shadow: 0 0 4px rgba(255, 179, 0, 0.4);
            }
            .patent-label-counter {
                position: fixed;
                bottom: 16px;
                right: 16px;
                background: #409eff;
                color: #fff;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 12px;
                z-index: 99999;
                box-shadow: 0 2px 8px rgba(64, 158, 255, 0.4);
                animation: patentLabelFadeIn 0.3s ease;
                cursor: pointer;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            }
            .patent-label-counter:hover {
                background: #66b1ff;
            }
            @keyframes patentLabelFadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        `;
        document.head.appendChild(style);
    }

    // 等待页面数据加载
    function waitForData(callback, maxWait = 15000) {
        const startTime = Date.now();

        function check() {
            const searchApp = document.querySelector('body > search-app');
            if (searchApp && searchApp.state && searchApp.state.result && searchApp.state.result.data) {
                callback(searchApp.state.result.data);
                return;
            }

            if (Date.now() - startTime < maxWait) {
                setTimeout(check, 500);
            } else {
                console.warn('[Patent Labeler] 页面数据加载超时，尝试从 DOM 提取');
                tryExtractFromDOM();
            }
        }

        check();
    }

    // 转义正则特殊字符
    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // 从 search-app state 提取 callouts，按 label 分组
    function extractLabels(data) {
        const images = data.images || [];
        const callouts = images.flatMap(img => img.callouts || []);

        // 打印 callouts 结构以便调试
        console.log('[Patent Labeler] callouts 原始数据:', JSON.stringify(callouts, null, 2));

        // 按 label 分组（key 使用小写，保留原始 label 用于显示）
        const labelMap = {};
        const originalLabelMap = {}; // 小写 -> 原始 label

        for (const c of callouts) {
            if (typeof c === 'object' && c !== null && c.label) {
                const lowerLabel = c.label.toLowerCase();
                if (!labelMap[lowerLabel]) {
                    labelMap[lowerLabel] = [];
                    originalLabelMap[lowerLabel] = c.label; // 保留原始大小写
                }
                // id 去重
                if (!labelMap[lowerLabel].includes(c.id)) {
                    labelMap[lowerLabel].push(c.id);
                }
            }
        }

        // 按 label 长度从长到短排序，优先匹配更长的文案
        const sortedLabels = Object.keys(labelMap).sort((a, b) => b.length - a.length);

        console.log('[Patent Labeler] label 分组映射:', labelMap);
        console.log('[Patent Labeler] originalLabelMap:', originalLabelMap);
        console.log('[Patent Labeler] 排序后的 labels:', sortedLabels);

        return { labelMap, sortedLabels, originalLabelMap };
    }

    // 从 searchApp 获取 claims 原始 HTML
    function getOriginalClaimsHtml(data) {
        // claims 的原始内容在 data.claims.content 中
        if (data.claims && data.claims.content) {
            return data.claims.content;
        }
        // 如果没有直接的 claims 字段，尝试其他可能的位置
        if (data.result && data.result.claims && data.result.claims.content) {
            return data.result.claims.content;
        }
        return null;
    }

    // 高亮 Claims 中的标号
    function highlightClaims({ labelMap, sortedLabels, originalLabelMap }, data) {
        if (!sortedLabels.length) {
            console.log('[Patent Labeler] 未找到任何 callouts label');
            return 0;
        }

        console.log('[Patent Labeler] 获取到的匹配标签:', sortedLabels);

        // 找到 claims 容器
        const claimsContainer = document.querySelector('section#claims patent-text');
        console.log('[Patent Labeler] claimsContainer:', claimsContainer);

        if (!claimsContainer) {
            console.warn('[Patent Labeler] 未找到 claims DOM 容器 #claims');
            return 0;
        }

        // 从 searchApp 获取原始 claims HTML
        if (!originalClaimsHtml && data) {
            originalClaimsHtml = getOriginalClaimsHtml(data);
            if (originalClaimsHtml) {
                console.log('[Patent Labeler] 从 searchApp 获取到原始 claims HTML');
            }
        }

        // 构建正则，按 label 长度从长到短排序，优先匹配更长的文案
        const escapedLabels = sortedLabels.map(l => escapeRegExp(l));
        const pattern = '\\b(' + escapedLabels.join('|') + ')\\b';
        const regex = new RegExp(pattern, 'gi');

        console.log('[Patent Labeler] 正则表达式:', regex.toString());

        // 构建 id 到 filenames 的映射（从 figure-callout 元素获取）
        const idToFilenames = {};
        document.querySelectorAll('figure-callout').forEach(el => {
            const id = el.getAttribute('id');
            const filenames = el.getAttribute('filenames');
            if (id && filenames) {
                idToFilenames[id] = filenames;
            }
        });

        let highlightCount = 0;

        // 深度遍历文本节点进行安全替换
        function walkAndReplace(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.nodeValue;
                const matches = text.match(regex);
                if (matches) {
                    console.log('[Patent Labeler] 找到匹配:', matches);
                    regex.lastIndex = 0; // 重置正则
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = text.replace(regex, (match) => {
                        highlightCount++;
                        const lowerMatch = match.toLowerCase();
                        const ids = labelMap[lowerMatch] || [];
                        const idDisplay = ids.join(',');
                        const originalLabel = originalLabelMap[lowerMatch] || match;
                        // 获取所有 id 对应的 filenames，用 | 分隔不同 id 的 filenames
                        const allFilenames = ids.map(id => idToFilenames[id] || '').filter(f => f).join('|');
                        console.log(`[Patent Labeler] 替换: "${match}" -> "${originalLabel}(${idDisplay})"`);
                        return `<span class="${HIGHLIGHT_CLASS}" title="标号: ${idDisplay}" data-filenames="${allFilenames}" data-index="0" style="cursor: pointer;">${originalLabel}<small style="color:#8b6914; font-size:10px; margin-left:2px;">(${idDisplay})</small></span>`;
                    });

                    // 替换原有的文本节点
                    const fragment = document.createDocumentFragment();
                    while (tempDiv.firstChild) {
                        fragment.appendChild(tempDiv.firstChild);
                    }
                    node.parentNode.replaceChild(fragment, node);
                }
            } else if (
                node.nodeType === Node.ELEMENT_NODE &&
                node.tagName !== 'SCRIPT' &&
                node.tagName !== 'STYLE' &&
                !node.classList?.contains(HIGHLIGHT_CLASS)
            ) {
                // 倒序遍历更安全（子节点数量会变）
                for (let i = node.childNodes.length - 1; i >= 0; i--) {
                    walkAndReplace(node.childNodes[i]);
                }
            }
        }

        walkAndReplace(claimsContainer);

        // 添加点击事件（点击高亮标号循环切换显示对应图片）
        if (highlightCount > 0) {
            document.querySelectorAll(`.${HIGHLIGHT_CLASS}`).forEach(el => {
                el.addEventListener('click', () => {
                    const allFilenames = el.getAttribute('data-filenames');
                    if (allFilenames) {
                        // 按 | 分隔得到每个 id 的 filenames
                        const filenameGroups = allFilenames.split('|');
                        let currentIndex = parseInt(el.getAttribute('data-index') || '0', 10);
                        
                        // 循环切换到下一个
                        currentIndex = (currentIndex + 1) % filenameGroups.length;
                        el.setAttribute('data-index', currentIndex.toString());
                        
                        // 获取当前 filenames 的第一个文件
                        const currentFilenames = filenameGroups[currentIndex];
                        const firstFile = currentFilenames.split(',')[0];
                        const label = el.textContent.replace(/\([^)]+\)/g, '').trim();
                        
                        // dispatch RESULT_IMG_SHOW 事件
                        const searchApp = document.querySelector('body > search-app');
                        if (searchApp && searchApp.dispatch) {
                            searchApp.dispatch({
                                type: 'RESULT_IMG_SHOW',
                                filename: firstFile,
                                label: label,
                                origin: 'INLINE'
                            });
                            
                            // 在 #callouts 下的 hoverTarget 添加 id="tooltipTarget"
                            setTimeout(() => {
                                const callouts = document.querySelector('#callouts');
                                if (callouts) {
                                    const hoverTarget = callouts.querySelector('.hoverTarget.style-scope.image-viewer');
                                    if (hoverTarget && !hoverTarget.id) {
                                        hoverTarget.id = 'tooltipTarget';
                                    }
                                }
                            }, 100);
                        }
                    }
                });
            });
        }

        return highlightCount;
    }

    // 恢复原文
    function restoreOriginal() {
        const claimsContainer = document.querySelector('section#claims patent-text');
        if (!claimsContainer) return;

        // 优先使用从 searchApp 获取的原始 HTML
        if (originalClaimsHtml) {
            claimsContainer.innerHTML = originalClaimsHtml;
            delete claimsContainer.dataset.highlighted;
            console.log('[Patent Labeler] 已恢复原文（来自 searchApp）');
        } else if (claimsContainer.dataset.originalHtml) {
            // 备用：使用保存的 DOM innerHTML
            claimsContainer.innerHTML = claimsContainer.dataset.originalHtml;
            delete claimsContainer.dataset.highlighted;
            console.log('[Patent Labeler] 已恢复原文（来自保存的 DOM）');
        }
    }

    // 切换显示原文/标注
    function toggleOriginal(showOriginal) {
        userWantsOriginal = showOriginal;
        if (showOriginal) {
            restoreOriginal();
        } else {
            // 重新高亮
            tryHighlight();
        }
    }

    // 显示计数提示
    function showCounter(count) {
        const old = document.querySelector('.patent-label-counter');
        if (old) old.remove();

        const counter = document.createElement('div');
        counter.className = 'patent-label-counter';
        counter.textContent = `✓ 已高亮 ${count} 个标号`;
        counter.title = '点击关闭';
        counter.addEventListener('click', () => counter.remove());

        document.body.appendChild(counter);

        setTimeout(() => {
            if (counter.parentNode) {
                counter.style.transition = 'opacity 0.5s';
                counter.style.opacity = '0';
                setTimeout(() => counter.remove(), 500);
            }
        }, 5000);
    }

    // 尝试从 DOM 直接提取（备用方案）
    function tryExtractFromDOM() {
        const callouts = [];
        const imgElements = document.querySelectorAll('figure[data-label], [class*="callout"], [class*="label-ref"]');
        imgElements.forEach(el => {
            const label = el.getAttribute('data-label') || el.textContent?.trim();
            const id = el.getAttribute('data-id') || el.getAttribute('id') || label;
            if (label) {
                callouts.push({ id, label });
            }
        });

        if (callouts.length > 0) {
            const labelMap = {};
            const originalLabelMap = {};
            for (const c of callouts) {
                const lowerLabel = c.label.toLowerCase();
                if (!labelMap[lowerLabel]) {
                    labelMap[lowerLabel] = [];
                    originalLabelMap[lowerLabel] = c.label;
                }
                if (!labelMap[lowerLabel].includes(c.id)) {
                    labelMap[lowerLabel].push(c.id);
                }
            }
            const sortedLabels = Object.keys(labelMap).sort((a, b) => b.length - a.length);

            const count = highlightClaims({ labelMap, sortedLabels, originalLabelMap }, null);
            if (count > 0) showCounter(count);
        } else {
            console.log('[Patent Labeler] DOM 中未找到标号数据');
        }
    }

    // 主函数
    function main() {
        console.log('[Patent Labeler] 脚本开始执行');
        injectStyles();

        // 先尝试立即执行
        tryHighlight();

        // 监听 DOM 变化，SPA 页面数据加载后重新执行
        const observer = new MutationObserver((mutations) => {
            const claimsEl = document.querySelector('section#claims patent-text');
            if (claimsEl && !claimsEl.dataset.highlighted && !userWantsOriginal) {
                console.log('[Patent Labeler] 检测到 claims 元素变化');
                tryHighlight();
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        // 监听来自 content script 的消息（通过 window.postMessage）
        window.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'PATENT_LABELER_TOGGLE') {
                toggleOriginal(event.data.showOriginal);
            } else if (event.data && event.data.type === 'PATENT_LABELER_GET_CALLOUTS') {
                // 提取 callouts 数据并返回给 content script
                const searchApp = document.querySelector('body > search-app');
                let callouts = [];
                if (searchApp && searchApp.state && searchApp.state.result && searchApp.state.result.data) {
                    const data = searchApp.state.result.data;
                    const images = data.images || [];
                    callouts = images.flatMap(img => img.callouts || []);
                }
                window.postMessage({
                    type: 'PATENT_LABELER_CALLOUTS_RESPONSE',
                    callouts: callouts
                }, '*');
            } else if (event.data && event.data.type === 'PATENT_LABELER_SHOW_IMAGE') {
                // 显示专利图片
                const searchApp = document.querySelector('body > search-app');
                if (searchApp && searchApp.dispatch) {
                    searchApp.dispatch({
                        type: 'RESULT_IMG_SHOW',
                        filename: event.data.filename,
                        label: event.data.label,
                        origin: 'INLINE'
                    });
                    
                    // 在 #callouts 下的 hoverTarget 添加 id="tooltipTarget"
                    setTimeout(() => {
                        const callouts = document.querySelector('#callouts');
                        if (callouts) {
                            const hoverTarget = callouts.querySelector('.hoverTarget.style-scope.image-viewer');
                            if (hoverTarget && !hoverTarget.id) {
                                hoverTarget.id = 'tooltipTarget';
                            }
                        }
                    }, 100);
                }
            }
        });
    }

    // 尝试高亮（带去重）
    function tryHighlight() {
        // 如果用户明确选择显示原文，不执行高亮
        if (userWantsOriginal) {
            console.log('[Patent Labeler] 用户选择显示原文，跳过高亮');
            return;
        }
        
        const claimsEl = document.querySelector('section#claims patent-text');
        if (!claimsEl) {
            console.log('[Patent Labeler] 未找到 claims 元素，等待中...');
            return;
        }
        if (claimsEl.dataset.highlighted) {
            console.log('[Patent Labeler] 已高亮，跳过');
            return;
        }

        waitForData((data) => {
            if (claimsEl.dataset.highlighted) return;

            const { labelMap, sortedLabels, originalLabelMap } = extractLabels(data);
            const count = highlightClaims({ labelMap, sortedLabels, originalLabelMap }, data);
            if (count > 0) {
                claimsEl.dataset.highlighted = 'true';
                showCounter(count);
                console.log(`[Patent Labeler] 完成，共高亮 ${count} 个标号`);
            } else {
                console.log('[Patent Labeler] 未匹配到任何标号');
            }
        });
    }

    // 等待 DOM 就绪后执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', main);
    } else {
        main();
    }
})();
