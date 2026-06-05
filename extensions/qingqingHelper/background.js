// background.js - 后台服务工作者

const HEARTBEAT_INTERVAL = 10000;
const HEALTH_TIMEOUT = 3000;

let serverStatus = {
  online: false,
  lastCheck: 0,
  latency: 0,
  message: ''
};

// 记录已执行搜图的图片 { filename: { tabId, url, timestamp } }
let searchedImages = new Map();

// ==================== WebSocket 客户端 ====================

let ws = null;
let wsReconnectTimer = null;
let wsHeartbeatTimer = null;
let wsConnected = false;
const WS_HEARTBEAT_INTERVAL = 25000; // 25秒发送一次心跳

async function getServerUrl() {
  const settings = await chrome.storage.local.get(['serverUrl']);
  return settings.serverUrl || 'http://localhost:5277';
}

async function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return; // 已连接或正在连接
  }
  
  try {
    const serverUrl = await getServerUrl();
    const wsUrl = serverUrl.replace(/^http/, 'ws') + '/ws';
    
    console.log('[WS] 连接:', wsUrl);
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('[WS] 已连接');
      updateWsStatus(true);
      clearTimeout(wsReconnectTimer);
      
      // 启动心跳
      startWsHeartbeat();
    };
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWsMessage(message);
      } catch (e) {
        console.error('[WS] 解析消息失败:', e);
      }
    };
    
    ws.onclose = () => {
      console.log('[WS] 连接关闭');
      updateWsStatus(false);
      stopWsHeartbeat();
      scheduleReconnect();
    };
    
    ws.onerror = (error) => {
      console.error('[WS] 连接错误:', error);
      updateWsStatus(false);
    };
    
  } catch (e) {
    console.error('[WS] 连接失败:', e);
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  clearTimeout(wsReconnectTimer);
  wsReconnectTimer = setTimeout(() => {
    console.log('[WS] 尝试重连...');
    connectWebSocket();
  }, 5000);
}

function startWsHeartbeat() {
  stopWsHeartbeat();
  wsHeartbeatTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
    }
  }, WS_HEARTBEAT_INTERVAL);
}

function stopWsHeartbeat() {
  if (wsHeartbeatTimer) {
    clearInterval(wsHeartbeatTimer);
    wsHeartbeatTimer = null;
  }
}

// 处理来自服务器的 WebSocket 消息
async function handleWsMessage(message) {
  const { type, request_id } = message;
  
  console.log('[WS] 收到消息:', type);
  
  switch (type) {
    case 'ping':
      // 响应心跳
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }));
      }
      break;
      
    case 'pong':
      // 心跳响应，计算延迟
      if (message.timestamp) {
        const latency = Date.now() - message.timestamp;
        serverStatus.latency = latency;
      }
      break;
      
    case 'prepare-click':
      // 服务器准备点击，需要确认 hover 元素
      await handlePrepareClick(message);
      break;
      
    default:
      console.log('[WS] 未知消息类型:', type);
  }
}

// 处理 prepare-click 消息：移动鼠标到目标位置，确认 hover 元素
async function handlePrepareClick(message) {
  const { request_id, viewport_x, viewport_y, nav_bar_height, element_info } = message;
  
  // 获取当前活动的 tab
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!activeTab) {
    sendWsMessage({
      type: 'confirm-hover',
      request_id,
      confirmed: false,
      error: '没有活动标签页'
    });
    return;
  }
  
  // 在页面中检测指定坐标位置的元素
  try {
    const result = await chrome.scripting.executeScript({
      target: { tabId: activeTab.id },
      func: (x, y, expectedTag, expectedText) => {
        // 获取指定坐标位置的元素
        const el = document.elementFromPoint(x, y);
        if (!el) return { found: false, error: '坐标位置没有元素' };
        
        const actualTag = el.tagName;
        const actualText = (el.textContent || '').trim().substring(0, 50);
        const actualRole = el.getAttribute('role');
        const actualJsname = el.getAttribute('jsname');
        
        // 检查元素是否匹配预期
        let matched = true;
        let reasons = [];
        
        if (expectedTag && actualTag !== expectedTag) {
          matched = false;
          reasons.push(`tag不匹配: 期望${expectedTag}, 实际${actualTag}`);
        }
        
        if (expectedText && !actualText.includes(expectedText)) {
          matched = false;
          reasons.push(`text不匹配: 期望包含"${expectedText}", 实际"${actualText}"`);
        }
        
        // 获取元素的精确位置
        const rect = el.getBoundingClientRect();
        
        return {
          found: true,
          matched,
          reasons,
          element: {
            tag: actualTag,
            text: actualText,
            role: actualRole,
            jsname: actualJsname,
            rect: {
              x: Math.round(rect.left + rect.width / 2),
              y: Math.round(rect.top + rect.height / 2),
              width: Math.round(rect.width),
              height: Math.round(rect.height)
            }
          }
        };
      },
      args: [
        viewport_x, 
        viewport_y, 
        element_info?.tag || null,
        element_info?.text || null
      ],
      world: 'MAIN'
    });
    
    const checkResult = result?.[0]?.result;
    console.log('[WS] 元素检查结果:', JSON.stringify(checkResult));
    
    if (checkResult && checkResult.found) {
      sendWsMessage({
        type: 'confirm-hover',
        request_id,
        confirmed: checkResult.matched,
        element: checkResult.element,
        reasons: checkResult.reasons
      });
    } else {
      sendWsMessage({
        type: 'confirm-hover',
        request_id,
        confirmed: false,
        error: checkResult?.error || '元素检查失败'
      });
    }
    
  } catch (e) {
    console.error('[WS] 元素检查异常:', e);
    sendWsMessage({
      type: 'confirm-hover',
      request_id,
      confirmed: false,
      error: e.message
    });
  }
}

