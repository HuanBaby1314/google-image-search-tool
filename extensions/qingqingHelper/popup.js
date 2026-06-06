const PRESET_CONFIG = {
    "shutterstock": {
        "seq": 0,
        "key": "shutterstock",
        "name": "Shutterstock",
        "color": "#333333",
        "url": "https://www.shutterstock.com/zh/image-photo/{id}",
        "selector": "#main-content [data-automation=\"ContributorDetails\"] span:nth-child(2)"
    },
    "123rf": {
        "seq": 1,
        "key": "123rf",
        "name": "123rf",
        "color": "#ff9900",
        "url": "https://www.123rf.com/photo_{id}.html",
        "selector": ".ImageDetailsInfo__contributor--name a, .ImageDetails__information--link"
    }
};

let CONFIG = {};

function getSortedConfig() {
    return Object.values(CONFIG).sort((a, b) => (a.seq || 0) - (b.seq || 0));
}

function showToast(msg) {
    let oldToast = document.getElementById('global-toast');
    if (oldToast) oldToast.remove();
    const toast = document.createElement('div');
    toast.id = 'global-toast';
    toast.innerHTML = msg.replace(/\n/g, '<br/>');
    toast.style.cssText = "position:fixed; top:20px; left:50%; transform:translate(-50%, -20px); background:rgba(0,0,0,0.8); color:#fff; padding:12px 24px; font-size:14px; border-radius:6px; z-index:9999999; transition:all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); pointer-events:none; box-shadow:0 6px 16px rgba(0,0,0,0.2); opacity:0; text-align:center; line-height:1.5;";
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.transform = "translate(-50%, 0)";
        toast.style.opacity = '1';
    }, 10);
    setTimeout(() => {
        toast.style.transform = "translate(-50%, -20px)";
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

document.addEventListener('DOMContentLoaded', async () => {
    const manifest = chrome.runtime.getManifest();
    const appTitle = document.getElementById('appTitle');
    if (appTitle && manifest.name) {
        // Automatically inject the extension name defined in manifest.json
        appTitle.innerHTML = `🚀 ${manifest.name}`;
    }

    // Tab 切换逻辑
    const tabItems = document.querySelectorAll('.tab-item');
    const tabContents = document.querySelectorAll('.tab-content');

    // 恢复上次的 tab 状态
    const tabStorage = await chrome.storage.local.get(['activeTab']);
    if (tabStorage.activeTab) {
        tabItems.forEach(t => t.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        const targetItem = document.querySelector(`.tab-item[data-tab="${tabStorage.activeTab}"]`);
        const targetContent = document.getElementById(`tab-${tabStorage.activeTab}`);
        if (targetItem && targetContent) {
            targetItem.classList.add('active');
            targetContent.classList.add('active');
        }
    }

    tabItems.forEach(item => {
        item.addEventListener('click', () => {
            const targetTab = item.getAttribute('data-tab');
            tabItems.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            item.classList.add('active');
            document.getElementById(`tab-${targetTab}`).classList.add('active');
            // 保存当前 tab 状态
            chrome.storage.local.set({ activeTab: targetTab });
        });
    });

    // 读取配置和恢复状态
    const raw = await chrome.storage.local.get(['customConfig', 'draftConfig', 'pickingFor', 'pickedSelector', 'savedData']);

    if (raw.customConfig && Object.keys(raw.customConfig).length > 0) {
        CONFIG = raw.customConfig;
    } else {
        CONFIG = JSON.parse(JSON.stringify(PRESET_CONFIG));
    }

    // --- 新增：自动恢复拾取状态 ---
    if (raw.pickingFor) {
        // 说明刚才用户点击了拾取，现在回来了
        if (raw.draftConfig) {
            CONFIG = raw.draftConfig; // 恢复草稿数据到当前内存
        }
        if (raw.pickedSelector) {
            // 将点选到的选择器填充进去
            if (!CONFIG[raw.pickingFor]) {
                CONFIG[raw.pickingFor] = { key: raw.pickingFor, name: '', color: '#333', url: '', selector: '' };
            }
            CONFIG[raw.pickingFor].selector = raw.pickedSelector;
        }
        // 清理临时状态
        await chrome.storage.local.remove(['pickingFor', 'pickedSelector', 'draftConfig']);
        // 自动打开设置窗口
        setTimeout(() => {
            const btn = document.getElementById('settingsBtn');
            if (btn) btn.click();
        }, 150); // 略微延迟等弹窗绑定好
    }
    // ----------------------------

    bindMainEvents();
    bindSettingsEvents();

    if (raw.savedData) {
        renderAllRows(raw.savedData);
    }
});


function bindMainEvents() {
    const startBtn = document.getElementById('startBtn');
    const resultBody = document.getElementById('resultBody');
    const copyResultBtn = document.getElementById('copyResultBtn');
    const clearBtn = document.getElementById('clearBtn');
    const fullScreenBtn = document.getElementById('fullScreenBtn');

    if (fullScreenBtn) fullScreenBtn.onclick = () => chrome.tabs.create({ url: chrome.runtime.getURL('popup.html') });

    // V2+: Global mixed input with preflight detection
    const globalMixedInput = document.getElementById('globalMixedInput');
    const globalPreview = document.getElementById('globalMixedPreview');
    const unmatchedBox = document.getElementById('unmatchedBox');
    const unmatchedList = document.getElementById('unmatchedList');

    let debounceTimer;
    globalMixedInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const val = globalMixedInput.value.trim();
            if (!val) {
                globalPreview.style.display = 'none';
                unmatchedBox.style.display = 'none';
                return;
            }

            const storage = await chrome.storage.local.get(['savedData']);
            const currentData = storage.savedData || {};
            const seenIdentifiers = new Set();

            // 从历史记录中提取已成功的 ID 和 URL 用于去重
            Object.values(currentData).forEach(item => {
                if (item.status === "成功") {
                    if (item.id && item.id !== 'link') seenIdentifiers.add(item.id);
                    if (item.url) seenIdentifiers.add(item.url);
                }
            });

            const lines = val.split('\n').filter(l => l.trim());
            let previewHtml = "";
            let unmatchedIds = [];
            const activeSources = Object.keys(CONFIG);

            for (const line of lines) {
                const text = line.trim();

                // 去重逻辑：检查原始输入字符串是否已存在
                if (seenIdentifiers.has(text)) continue;

                if (text.startsWith('http')) {
                    // 提取 URL 中的 ID 用于交叉去重
                    const idMatch = text.match(/(\d+)/);
                    const extractedId = idMatch ? idMatch[0] : null;
                    if (extractedId && seenIdentifiers.has(extractedId)) continue;

                    let sourceName = "未知来源";
                    for (const key in CONFIG) {
                        try {
                            const urlObj = new URL(text);
                            const templateObj = new URL(CONFIG[key].url.replace('{id}', '123'));
                            if (urlObj.hostname.includes(templateObj.hostname.replace('www.', ''))) {
                                sourceName = CONFIG[key].name;
                                break;
                            }
                        } catch (e) { }
                    }

                    try {
                        const res = await fetch(text, { method: 'HEAD' });
                        if (res.ok) {
                            previewHtml += `<div style="margin-bottom:4px; font-size:11px;"><span style="color:#67c23a">[${sourceName}]</span> 🔗 <a href="${text}" target="_blank" style="color:#409eff;">${text}</a></div>`;
                            seenIdentifiers.add(text);
                            if (extractedId) seenIdentifiers.add(extractedId);
                        } else {
                            unmatchedIds.push(`失效链接: ${text}`);
                        }
                    } catch (e) {
                        unmatchedIds.push(`无法访问: ${text}`);
                    }
                } else {
                    const ids = text.match(/\d{8,}/g) || [];
                    if (ids.length === 0 && text.match(/\d+/)) {
                        unmatchedIds.push(`${text} (过短)`);
                        continue;
                    }

                    for (const id of ids) {
                        if (seenIdentifiers.has(id)) continue;

                        let foundValidSource = false;
                        for (const srcKey of activeSources) {
                            const conf = CONFIG[srcKey];
                            const testUrl = conf.url.replace('{id}', id);

                            // 检查生成的 URL 是否已存在 (ID vs URL 去重)
                            if (seenIdentifiers.has(testUrl)) {
                                foundValidSource = true;
                                seenIdentifiers.add(id); // 标记 ID 已处理
                                break;
                            }

                            try {
                                const res = await fetch(testUrl, { method: 'HEAD' });
                                if (res.ok) {
                                    previewHtml += `<div style="margin-bottom:4px; font-size:11px;"><span style="color:#67c23a">[${conf.name}]</span> 🆔 <a href="${testUrl}" target="_blank" style="color:#409eff;">${testUrl}</a></div>`;
                                    foundValidSource = true;
                                    seenIdentifiers.add(id);
                                    seenIdentifiers.add(testUrl);
                                    break;
                                }
                            } catch (e) { }
                        }
                        if (!foundValidSource) {
                            unmatchedIds.push(id);
                        }
                    }
                }
            }

            globalPreview.innerHTML = previewHtml || "未识别到匹配的有效链接";
            globalPreview.style.display = previewHtml ? 'block' : 'none';

            if (unmatchedIds.length > 0) {
                unmatchedList.innerText = [...new Set(unmatchedIds)].join(', ');
                unmatchedBox.style.display = 'block';
            } else {
                unmatchedBox.style.display = 'none';
            }
        }, 800);
    });

    startBtn.addEventListener('click', async () => {
        const storage = await chrome.storage.local.get(['savedData']);
        const currentData = storage.savedData || {};
        const activeSources = Object.keys(CONFIG);

        const globalVal = globalMixedInput.value;
        let allTasks = [];
        let currentOrder = Date.now();

        // --- 全局去重集合 (ID和URL) ---
        const seenIdentifiers = new Set();
        // 初始化：将历史成功的 ID 和 URL 加入已见集合
        Object.values(currentData).forEach(item => {
            if (item.status === "成功") {
                if (item.id && item.id !== 'link') seenIdentifiers.add(item.id);
                if (item.url) seenIdentifiers.add(item.url);
            }
        });

        // --- 1. 处理全局混合输入 ---
        if (globalVal.trim()) {
            const lines = globalVal.split('\n').filter(l => l.trim());
            for (const line of lines) {
                const text = line.trim();
                if (seenIdentifiers.has(text)) continue;

                if (text.startsWith('http')) {
                    const idMatch = text.match(/(\d+)/);
                    const extractedId = idMatch ? idMatch[0] : null;
                    if (extractedId && seenIdentifiers.has(extractedId)) continue;

                    let detectedSrc = null;
                    for (const key in CONFIG) {
                        try {
                            const urlObj = new URL(text);
                            const templateObj = new URL(CONFIG[key].url.replace('{id}', '123'));
                            if (urlObj.hostname.includes(templateObj.hostname.replace('www.', ''))) {
                                detectedSrc = key; break;
                            }
                        } catch (e) { }
                    }
                    if (detectedSrc) {
                        allTasks.push({ srcKey: detectedSrc, srcConf: CONFIG[detectedSrc], id: extractedId || 'link', url: text, ts: currentOrder++ });
                        seenIdentifiers.add(text);
                        if (extractedId) seenIdentifiers.add(extractedId);
                    }
                } else {
                    const ids = text.match(/\d{8,}/g) || [];
                    // 并行检测所有ID
                    const detectPromises = ids.filter(id => !seenIdentifiers.has(id)).map(async (id) => {
                        for (const srcKey of activeSources) {
                            const conf = CONFIG[srcKey];
                            const testUrl = conf.url.replace('{id}', id);
                            if (seenIdentifiers.has(testUrl)) {
                                seenIdentifiers.add(id);
                                return null;
                            }
                            try {
                                const res = await fetch(testUrl, { method: 'HEAD', signal: AbortSignal.timeout(3000) });
                                if (res.ok) {
                                    return { srcKey, conf, id, url: testUrl };
                                }
                            } catch (e) { }
                        }
                        return null;
                    });
                    const detected = await Promise.allSettled(detectPromises);
                    for (const result of detected) {
                        if (result.status === 'fulfilled' && result.value) {
                            const { srcKey, conf, id, url } = result.value;
                            if (!seenIdentifiers.has(id)) {
                                allTasks.push({ srcKey, srcConf: conf, id, url, ts: currentOrder++ });
                                seenIdentifiers.add(id);
                                seenIdentifiers.add(url);
                            }
                        }
                    }
                }
            }
        }

        // --- 2. 处理各来源自己的混合输入 ---
        for (const srcKey of activeSources) {
            const srcConf = CONFIG[srcKey];
            const mixedVal = document.getElementById(`mixed-${srcKey}`)?.value || '';
            const lines = mixedVal.split('\n').filter(l => l.trim());

            for (const line of lines) {
                const text = line.trim();
                if (seenIdentifiers.has(text)) continue;

                if (text.startsWith('http')) {
                    const idMatch = text.match(/(\d+)/);
                    const extractedId = idMatch ? idMatch[0] : null;
                    if (extractedId && seenIdentifiers.has(extractedId)) continue;

                    allTasks.push({ srcKey, srcConf, id: extractedId || 'link', url: text, ts: currentOrder++ });
                    seenIdentifiers.add(text);
                    if (extractedId) seenIdentifiers.add(extractedId);
                } else {
                    const ids = text.match(/\d{8,}/g) || [];
                    for (const id of ids) {
                        if (seenIdentifiers.has(id)) continue;
                        const testUrl = srcConf.url.replace('{id}', id);
                        if (seenIdentifiers.has(testUrl)) {
                            seenIdentifiers.add(id);
                            continue;
                        }
                        allTasks.push({ srcKey, srcConf, id, url: testUrl, ts: currentOrder++ });
                        seenIdentifiers.add(id);
                        seenIdentifiers.add(testUrl);
                    }
                }
            }
        }

        if (allTasks.length === 0) return showToast(globalVal.trim() ? "输入内容已在历史记录或当前批次中重复" : "请先输入数据");

        startBtn.disabled = true;
        const originalText = startBtn.innerText;
        startBtn.innerText = "🔍 正在检测平台...";
        await new Promise(r => setTimeout(r, 100)); // 让UI更新

        const totalIds = allTasks.length;
        startBtn.innerText = `⚡ 正在采集中... (0/${totalIds})`;

        let successCount = 0;
        let failCount = 0;
        let doneCount = 0;

        await Promise.allSettled(allTasks.map(async (task) => {
            try {
                const resp = await fetch(task.url);
                const html = await resp.text();
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const author = doc.querySelector(task.srcConf.selector)?.innerText.trim() || "未知作者";

                currentData[`${task.srcKey}-${task.id}`] = { id: task.id, url: task.url, name: author, source: task.srcKey, status: "成功", ts: task.ts };
                successCount++;
            } catch (e) {
                currentData[`${task.srcKey}-${task.id}`] = { id: task.id, url: task.url, name: "-", source: task.srcKey, status: "采集失败", ts: task.ts };
                failCount++;
            }
            doneCount++;
            startBtn.innerText = `⚡ 正在采集中... (${doneCount}/${totalIds})`;
            renderAllRows(currentData);
        }));

        await chrome.storage.local.set({ savedData: currentData });
        startBtn.disabled = false;
        startBtn.innerText = originalText;
        showToast(`🎉 采集任务完成！\n成功: ${successCount} 条\n失败: ${failCount} 条`);
    });

    copyResultBtn.onclick = async () => {
        const res = await chrome.storage.local.get(['savedData']);
        const data = res.savedData || {};

        // 与表格渲染相同的排序逻辑：来源顺序 + 输入顺序
        const arr = Object.values(data);
        arr.sort((a, b) => {
            const confA = CONFIG[a.source] || {};
            const confB = CONFIG[b.source] || {};
            const orderA = typeof confA.seq === 'number' ? confA.seq : 999;
            const orderB = typeof confB.seq === 'number' ? confB.seq : 999;
            if (orderA !== orderB) return orderA - orderB;
            return (a.ts || 0) - (b.ts || 0);
        });

        const groups = {};
        getSortedConfig().forEach(c => groups[c.key] = []);
        arr.forEach(item => {
            if (!groups[item.source]) groups[item.source] = [];
            groups[item.source].push(`${item.id}，作者 ${item.name}`);
        });

        let output = "图案素材:\n";
        let hasContent = false;

        for (const srcKey in groups) {
            if (groups[srcKey].length > 0) {
                const srcName = CONFIG[srcKey] ? CONFIG[srcKey].name : srcKey;
                output += `${srcName}:\n` + groups[srcKey].join('\n') + "\n";
                hasContent = true;
            }
        }

        if (!hasContent) return showToast("无数据");
        navigator.clipboard.writeText(output.trim());
        showToast("格式化结果已复制！");
    };

    clearBtn.onclick = async () => {
        if (confirm("清空历史？")) {
            await chrome.storage.local.remove('savedData');
            document.getElementById('resultBody').innerHTML = '';
            document.getElementById('batchDeleteBtn').style.display = 'none';
            document.getElementById('selectAll').checked = false;
            showToast("历史记录已清空");
        }
    };

    // --- V2: 批量删除逻辑 ---
    const selectAll = document.getElementById('selectAll');
    const batchDeleteBtn = document.getElementById('batchDeleteBtn');

    selectAll.onchange = () => {
        const chks = document.querySelectorAll('.row-chk');
        chks.forEach(c => c.checked = selectAll.checked);
        toggleBatchBtn();
    };

    batchDeleteBtn.onclick = async () => {
        const chks = Array.from(document.querySelectorAll('.row-chk:checked'));
        if (chks.length === 0) return;

        if (confirm(`确定要删除选中的 ${chks.length} 条记录吗？`)) {
            const storage = await chrome.storage.local.get(['savedData']);
            const data = storage.savedData || {};
            chks.forEach(chk => {
                const key = chk.getAttribute('data-key');
                delete data[key];
                const row = document.getElementById(`row-${key}`);
                if (row) row.remove();
            });
            await chrome.storage.local.set({ savedData: data });
            showToast(`已删除 ${chks.length} 条记录`);
            selectAll.checked = false;
            toggleBatchBtn();
        }
    };
}

