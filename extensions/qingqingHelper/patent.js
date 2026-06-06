/**
 * 专利标号功能模块
 * 处理专利号输入、打开 Google Patents、最近访问记录
 */

const PATENT_RECENT_KEY = 'patent_recent';
const PATENT_MAX_RECENT = 10;

// 打开专利页面
function openPatentPage(patentNo) {
    const no = patentNo.trim();
    if (!no) return;

    const url = `https://patents.google.com/patent/${no}/en?oq=${no}`;
    window.open(url, '_blank');

    // 保存到最近访问
    saveRecentPatent(no);
}

// 保存到最近访问
async function saveRecentPatent(no) {
    const result = await chrome.storage.local.get([PATENT_RECENT_KEY]);
    let list = result[PATENT_RECENT_KEY] || [];

    // 去重并移到最前
    list = list.filter(p => p.no !== no);
    list.unshift({ no, time: Date.now() });

    // 限制数量
    if (list.length > PATENT_MAX_RECENT) {
        list = list.slice(0, PATENT_MAX_RECENT);
    }

    await chrome.storage.local.set({ [PATENT_RECENT_KEY]: list });
    renderRecentPatents(list);
}

// 删除单条记录
async function removeRecentPatent(no) {
    const result = await chrome.storage.local.get([PATENT_RECENT_KEY]);
    let list = result[PATENT_RECENT_KEY] || [];
    list = list.filter(p => p.no !== no);
    await chrome.storage.local.set({ [PATENT_RECENT_KEY]: list });
    renderRecentPatents(list);
}

// 清空所有记录
async function clearRecentPatents() {
    await chrome.storage.local.remove([PATENT_RECENT_KEY]);
    renderRecentPatents([]);
}

// 格式化时间
function formatPatentTime(timestamp) {
    const now = Date.now();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 30) return `${days}天前`;
    return new Date(timestamp).toLocaleDateString('zh-CN');
}

// 渲染最近访问列表
function renderRecentPatents(list) {
    const recentSection = document.getElementById('recentSection');
    const recentList = document.getElementById('recentList');
    const emptyState = document.getElementById('patentEmptyState');

    if (!list || list.length === 0) {
        recentSection.style.display = 'none';
        emptyState.style.display = 'flex';
        return;
    }

    recentSection.style.display = 'block';
    emptyState.style.display = 'none';

    recentList.innerHTML = list.map(p => `
        <div class="recent-item" data-no="${p.no}">
            <span class="recent-no">${p.no}</span>
            <span class="recent-time">${formatPatentTime(p.time)}</span>
            <span class="recent-delete" data-no="${p.no}" title="删除">✖</span>
        </div>
    `).join('');

    // 绑定点击事件
    recentList.querySelectorAll('.recent-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // 如果点击的是删除按钮，不打开专利
            if (e.target.classList.contains('recent-delete')) return;
            const no = item.getAttribute('data-no');
            openPatentPage(no);
        });
    });

    // 绑定删除事件
    recentList.querySelectorAll('.recent-delete').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const no = btn.getAttribute('data-no');
            removeRecentPatent(no);
        });
    });
}