function sendWsMessage(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  } else {
    console.warn('[WS] 连接未就绪，无法发送消息');
  }
}

// ==================== 系统通知 ====================

function showNotification(title, message) {
  try {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title: title,
      message: message,
      priority: 1
    });
  } catch (e) {
    console.error('[通知] 发送失败:', e);
  }
}

function notifySearchComplete(total, successCount, failCount) {
  let title = '搜图任务完成';
  let parts = [];
  
  if (total > 0) {
    parts.push(`共 ${total} 张`);
  }
  if (successCount > 0) {
    parts.push(`成功 ${successCount} 张`);
  }
  if (failCount > 0) {
    parts.push(`失败 ${failCount} 张`);
  }
  
  let message = parts.join('，');
  if (!message) {
    message = '任务已完成';
  }
  
  showNotification(title, message);
}

// 从storage加载搜索记录
async function loadSearchedImages() {
  try {
    const result = await chrome.storage.local.get(['searchedImages']);
    if (result.searchedImages) {
      searchedImages = new Map(Object.entries(result.searchedImages));
      console.log('[搜图] 加载搜索记录:', searchedImages.size, '条');
    }
  } catch (e) {
    console.error('[搜图] 加载搜索记录失败:', e);
  }
}

// 保存搜索记录到storage
async function saveSearchedImages() {
  try {
    const obj = Object.fromEntries(searchedImages);
    await chrome.storage.local.set({ searchedImages: obj });
  } catch (e) {
    console.error('[搜图] 保存搜索记录失败:', e);
  }
}

// 心跳检测
async function startHeartbeat() {
  // WebSocket 心跳已内置，这里只做备用的 HTTP 健康检查
  // 初始检查一次
  await checkServerHealth();
  // 每 60 秒检查一次（作为 WebSocket 断开时的备用检测）
  setInterval(checkServerHealth, 60000);
}

