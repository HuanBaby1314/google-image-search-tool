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

// ==================== 内存检测 ====================

// 内存检测开关（默认关闭）
let memoryCheckEnabled = false;

// 从存储加载内存检测开关状态
async function loadMemoryCheckSetting() {
  const settings = await chrome.storage.local.get(['memoryCheckEnabled']);
  memoryCheckEnabled = settings.memoryCheckEnabled === true;
  console.log('[内存] 检测开关:', memoryCheckEnabled ? '开启' : '关闭');
}

// 设置内存检测开关
async function setMemoryCheckEnabled(enabled) {
  memoryCheckEnabled = enabled;
  await chrome.storage.local.set({ memoryCheckEnabled: enabled });
  console.log('[内存] 检测开关已', enabled ? '开启' : '关闭');
}

// 每个 tab 预估内存占用 (MB) - 保守估计
const MEMORY_PER_TAB = {
  google: 350,  // Google 搜图页面（含图片加载）
  amazon: 450   // Amazon 搜图页面（更重）
};

// 最低保留可用内存 (MB)
const MIN_RESERVED_MEMORY = 2048; // 2GB

// 最大同时搜图 tab 数量限制
const MAX_CONCURRENT_TABS = {
  single: 30,  // 单平台
  all: 60      // 全平台
};

/**
 * 检查内存是否足够执行搜图任务
 * @param {string} platform - 'google' | 'amazon' | 'all'
 * @param {number} imageCount - 图片数量
 * @returns {Promise<{sufficient: boolean, available: number, required: number, tabsToClose: number, message: string}>}
 */