// 渲染标号列表
function renderCalloutsList(callouts) {
    const calloutsSection = document.getElementById('calloutsSection');
    const calloutsList = document.getElementById('calloutsList');

    if (!callouts || callouts.length === 0) {
        calloutsSection.style.display = 'none';
        return;
    }

    calloutsSection.style.display = 'block';

    // 按 label 分组，同时记录每个 label 对应的所有 id 和 filenames
    const labelMap = {};
    for (const c of callouts) {
        if (typeof c === 'object' && c !== null && c.label) {
            if (!labelMap[c.label]) {
                labelMap[c.label] = { ids: [], filenames: [] };
            }
            if (c.id && !labelMap[c.label].ids.includes(c.id)) {
                labelMap[c.label].ids.push(c.id);
            }
        }
    }

    // 从 figure-callout 获取 filenames
    document.querySelectorAll('figure-callout').forEach(el => {
        const id = el.getAttribute('id');
        const filenames = el.getAttribute('filenames');
        if (id && filenames) {
            // 找到包含这个 id 的 label，添加 filenames
            for (const label in labelMap) {
                if (labelMap[label].ids.includes(id) && !labelMap[label].filenames.includes(filenames)) {
                    labelMap[label].filenames.push(filenames);
                }
            }
        }
    });

    // 生成表格行
    calloutsList.innerHTML = Object.entries(labelMap).map(([label, data]) => {
        const idsDisplay = data.ids.join(', ');
        const filenamesAttr = data.filenames.join('|');
        return `
        <tr style="border-bottom: 1px solid #ebeef5; cursor: pointer;" 
            class="callout-row" 
            data-label="${label}" 
            data-filenames="${filenamesAttr}" 
            data-index="0">
            <td style="padding: 10px 12px; font-weight: 600; color: #409eff; font-family: monospace;">${idsDisplay}</td>
            <td style="padding: 10px 12px;">
                <span style="background: #fff3cd; padding: 2px 6px; border-radius: 3px; border: 1px solid #ffeba2; font-weight: 500;">${label}</span>
            </td>
        </tr>
        `;
    }).join('');

    // 添加点击事件
    calloutsList.querySelectorAll('.callout-row').forEach(row => {
        row.addEventListener('click', async () => {
            const filenamesStr = row.getAttribute('data-filenames');
            const label = row.getAttribute('data-label');
            if (!filenamesStr) return;

            const filenameGroups = filenamesStr.split('|');
            let currentIndex = parseInt(row.getAttribute('data-index') || '0', 10);
            
            // 循环切换到下一个
            currentIndex = (currentIndex + 1) % filenameGroups.length;
            row.setAttribute('data-index', currentIndex.toString());
            
            const currentFilenames = filenameGroups[currentIndex];
            const firstFile = currentFilenames.split(',')[0];

            // 发送消息到 content script 显示图片
            try {
                const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
                if (tabs[0]) {
                    chrome.tabs.sendMessage(tabs[0].id, {
                        action: 'showPatentImage',
                        filename: firstFile,
                        label: label
                    }).catch(() => {});
                }
            } catch (e) {
                console.log('发送消息失败:', e);
            }
        });
    });
}

// 获取当前专利页面的标号数据
async function fetchCurrentPatentCallouts() {
    try {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        const tab = tabs[0];
        if (!tab || !tab.url || !tab.url.includes('patents.google.com/patent/')) {
            return null;
        }

        // 从 URL 提取专利号
        const patentMatch = tab.url.match(/patent\/([A-Z0-9]+)/i);
        const patentNo = patentMatch ? patentMatch[1] : null;

        // 向 content script 发送消息获取 callouts
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'getCallouts' });
        if (response && response.callouts) {
            return { patentNo, callouts: response.callouts };
        }
        return { patentNo, callouts: [] };
    } catch (e) {
        console.log('获取标号数据失败:', e);
        return null;
    }
}

// 初始化专利标号功能
async function initPatentTab() {
    const patentNoInput = document.getElementById('patentNoInput');
    const openPatentBtn = document.getElementById('openPatentBtn');
    const clearRecentBtn = document.getElementById('clearRecentBtn');
    const showOriginalToggle = document.getElementById('showOriginalToggle');

    // 打开专利按钮
    openPatentBtn.addEventListener('click', () => {
        openPatentPage(patentNoInput.value);
        patentNoInput.value = '';
    });

    // 回车打开专利
    patentNoInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') {
            openPatentPage(patentNoInput.value);
            patentNoInput.value = '';
        }
    });

    // 清空最近记录
    clearRecentBtn.addEventListener('click', clearRecentPatents);

    // 加载最近访问记录
    const result = await chrome.storage.local.get([PATENT_RECENT_KEY]);
    const recentList = result[PATENT_RECENT_KEY] || [];
    renderRecentPatents(recentList);

    // 初始化显示原文开关
    const storageResult = await chrome.storage.local.get(['patentShowOriginal']);
    showOriginalToggle.checked = storageResult.patentShowOriginal || false;

    // 开关变化时发送消息到 content script
    showOriginalToggle.addEventListener('change', async () => {
        const isOriginal = showOriginalToggle.checked;
        await chrome.storage.local.set({ patentShowOriginal: isOriginal });

        // 向当前 Google Patents 标签页发送消息
        try {
            const tabs = await chrome.tabs.query({ url: 'https://patents.google.com/*' });
            for (const tab of tabs) {
                chrome.tabs.sendMessage(tab.id, {
                    action: 'toggleOriginal',
                    showOriginal: isOriginal
                }).catch(() => {
                    // 忽略无法发送消息的情况（如页面未加载）
                });
            }
        } catch (e) {
            console.log('发送消息失败:', e);
        }
    });

    // 自动获取当前专利页面的标号数据
    const patentData = await fetchCurrentPatentCallouts();
    if (patentData) {
        renderCalloutsList(patentData.callouts);
        // 如果有专利号，自动填入输入框
        if (patentData.patentNo) {
            patentNoInput.value = patentData.patentNo;
        }
    }
}

// 页面加载后初始化
document.addEventListener('DOMContentLoaded', () => {
    initPatentTab();
});