async function checkServerHealth() {
  // 如果 WebSocket 已连接，优先使用 WebSocket 状态
  if (wsConnected) {
    serverStatus = {
      online: true,
      lastCheck: Date.now(),
      latency: serverStatus.latency || 0,
      message: 'WebSocket 已连接'
    };
    updateBadge();
    await chrome.storage.local.set({ serverStatus });
    return;
  }
  
  // WebSocket 未连接时，使用 HTTP 健康检查作为备用
  try {
    const settings = await chrome.storage.local.get(['serverUrl']);
    const serverUrl = settings.serverUrl || 'http://localhost:5277';
    
    const startTime = Date.now();
    const response = await fetch(`${serverUrl}/api/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(HEALTH_TIMEOUT)
    });
    const latency = Date.now() - startTime;

    if (response.ok) {
      const data = await response.json();
      serverStatus = {
        online: true,
        lastCheck: Date.now(),
        latency: latency,
        message: data.message || '服务正常'
      };
    } else {
      throw new Error('服务器响应异常');
    }
  } catch (error) {
    serverStatus = {
      online: false,
      lastCheck: Date.now(),
      latency: 0,
      message: error.message
    };
  }

  updateBadge();
  await chrome.storage.local.set({ serverStatus });
}

function updateBadge() {
  if (serverStatus.online) {
    chrome.action.setBadgeText({ text: 'ON' });
    chrome.action.setBadgeBackgroundColor({ color: '#4caf50' });
  } else {
    chrome.action.setBadgeText({ text: 'OFF' });
    chrome.action.setBadgeBackgroundColor({ color: '#f44336' });
  }
}

// 更新 WebSocket 连接状态并同步到 serverStatus
function updateWsStatus(connected, latency = 0) {
  wsConnected = connected;
  
  if (connected) {
    serverStatus = {
      online: true,
      lastCheck: Date.now(),
      latency: latency,
      message: 'WebSocket 已连接'
    };
  } else {
    serverStatus = {
      online: false,
      lastCheck: Date.now(),
      latency: 0,
      message: 'WebSocket 断开'
    };
  }
  
  updateBadge();
  chrome.storage.local.set({ serverStatus }).catch(() => {});
}

function waitForTabComplete(tabId) {
  return new Promise((resolve) => {
    const check = async () => {
      try {
        const tab = await chrome.tabs.get(tabId);
        if (tab.status === 'complete') {
          resolve();
        } else {
          setTimeout(check, 100);
        }
      } catch {
        resolve();
      }
    };
    check();
  });
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 检查tab是否还存在且URL是搜图结果页面
async function isTabValidForSkip(tabId, recordedUrl) {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !tab.url) {
      return false;
    }
    
    // Google搜图页面
    const isGoogleSearch = tab.url.includes('google.com') && (
      tab.url.includes('/search') || 
      tab.url.includes('lens.google') ||
      tab.url.includes('tbm=isch')
    );
    
    // Amazon搜图页面
    const isAmazonSearch = tab.url.includes('amazon.com') && (
      tab.url.includes('/stylesnap') ||
      tab.url.includes('/s') ||
      tab.url.includes('/gp/')
    );
    
    if (recordedUrl && recordedUrl.includes('/search')) {
      return isGoogleSearch && tab.url.includes('/search');
    }
    
    if (recordedUrl && recordedUrl.includes('amazon.com')) {
      return isAmazonSearch;
    }
    
    return isGoogleSearch || isAmazonSearch;
  } catch {
    return false;
  }
}

// 清理无效的记录
async function cleanupSearchedImages() {
  let changed = false;
  for (const [filename, record] of searchedImages.entries()) {
    const valid = await isTabValidForSkip(record.tabId, record.url);
    if (!valid) {
      searchedImages.delete(filename);
      console.log('[搜图] 清理无效记录:', filename);
      changed = true;
    }
  }
  if (changed) {
    await saveSearchedImages();
  }
}

// ==================== 页面内执行的函数 ====================

function clickSearchByImage() {
  console.log('[搜图] 查找按图搜索按钮...');
  
  const selectors = [
    'div[aria-label="按图搜索"]',
    'div[aria-label="Search by image"]',
    'div[aria-label="以圖搜尋"]',
    'div[jsname="R6LKDc"]'
  ];
  
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el) {
      console.log('[搜图] 找到按钮，点击:', selector);
      el.click();
      return { success: true, method: 'selector', selector };
    }
  }
  
  const allDivs = document.querySelectorAll('div, button, span');
  for (const el of allDivs) {
    const text = el.textContent?.trim() || '';
    if (text === '按图搜索' || text === 'Search by image') {
      console.log('[搜图] 通过文本找到按钮');
      el.click();
      return { success: true, method: 'text' };
    }
  }
  
  return { success: false, error: '未找到按图搜索按钮' };
}

function clickUploadFile() {
  console.log('[搜图] 查找上传文件标签...');
  
  const spans = document.querySelectorAll('span[role="button"][jsaction][jsname]');
  console.log('[搜图] 找到 span[role="button"] 元素:', spans.length);
  
  for (const span of spans) {
    const text = span.textContent?.trim() || '';
    console.log('[搜图] 检查元素文本:', text);
    if (text === '上传文件' || text === 'Upload a file' || text === '上傳檔案') {
      console.log('[搜图] 找到上传文件按钮，点击');
      span.click();
      return { success: true, method: 'span-role-button', text };
    }
  }
  
  const allSpans = document.querySelectorAll('span');
  for (const span of allSpans) {
    const text = span.textContent?.trim() || '';
    if (text === '上传文件') {
      console.log('[搜图] 通过文本找到上传文件span');
      span.click();
      return { success: true, method: 'span-text' };
    }
  }
  
  return { success: false, error: '未找到上传文件标签' };
}

function findFileUploadButton() {
  try {
    console.log('[搜图] 开始查找文件上传按钮...');
    
    const navBarHeight = window.outerHeight - window.innerHeight;
    console.log('[搜图] 导航栏高度:', navBarHeight);
    
    const spans = document.querySelectorAll('span[jsname][jsaction][role="button"]');
    console.log('[搜图] 找到 span[jsname][jsaction][role="button"] 元素:', spans.length);
    
    for (const span of spans) {
      const text = span.textContent?.trim() || '';
      console.log('[搜图] 检查元素文本:', text);
      if (text === '上传文件' || text === 'Upload a file') {
        const rect = span.getBoundingClientRect();
        console.log('[搜图] 找到上传文件按钮:', rect);
        return {
          success: true,
          method: 'span-role-button',
          navBarHeight: navBarHeight,
          viewport: {
            x: Math.round(rect.left + rect.width / 2),
            y: Math.round(rect.top + rect.height / 2),
            left: Math.round(rect.left),
            top: Math.round(rect.top)
          },
          size: {
            width: Math.round(rect.width),
            height: Math.round(rect.height)
          },
          element: {
            tag: span.tagName,
            text: text,
            className: span.className
          }
        };
      }
    }
    
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      const rect = fileInput.getBoundingClientRect();
      if (rect.width > 0 || rect.height > 0) {
        console.log('[搜图] 使用file input');
        return {
          success: true,
          method: 'file-input',
          navBarHeight: navBarHeight,
          viewport: {
            x: Math.round(rect.left + rect.width / 2),
            y: Math.round(rect.top + rect.height / 2)
          },
          size: { width: Math.round(rect.width), height: Math.round(rect.height) },
          element: { tag: 'INPUT', type: 'file' }
        };
      }
    }
    
    const allButtons = [];
    document.querySelectorAll('span[role="button"]').forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        allButtons.push({
          text: el.textContent?.trim()?.substring(0, 30),
          jsname: el.getAttribute('jsname'),
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2)
        });
      }
    });
    
    console.log('[搜图] 未找到上传文件按钮，所有 role=button 的 span:', allButtons);
    
    return { 
      success: false, 
      error: '未找到上传文件按钮',
      navBarHeight: navBarHeight,
      availableElements: allButtons
    };
  } catch (e) {
    console.error('[搜图] findFileUploadButton异常:', e);
    return { success: false, error: '函数执行异常: ' + e.message };
  }
}

function clickSearchBtn() {
  console.log('[搜图] 查找搜索按钮...');
  
  const selectors = [
    'div[aria-label="搜尋"][role="button"]',
    'div[aria-label="Search"][role="button"]',
    'div[aria-label="搜索"][role="button"]',
    'button[aria-label="搜尋"]',
    'button[aria-label="Search"]'
  ];
  
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el) {
      console.log('[搜图] 找到搜索按钮:', selector);
      el.click();
      return { success: true, method: 'selector' };
    }
  }
  
  const buttons = document.querySelectorAll('div[role="button"], button');
  for (const btn of buttons) {
    const text = btn.textContent?.trim() || '';
    if (text === '搜尋' || text === 'Search' || text === '搜索') {
      console.log('[搜图] 通过文本找到搜索按钮');
      btn.click();
      return { success: true, method: 'text' };
    }
  }
  
  return { success: false, error: '未找到搜索按钮' };
}

function getPageInfo() {
  const buttons = [];
  document.querySelectorAll('button, div[role="button"], [role="tab"], span').forEach(el => {
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      buttons.push({
        tag: el.tagName,
        text: el.textContent?.trim()?.substring(0, 50),
        aria: el.getAttribute('aria-label'),
        class: el.className?.substring(0, 30)
      });
    }
  });
  
  const fileInputs = document.querySelectorAll('input[type="file"]');
  
  return {
    url: window.location.href,
    title: document.title,
    buttons: buttons.slice(0, 30),
    fileInputs: fileInputs.length
  };
}

// ==================== Amazon搜图页面函数 ====================

function findAmazonUploadButton() {
  try {
    console.log('[Amazon搜图] 查找上传按钮...');
    
    const navBarHeight = window.outerHeight - window.innerHeight;
    console.log('[Amazon搜图] 导航栏高度:', navBarHeight);
    
    // 方法1: 通过ID选择器查找
    const targetBtn = document.querySelector('span#a-autoid-0-announce');
    if (targetBtn) {
      const rect = targetBtn.getBoundingClientRect();
      console.log('[Amazon搜图] 通过ID找到按钮:', rect);
      return {
        success: true,
        method: 'id-selector',
        navBarHeight: navBarHeight,
        viewport: {
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2),
          left: Math.round(rect.left),
          top: Math.round(rect.top)
        },
        size: {
          width: Math.round(rect.width),
          height: Math.round(rect.height)
        },
        element: {
          tag: targetBtn.tagName,
          text: targetBtn.textContent?.trim(),
          id: targetBtn.id
        }
      };
    }
    
    // 方法2: 查找包含 "Upload" 或 "上传" 文本的按钮
    const allSpans = document.querySelectorAll('span, button, a');
    for (const el of allSpans) {
      const text = el.textContent?.trim() || '';
      if (text.includes('Upload') || text.includes('上传') || text.includes('Browse')) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 20) {
          console.log('[Amazon搜图] 通过文本找到按钮:', text);
          return {
            success: true,
            method: 'text-match',
            navBarHeight: navBarHeight,
            viewport: {
              x: Math.round(rect.left + rect.width / 2),
              y: Math.round(rect.top + rect.height / 2),
              left: Math.round(rect.left),
              top: Math.round(rect.top)
            },
            size: {
              width: Math.round(rect.width),
              height: Math.round(rect.height)
            },
            element: {
              tag: el.tagName,
              text: text.substring(0, 30)
            }
          };
        }
      }
    }
    
    // 方法3: 查找file input
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      const rect = fileInput.getBoundingClientRect();
      console.log('[Amazon搜图] 使用file input');
      return {
        success: true,
        method: 'file-input',
        navBarHeight: navBarHeight,
        viewport: {
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2)
        },
        size: { width: Math.round(rect.width), height: Math.round(rect.height) },
        element: { tag: 'INPUT', type: 'file' }
      };
    }
    
    // 记录所有可点击元素用于调试
    const allButtons = [];
    document.querySelectorAll('span[role="button"], button, a').forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        allButtons.push({
          tag: el.tagName,
          text: el.textContent?.trim()?.substring(0, 30),
          id: el.id,
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2)
        });
      }
    });
    
    console.log('[Amazon搜图] 未找到上传按钮，所有可点击元素:', allButtons);
    
    return { 
      success: false, 
      error: '未找到上传按钮',
      navBarHeight: navBarHeight,
      availableElements: allButtons.slice(0, 20)
    };
  } catch (e) {
    console.error('[Amazon搜图] findAmazonUploadButton异常:', e);
    return { success: false, error: '函数执行异常: ' + e.message };
  }
}

// ==================== 准备单个Tab ====================

async function prepareSearchTab(imageInfo) {
  const { filename, isLocal } = imageInfo;
  
  try {
    // 打开Google搜图页面
    const tab = await chrome.tabs.create({
      url: 'https://www.google.com/imghp',
      active: false
    });
    
    await waitForTabComplete(tab.id);
    await wait(2000);
    
    // 记录图片对应的tab信息
    searchedImages.set(filename, {
      tabId: tab.id,
      url: tab.url,
      timestamp: Date.now()
    });
    await saveSearchedImages();
    
    // 点击"按图搜索"
    let result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: clickSearchByImage,
      world: 'MAIN'
    });
    
    if (!result[0]?.result?.success) {
      console.error('[搜图] 点击按图搜索失败:', filename);
      return { success: false, filename, error: '点击按图搜索失败' };
    }
    
    await wait(1500);
    
    // 点击"上传文件"
    result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: clickUploadFile,
      world: 'MAIN'
    });
    
    console.log('[搜图] Tab准备完成:', filename, 'tabId:', tab.id);
    
    return { 
      success: true, 
      filename, 
      isLocal,
      tabId: tab.id,
      uploadSuccess: result[0]?.result?.success || false
    };
    
  } catch (error) {
    console.error('[搜图] 准备Tab失败:', filename, error);
    return { success: false, filename, error: error.message };
  }
}

// 通过复制已有Tab来创建新Tab（更快，继承页面状态）
async function duplicateSearchTab(sourceTabId, imageInfo) {
  const { filename, isLocal } = imageInfo;
  
  try {
    // 复制tab
    const newTab = await chrome.tabs.duplicate(sourceTabId);
    await waitForTabComplete(newTab.id);
    await wait(1000);
    
    // 记录图片对应的tab信息
    searchedImages.set(filename, {
      tabId: newTab.id,
      url: newTab.url,
      timestamp: Date.now()
    });
    await saveSearchedImages();
    
    console.log('[搜图] Tab复制完成:', filename, 'tabId:', newTab.id);
    
    return {
      success: true,
      filename,
      isLocal,
      tabId: newTab.id
    };
    
  } catch (error) {
    console.error('[搜图] 复制Tab失败:', filename, error);
    return { success: false, filename, error: error.message };
  }
}

// 创建Tab分组
async function createTabGroup(tabIds, title) {
  try {
    if (tabIds.length === 0) return -1;
    
    // 将所有tab加入分组
    const groupId = await chrome.tabs.group({ tabIds });
    
    // 设置分组标题和颜色
    await chrome.tabGroups.update(groupId, {
      title: title || 'Google搜图',
      color: 'blue',
      collapsed: false
    });
    
    console.log('[搜图] 创建Tab分组:', title, 'groupId:', groupId, 'tabs:', tabIds.length);
    return groupId;
    
  } catch (error) {
    console.error('[搜图] 创建分组失败:', error);
    return -1;
  }
}

// ==================== Amazon搜图Tab准备 ====================

async function prepareAmazonSearchTab(imageInfo) {
  const { filename, isLocal } = imageInfo;
  
  try {
    // 打开Amazon StyleSnap页面
    const tab = await chrome.tabs.create({
      url: 'https://www.amazon.com/stylesnap',
      active: false
    });
    
    await waitForTabComplete(tab.id);
    await wait(3000); // Amazon页面加载较慢，多等一会
    
    // 记录图片对应的tab信息
    searchedImages.set(filename, {
      tabId: tab.id,
      url: tab.url,
      timestamp: Date.now()
    });
    await saveSearchedImages();
    
    console.log('[Amazon搜图] Tab准备完成:', filename, 'tabId:', tab.id);
    
    return { 
      success: true, 
      filename, 
      isLocal,
      tabId: tab.id
    };
    
  } catch (error) {
    console.error('[Amazon搜图] 准备Tab失败:', filename, error);
    return { success: false, filename, error: error.message };
  }
}

// 通过复制已有Tab来创建新Tab（更快）
async function duplicateAmazonSearchTab(sourceTabId, imageInfo) {
  const { filename, isLocal } = imageInfo;
  
  try {
    // 复制tab
    const newTab = await chrome.tabs.duplicate(sourceTabId);
    await waitForTabComplete(newTab.id);
    await wait(1500);
    
    // 记录图片对应的tab信息
    searchedImages.set(filename, {
      tabId: newTab.id,
      url: newTab.url,
      timestamp: Date.now()
    });
    await saveSearchedImages();
    
    console.log('[Amazon搜图] Tab复制完成:', filename, 'tabId:', newTab.id);
    
    return {
      success: true,
      filename,
      isLocal,
      tabId: newTab.id
    };
    
  } catch (error) {
    console.error('[Amazon搜图] 复制Tab失败:', filename, error);
    return { success: false, filename, error: error.message };
  }
}

// ==================== Amazon上传到Tab ====================

async function uploadToAmazonTab(prepareResult) {
  const { filename, isLocal, tabId } = prepareResult;
  const settings = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = settings.serverUrl || 'http://localhost:5277';
  const logs = [];
  const MAX_RETRIES = 3;
  
  try {
    // 激活tab
    await chrome.tabs.update(tabId, { active: true });
    await wait(500);
    
    let buttonResult = null;
    
    // 重试循环
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      logs.push(`[上传] 第 ${attempt}/${MAX_RETRIES} 次尝试`);
      
      // 获取上传按钮坐标
      logs.push('获取上传按钮坐标');
      
      let result = await chrome.scripting.executeScript({
        target: { tabId },
        func: findAmazonUploadButton,
        world: 'MAIN'
      });
      
      buttonResult = result?.[0]?.result;
      
      if (!buttonResult || !buttonResult.success) {
        logs.push('上传按钮未找到');
        if (attempt < MAX_RETRIES) {
          await wait(1000);
          continue;
        }
        throw new Error('获取上传按钮坐标失败');
      }
      
      logs.push('按钮坐标: (' + buttonResult.viewport.x + ', ' + buttonResult.viewport.y + ')');
      
      await wait(300);
      
      // 通知服务器点击坐标并选择文件
      logs.push('服务器点击坐标');
      const uploadResponse = await fetch(`${serverUrl}/api/select-file-and-upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          filename,
          isLocal: isLocal || false,
          buttonX: buttonResult.viewport.x,
          buttonY: buttonResult.viewport.y,
          navBarHeight: buttonResult.navBarHeight,
          buttonWidth: buttonResult.size?.width || 0,
          buttonHeight: buttonResult.size?.height || 0
        }),
        signal: AbortSignal.timeout(30000)
      });
      
      const uploadResult = await uploadResponse.json();
      logs.push('服务器响应: ' + JSON.stringify(uploadResult));
      
      if (uploadResult.success) {
        // 上传成功，Amazon会自动处理图片搜索
        await wait(3000);
        
        // 异步更新URL记录
        setTimeout(async () => {
          try {
            const finalTab = await chrome.tabs.get(tabId);
            if (finalTab && finalTab.url) {
              searchedImages.set(filename, {
                tabId,
                url: finalTab.url,
                timestamp: Date.now()
              });
              await saveSearchedImages();
            }
          } catch (e) {
            console.log('[Amazon搜图] 异步更新URL失败:', e);
          }
        }, 5000);
        
        logs.push('Amazon搜图完成!');
        return { success: true, filename, tabId, logs };
      }
      
      // 上传失败，重试
      logs.push(`上传失败: ${uploadResult.error}，准备重试...`);
      await wait(500);
    }
    
    throw new Error(`${MAX_RETRIES} 次尝试后仍失败`);
    
  } catch (error) {
    logs.push('失败: ' + error.message);
    console.error('[Amazon搜图] 上传失败:', filename, logs.join('\n'));
    return { success: false, filename, error: error.message, logs };
  }
}