async function checkMemoryForTask(platform, imageCount) {
  // 如果内存检测关闭，直接通过
  if (!memoryCheckEnabled) {
    return {
      sufficient: true,
      available: -1,
      required: -1,
      tabsToClose: 0,
      message: '内存检测已关闭'
    };
  }

  try {
    const memInfo = await chrome.system.memory.getInfo();
    const availableMB = Math.round(memInfo.availableCapacity / 1024 / 1024);

    // 检查数量限制
    const maxTabs = platform === 'all' ? MAX_CONCURRENT_TABS.all : MAX_CONCURRENT_TABS.single;
    if (imageCount > maxTabs) {
      return {
        sufficient: false,
        available: availableMB,
        required: 0,
        tabsToClose: 0,
        message: `单次最多支持 ${maxTabs} 张图片${platform === 'all' ? '全平台' : ''}搜图，当前选择了 ${imageCount} 张`
      };
    }

    // 计算需要创建的 tab 数量
    let tabsToCreate = platform === 'all' ? imageCount * 2 : imageCount;

    // 计算所需内存
    let memoryPerTab = MEMORY_PER_TAB.google;
    if (platform === 'amazon') memoryPerTab = MEMORY_PER_TAB.amazon;
    if (platform === 'all') memoryPerTab = MEMORY_PER_TAB.google + MEMORY_PER_TAB.amazon;

    const requiredMB = tabsToCreate * memoryPerTab + MIN_RESERVED_MEMORY;
    const surplus = availableMB - requiredMB;

    if (surplus < 0) {
      const tabsToClose = Math.ceil(Math.abs(surplus) / 350);
      return {
        sufficient: false,
        available: availableMB,
        required: requiredMB,
        tabsToClose,
        message: `内存不足！可用 ${availableMB}MB，需要约 ${requiredMB}MB。请先关闭 ${tabsToClose} 个标签页后再试。`
      };
    }

    return {
      sufficient: true,
      available: availableMB,
      required: requiredMB,
      tabsToClose: 0,
      message: `内存充足（可用 ${availableMB}MB，需要 ${requiredMB}MB）`
    };

  } catch (error) {
    console.error('[内存] 检测失败:', error);
    return {
      sufficient: true,
      available: -1,
      required: -1,
      tabsToClose: 0,
      message: '内存检测失败，跳过检查'
    };
  }
}

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
      func: (x, y, expectedType, expectedTag, expectedText) => {
        // 获取指定坐标位置的元素
        const el = document.elementFromPoint(x, y);
        if (!el) return { found: false, error: '坐标位置没有元素' };
        
        const actualTag = el.tagName;
        const actualText = (el.textContent || '').trim().substring(0, 100);
        const actualRole = el.getAttribute('role');
        const actualJsname = el.getAttribute('jsname');
        const actualType = el.getAttribute('type');
        const actualAriaLabel = el.getAttribute('aria-label');
        const actualClassName = el.className || '';
        
        // 检查元素是否匹配预期
        let matched = true;
        let reasons = [];
        let isFileUploadButton = false;
        
        // 检测是否是文件上传按钮
        if (expectedType === 'file_upload_button') {
          // 文件上传按钮的特征：
          // 1. input[type="file"]
          // 2. 包含"上传"、"Upload"、"选择文件"等文本的按钮
          // 3. 触发文件选择的label或div
          // 4. aria-label包含上传相关关键词
          
          const uploadKeywords = ['上传', 'upload', '选择文件', 'choose file', 'select file', 
                                  'browse', '浏览', '选取', 'pick'];
          
          // 检查是否是 input[type="file"]
          if (actualTag === 'INPUT' && actualType === 'file') {
            isFileUploadButton = true;
            reasons.push('是input[type="file"]元素');
          }
          
          // 检查文本是否包含上传关键词
          const textLower = actualText.toLowerCase();
          const hasUploadKeyword = uploadKeywords.some(kw => textLower.includes(kw));
          if (hasUploadKeyword) {
            isFileUploadButton = true;
            reasons.push(`文本包含上传关键词: "${actualText}"`);
          }
          
          // 检查aria-label是否包含上传关键词
          if (actualAriaLabel) {
            const ariaLower = actualAriaLabel.toLowerCase();
            const hasAriaKeyword = uploadKeywords.some(kw => ariaLower.includes(kw));
            if (hasAriaKeyword) {
              isFileUploadButton = true;
              reasons.push(`aria-label包含上传关键词: "${actualAriaLabel}"`);
            }
          }
          
          // 检查class是否包含上传相关关键词
          const classLower = actualClassName.toLowerCase();
          const classKeywords = ['upload', 'file-input', 'file-select', 'attach'];
          const hasClassKeyword = classKeywords.some(kw => classLower.includes(kw));
          if (hasClassKeyword) {
            isFileUploadButton = true;
            reasons.push(`class包含上传相关关键词`);
          }
          
          // 检查是否有相邻的 input[type="file"]（可能是label或按钮触发文件选择）
          const nearbyInput = el.querySelector('input[type="file"]') || 
                             el.parentElement?.querySelector('input[type="file"]');
          if (nearbyInput) {
            isFileUploadButton = true;
            reasons.push('包含或相邻有input[type="file"]');
          }
          
          // 检查是否是可点击的元素（按钮、div、span等）
          const clickableTags = ['BUTTON', 'DIV', 'SPAN', 'A', 'LABEL'];
          const isClickable = clickableTags.includes(actualTag) || 
                             el.onclick || 
                             actualRole === 'button';
          
          if (!isFileUploadButton && isClickable) {
            // 如果是可点击元素但没有明确的上传特征，标记为不确定
            reasons.push('是可点击元素，但未检测到明确的文件上传特征');
          }
          
          matched = isFileUploadButton;
          
        } else {
          // 通用元素检查（非文件上传按钮）
          if (expectedTag && actualTag !== expectedTag) {
            matched = false;
            reasons.push(`tag不匹配: 期望${expectedTag}, 实际${actualTag}`);
          }
          
          if (expectedText && !actualText.includes(expectedText)) {
            matched = false;
            reasons.push(`text不匹配: 期望包含"${expectedText}", 实际"${actualText}"`);
          }
        }
        
        // 获取元素的精确位置
        const rect = el.getBoundingClientRect();
        
        return {
          found: true,
          matched,
          isFileUploadButton,
          reasons,
          element: {
            tag: actualTag,
            text: actualText,
            role: actualRole,
            jsname: actualJsname,
            type: actualType,
            ariaLabel: actualAriaLabel,
            className: actualClassName.substring(0, 100),
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
        element_info?.expected_type || null,
        element_info?.tag || null,
        element_info?.text || null
      ],
      world: 'MAIN'
    });
    
    const checkResult = result?.[0]?.result;
    console.log('[WS] 元素检查结果:', JSON.stringify(checkResult));
    
    if (checkResult && checkResult.found) {
      const response = {
        type: 'confirm-hover',
        request_id,
        confirmed: checkResult.matched,
        isFileUploadButton: checkResult.isFileUploadButton,
        element: checkResult.element,
        reasons: checkResult.reasons
      };
      
      // 如果元素不匹配，尝试搜索目标元素并返回修正坐标
      if (!checkResult.matched && element_info?.expected_type === 'file_upload_button') {
        try {
          const searchResult = await chrome.scripting.executeScript({
            target: { tabId: activeTab.id },
            func: () => {
              // 搜索文件上传相关元素
              const selectors = [
                'input[type="file"]',
                'label[for]',
                '[aria-label*="upload" i]',
                '[aria-label*="上传" i]',
                'button[class*="upload" i]',
                'div[class*="upload" i]',
                'span[class*="upload" i]'
              ];
              
              for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) {
                  const rect = el.getBoundingClientRect();
                  if (rect.width > 0 && rect.height > 0) {
                    return {
                      found: true,
                      x: Math.round(rect.left + rect.width / 2),
                      y: Math.round(rect.top + rect.height / 2),
                      tag: el.tagName,
                      selector: sel
                    };
                  }
                }
              }
              
              // 如果没找到，搜索包含上传关键词的可点击元素
              const allElements = document.querySelectorAll('button, div[role="button"], span[role="button"], label, a');
              const uploadKeywords = ['上传', 'upload', '选择文件', 'choose file', 'select file', 'browse', '浏览'];
              
              for (const el of allElements) {
                const text = (el.textContent || '').toLowerCase();
                const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
                
                if (uploadKeywords.some(kw => text.includes(kw) || ariaLabel.includes(kw))) {
                  const rect = el.getBoundingClientRect();
                  if (rect.width > 0 && rect.height > 0) {
                    return {
                      found: true,
                      x: Math.round(rect.left + rect.width / 2),
                      y: Math.round(rect.top + rect.height / 2),
                      tag: el.tagName,
                      text: el.textContent?.trim().substring(0, 50)
                    };
                  }
                }
              }
              
              return { found: false };
            },
            args: [],
            world: 'MAIN'
          });
          
          const targetResult = searchResult?.[0]?.result;
          if (targetResult?.found) {
            response.corrected_x = targetResult.x;
            response.corrected_y = targetResult.y;
            response.reasons = [...(response.reasons || []), 
              `找到目标元素: ${targetResult.tag} at (${targetResult.x}, ${targetResult.y})`];
            console.log('[WS] 找到目标元素，修正坐标:', targetResult.x, targetResult.y);
          }
        } catch (e) {
          console.warn('[WS] 搜索目标元素失败:', e);
        }
      }
      
      sendWsMessage(response);
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

function notifySearchComplete(total, successCount, failCount, platform) {
  const platformName = platform === 'google' ? 'Google' : platform === 'amazon' ? 'Amazon' : '全平台';
  let title = `${platformName} 搜图任务完成`;
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

// ==================== 上传模式管理 ====================

// 获取上传模式: 'cdp' 或 'pyautogui'
async function getUploadMode() {
  const settings = await chrome.storage.local.get(['uploadMode']);
  return settings.uploadMode || 'cdp'; // 默认 CDP 模式
}

// 设置上传模式
async function setUploadMode(mode) {
  await chrome.storage.local.set({ uploadMode: mode });
  console.log('[模式] 已切换到:', mode);
}

// ==================== CDP 文件上传 ====================

/**
 * 通过 CDP 获取文件的本地绝对路径
 * @param {string} filename - 文件名
 * @param {string|null} serverPath - 服务器上的绝对路径（本地图片上传时保存的）
 * @returns {Promise<string|null>} - 文件绝对路径或 null
 */
async function getFilePathForCDP(filename, serverPath) {
  // 优先使用 serverPath（本地图片上传时保存的绝对路径）
  if (serverPath) {
    console.log('[CDP] 使用 serverPath:', serverPath);
    return serverPath;
  }

  const settings = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = settings.serverUrl || 'http://localhost:5277';

  try {
    // 尝试从服务器获取文件路径
    const resp = await fetch(`${serverUrl}/api/check-file`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
      signal: AbortSignal.timeout(3000)
    });
    const result = await resp.json();
    if (result.exists && result.path) {
      console.log('[CDP] 服务器返回文件路径:', result.path);
      return result.path;
    }
  } catch (e) {
    console.log('[CDP] 服务器不可用');
  }

  return null;
}

