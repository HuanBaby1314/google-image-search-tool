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
  await checkServerHealth();
  setInterval(checkServerHealth, HEARTBEAT_INTERVAL);
}

async function checkServerHealth() {
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
    
    // 检查URL是否包含Google搜图特征
    // 搜图结果URL通常包含: google.com/search, lens.google, imghp等
    const isGoogleSearch = tab.url.includes('google.com') && (
      tab.url.includes('/search') || 
      tab.url.includes('lens.google') ||
      tab.url.includes('tbm=isch')
    );
    
    // 如果记录的URL是搜图结果，检查当前URL是否也是搜图结果
    if (recordedUrl && recordedUrl.includes('/search')) {
      return isGoogleSearch && tab.url.includes('/search');
    }
    
    return isGoogleSearch;
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

// ==================== 执行搜图流程 ====================

async function executeGoogleSearch(imageInfo) {
  const { filename, isLocal } = imageInfo;
  const settings = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = settings.serverUrl || 'http://localhost:5277';
  
  const logs = [];
  
  try {
    // 步骤1: 打开Google搜图页面
    logs.push('步骤1: 打开Google搜图页面');
    const tab = await chrome.tabs.create({
      url: 'https://www.google.com/imghp',
      active: true
    });
    
    await waitForTabComplete(tab.id);
    await wait(3000);
    
    // 记录图片对应的tab信息
    searchedImages.set(filename, {
      tabId: tab.id,
      url: tab.url,
      timestamp: Date.now()
    });
    await saveSearchedImages();
    console.log('[搜图] 记录图片tab:', filename, '-> tabId:', tab.id);
    
    let pageInfo = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: getPageInfo,
      world: 'MAIN'
    });
    logs.push('页面信息: ' + JSON.stringify(pageInfo[0]?.result?.title));
    
    // 步骤2: 点击"按图搜索"
    logs.push('步骤2: 点击按图搜索');
    let result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: clickSearchByImage,
      world: 'MAIN'
    });
    
    logs.push('按图搜索结果: ' + JSON.stringify(result[0]?.result));
    
    if (!result[0]?.result?.success) {
      pageInfo = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: getPageInfo,
        world: 'MAIN'
      });
      logs.push('页面按钮: ' + JSON.stringify(pageInfo[0]?.result?.buttons?.slice(0, 10)));
      throw new Error('点击按图搜索失败');
    }
    
    await wait(2000);
    
    // 步骤3: 点击"上传文件"
    logs.push('步骤3: 点击上传文件');
    result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: clickUploadFile,
      world: 'MAIN'
    });
    
    logs.push('上传文件结果: ' + JSON.stringify(result[0]?.result));
    
    if (!result[0]?.result?.success) {
      logs.push('上传文件标签未找到，继续尝试...');
    }
    
    await wait(1500);
    
    // 步骤4: 获取文件选择按钮坐标
    logs.push('步骤4: 获取文件选择按钮坐标');
    
    const debugResult = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const spans = document.querySelectorAll('span[role="button"]');
        return Array.from(spans).map(s => ({
          text: s.textContent?.trim()?.substring(0, 30),
          jsname: s.getAttribute('jsname'),
          jsaction: s.getAttribute('jsaction')
        }));
      },
      world: 'MAIN'
    });
    console.log('[搜图] 页面上所有 role=button 的 span:', JSON.stringify(debugResult[0]?.result));
    
    result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: findFileUploadButton,
      world: 'MAIN'
    });
    
    console.log('[搜图] executeScript返回结果:', JSON.stringify(result));
    
    const buttonResult = result?.[0]?.result;
    console.log('[搜图] buttonResult:', JSON.stringify(buttonResult));
    
    if (!buttonResult || !buttonResult.success) {
      const errorMsg = buttonResult?.error || '返回结果为空';
      console.log('[搜图] 获取坐标失败:', errorMsg);
      logs.push('按钮坐标结果: 失败 - ' + errorMsg);
      throw new Error('获取文件选择按钮坐标失败: ' + errorMsg);
    }
    
    logs.push('按钮坐标结果: ' + JSON.stringify({
      success: buttonResult.success,
      method: buttonResult.method,
      x: buttonResult.viewport?.x,
      y: buttonResult.viewport?.y,
      navBarHeight: buttonResult.navBarHeight
    }));
    
    const buttonPosition = buttonResult;
    console.log('[搜图] 按钮坐标:', buttonPosition.viewport.x, buttonPosition.viewport.y, 
                '方法:', buttonPosition.method, '导航栏高度:', buttonPosition.navBarHeight);
    
    await wait(1000);
    
    // 步骤5: 通知服务器点击坐标并选择文件
    logs.push('步骤5: 服务器点击坐标 (' + buttonPosition.viewport.x + ', ' + buttonPosition.viewport.y + ') 导航栏高度: ' + buttonPosition.navBarHeight);
    const uploadResponse = await fetch(`${serverUrl}/api/select-file-and-upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        filename: filename,
        isLocal: isLocal || false,
        buttonX: buttonPosition.viewport.x,
        buttonY: buttonPosition.viewport.y,
        navBarHeight: buttonPosition.navBarHeight
      }),
      signal: AbortSignal.timeout(30000)
    });
    
    const uploadResult = await uploadResponse.json();
    logs.push('服务器响应: ' + JSON.stringify(uploadResult));
    
    if (!uploadResult.success) {
      throw new Error('服务器选择文件失败: ' + uploadResult.error);
    }
    
    await wait(4000);
    
    // 步骤6: 点击搜索按钮
    logs.push('步骤6: 点击搜索按钮');
    result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: clickSearchBtn,
      world: 'MAIN'
    });
    
    logs.push('搜索按钮结果: ' + JSON.stringify(result[0]?.result));
    
    if (!result[0]?.result?.success) {
      logs.push('搜索按钮未找到，可能已自动提交');
    }
    
    // 等待页面跳转
    await wait(2000);
    
    // 获取最终URL并更新记录
    try {
      const finalTab = await chrome.tabs.get(tab.id);
      if (finalTab && finalTab.url) {
        searchedImages.set(filename, {
          tabId: tab.id,
          url: finalTab.url,
          timestamp: Date.now()
        });
        await saveSearchedImages();
        console.log('[搜图] 更新记录URL:', filename, '->', finalTab.url);
      }
    } catch (e) {
      console.log('[搜图] 获取最终URL失败:', e);
    }
    
    logs.push('搜图完成!');
    
    return { success: true, logs, tabId: tab.id };
    
  } catch (error) {
    logs.push('失败: ' + error.message);
    console.error('[搜图] 失败:', logs.join('\n'));
    return { success: false, error: error.message, logs };
  }
}

async function executeBatchGoogleSearch(images) {
  // 先清理无效的记录
  await cleanupSearchedImages();
  
  // 过滤掉已经在搜图中的图片
  const imagesToSearch = [];
  const skippedImages = [];
  
  for (const img of images) {
    const record = searchedImages.get(img.filename);
    if (record) {
      // 检查tab是否还存在且URL是搜图结果
      const valid = await isTabValidForSkip(record.tabId, record.url);
      if (valid) {
        skippedImages.push(img.filename);
        console.log('[搜图] 跳过已搜图的图片:', img.filename, 'tabId:', record.tabId, 'url:', record.url);
        continue;
      } else {
        // tab已关闭或URL不是搜图结果，删除记录
        searchedImages.delete(img.filename);
        await saveSearchedImages();
        console.log('[搜图] 删除无效记录:', img.filename);
      }
    }
    imagesToSearch.push(img);
  }
  
  if (skippedImages.length > 0) {
    console.log('[搜图] 跳过已搜图的图片:', skippedImages.length, '张');
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
  
  const results = [];
  
  for (let i = 0; i < imagesToSearch.length; i++) {
    chrome.runtime.sendMessage({
      type: 'searchProgress',
      current: i + 1,
      total: imagesToSearch.length,
      filename: imagesToSearch[i].filename
    }).catch(() => {});
    
    const result = await executeGoogleSearch(imagesToSearch[i]);
    results.push(result);
    
    console.log('[搜图] 图片 ' + (i+1) + ' 日志:', result.logs?.join('\n'));
    
    if (i < imagesToSearch.length - 1) {
      await wait(2000);
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
    // 返回已搜图的图片列表
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
        const successCount = results.filter(r => r.success).length;
        const failCount = results.filter(r => !r.success).length;
        
        results.forEach((r, i) => {
          console.log(`[搜图] 图片${i+1}日志:`, r.logs?.join('\n'));
        });
        
        chrome.runtime.sendMessage({
          type: 'searchComplete',
          successCount,
          failCount,
          results
        }).catch(() => {});
      })
      .catch(error => {
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
});

chrome.runtime.onStartup.addListener(async () => {
  await loadSearchedImages();
  startHeartbeat();
});

// Service Worker激活时加载记录并启动心跳
loadSearchedImages().then(() => {
  startHeartbeat();
});