// ==================== Amazon批量搜图主流程 ====================

async function executeBatchAmazonSearch(images) {
  // 先清理无效的记录
  await cleanupSearchedImages();
  
  // 过滤掉已经在搜图中的图片
  const imagesToSearch = [];
  const skippedImages = [];
  
  for (const img of images) {
    const record = searchedImages.get(img.filename);
    if (record) {
      const valid = await isTabValidForSkip(record.tabId, record.url);
      if (valid) {
        skippedImages.push(img.filename);
        console.log('[Amazon搜图] 跳过已搜图的图片:', img.filename);
        continue;
      } else {
        searchedImages.delete(img.filename);
        await saveSearchedImages();
      }
    }
    imagesToSearch.push(img);
  }
  
  if (skippedImages.length > 0) {
    chrome.runtime.sendMessage({
      type: 'searchSkipped',
      count: skippedImages.length,
      filenames: skippedImages
    }).catch(() => {});
  }
  
  if (imagesToSearch.length === 0) {
    console.log('[Amazon搜图] 所有图片都已搜图');
    return [];
  }
  
  console.log('[Amazon搜图] 需要搜图的图片:', imagesToSearch.length, '张');
  
  // ========== 阶段1: 准备Tab ==========
  chrome.runtime.sendMessage({
    type: 'searchPhase',
    phase: 'prepare',
    total: imagesToSearch.length
  }).catch(() => {});
  
  const prepareResults = [];
  let firstTabId = null;
  
  // 第一个tab：正常创建并准备
  chrome.runtime.sendMessage({
    type: 'searchProgress',
    phase: 'prepare',
    current: 1,
    total: imagesToSearch.length,
    filename: imagesToSearch[0].filename
  }).catch(() => {});
  
  console.log('[Amazon搜图] 创建第一个Tab...');
  const firstResult = await prepareAmazonSearchTab(imagesToSearch[0]);
  prepareResults.push(firstResult);
  
  if (firstResult.success) {
    firstTabId = firstResult.tabId;
    console.log('[Amazon搜图] 第一个Tab准备完成，tabId:', firstTabId);
  } else {
    console.error('[Amazon搜图] 第一个Tab准备失败，无法复制后续Tab');
    // 如果第一个失败，后续全部标记失败
    for (let i = 1; i < imagesToSearch.length; i++) {
      prepareResults.push({ 
        success: false, 
        filename: imagesToSearch[i].filename, 
        error: '首个Tab准备失败' 
      });
    }
  }
  
  // 后续tab：通过复制第一个tab创建
  if (firstTabId) {
    for (let i = 1; i < imagesToSearch.length; i++) {
      chrome.runtime.sendMessage({
        type: 'searchProgress',
        phase: 'prepare',
        current: i + 1,
        total: imagesToSearch.length,
        filename: imagesToSearch[i].filename
      }).catch(() => {});
      
      console.log('[Amazon搜图] 复制Tab:', imagesToSearch[i].filename);
      const result = await duplicateAmazonSearchTab(firstTabId, imagesToSearch[i]);
      prepareResults.push(result);
      
      // 短暂间隔
      if (i < imagesToSearch.length - 1) {
        await wait(300);
      }
    }
  }
  
  const preparedTabs = prepareResults.filter(r => r.success);
  const prepareFailed = prepareResults.filter(r => !r.success);
  
  console.log('[Amazon搜图] Tab准备完成:', preparedTabs.length, '个成功,', prepareFailed.length, '个失败');
  
  // 创建Tab分组
  if (preparedTabs.length > 0) {
    const tabIds = preparedTabs.map(t => t.tabId);
    const timestamp = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    const groupTitle = `Amazon搜图 ${timestamp} (${preparedTabs.length})`;
    await createTabGroup(tabIds, groupTitle);
  }
  
  // ========== 阶段2: 逐个上传 ==========
  chrome.runtime.sendMessage({
    type: 'searchPhase',
    phase: 'upload',
    total: preparedTabs.length
  }).catch(() => {});
  
  const results = [...prepareFailed];
  
  for (let i = 0; i < preparedTabs.length; i++) {
    const tab = preparedTabs[i];
    
    chrome.runtime.sendMessage({
      type: 'searchProgress',
      phase: 'upload',
      current: i + 1,
      total: preparedTabs.length,
      filename: tab.filename
    }).catch(() => {});
    
    console.log('[Amazon搜图] 开始上传:', tab.filename, '(' + (i+1) + '/' + preparedTabs.length + ')');
    
    const result = await uploadToAmazonTab(tab);
    results.push(result);
    
    console.log('[Amazon搜图] 上传完成:', tab.filename, result.success ? '成功' : '失败');
    
    // 间隔一下再处理下一个
    if (i < preparedTabs.length - 1) {
      await wait(1000);
    }
  }
  
  return results;
}