/**
 * 通过 chrome.debugger (CDP) 上传文件到当前 Tab
 * 使用 DOM.setFileInputFiles 直接注入文件路径，无需 pyautogui
 *
 * @param {number} tabId - 目标 Tab ID
 * @param {string} filePath - 文件的本地绝对路径
 * @returns {Promise<{success: boolean, error?: string}>}
 */
async function cdpUploadFile(tabId, filePath) {
  const target = { tabId };
  const cdpVersion = '1.3';

  // 检查 chrome.debugger API 是否可用
  if (!chrome.debugger || typeof chrome.debugger.attach !== 'function') {
    console.error('[CDP] chrome.debugger API 不可用，请确认：');
    console.error('[CDP] 1. manifest.json 中已声明 "debugger" 权限');
    console.error('[CDP] 2. 扩展已完全重新加载（edge://extensions 点击重新加载）');
    return { success: false, error: 'chrome.debugger API 不可用，请重新加载扩展后重试' };
  }

  try {
    console.log('[CDP] 开始上传文件:', filePath);

    // 1. 附加调试器
    try {
      await chrome.debugger.attach(target, cdpVersion);
    } catch (e) {
      // 如果已经附加，忽略错误
      if (!e.message?.includes('already attached')) {
        throw e;
      }
    }

    try {
      // 2. 启用 DOM 域
      await chrome.debugger.sendCommand(target, 'DOM.enable');

      // 3. 获取文档根节点
      const { root } = await chrome.debugger.sendCommand(target, 'DOM.getDocument');
      console.log('[CDP] 获取文档根节点成功');

      // 4. 查找 input[type="file"] 元素
      let { nodeId } = await chrome.debugger.sendCommand(target, 'DOM.querySelector', {
        nodeId: root.nodeId,
        selector: 'input[type="file"]'
      });

      // 如果没找到，等待一下再试（Google 页面动态加载）
      if (!nodeId) {
        console.log('[CDP] 未找到 file input，等待 1 秒后重试...');
        await wait(1000);

        const { root: newRoot } = await chrome.debugger.sendCommand(target, 'DOM.getDocument');
        const retry = await chrome.debugger.sendCommand(target, 'DOM.querySelector', {
          nodeId: newRoot.nodeId,
          selector: 'input[type="file"]'
        });
        nodeId = retry.nodeId;
      }

      if (!nodeId) {
        // 尝试搜索所有 input 元素
        console.log('[CDP] 仍未找到 file input，尝试搜索所有 input...');
        const { root: docRoot } = await chrome.debugger.sendCommand(target, 'DOM.getDocument');
        const { nodeIds } = await chrome.debugger.sendCommand(target, 'DOM.querySelectorAll', {
          nodeId: docRoot.nodeId,
          selector: 'input'
        });

        console.log('[CDP] 找到', nodeIds?.length || 0, '个 input 元素');

        // 尝试逐个检查是否是 file 类型
        for (const nId of (nodeIds || [])) {
          try {
            const { attributes } = await chrome.debugger.sendCommand(target, 'DOM.getAttributes', {
              nodeId: nId
            });
            const attrs = attributes || [];
            for (let i = 0; i < attrs.length; i += 2) {
              if (attrs[i] === 'type' && attrs[i + 1] === 'file') {
                nodeId = nId;
                console.log('[CDP] 通过遍历找到 file input, nodeId:', nodeId);
                break;
              }
            }
            if (nodeId) break;
          } catch (e) {
            // 忽略单个元素的错误
          }
        }
      }

      if (!nodeId) {
        return { success: false, error: '未找到文件输入框 (input[type="file"])，请确认已点击"上传文件"' };
      }

      console.log('[CDP] 找到 file input, nodeId:', nodeId);

      // 5. 核心：注入文件路径
      await chrome.debugger.sendCommand(target, 'DOM.setFileInputFiles', {
        nodeId: nodeId,
        files: [filePath]
      });

      console.log('[CDP] 文件路径注入成功！');
      return { success: true };

    } finally {
      // 6. 断开调试器
      try {
        await chrome.debugger.detach(target);
      } catch (e) {
        // 忽略断开错误
      }
    }

  } catch (error) {
    console.error('[CDP] 上传失败:', error);
    // 确保断开调试器
    try {
      await chrome.debugger.detach(target);
    } catch (e) {}
    return { success: false, error: error.message || 'CDP 上传失败' };
  }
}

/**
/**
 * CDP 模式的完整搜图流程
 * 替代 pyautogui 模式的 uploadToTab 函数
 *
 * @param {object} prepareResult - { filename, isLocal, tabId, serverPath }
 */