function toggleBatchBtn() {
    const batchDeleteBtn = document.getElementById('batchDeleteBtn');
    const hasChecked = document.querySelectorAll('.row-chk:checked').length > 0;
    batchDeleteBtn.style.display = hasChecked ? 'inline-block' : 'none';
}

function renderAllRows(dataObj) {
    const resultBody = document.getElementById('resultBody');
    resultBody.innerHTML = '';

    const arr = Object.values(dataObj);
    // 严格按来源配置位置，以及数据输入时间顺序排列
    arr.sort((a, b) => {
        const confA = CONFIG[a.source] || {};
        const confB = CONFIG[b.source] || {};
        const orderA = typeof confA.seq === 'number' ? confA.seq : 999;
        const orderB = typeof confB.seq === 'number' ? confB.seq : 999;
        if (orderA !== orderB) return orderA - orderB;
        return (a.ts || 0) - (b.ts || 0);
    });

    arr.forEach(item => {
        const srcConf = CONFIG[item.source] || { name: item.source, color: '#000' };
        const row = document.createElement('tr');
        const itemKey = `${item.source}-${item.id}`;
        row.id = `row-${itemKey}`;

        row.innerHTML = `
            <td><input type="checkbox" class="row-chk" data-key="${itemKey}"></td>
            <td><span class="tag" style="background:${srcConf.color}; font-size:10px; padding:2px 6px; border-radius:4px; color:white; margin-right:5px; font-weight:bold;">${srcConf.name}</span> ${item.id}</td>
            <td style="color:#409eff; cursor:pointer" class="copy-cell">${item.name}</td>
            <td style="color:${(item.status || '').includes('失败') ? 'red' : 'green'}">${item.status || '成功'}</td>
            <td>
                <span class="delete-cell" title="删除" style="cursor:pointer; font-size:15px; opacity:0.8; transition:0.2s;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.8">✖</span>
            </td>
        `;

        row.querySelector('.row-chk').onchange = () => toggleBatchBtn();
        row.querySelector('.copy-cell').onclick = () => {
            navigator.clipboard.writeText(item.name);
            showToast("作者名已复制");
        };
        row.querySelector('.delete-cell').onclick = async () => {
            if (confirm("确定要删除这条记录吗？")) {
                row.remove();
                const storage = await chrome.storage.local.get(['savedData']);
                if (storage.savedData) {
                    delete storage.savedData[itemKey];
                    await chrome.storage.local.set({ savedData: storage.savedData });
                }
                toggleBatchBtn();
            }
        };
        resultBody.appendChild(row);
    });
}