// ==================== 阶段2: 上传到Tab ====================

async function uploadToTab(prepareResult) {
  const { filename, isLocal, tabId } = prepareResult;
  const settings = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = settings.serverUrl || 'http://localhost:5277';
  const logs = [];
  const MAX_RETRIES = 3;
  
  try {
    // 激活tab
    await chrome.tabs.update(tabId, { active: true });
    await wait(500);
    
    let buttonResult = null;
    
    // 重试循环
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      logs.push(`[上传] 第 ${attempt}/${MAX_RETRIES} 次尝试`);
      
      // 获取文件选择按钮坐标
      logs.push('获取文件选择按钮坐标');
      
      let result = await chrome.scripting.executeScript({
        target: { tabId },
        func: findFileUploadButton,
        world: 'MAIN'
      });
      
      buttonResult = result?.[0]?.result;
      
      // 如果按钮不存在，重新点击"以图搜图"打开文件上传视图
      if (!buttonResult || !buttonResult.success) {
        logs.push('文件上传按钮未找到，尝试重新点击以图搜图...');
        
        // 重新点击"按图搜图"
        let searchResult = await chrome.scripting.executeScript({
          target: { tabId },
          func: clickSearchByImage,
          world: 'MAIN'
        });
        
        if (!searchResult[0]?.result?.success) {
          logs.push('重新点击以图搜图失败');
          if (attempt < MAX_RETRIES) {
            await wait(1000);
            continue;
          }
          throw new Error('无法打开以图搜图视图');
        }
        
        await wait(1500);
        
        // 重新点击"上传文件"
        await chrome.scripting.executeScript({
          target: { tabId },
          func: clickUploadFile,
          world: 'MAIN'
        });
        
        await wait(1000);
        
        // 重新获取坐标
        result = await chrome.scripting.executeScript({
          target: { tabId },
          func: findFileUploadButton,
          world: 'MAIN'
        });
        
        buttonResult = result?.[0]?.result;
        
        if (!buttonResult || !buttonResult.success) {
          logs.push('重新获取坐标仍然失败');
          if (attempt < MAX_RETRIES) {
            await wait(500);
            continue;
          }
          throw new Error('获取文件选择按钮坐标失败');
        }
      }
      
      logs.push('按钮坐标: (' + buttonResult.viewport.x + ', ' + buttonResult.viewport.y + ')');
      
      await wait(300);
      
      // 通知服务器点击坐标并选择文件
      logs.push('服务器点击坐标');
      const uploadResponse = await fetch(`${serverUrl}/api/select-file-and-upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          filename,
          isLocal: isLocal || false,
          buttonX: buttonResult.viewport.x,
          buttonY: buttonResult.viewport.y,
          navBarHeight: buttonResult.navBarHeight,
          buttonWidth: buttonResult.size?.width || 0,
          buttonHeight: buttonResult.size?.height || 0
        }),
        signal: AbortSignal.timeout(30000)
      });
      
      const uploadResult = await uploadResponse.json();
      logs.push('服务器响应: ' + JSON.stringify(uploadResult));
      
      if (uploadResult.success) {
        // 上传成功，点击搜索按钮后直接返回
        await wait(2000);
        
        // 点击搜索按钮
        logs.push('点击搜索按钮');
        result = await chrome.scripting.executeScript({
          target: { tabId },
          func: clickSearchBtn,
          world: 'MAIN'
        });
        
        if (!result[0]?.result?.success) {
          logs.push('搜索按钮未找到，可能已自动提交');
        }
        
        // 不等待页面加载，直接更新记录并返回
        // 异步更新URL记录
        setTimeout(async () => {
          try {
            const finalTab = await chrome.tabs.get(tabId);
            if (finalTab && finalTab.url) {
              searchedImages.set(filename, {
                tabId,
                url: finalTab.url,
                timestamp: Date.now()
              });
              await saveSearchedImages();
            }
          } catch (e) {
            console.log('[搜图] 异步更新URL失败:', e);
          }
        }, 5000);
        
        logs.push('搜图完成!');
        return { success: true, filename, tabId, logs };
      }
      
      // 上传失败，重试
      logs.push(`上传失败: ${uploadResult.error}，准备重试...`);
      await wait(500);
    }
    
    throw new Error(`${MAX_RETRIES} 次尝试后仍失败`);
    
  } catch (error) {
    logs.push('失败: ' + error.message);
    console.error('[搜图] 上传失败:', filename, logs.join('\n'));
    return { success: false, filename, error: error.message, logs };
  }
}

// ==================== 批量搜图主流程 ====================

async function executeBatchGoogleSearch(images) {
  // 先清理无效的记录
  await cleanupSearchedImages();
  
  // 过滤掉已经在搜图中的图片
  const imagesToSearch = [];
  const skippedImages = [];
  
  for (const img of images) {
    const record = searchedImages.get(img.filename);
    if (record) {
      const valid = await isTabValidForSkip(record.tabId, record.url);
      if (valid) {
        skippedImages.push(img.filename);
        console.log('[搜图] 跳过已搜图的图片:', img.filename);
        continue;
      } else {
        searchedImages.delete(img.filename);
        await saveSearchedImages();
      }
    }
    imagesToSearch.push(img);
  }
  
  if (skippedImages.length > 0) {
    chrome.runtime.sendMessage({
      type: 'searchSkipped',
      count: skippedImages.length,
      filenames: skippedImages
    }).catch(() => {});
  }
  
  if (imagesToSearch.length === 0) {
    console.log('[搜图] 所有图片都已搜图');
    return [];
  }
  
  console.log('[搜图] 需要搜图的图片:', imagesToSearch.length, '张');
  
  // ========== 阶段1: 准备Tab（第一个创建，后续复制） ==========
  chrome.runtime.sendMessage({
    type: 'searchPhase',
    phase: 'prepare',
    total: imagesToSearch.length
  }).catch(() => {});
  
  const prepareResults = [];
  let firstTabId = null;
  
  // 第一个tab：正常创建并准备
  chrome.runtime.sendMessage({
    type: 'searchProgress',
    phase: 'prepare',
    current: 1,
    total: imagesToSearch.length,
    filename: imagesToSearch[0].filename
  }).catch(() => {});
  
  console.log('[搜图] 创建第一个Tab...');
  const firstResult = await prepareSearchTab(imagesToSearch[0]);
  prepareResults.push(firstResult);
  
  if (firstResult.success) {
    firstTabId = firstResult.tabId;
    console.log('[搜图] 第一个Tab准备完成，tabId:', firstTabId);
  } else {
    console.error('[搜图] 第一个Tab准备失败，无法复制后续Tab');
    // 如果第一个失败，后续全部标记失败
    for (let i = 1; i < imagesToSearch.length; i++) {
      prepareResults.push({ 
        success: false, 
        filename: imagesToSearch[i].filename, 
        error: '首个Tab准备失败' 
      });
    }
  }
  
  // 后续tab：通过复制第一个tab创建
  if (firstTabId) {
    for (let i = 1; i < imagesToSearch.length; i++) {
      chrome.runtime.sendMessage({
        type: 'searchProgress',
        phase: 'prepare',
        current: i + 1,
        total: imagesToSearch.length,
        filename: imagesToSearch[i].filename
      }).catch(() => {});
      
      console.log('[搜图] 复制Tab:', imagesToSearch[i].filename);
      const result = await duplicateSearchTab(firstTabId, imagesToSearch[i]);
      prepareResults.push(result);
      
      // 短暂间隔
      if (i < imagesToSearch.length - 1) {
        await wait(300);
      }
    }
  }
  
  const preparedTabs = prepareResults.filter(r => r.success);
  const prepareFailed = prepareResults.filter(r => !r.success);
  
  console.log('[搜图] Tab准备完成:', preparedTabs.length, '个成功,', prepareFailed.length, '个失败');
  
  // 创建Tab分组
  if (preparedTabs.length > 0) {
    const tabIds = preparedTabs.map(t => t.tabId);
    const timestamp = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    const groupTitle = `搜图 ${timestamp} (${preparedTabs.length})`;
    await createTabGroup(tabIds, groupTitle);
  }
  
  // ========== 阶段2: 逐个上传 ==========
  chrome.runtime.sendMessage({
    type: 'searchPhase',
    phase: 'upload',
    total: preparedTabs.length
  }).catch(() => {});
  
  const results = [...prepareFailed];
  
  for (let i = 0; i < preparedTabs.length; i++) {
    const tab = preparedTabs[i];
    
    chrome.runtime.sendMessage({
      type: 'searchProgress',
      phase: 'upload',
      current: i + 1,
      total: preparedTabs.length,
      filename: tab.filename
    }).catch(() => {});
    
    console.log('[搜图] 开始上传:', tab.filename, '(' + (i+1) + '/' + preparedTabs.length + ')');
    
    const result = await uploadToTab(tab);
    results.push(result);
    
    console.log('[搜图] 上传完成:', tab.filename, result.success ? '成功' : '失败');
    
    // 间隔一下再处理下一个
    if (i < preparedTabs.length - 1) {
      await wait(1000);
    }
  }
  
  return results;
}

// 监听消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getServerStatus') {
    sendResponse(serverStatus);
    return true;
  }

  if (request.action === 'checkServerNow') {
    checkServerHealth().then(() => sendResponse(serverStatus));
    return true;
  }

  if (request.action === 'getSearchedImages') {
    const list = [];
    for (const [filename, record] of searchedImages.entries()) {
      list.push({
        filename,
        tabId: record.tabId,
        timestamp: record.timestamp
      });
    }
    sendResponse({ searchedImages: list });
    return true;
  }

  if (request.action === 'startGoogleSearch') {
    executeBatchGoogleSearch(request.images)
      .then(results => {
        const total = results.length;
        const successCount = results.filter(r => r.success).length;
        const failCount = results.filter(r => !r.success).length;
        
        results.forEach((r, i) => {
          console.log(`[搜图] 图片${i+1}日志:`, r.logs?.join('\n'));
        });
        
        // 发送系统通知
        notifySearchComplete(total, successCount, failCount);
        
        chrome.runtime.sendMessage({
          type: 'searchComplete',
          successCount,
          failCount,
          results
        }).catch(() => {});
      })
      .catch(error => {
        // 错误也发送通知
        showNotification('搜图任务失败', error.message);
        
        chrome.runtime.sendMessage({
          type: 'searchError',
          error: error.message
        }).catch(() => {});
      });
    
    sendResponse({ started: true });
    return true;
  }

  if (request.action === 'startAmazonSearch') {
    executeBatchAmazonSearch(request.images)
      .then(results => {
        const total = results.length;
        const successCount = results.filter(r => r.success).length;
        const failCount = results.filter(r => !r.success).length;
        
        results.forEach((r, i) => {
          console.log(`[Amazon搜图] 图片${i+1}日志:`, r.logs?.join('\n'));
        });
        
        // 发送系统通知
        notifySearchComplete(total, successCount, failCount);
        
        chrome.runtime.sendMessage({
          type: 'searchComplete',
          successCount,
          failCount,
          results
        }).catch(() => {});
      })
      .catch(error => {
        // 错误也发送通知
        showNotification('Amazon搜图任务失败', error.message);
        
        chrome.runtime.sendMessage({
          type: 'searchError',
          error: error.message
        }).catch(() => {});
      });
    
    sendResponse({ started: true });
    return true;
  }
});

// 初始化
chrome.runtime.onInstalled.addListener(async () => {
  await loadSearchedImages();
  startHeartbeat();
  connectWebSocket();
});

// 服务工作者启动时也连接 WebSocket
connectWebSocket();