async function uploadToTabCDP(prepareResult) {
  const { filename, isLocal, tabId, serverPath } = prepareResult;
  const logs = [];
  const MAX_RETRIES = 2;

  try {
    // CDP 不需要激活 tab，后台即可操作
    logs.push('[CDP] 开始处理: ' + filename + ' (tabId: ' + tabId + ')');

    // 获取文件路径
    logs.push('[CDP] 获取文件路径...');
    const filePath = await getFilePathForCDP(filename, serverPath);

    if (!filePath) {
      logs.push('[CDP] 无法获取文件路径');
      return { success: false, filename, tabId, error: '无法获取文件路径', logs };
    }

    logs.push('[CDP] 文件路径: ' + filePath);

    // 确保已点击"按图搜图"和"上传文件"标签（file input 需要先出现在 DOM 中）
    logs.push('[CDP] 检查 file input 是否已加载...');
    let result = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const fileInput = document.querySelector('input[type="file"]');
        return { found: !!fileInput };
      },
      world: 'MAIN'
    });

    if (!result?.[0]?.result?.found) {
      // 先点击"按图搜图"按钮
      logs.push('[CDP] file input 未找到，尝试点击"按图搜图"...');
      await chrome.scripting.executeScript({
        target: { tabId },
        func: clickSearchByImage,
        world: 'MAIN'
      });

      // 轮询等待 file input 出现（最多 1.5s，每 100ms 检查一次）
      const deadline = Date.now() + 1500;
      let found = false;
      while (Date.now() < deadline) {
        const check = await chrome.scripting.executeScript({
          target: { tabId },
          func: () => {
            // 检查"上传文件"标签是否可见
            const spans = document.querySelectorAll('span[role="button"][jsaction][jsname]');
            for (const span of spans) {
              const text = span.textContent?.trim() || '';
              if (text === '上传文件' || text === 'Upload a file' || text === '上傳檔案') {
                const rect = span.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) return { uploadTabVisible: true };
              }
            }
            return { uploadTabVisible: false };
          },
          world: 'MAIN'
        });

        if (check?.[0]?.result?.uploadTabVisible) {
          logs.push('[CDP] "上传文件"标签已显示，立即点击');
          await chrome.scripting.executeScript({
            target: { tabId },
            func: clickUploadFile,
            world: 'MAIN'
          });
          found = true;
          break;
        }
        await wait(100);
      }

      if (!found) {
        // 超时了也尝试点击一次
        logs.push('[CDP] 等待超时，仍尝试点击"上传文件"');
        await chrome.scripting.executeScript({
          target: { tabId },
          func: clickUploadFile,
          world: 'MAIN'
        });
      }

      // 轮询等待 file input 出现（最多 1.5s）
      const fiDeadline = Date.now() + 1500;
      let fiFound = false;
      while (Date.now() < fiDeadline) {
        const check = await chrome.scripting.executeScript({
          target: { tabId },
          func: () => !!document.querySelector('input[type="file"]'),
          world: 'MAIN'
        });
        if (check?.[0]?.result) {
          logs.push('[CDP] file input 已出现');
          fiFound = true;
          break;
        }
        await wait(100);
      }

      if (!fiFound) {
        logs.push('[CDP] file input 未出现');
        return { success: false, filename, tabId, error: '无法打开文件上传界面', logs };
      }
    }

    // 使用 CDP 上传
    let uploadSuccess = false;
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      logs.push(`[CDP] 第 ${attempt}/${MAX_RETRIES} 次尝试上传`);
      const cdpResult = await cdpUploadFile(tabId, filePath);
      logs.push('[CDP] 上传结果: ' + JSON.stringify(cdpResult));

      if (cdpResult.success) {
        uploadSuccess = true;
        break;
      }

      if (attempt < MAX_RETRIES) {
        logs.push('[CDP] 重试中...');
        await wait(500);
      }
    }

    if (uploadSuccess) {
      // 上传成功，等待处理后点击搜索
      await wait(500);

      logs.push('[CDP] 点击搜索按钮...');
      result = await chrome.scripting.executeScript({
        target: { tabId },
        func: clickSearchBtn,
        world: 'MAIN'
      });

      if (!result?.[0]?.result?.success) {
        logs.push('[CDP] 搜索按钮未找到，可能已自动提交');
      }

      // 异步更新 URL 记录
      setTimeout(async () => {
        try {
          const finalTab = await chrome.tabs.get(tabId);
          if (finalTab && finalTab.url) {
            searchedImages.set(filename + '_google', {
              tabId,
              url: finalTab.url,
              timestamp: Date.now()
            });
            await saveSearchedImages();
          }
        } catch (e) {
          console.log('[CDP] 异步更新URL失败:', e);
        }
      }, 3000);

      logs.push('[CDP] 搜图完成!');
      return { success: true, filename, tabId, logs };
    }

    return { success: false, filename, tabId, error: 'CDP 上传失败', logs };

  } catch (error) {
    logs.push('[CDP] 失败: ' + error.message);
    console.error('[CDP] 上传失败:', filename, logs.join('\n'));
    return { success: false, filename, tabId, error: error.message, logs };
  }
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

// 轻量创建：只打开页面，不点击按钮（按钮点击交给上传阶段处理）
async function createSearchTab(imageInfo) {
  const { filename, isLocal, serverPath } = imageInfo;

  try {
    const tab = await chrome.tabs.create({
      url: 'https://www.google.com/imghp',
      active: false
    });

    await waitForTabComplete(tab.id);

    searchedImages.set(filename + '_google', {
      tabId: tab.id,
      url: tab.url,
      timestamp: Date.now()
    });
    await saveSearchedImages();

    console.log('[搜图] Tab创建完成:', filename, 'tabId:', tab.id);

    return {
      success: true,
      filename,
      isLocal,
      tabId: tab.id,
      serverPath
    };

  } catch (error) {
    console.error('[搜图] 创建Tab失败:', filename, error);
    return { success: false, filename, error: error.message };
  }
}

// 通过复制已有Tab来创建新Tab（更快，继承页面状态）
async function duplicateSearchTab(sourceTabId, imageInfo) {
  const { filename, isLocal, serverPath } = imageInfo;

  try {
    // 复制tab
    const newTab = await chrome.tabs.duplicate(sourceTabId);

    // 强制不激活（duplicate 默认会激活新 tab）
    await chrome.tabs.update(newTab.id, { active: false });

    await waitForTabComplete(newTab.id);

    searchedImages.set(filename + '_google', {
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
      tabId: newTab.id,
      serverPath
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
      title: title || '搜图',
      color: 'blue',
      collapsed: false
    });

    // 按传入顺序排列 tab（chrome.tabs.group 不保证顺序）
    for (let i = 0; i < tabIds.length; i++) {
      try {
        await chrome.tabs.move(tabIds[i], { index: -1 });
      } catch (e) {
        // 忽略单个 tab 移动失败
      }
    }

    console.log('[搜图] 创建Tab分组:', title, 'groupId:', groupId, 'tabs:', tabIds.length);
    return groupId;

  } catch (error) {
    console.error('[搜图] 创建分组失败:', error);
    return -1;
  }
}