// ============== 设置弹窗逻辑 ===============
function bindSettingsEvents() {
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsPanel = document.getElementById('settingsPanel');
    const settingsArrow = document.getElementById('settingsArrow');
    const addSourceConfigBtn = document.getElementById('addSourceConfigBtn');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const exportConfigBtn = document.getElementById('exportConfigBtn');
    const importConfigBtn = document.getElementById('importConfigBtn');
    const importFileInput = document.getElementById('importFileInput');
    const configItemsContainer = document.getElementById('configItemsContainer');

    if (!settingsBtn) return; // in case of page reload mismatch

    settingsBtn.onclick = () => {
        const isVisible = settingsPanel.style.display !== 'none';
        if (!isVisible) {
            renderConfigList();
            settingsPanel.style.display = 'block';
            settingsArrow.style.transform = 'rotate(180deg)';
        } else {
            settingsPanel.style.display = 'none';
            settingsArrow.style.transform = 'rotate(0deg)';
        }
    };

    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function renderConfigList() {
        configItemsContainer.innerHTML = '';
        getSortedConfig().forEach(src => addConfigRow(src));
    }

    function addConfigRow(src) {
        const div = document.createElement('div');
        div.className = 'cfg-row';
        div.style.position = 'relative';
        div.style.paddingLeft = '35px';
        div.style.transition = 'all 0.2s';
        div.innerHTML = `
            <div class="drag-handle" title="按住拖拽优先排序" style="position:absolute; left:8px; top:50%; transform:translateY(-50%); cursor:grab; color:#c0c4cc; font-size:24px; user-select:none;">⋮⋮</div>
            <span class="del-cfg-btn" title="删除来源" style="position:absolute; right:10px; top:10px; color:#f56c6c; font-size:16px; cursor:pointer;" onmouseover="this.style.opacity=0.7" onmouseout="this.style.opacity=1">✖</span>
            <div style="display:flex; gap:10px; margin-bottom:10px; align-items:center; padding-right:20px;">
                <label style="font-size:12px; color:#606266; width:45px; flex-shrink:0;">ID标识</label>
                <input class="cfg-key" value="${escapeHtml(src.key)}" placeholder="如 rf123" style="flex:1; min-width:80px;">
                
                <label style="font-size:12px; color:#606266; width:30px; flex-shrink:0;">名称</label>
                <input class="cfg-name" value="${escapeHtml(src.name)}" placeholder="界面显示" style="flex:1; min-width:80px;">
                
                <label style="font-size:12px; color:#606266; width:45px; flex-shrink:0;">标签色</label>
                <input type="color" class="cfg-color" value="${escapeHtml(src.color)}" style="width:30px; height:28px; padding:0; border:none; background:transparent; cursor:pointer;">
            </div>
            <div style="display:flex; gap:10px; margin-bottom:10px; align-items:center;">
                <label style="font-size:12px; color:#606266; width:45px; flex-shrink:0;">URL模板</label>
                <input class="cfg-url" value="${escapeHtml(src.url)}" placeholder="如 https://domain.com/photo_{id}.html" style="flex:1; box-sizing:border-box;">
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
                <label style="font-size:12px; color:#606266; width:45px; flex-shrink:0;">选择器</label>
                <input class="cfg-sel" value="${escapeHtml(src.selector)}" placeholder="页面元素的 CSS 提取规则" style="flex:1;">
                <button class="pick-btn" style="background:#67c23a; color:white; border:none; padding:6px 12px; border-radius:4px; font-size:12px; cursor:pointer; flex-shrink:0;">页面点选选择器</button>
            </div>
        `;
        div.querySelector('.del-cfg-btn').onclick = () => div.remove();

        // 拖拽手柄逻辑
        const handle = div.querySelector('.drag-handle');
        handle.addEventListener('mousedown', () => div.setAttribute('draggable', 'true'));
        handle.addEventListener('mouseup', () => div.removeAttribute('draggable'));

        div.addEventListener('dragstart', (e) => {
            window._draggedRow = div;
            e.dataTransfer.effectAllowed = 'move';
            setTimeout(() => {
                div.style.opacity = '0.5';
                div.style.background = '#f0f9eb';
            }, 0);
        });

        div.addEventListener('dragend', () => {
            div.style.opacity = '1';
            div.style.background = '';
            div.removeAttribute('draggable');
            window._draggedRow = null;
        });

        div.addEventListener('dragover', (e) => {
            e.preventDefault(); // 允许放置
            const draggingNode = window._draggedRow;
            if (!draggingNode || draggingNode === div) return;

            const bounding = div.getBoundingClientRect();
            const offset = bounding.y + (bounding.height / 2);
            if (e.clientY > offset) {
                div.parentNode.insertBefore(draggingNode, div.nextSibling);
            } else {
                div.parentNode.insertBefore(draggingNode, div);
            }
        });

        div.querySelector('.pick-btn').onclick = async () => {
            const currentKey = div.querySelector('.cfg-key').value.trim();
            if (!currentKey) return showToast('请先填写标识符再拾取！');

            // 自动将当前弹窗里的临时修改存入草稿
            const draftConf = {};
            const rows = configItemsContainer.querySelectorAll('.cfg-row');
            let draftSeq = 0;
            for (const r of rows) {
                const k = r.querySelector('.cfg-key').value.trim();
                if (k) draftConf[k] = {
                    seq: draftSeq++,
                    key: k, name: r.querySelector('.cfg-name').value.trim(),
                    color: r.querySelector('.cfg-color').value, url: r.querySelector('.cfg-url').value.trim(),
                    selector: r.querySelector('.cfg-sel').value.trim()
                };
            }
            if (!draftConf[currentKey]) draftConf[currentKey] = { key: currentKey, name: '', color: '#333', url: '', selector: '' };

            // 记录下我们当前在为哪个项目拾取
            await chrome.storage.local.set({ draftConfig: draftConf, pickingFor: currentKey });
            startPickingSelector();
        };
        configItemsContainer.appendChild(div);
    }

    addSourceConfigBtn.onclick = async () => {
        let key = 'new_' + Date.now();
        let name = '新增来源';
        let url = '';

        try {
            const allActiveTabs = await chrome.tabs.query({ active: true });
            const tab = allActiveTabs.find(t => t.url && !t.url.startsWith('chrome://') && !t.url.startsWith('edge://') && !t.url.startsWith('chrome-extension://'));

            if (tab && tab.url) {
                const urlObj = new URL(tab.url);
                url = urlObj.origin + '/{id}'; // 默认模板使用其Origin基础路径

                const hostname = urlObj.hostname;
                const parts = hostname.split('.');

                // 智能提取域名主干 (比如 www.shutterstock.com 提取出 shutterstock)
                let domainMain = parts.length > 2 ? parts[parts.length - 2] : parts[0];
                if (parts.length > 2 && ['com', 'co', 'net', 'org'].includes(parts[parts.length - 2])) {
                    domainMain = parts[parts.length - 3] || parts[0];
                }

                if (domainMain && domainMain !== 'www') {
                    key = domainMain;
                    name = domainMain.charAt(0).toUpperCase() + domainMain.slice(1);
                }
            }
        } catch (e) {
            console.error('URL解析失败', e);
        }

        addConfigRow({ key: key, name: name, color: '#409eff', url: url, selector: '' });

        setTimeout(() => {
            configItemsContainer.scrollTop = configItemsContainer.scrollHeight;
        }, 50);
    };

    saveSettingsBtn.onclick = async () => {
        const newConf = {};
        const rows = configItemsContainer.querySelectorAll('.cfg-row');
        let seqOrder = 0;
        for (const r of rows) {
            const key = r.querySelector('.cfg-key').value.trim();
            if (!key) continue;
            newConf[key] = {
                seq: seqOrder++,
                key: key,
                name: r.querySelector('.cfg-name').value.trim(),
                color: r.querySelector('.cfg-color').value,
                url: r.querySelector('.cfg-url').value.trim(),
                selector: r.querySelector('.cfg-sel').value.trim()
            };
        }
        CONFIG = newConf;
        await chrome.storage.local.set({ customConfig: CONFIG });
        showToast("配置已生效！");
        settingsPanel.style.display = 'none';
        settingsArrow.style.transform = 'rotate(0deg)';
        renderMainUI(); // 刷新主界面
    };

    exportConfigBtn.onclick = () => {
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(CONFIG, null, 2));
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", "qingqing_config.json");
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    };

    importConfigBtn.onclick = () => {
        importFileInput.click();
    };

    importFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (evt) => {
            try {
                const importedConf = JSON.parse(evt.target.result);
                if (typeof importedConf === 'object' && Object.keys(importedConf).length > 0) {
                    CONFIG = importedConf;
                    renderConfigList();
                    showToast("导入成功！请记得点击保存。");
                }
            } catch (er) {
                showToast("文件格式有误！");
            }
        };
        reader.readAsText(file);
    });
}