// ==================== Amazon搜图Tab创建 ====================

// 轻量创建：只打开页面，不点击按钮
async function createAmazonSearchTab(imageInfo) {
  const { filename, isLocal, serverPath } = imageInfo;

  try {
    const tab = await chrome.tabs.create({
      url: 'https://www.amazon.com/stylesnap',
      active: false
    });

    await waitForTabComplete(tab.id);

    searchedImages.set(filename + '_amazon', {
      tabId: tab.id,
      url: tab.url,
      timestamp: Date.now()
    });
    await saveSearchedImages();

    console.log('[Amazon搜图] Tab创建完成:', filename, 'tabId:', tab.id);

    return {
      success: true,
      filename,
      isLocal,
      tabId: tab.id,
      serverPath
    };

  } catch (error) {
    console.error('[Amazon搜图] 创建Tab失败:', filename, error);
    return { success: false, filename, error: error.message };
  }
}

// ==================== Amazon CDP 上传 ====================

/**
 * CDP 模式 Amazon 上传
 */
async function uploadToAmazonTabCDP(prepareResult) {
  const { filename, isLocal, tabId, serverPath } = prepareResult;
  const logs = [];
  const MAX_RETRIES = 2;

  // 检查 chrome.debugger API
  if (!chrome.debugger || typeof chrome.debugger.attach !== 'function') {
    return { success: false, filename, tabId, error: 'chrome.debugger API 不可用', logs };
  }

  try {
    logs.push('[Amazon CDP] 开始处理: ' + filename);

    // 获取文件路径
    logs.push('[Amazon CDP] 获取文件路径...');
    const filePath = await getFilePathForCDP(filename, serverPath);

    if (!filePath) {
      return { success: false, filename, tabId, error: '无法获取文件路径', logs };
    }

    logs.push('[Amazon CDP] 文件路径: ' + filePath);

    // 轮询等待 file input 出现（Amazon 页面可能需要加载时间）
    const deadline = Date.now() + 3000;
    let fileInputFound = false;

    while (Date.now() < deadline) {
      const check = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          // 检查 file input
          const fileInput = document.querySelector('input[type="file"]');
          if (fileInput) return { found: true };

          // 检查上传按钮
          const uploadBtn = document.querySelector('span#a-autoid-0-announce');
          if (uploadBtn) {
            const rect = uploadBtn.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) return { found: false, hasButton: true };
          }

          return { found: false, hasButton: false };
        },
        world: 'MAIN'
      });

      const result = check?.[0]?.result;

      if (result?.found) {
        fileInputFound = true;
        logs.push('[Amazon CDP] file input 已出现');
        break;
      }

      if (result?.hasButton) {
        // 点击上传按钮触发 file input
        logs.push('[Amazon CDP] 点击上传按钮...');
        await chrome.scripting.executeScript({
          target: { tabId },
          func: () => {
            const btn = document.querySelector('span#a-autoid-0-announce');
            if (btn) btn.click();
          },
          world: 'MAIN'
        });
      }

      await wait(200);
    }

    if (!fileInputFound) {
      // 最后再检查一次
      const finalCheck = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => !!document.querySelector('input[type="file"]'),
        world: 'MAIN'
      });

      if (!finalCheck?.[0]?.result) {
        logs.push('[Amazon CDP] file input 未出现');
        return { success: false, filename, tabId, error: '无法找到文件上传入口', logs };
      }
    }

    // 使用 CDP 上传
    let uploadSuccess = false;
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      logs.push(`[Amazon CDP] 第 ${attempt}/${MAX_RETRIES} 次尝试上传`);

      // CDP 上传
      const target = { tabId };
      try {
        await chrome.debugger.attach(target, '1.3');
      } catch (e) {
        if (!e.message?.includes('already attached')) throw e;
      }

      try {
        await chrome.debugger.sendCommand(target, 'DOM.enable');
        const { root } = await chrome.debugger.sendCommand(target, 'DOM.getDocument');

        const { nodeId } = await chrome.debugger.sendCommand(target, 'DOM.querySelector', {
          nodeId: root.nodeId,
          selector: 'input[type="file"]'
        });

        if (nodeId) {
          await chrome.debugger.sendCommand(target, 'DOM.setFileInputFiles', {
            nodeId,
            files: [filePath]
          });
          uploadSuccess = true;
          logs.push('[Amazon CDP] 文件注入成功');
        } else {
          logs.push('[Amazon CDP] 未找到 file input nodeId');
        }
      } finally {
        try { await chrome.debugger.detach(target); } catch (e) {}
      }

      if (uploadSuccess) break;
      if (attempt < MAX_RETRIES) await wait(300);
    }

    if (uploadSuccess) {
      // Amazon 会自动处理搜索，等待结果加载
      await wait(2000);

      // 异步更新 URL
      setTimeout(async () => {
        try {
          const finalTab = await chrome.tabs.get(tabId);
          if (finalTab?.url) {
            searchedImages.set(filename + '_amazon', { tabId, url: finalTab.url, timestamp: Date.now() });
            await saveSearchedImages();
          }
        } catch (e) {}
      }, 5000);

      logs.push('[Amazon CDP] 搜图完成');
      return { success: true, filename, tabId, logs };
    }

    return { success: false, filename, tabId, error: 'CDP 上传失败', logs };

  } catch (error) {
    logs.push('[Amazon CDP] 失败: ' + error.message);
    try { await chrome.debugger.detach({ tabId }); } catch (e) {}
    return { success: false, filename, tabId, error: error.message, logs };
  }
}

// ==================== Amazon pyautogui 上传 ====================