async function startPickingSelector() {
    try {
        const allActiveTabs = await chrome.tabs.query({ active: true });
        // 跨窗口寻找真实的网页 (排除扩展页面和浏览器系统页面)
        const tab = allActiveTabs.find(t => t.url && !t.url.startsWith('chrome://') && !t.url.startsWith('edge://') && !t.url.startsWith('chrome-extension://'));

        if (!tab) {
            chrome.storage.local.remove(['pickingFor', 'draftConfig']);
            return showToast('请先在浏览器中打开一个真实的素材网页\\n不要在扩展页面或系统空白页上提取。');
        }

        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: function () {
                if (window._isPickingActive) return;
                window._isPickingActive = true;

                const overlay = document.createElement('div');
                overlay.style.cssText = "position:fixed; top:0; left:0; width:100%; height:100%; z-index:9999999; background:rgba(0,0,0,0); border: 2px solid #409eff; box-sizing:border-box; pointer-events:none;";
                document.body.appendChild(overlay);

                const tip = document.createElement('div');
                tip.style.cssText = "position:fixed; top:20px; right:20px; background:#409eff; color:white; padding:15px; border-radius:8px; z-index:10000000; font-family:sans-serif; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.2); pointer-events:none;";
                tip.innerHTML = "<div style='font-size:16px; font-weight:bold; margin-bottom:5px;'>🎯 元素拾取器已开启</div><div>请在页面上点击你要采集的元素</div><div style='font-size:12px; opacity:0.8; margin-top:5px;'>(按 Esc 取消)</div>";
                document.body.appendChild(tip);

                const highlightBox = document.createElement('div');
                highlightBox.style.cssText = "position:absolute; border:2px dashed red; background:rgba(255,0,0,0.1); z-index:9999998; pointer-events:none; transition: all 0.1s;";
                document.body.appendChild(highlightBox);

                let hoveringElement = null;

                const mouseOverHandler = (e) => {
                    hoveringElement = e.target;
                    const rect = hoveringElement.getBoundingClientRect();
                    highlightBox.style.top = (rect.top + window.scrollY) + 'px';
                    highlightBox.style.left = (rect.left + window.scrollX) + 'px';
                    highlightBox.style.width = rect.width + 'px';
                    highlightBox.style.height = rect.height + 'px';
                    e.stopPropagation();
                };

                const getUniqueSelector = (el) => {
                    if (!el || el.nodeType !== 1) return '';
                    if (el.id) return `#${CSS.escape(el.id)}`;

                    let path = [];
                    while (el && el.nodeType === Node.ELEMENT_NODE) {
                        let selector = el.nodeName.toLowerCase();
                        if (el.id) {
                            path.unshift(`#${CSS.escape(el.id)}`);
                            break;
                        } else {
                            let sibling = el, nth = 1;
                            while (sibling = sibling.previousElementSibling) {
                                if (sibling.nodeName.toLowerCase() == selector) nth++;
                            }
                            if (nth != 1) selector += ":nth-of-type(" + nth + ")";
                        }
                        path.unshift(selector);
                        el = el.parentNode;
                    }
                    return path.join(" > ");
                };

                const cleanup = () => {
                    window._isPickingActive = false;
                    document.removeEventListener('mouseover', mouseOverHandler, true);
                    document.removeEventListener('click', clickHandler, true);
                    document.removeEventListener('keydown', keydownHandler, true);
                    overlay.remove();
                    tip.remove();
                    highlightBox.remove();
                };

                const clickHandler = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    cleanup();
                    const selector = getUniqueSelector(e.target);
                    // 保存并提示
                    chrome.storage.local.set({ pickedSelector: selector }, () => {
                        const successTip = document.createElement('div');
                        successTip.style.cssText = "position:fixed; top:20px; left:50%; transform:translate(-50%, 0); background:#67c23a; color:white; padding:15px; border-radius:8px; z-index:10000000; font-family:sans-serif; text-align:center; box-shadow:0 4px 12px rgba(0,0,0,0.2); pointer-events:none; line-height:1.6;";
                        successTip.innerHTML = "✅ <b>选择器已获取并保存内部剪贴板！</b><br/>由于浏览器弹窗特性，拾取期间设置框体已被自动折叠<br/>您现在只需<b>【重新点击右上角的扩展图标】</b><br/>您的修改和新选取的内容将会自动加载！";
                        document.body.appendChild(successTip);
                        setTimeout(() => successTip.remove(), 5000);
                    });
                };

                const keydownHandler = (e) => {
                    if (e.key === 'Escape') cleanup();
                };

                document.addEventListener('mouseover', mouseOverHandler, true);
                document.addEventListener('click', clickHandler, true);
                document.addEventListener('keydown', keydownHandler, true);
            }
        });

        // 交互重点逻辑：
        const isFullScreen = window.innerWidth >= 800; // 宽屏说明是单独网页打开的插件
        if (!isFullScreen) {
            window.close(); // 自动关闭弹出层让出视线
        } else {
            const settingsPanel = document.getElementById('settingsPanel');
            const settingsArrow = document.getElementById('settingsArrow');
            if (settingsPanel) settingsPanel.style.display = 'none';
            if (settingsArrow) settingsArrow.style.transform = 'rotate(0deg)';
            showToast('拾取器已注入到后台网页！\\n请切换到你需要采集操作的浏览器选项卡！');
        }
    } catch (e) {
        chrome.storage.local.remove(['pickingFor', 'draftConfig']);
        showToast("无法启动选择器，权限可能受限。\\n请尝试刷新素材页面后重试。(错因: " + e.message + ")");
    }
}
function getImageTargets() {
    const result = {};
    const allTarget = document.querySelectorAll('figure-callout');
    allTarget.forEach(item => {
        const id = item.attributes.id.value;
        const imgLabel = item.attributes.label.value;
        if (result[id]) {
            result[id].add(imgLabel);
        } else {
            result[id] = new Set();
            result[id].add(imgLabel);
        }
    })
    return Object.entries(result).map(([id, imgSet]) => {
        return {
            id: id,
            imgLabel: Array.from(imgSet)
        }
    });
}