async function uploadToAmazonTab(prepareResult) {
  const { filename, isLocal, tabId } = prepareResult;
  const settings = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = settings.serverUrl || 'http://localhost:5277';
  const logs = [];
  const MAX_RETRIES = 3;

  try {
    // 激活tab（pyautogui 需要）
    await chrome.tabs.update(tabId, { active: true });
    await wait(500);

    let buttonResult = null;

    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      logs.push(`[上传] 第 ${attempt}/${MAX_RETRIES} 次尝试`);

      let result = await chrome.scripting.executeScript({
        target: { tabId },
        func: findAmazonUploadButton,
        world: 'MAIN'
      });

      buttonResult = result?.[0]?.result;

      if (!buttonResult || !buttonResult.success) {
        logs.push('上传按钮未找到');
        if (attempt < MAX_RETRIES) { await wait(1000); continue; }
        throw new Error('获取上传按钮坐标失败');
      }

      logs.push('按钮坐标: (' + buttonResult.viewport.x + ', ' + buttonResult.viewport.y + ')');
      await wait(300);

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
        await wait(3000);

        setTimeout(async () => {
          try {
            const finalTab = await chrome.tabs.get(tabId);
            if (finalTab?.url) {
              searchedImages.set(filename + '_amazon', { tabId, url: finalTab.url, timestamp: Date.now() });
              await saveSearchedImages();
            }
          } catch (e) {}
        }, 5000);

        logs.push('Amazon搜图完成!');
        return { success: true, filename, tabId, logs };
      }

      if (uploadResult.error?.includes('文件不存在')) {
        return { success: false, filename, error: uploadResult.error, logs };
      }

      logs.push(`上传失败: ${uploadResult.error}，准备重试...`);
      await wait(500);
    }

    throw new Error(`${MAX_RETRIES} 次尝试后仍失败`);

  } catch (error) {
    logs.push('失败: ' + error.message);
    return { success: false, filename, error: error.message, logs };
  }
}

// ==================== Amazon批量搜图主流程 ====================

async function executeBatchAmazonSearch(images) {
  await cleanupSearchedImages();

  const imagesToSearch = [];
  const skippedImages = [];

  for (const img of images) {
    const record = searchedImages.get(img.filename + '_amazon');
    if (record) {
      const valid = await isTabValidForSkip(record.tabId, record.url);
      if (valid) {
        skippedImages.push(img.filename);
        continue;
      } else {
        searchedImages.delete(img.filename + '_amazon');
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

  // 保存用户当前 tab
  const [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const currentTabId = currentTab?.id;

  // ========== 阶段1: 并行创建所有Tab ==========
  chrome.runtime.sendMessage({
    type: 'searchPhase',
    phase: 'prepare',
    total: imagesToSearch.length
  }).catch(() => {});

  const prepareResults = [];

  // 第一个tab：只打开页面
  chrome.runtime.sendMessage({
    type: 'searchProgress',
    phase: 'prepare',
    current: 1,
    total: imagesToSearch.length,
    filename: imagesToSearch[0].filename
  }).catch(() => {});

  console.log('[Amazon搜图] 创建第一个Tab...');
  const firstResult = await createAmazonSearchTab(imagesToSearch[0]);
  prepareResults.push(firstResult);

  let firstTabId = null;
  if (firstResult.success) {
    firstTabId = firstResult.tabId;
  } else {
    for (let i = 1; i < imagesToSearch.length; i++) {
      prepareResults.push({
        success: false,
        filename: imagesToSearch[i].filename,
        error: '首个Tab创建失败'
      });
    }
  }

  // 后续tab：并行复制
  if (firstTabId && imagesToSearch.length > 1) {
    console.log('[Amazon搜图] 并行复制剩余', imagesToSearch.length - 1, '个Tab...');

    const duplicatePromises = [];
    for (let i = 1; i < imagesToSearch.length; i++) {
      const promise = (async () => {
        chrome.runtime.sendMessage({
          type: 'searchProgress',
          phase: 'prepare',
          current: i + 1,
          total: imagesToSearch.length,
          filename: imagesToSearch[i].filename
        }).catch(() => {});

        const newTab = await chrome.tabs.duplicate(firstTabId);
        await chrome.tabs.update(newTab.id, { active: false });
        await waitForTabComplete(newTab.id);

        searchedImages.set(imagesToSearch[i].filename + '_amazon', {
          tabId: newTab.id,
          url: newTab.url,
          timestamp: Date.now()
        });
        await saveSearchedImages();

        return {
          success: true,
          filename: imagesToSearch[i].filename,
          isLocal: imagesToSearch[i].isLocal,
          tabId: newTab.id,
          serverPath: imagesToSearch[i].serverPath
        };
      })();
      duplicatePromises.push(promise);
    }

    const duplicateResults = await Promise.all(duplicatePromises);
    prepareResults.push(...duplicateResults);
  }

  // 立即恢复用户原 tab
  if (currentTabId) {
    try {
      await chrome.tabs.update(currentTabId, { active: true });
    } catch (e) {}
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

  // 获取上传模式
  const uploadMode = await getUploadMode();
  console.log('[Amazon搜图] 当前上传模式:', uploadMode);

  for (let i = 0; i < preparedTabs.length; i++) {
    const tab = preparedTabs[i];

    chrome.runtime.sendMessage({
      type: 'searchProgress',
      phase: 'upload',
      current: i + 1,
      total: preparedTabs.length,
      filename: tab.filename
    }).catch(() => {});

    console.log('[Amazon搜图] 开始上传:', tab.filename, '(' + (i+1) + '/' + preparedTabs.length + ')', '模式:', uploadMode);

    const t_start = Date.now();
    let result;

    if (uploadMode === 'cdp') {
      result = await uploadToAmazonTabCDP(tab);
    } else {
      result = await uploadToAmazonTab(tab);
    }

    const t_elapsed = ((Date.now() - t_start) / 1000).toFixed(2);
    results.push(result);

    console.log('[Amazon搜图] 上传完成:', tab.filename, result.success ? '成功' : '失败', `耗时: ${t_elapsed}s`);

    if (i < preparedTabs.length - 1) {
      await wait(200);
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
    await wait(200);
    
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
            await wait(500);
            continue;
          }
          throw new Error('无法打开以图搜图视图');
        }
        
        await wait(800);
        
        // 重新点击"上传文件"
        await chrome.scripting.executeScript({
          target: { tabId },
          func: clickUploadFile,
          world: 'MAIN'
        });
        
        await wait(500);
        
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
            await wait(300);
            continue;
          }
          throw new Error('获取文件选择按钮坐标失败');
        }
      }
      
      logs.push('按钮坐标: (' + buttonResult.viewport.x + ', ' + buttonResult.viewport.y + ')');
      
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
      
      if (uploadResult.timing) {
        console.log(`[搜图] ${filename} 服务器耗时:`, uploadResult.timing);
      }
      
      if (uploadResult.success) {
        // 上传成功，等待文件对话框关闭后点击搜索
        await wait(500);
        
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
        
        // 异步更新URL记录
        setTimeout(async () => {
          try {
            const finalTab = await chrome.tabs.get(tabId);
            if (finalTab && finalTab.url) {
              searchedImages.set(filename + '_google', {
                tabId,
                url: finalTab.url,
                timestamp: Date.now()
              });
              await saveSearchedImages();
            }
          } catch (e) {
            console.log('[搜图] 异步更新URL失败:', e);
          }
        }, 3000);

        logs.push('搜图完成!');
        return { success: true, filename, tabId, logs };
      }
      
      // 上传失败，检查是否是文件不存在（不需要重试）
      if (uploadResult.error && uploadResult.error.includes('文件不存在')) {
        logs.push(`文件不存在，跳过: ${filename}`);
        console.error(`[搜图] 文件不存在: ${filename}，请先下载图片`);
        try {
          chrome.runtime.sendMessage({
            type: 'searchError',
            error: `文件不存在: ${filename}，请先下载图片`
          }).catch(() => {});
        } catch (e) {}
        return { success: false, filename, error: uploadResult.error, logs };
      }
      
      // 其他失败，重试
      logs.push(`上传失败: ${uploadResult.error}，准备重试...`);
      await wait(300);
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
    const record = searchedImages.get(img.filename + '_google');
    if (record) {
      const valid = await isTabValidForSkip(record.tabId, record.url);
      if (valid) {
        skippedImages.push(img.filename);
        console.log('[搜图] 跳过已搜图的图片:', img.filename);
        continue;
      } else {
        searchedImages.delete(img.filename + '_google');
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

  // 保存用户当前 tab，搜图结束后恢复
  const [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const currentTabId = currentTab?.id;

  // ========== 阶段1: 并行创建所有Tab ==========
  chrome.runtime.sendMessage({
    type: 'searchPhase',
    phase: 'prepare',
    total: imagesToSearch.length
  }).catch(() => {});
  
  const prepareResults = [];

  // 第一个tab：只打开页面，不点击按钮
  chrome.runtime.sendMessage({
    type: 'searchProgress',
    phase: 'prepare',
    current: 1,
    total: imagesToSearch.length,
    filename: imagesToSearch[0].filename
  }).catch(() => {});

  console.log('[搜图] 创建第一个Tab...');
  const firstResult = await createSearchTab(imagesToSearch[0]);
  prepareResults.push(firstResult);

  let firstTabId = null;
  if (firstResult.success) {
    firstTabId = firstResult.tabId;
    console.log('[搜图] 第一个Tab创建完成，tabId:', firstTabId);
  } else {
    console.error('[搜图] 第一个Tab创建失败，无法复制后续Tab');
    for (let i = 1; i < imagesToSearch.length; i++) {
      prepareResults.push({
        success: false,
        filename: imagesToSearch[i].filename,
        error: '首个Tab创建失败'
      });
    }
  }

  // 后续tab：立即并行复制（不需要等按钮点击）
  if (firstTabId && imagesToSearch.length > 1) {
    console.log('[搜图] 并行复制剩余', imagesToSearch.length - 1, '个Tab...');

    const duplicatePromises = [];
    for (let i = 1; i < imagesToSearch.length; i++) {
      const promise = (async () => {
        chrome.runtime.sendMessage({
          type: 'searchProgress',
          phase: 'prepare',
          current: i + 1,
          total: imagesToSearch.length,
          filename: imagesToSearch[i].filename
        }).catch(() => {});

        const result = await duplicateSearchTab(firstTabId, imagesToSearch[i]);
        return result;
      })();
      duplicatePromises.push(promise);
    }

    // 等待所有Tab创建完成
    const duplicateResults = await Promise.all(duplicatePromises);
    prepareResults.push(...duplicateResults);
  }

  // Tab 创建完成，立即恢复用户原来的 tab
  if (currentTabId) {
    try {
      await chrome.tabs.update(currentTabId, { active: true });
      console.log('[搜图] 已恢复用户原 tab:', currentTabId);
    } catch (e) {
      // 原 tab 可能已关闭，忽略
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

  // 获取当前上传模式
  const uploadMode = await getUploadMode();
  console.log('[搜图] 当前上传模式:', uploadMode);

  for (let i = 0; i < preparedTabs.length; i++) {
    const tab = preparedTabs[i];

    chrome.runtime.sendMessage({
      type: 'searchProgress',
      phase: 'upload',
      current: i + 1,
      total: preparedTabs.length,
      filename: tab.filename
    }).catch(() => {});

    console.log('[搜图] 开始上传:', tab.filename, '(' + (i+1) + '/' + preparedTabs.length + ')', '模式:', uploadMode);

    const t_upload_start = Date.now();

    // 根据模式选择上传函数
    let result;
    if (uploadMode === 'cdp') {
      result = await uploadToTabCDP(tab);
    } else {
      result = await uploadToTab(tab);
    }

    const t_upload_elapsed = ((Date.now() - t_upload_start) / 1000).toFixed(2);
    results.push(result);

    console.log('[搜图] 上传完成:', tab.filename, result.success ? '成功' : '失败', `耗时: ${t_upload_elapsed}s`);

    // 短暂间隔再处理下一个（让浏览器有时间处理）
    if (i < preparedTabs.length - 1) {
      await wait(200);
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

  if (request.action === 'getUploadMode') {
    getUploadMode().then(mode => sendResponse({ mode }));
    return true;
  }

  if (request.action === 'setUploadMode') {
    setUploadMode(request.mode).then(() => sendResponse({ success: true }));
    return true;
  }

  if (request.action === 'getMemoryCheckEnabled') {
    sendResponse({ enabled: memoryCheckEnabled });
    return true;
  }

  if (request.action === 'setMemoryCheckEnabled') {
    setMemoryCheckEnabled(request.enabled).then(() => sendResponse({ success: true }));
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
    // 内存检查
    checkMemoryForTask('google', request.images.length).then(memCheck => {
      if (!memCheck.sufficient) {
        chrome.runtime.sendMessage({
          type: 'searchError',
          error: memCheck.message
        }).catch(() => {});
        showNotification('内存不足', memCheck.message);
        return;
      }

      // 内存充足，执行搜图
      if (memCheck.tabsToClose > 0) {
        showToast(memCheck.message, 'info');
      }

      executeBatchGoogleSearch(request.images)
        .then(results => {
          const total = results.length;
          const successCount = results.filter(r => r.success).length;
          const failCount = results.filter(r => !r.success).length;

          results.forEach((r, i) => {
            console.log(`[搜图] 图片${i+1}日志:`, r.logs?.join('\n'));
          });

          notifySearchComplete(total, successCount, failCount, 'google');

          chrome.runtime.sendMessage({
            type: 'searchComplete',
            successCount,
            failCount,
            results
          }).catch(() => {});
        })
        .catch(error => {
          showNotification('Google 搜图任务失败', error.message);
          chrome.runtime.sendMessage({ type: 'searchError', error: error.message }).catch(() => {});
        });
    });

    sendResponse({ started: true });
    return true;
  }

  if (request.action === 'startAmazonSearch') {
    // 内存检查
    checkMemoryForTask('amazon', request.images.length).then(memCheck => {
      if (!memCheck.sufficient) {
        chrome.runtime.sendMessage({
          type: 'searchError',
          error: memCheck.message
        }).catch(() => {});
        showNotification('内存不足', memCheck.message);
        return;
      }

      if (memCheck.tabsToClose > 0) {
        showToast(memCheck.message, 'info');
      }

      executeBatchAmazonSearch(request.images)
        .then(results => {
          const total = results.length;
          const successCount = results.filter(r => r.success).length;
          const failCount = results.filter(r => !r.success).length;

          results.forEach((r, i) => {
            console.log(`[Amazon搜图] 图片${i+1}日志:`, r.logs?.join('\n'));
          });

          notifySearchComplete(total, successCount, failCount, 'amazon');

          chrome.runtime.sendMessage({
            type: 'searchComplete',
            successCount,
            failCount,
            results
          }).catch(() => {});
        })
        .catch(error => {
          showNotification('Amazon 搜图任务失败', error.message);
          chrome.runtime.sendMessage({ type: 'searchError', error: error.message }).catch(() => {});
        });
    });

    sendResponse({ started: true });
    return true;
  }

  // 全平台搜图（Google + Amazon 并行执行）
  if (request.action === 'startAllPlatformSearch') {
    const images = request.images;

    // 内存检查（全平台需要双倍内存）
    checkMemoryForTask('all', images.length).then(memCheck => {
      if (!memCheck.sufficient) {
        chrome.runtime.sendMessage({
          type: 'searchError',
          error: memCheck.message
        }).catch(() => {});
        showNotification('内存不足', memCheck.message);
        return;
      }

      if (memCheck.tabsToClose > 0) {
        showToast(memCheck.message, 'info');
      }

      (async () => {
        try {
          console.log('[全平台] 开始并行搜图...');

          const [googleResults, amazonResults] = await Promise.all([
            executeBatchGoogleSearch(images),
            executeBatchAmazonSearch(images)
          ]);

          const googleSuccess = googleResults.filter(r => r.success).length;
          const googleFail = googleResults.filter(r => !r.success).length;
          const amazonSuccess = amazonResults.filter(r => r.success).length;
          const amazonFail = amazonResults.filter(r => !r.success).length;

          console.log('[全平台] Google:', googleSuccess, '成功,', googleFail, '失败');
          console.log('[全平台] Amazon:', amazonSuccess, '成功,', amazonFail, '失败');

          const totalSuccess = googleSuccess + amazonSuccess;
          const totalFail = googleFail + amazonFail;
          notifySearchComplete(images.length * 2, totalSuccess, totalFail, 'all');

          chrome.runtime.sendMessage({
            type: 'searchComplete',
            successCount: totalSuccess,
            failCount: totalFail,
            results: { google: googleResults, amazon: amazonResults }
          }).catch(() => {});

        } catch (error) {
          showNotification('全平台搜图任务失败', error.message);
          chrome.runtime.sendMessage({ type: 'searchError', error: error.message }).catch(() => {});
        }
      })();
    });

    sendResponse({ started: true });
    return true;
  }

  // 保存调试选取的元素到 storage
  if (request.action === 'saveDebugPickedElement') {
    console.log('[background] 保存选取的元素:', request.element);
    chrome.storage.local.set({
      debugPickedElement: request.element,
      debugPicking: false
    });
    sendResponse({ success: true });
    return true;
  }

  // 保存调试选取状态到 storage
  if (request.action === 'saveDebugPicking') {
    console.log('[background] 保存选取状态:', request.picking);
    chrome.storage.local.set({
      debugPicking: request.picking
    });
    sendResponse({ success: true });
    return true;
  }
});

// 初始化
chrome.runtime.onInstalled.addListener(async () => {
  await loadSearchedImages();
  await loadMemoryCheckSetting();
  startHeartbeat();
  connectWebSocket();
});

// 服务工作者启动时也加载设置和连接 WebSocket
loadMemoryCheckSetting();
connectWebSocket();
