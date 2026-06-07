/**
 * 以图搜图 Tab 模块
 * 从 Google Image Search Tool 提取，所有元素 ID 使用 is 前缀
 */

(function() {
  'use strict';

  let images = [];
  let downloadedFiles = [];
  let serverOnline = false;
  let statusUpdateInterval = null;
  let isSearching = false;
  let debugMode = false;
  let previewVisible = false;
  let currentToast = null;

  // ==================== Toast通知 ====================

  function showToast(message, type = 'info') {
    const container = document.getElementById('isToastContainer');
    if (!container) return;

    if (currentToast && currentToast.parentNode) {
      currentToast.parentNode.removeChild(currentToast);
    }

    const toast = document.createElement('div');
    toast.className = `is-toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    currentToast = toast;

    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
      if (currentToast === toast) {
        currentToast = null;
      }
    }, 5000);
  }

  // ==================== 工具函数 ====================

  function getTodayDir() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}${month}${day}`;
  }

  // ==================== 调试模式 ====================

  function toggleDebugMode() {
    debugMode = !debugMode;
    const panel = document.getElementById('isDebugPanel');
    const toggle = document.getElementById('isDebugToggle');

    if (debugMode) {
      panel.classList.add('visible');
      toggle.classList.add('active');
      debugLog('调试模式已启用', 'info');
    } else {
      panel.classList.remove('visible');
      toggle.classList.remove('active');
    }
  }

  function debugLog(message, type = 'info') {
    const log = document.getElementById('isDebugLog');
    if (!log) return;

    const entry = document.createElement('div');
    entry.className = `is-debug-log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
  }

  function debugClearLog() {
    const log = document.getElementById('isDebugLog');
    if (log) {
      log.innerHTML = '<div class="is-debug-log-entry info">日志已清空</div>';
    }
  }

  function updateStepStatus(step, status) {
    const stepEl = document.querySelector(`#tab-imagesearch .is-debug-step[data-step="${step}"]`);
    if (stepEl) {
      stepEl.classList.remove('active', 'success', 'error');
      if (status) stepEl.classList.add(status);
    }
  }

  function getCustomSelector() {
    return document.getElementById('isDebugSelector')?.value?.trim() || '';
  }

  function getTextFilter() {
    return document.getElementById('isDebugTextFilter')?.value?.trim() || '';
  }

  function getDebugFilename() {
    return document.getElementById('isDebugFilename')?.value?.trim() || '';
  }

  async function debugTestSelector() {
    const selector = getCustomSelector();
    const textFilter = getTextFilter();

    if (!selector && !textFilter) {
      debugLog('请输入选择器或文本内容', 'warn');
      return;
    }

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (sel, txt) => {
          let elements = [];
          if (sel) {
            try { elements = Array.from(document.querySelectorAll(sel)); } catch (e) {}
          }
          if (txt) {
            const matches = Array.from(document.querySelectorAll('*')).filter(el => {
              const text = el.textContent || '';
              return text.includes(txt) && text.length < 100;
            });
            elements = elements.length > 0 ? elements.filter(el => matches.includes(el)) : matches;
          }
          return {
            count: elements.length,
            elements: elements.slice(0, 5).map(el => ({
              tag: el.tagName.toLowerCase(),
              text: (el.textContent || '').trim().substring(0, 50)
            }))
          };
        },
        args: [selector, textFilter],
        world: 'MAIN'
      });

      const result = results[0]?.result;
      if (result) {
        debugLog(`找到 ${result.count} 个元素`, result.count > 0 ? 'success' : 'warn');
        result.elements?.forEach((el, i) => {
          debugLog(`  [${i}] ${el.tag} - "${el.text}"`, 'info');
        });
      }
    } catch (error) {
      debugLog(`测试失败: ${error.message}`, 'error');
    }
  }

  async function debugInspectPage() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const buttons = [];
          document.querySelectorAll('div[role="button"], button, a, span[role="button"]').forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
              buttons.push({
                tag: el.tagName.toLowerCase(),
                text: (el.textContent || '').trim().substring(0, 50),
                aria: el.getAttribute('aria-label') || ''
              });
            }
          });
          return { url: window.location.href, title: document.title, buttons: buttons.slice(0, 20) };
        },
        world: 'MAIN'
      });

      const result = results[0]?.result;
      if (result) {
        debugLog('页面检查:', 'info');
        debugLog(`  URL: ${result.url}`, 'info');
        debugLog(`  标题: ${result.title}`, 'info');
        result.buttons.forEach((btn, i) => {
          debugLog(`  [${i}] ${btn.tag} - "${btn.text}"`, 'info');
        });
      }
    } catch (error) {
      debugLog(`检查失败: ${error.message}`, 'error');
    }
  }

  async function debugRunStep(step) {
    debugLog(`执行步骤 ${step}...`, 'info');
    updateStepStatus(step, 'active');

    try {
      switch (step) {
        case 1: await debugStep1(); break;
        case 2: await debugStep2(); break;
        case 3: await debugStep3(); break;
        case 4: await debugStep4(); break;
        default: debugLog('未知步骤', 'error');
      }
      updateStepStatus(step, 'success');
    } catch (error) {
      debugLog(`步骤 ${step} 失败: ${error.message}`, 'error');
      updateStepStatus(step, 'error');
    }
  }

  async function debugStep1() {
    await chrome.tabs.create({ url: 'https://www.google.com/imghp', active: true });
    await new Promise(r => setTimeout(r, 2000));
    debugLog('Google搜图页面已打开', 'success');
  }

  async function debugStep2() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const el = document.querySelector('div[aria-label="按图搜索"], div[aria-label="Search by image"]');
        if (el) { el.click(); return { success: true }; }
        return { success: false, error: '未找到' };
      },
      world: 'MAIN'
    });
    if (result[0]?.result?.success) debugLog('点击成功', 'success');
    else throw new Error('点击失败');
  }

  async function debugStep3() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const result = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const spans = document.querySelectorAll('span');
        for (const span of spans) {
          if (span.textContent?.trim() === '上传文件') {
            span.click();
            return { success: true };
          }
        }
        return { success: false, error: '未找到' };
      },
      world: 'MAIN'
    });
    if (result[0]?.result?.success) debugLog('点击成功', 'success');
    else throw new Error('点击失败');
  }

  async function debugStep4() {
    const filename = getDebugFilename();
    if (!filename) throw new Error('请输入文件名');

    const serverUrl = document.getElementById('isServerUrl').value;
    const response = await fetch(`${serverUrl}/api/select-file-and-upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
      signal: AbortSignal.timeout(30000)
    });
    const result = await response.json();
    if (result.success) debugLog('文件选择成功', 'success');
    else throw new Error(result.error);
  }

  // ==================== 初始化 ====================

  function checkScriptingAPI() {
    return !!(chrome.scripting && chrome.scripting.executeScript);
  }

  async function saveState() {
    await chrome.storage.local.set({ images, downloadedFiles, lastScanTime: Date.now() });
  }

  async function restoreState() {
    const saved = await chrome.storage.local.get(['images', 'downloadedFiles', 'lastScanTime']);

    if (saved.images?.length > 0) images = saved.images;
    if (saved.downloadedFiles) downloadedFiles = saved.downloadedFiles;

    renderImageList();
    updateButtons();
    updateDownloadCount();
  }

  function updateDownloadCount() {
    const countEl = document.getElementById('isDownloadCount');
    const clearBtn = document.getElementById('isClearDownloadBtn');

    if (countEl) {
      countEl.textContent = downloadedFiles.length > 0 ? `已下载: ${downloadedFiles.length} 张` : '';
    }
    if (clearBtn) {
      clearBtn.style.display = downloadedFiles.length > 0 ? 'block' : 'none';
    }
  }

  function isImageDownloaded(imageSrc) {
    return downloadedFiles.some(f => f.url === imageSrc);
  }

  // 清除图片列表
  function clearImages() {
    images = [];
    renderImageList();
    updateButtons();
    saveState();
    showToast('已清除图片列表', 'info');
  }

  // 选择本地图片
  async function selectLocalImages() {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = 'image/*';

    input.onchange = async (e) => {
      const files = Array.from(e.target.files);
      if (files.length === 0) return;

      let addedCount = 0;
      const serverUrl = document.getElementById('isServerUrl').value;

      for (const file of files) {
        if (images.some(img => img.filename === file.name && img.source === 'local')) {
          continue;
        }

        try {
          const base64 = await readFileAsBase64(file);

          const response = await fetch(`${serverUrl}/api/save-local-image`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              filename: file.name,
              fileData: base64
            }),
            signal: AbortSignal.timeout(10000)
          });

          const result = await response.json();

          if (result.success) {
            const imageUrl = `${serverUrl}${result.url}`;
            const dimensions = await getImageDimensions(imageUrl);

            images.push({
              src: imageUrl,
              filename: file.name,
              width: dimensions.width,
              height: dimensions.height,
              alt: file.name,
              source: 'local',
              isLocal: true
            });

            addedCount++;
          } else {
            showToast(`上传失败: ${file.name}`, 'error');
          }
        } catch (error) {
          console.error('上传本地图片失败:', error);
          showToast(`上传失败: ${file.name}`, 'error');
        }
      }

      if (addedCount > 0) {
        renderImageList();
        updateButtons();
        await saveState();
        showToast(`已添加 ${addedCount} 张本地图片`, 'success');
      } else {
        showToast('没有新图片添加', 'info');
      }
    };

    input.click();
  }

  function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function getImageDimensions(url) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
      img.onerror = () => resolve({ width: 0, height: 0 });
      img.src = url;
    });
  }

  async function clearDownloadedFiles() {
    downloadedFiles = [];
    await saveState();
    updateButtons();
    updateDownloadCount();
    renderImageList();
    showToast('已清空下载记录', 'info');
  }

  function startStatusListener() {
    updateStatusFromStorage();
    statusUpdateInterval = setInterval(updateStatusFromStorage, 2000);
  }

  async function updateStatusFromStorage() {
    try {
      const result = await chrome.storage.local.get(['serverStatus']);
      const status = result.serverStatus;
      if (status) {
        serverOnline = status.online;
        updateStatusUI(status);
        updateButtons();
      }
    } catch (error) {}
  }

  function updateStatusUI(status) {
    const dot = document.getElementById('isStatusDot');
    const label = document.getElementById('isStatusLabel');
    const footer = document.getElementById('isStatus');
    const statusMini = document.getElementById('isServerStatusMini');

    if (status.online) {
      dot.className = 'status-dot online';
      label.textContent = '在线';
      footer.textContent = '服务在线';
      footer.className = 'status success';
      statusMini.classList.remove('clickable');
      statusMini.title = '';
    } else {
      dot.className = 'status-dot offline';
      label.textContent = '离线';
      footer.textContent = '服务离线 - 点击状态栏启动服务';
      footer.className = 'status error';
      statusMini.classList.add('clickable');
      statusMini.title = '点击启动本地服务';
    }
  }

  function onStatusClick() {
    if (serverOnline) return;
    showToast('正在启动本地服务...', 'info');
    chrome.tabs.create({ url: 'qqhelpr://start', active: true });
  }

  // ==================== 扫描图片 ====================

  async function scanImages() {
    const scanBtn = document.getElementById('isScanBtn');
    scanBtn.disabled = true;

    try {
      if (!checkScriptingAPI()) throw new Error('scripting API不可用');

      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') ||
          tab.url.startsWith('chrome-extension://')) {
        showToast('无法在此页面使用，请打开普通网页', 'error');
        return;
      }

      showToast('正在扫描图片...', 'info');

      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: scanPageImages,
        world: 'MAIN'
      });

      if (results?.[0]?.result) {
        images = results[0].result;
      } else {
        images = [];
      }

      renderImageList();
      updateButtons();
      await saveState();
      showToast(`找到 ${images.length} 张图片`, 'success');

    } catch (error) {
      showToast('扫描失败: ' + error.message, 'error');
    } finally {
      scanBtn.disabled = false;
    }
  }

  function scanPageImages() {
    const images = [];
    const seen = new Set();

    function cleanUrl(url) {
      if (!url) return null;
      url = url.trim();
      if (url.startsWith('data:') && url.length < 2000) return null;
      if (url.startsWith('javascript:') || url === 'about:blank') return null;
      try { return new URL(url, window.location.href).href; } catch { return null; }
    }

    function isImageUrl(url) {
      if (!url) return false;
      if (url.includes('.svg') || url.includes('svg+xml')) return false;
      return /\.(jpg|jpeg|png|gif|webp|bmp|ico|tiff|avif)(\?.*)?$/i.test(url);
    }

    function addImage(src, width, height, alt, source) {
      if (!src) return;
      const cleanSrc = cleanUrl(src);
      if (!cleanSrc || seen.has(cleanSrc)) return;
      if (cleanSrc.length < 10) return;
      if (cleanSrc.includes('.svg') || cleanSrc.includes('svg+xml')) return;
      if (width > 0 && width < 50) return;
      if (height > 0 && height < 50) return;
      if (width === 1 || height === 1) return;

      seen.add(cleanSrc);

      let filename = '';
      try {
        const url = new URL(cleanSrc);
        filename = decodeURIComponent(url.pathname.split('/').pop() || '');
        filename = filename.split('?')[0].split('#')[0];
      } catch { filename = ''; }

      if (!filename || !filename.includes('.') || filename.length < 3) {
        const ext = cleanSrc.match(/\.(jpg|jpeg|png|gif|webp|bmp)(\?|$)/i)?.[1] || 'jpg';
        filename = `image_${images.length}.${ext}`;
      }

      filename = filename.replace(/[<>:"/\\|?*]/g, '_');

      images.push({
        src: cleanSrc,
        filename: filename,
        width: width || 0,
        height: height || 0,
        alt: alt || '',
        source: source || 'unknown'
      });
    }

    document.querySelectorAll('img').forEach(img => {
      const attrs = ['src', 'data-src', 'data-original', 'data-lazy-src', 'data-image-src', 'data-image'];
      let src = null;
      for (const attr of attrs) {
        const val = img.getAttribute(attr);
        if (val && val.length > 10 && !val.startsWith('data:') && !val.includes('.svg')) {
          src = val;
          break;
        }
      }
      if (!src) src = img.src;
      if (!src && img.srcset) {
        const parts = img.srcset.split(',');
        if (parts.length > 0) src = parts[parts.length - 1].trim().split(/\s+/)[0];
      }
      if (src && !src.includes('.svg')) {
        const w = img.naturalWidth || img.width || parseInt(img.getAttribute('width')) || 0;
        const h = img.naturalHeight || img.height || parseInt(img.getAttribute('height')) || 0;
        addImage(src, w, h, img.alt || img.title || '', 'img');
      }
    });

    document.querySelectorAll('*').forEach(el => {
      try {
        const bg = window.getComputedStyle(el).backgroundImage;
        if (bg && bg !== 'none' && bg.includes('url(')) {
          const matches = bg.matchAll(/url\(["']?([^"')]+)["']?\)/g);
          for (const m of matches) {
            if (m[1] && !m[1].startsWith('data:') && !m[1].includes('.svg')) {
              addImage(m[1], 0, 0, '', 'background');
            }
          }
        }
      } catch (e) {}
    });

    document.querySelectorAll('a[href]').forEach(link => {
      if (isImageUrl(link.href)) addImage(link.href, 0, 0, link.title || '', 'link');
    });

    document.querySelectorAll('meta[property="og:image"]').forEach(meta => {
      const c = meta.getAttribute('content');
      if (c && !c.includes('.svg')) addImage(c, 0, 0, '', 'meta');
    });

    function scanShadowRoots(root) {
      root.querySelectorAll('*').forEach(el => {
        if (el.shadowRoot) {
          el.shadowRoot.querySelectorAll('img').forEach(img => {
            if (img.src && !img.src.includes('.svg')) {
              addImage(img.src, img.naturalWidth, img.naturalHeight, img.alt || '', 'shadow');
            }
          });
          scanShadowRoots(el.shadowRoot);
        }
      });
    }
    scanShadowRoots(document);

    return images;
  }

  // ==================== 渲染UI ====================

  function renderImageList() {
    const list = document.getElementById('isImageList');
    const count = document.getElementById('isImageCount');

    if (images.length === 0) {
      list.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">暂无图片<br><small>点击扫描或选择本地图片</small></div>';
      count.textContent = '0 张图片';
      return;
    }

    const sources = {};
    images.forEach(img => {
      sources[img.source] = (sources[img.source] || 0) + 1;
    });

    list.innerHTML = `
      <div style="font-size: 11px; color: #666; padding: 4px; margin-bottom: 4px; background: #f0f0f0; border-radius: 4px;">
        来源: ${Object.entries(sources).map(([k, v]) => `${k}(${v})`).join(', ')}
      </div>
      ${images.map((img, index) => {
        const isLocal = img.source === 'local';
        const downloaded = isImageDownloaded(img.src);
        let statusClass = 'pending';
        let statusText = '待下载';

        if (isLocal) {
          statusClass = 'local';
          statusText = '本地';
        } else if (downloaded) {
          statusClass = 'downloaded';
          statusText = '已下载';
        }

        return `
          <div class="is-image-item" data-index="${index}">
            <input type="checkbox" class="is-image-checkbox" data-index="${index}" checked>
            <span class="filename" title="${img.src}">${img.filename}</span>
            <span class="size">${img.width > 0 ? img.width + 'x' + img.height : ''}</span>
            <span class="is-status ${statusClass}">${statusText}</span>
            <div class="preview-trigger" data-src="${img.src}" data-filename="${img.filename}" data-width="${img.width}" data-height="${img.height}">
              <img src="${img.src}" alt="${img.alt}" loading="lazy">
            </div>
          </div>
        `;
      }).join('')}
    `;

    count.textContent = `${images.length} 张图片`;

    list.querySelectorAll('.is-image-checkbox').forEach(cb => {
      cb.addEventListener('change', updateButtons);
    });

    list.querySelectorAll('.preview-trigger').forEach(trigger => {
      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        showPreview(e.currentTarget);
      });
    });
  }

  function showPreview(element) {
    if (previewVisible) {
      hidePreview();
      return;
    }

    const overlay = document.getElementById('isPreviewOverlay');
    const previewImg = document.getElementById('isPreviewImage');
    const previewInfo = document.getElementById('isPreviewInfo');

    previewImg.src = element.getAttribute('data-src');
    previewInfo.textContent = `${element.getAttribute('data-filename')} (${element.getAttribute('data-width')}x${element.getAttribute('data-height')})`;

    overlay.style.display = 'flex';
    previewVisible = true;
  }

  function hidePreview() {
    document.getElementById('isPreviewOverlay').style.display = 'none';
    previewVisible = false;
  }

  function toggleSelectAll(e) {
    document.querySelectorAll('.is-image-checkbox').forEach(cb => { cb.checked = e.target.checked; });
    updateButtons();
  }

  function updateButtons() {
    const checked = document.querySelectorAll('.is-image-checkbox:checked');
    const hasSelection = checked.length > 0;

    document.getElementById('isScanBtn').disabled = false;
    document.getElementById('isSelectLocalBtn').disabled = false;
    document.getElementById('isClearImagesBtn').disabled = images.length === 0;
    document.getElementById('isDownloadBtn').disabled = !hasSelection || isSearching;
    document.getElementById('isSearchBtn').disabled = !hasSelection || !serverOnline || isSearching;
    document.getElementById('isAmazonSearchBtn').disabled = !hasSelection || !serverOnline || isSearching;
  }

  function getSelectedImages() {
    const checkboxes = document.querySelectorAll('.is-image-checkbox:checked');
    return Array.from(checkboxes).map(cb => images[parseInt(cb.dataset.index)]);
  }

  // ==================== 分割图片模块 ====================

  let splitFileData = null;  // 当前选择的分割文件

  function initSplitModule() {
    const toggle = document.getElementById('isSplitToggle');
    const content = document.getElementById('isSplitContent');
    const switchInput = document.getElementById('isSplitSwitch');
    const slider = document.getElementById('isSplitSlider');
    const sliderDot = document.getElementById('isSplitSliderDot');
    const dropZone = document.getElementById('isSplitDropZone');
    const fileInput = document.getElementById('isSplitFileInput');
    const preview = document.getElementById('isSplitPreview');
    const previewImg = document.getElementById('isSplitPreviewImg');
    const confirmBtn = document.getElementById('isSplitConfirmBtn');
    const cancelBtn = document.getElementById('isSplitCancelBtn');

    // 从本地存储恢复状态，默认展开
    const savedState = localStorage.getItem('splitExpanded');
    const isExpanded = savedState !== null ? savedState === 'true' : true;
    content.style.display = isExpanded ? 'block' : 'none';
    switchInput.checked = isExpanded;
    updateSwitchStyle(isExpanded);

    function updateSwitchStyle(checked) {
      slider.style.backgroundColor = checked ? '#409eff' : '#dcdfe6';
      sliderDot.style.left = checked ? '18px' : '2px';
    }

    // 开关切换
    switchInput.addEventListener('change', (e) => {
      const isVisible = e.target.checked;
      content.style.display = isVisible ? 'block' : 'none';
      updateSwitchStyle(isVisible);
      localStorage.setItem('splitExpanded', isVisible);
    });

    // 点击整个 header 区域也切换（但不包括 switch 本身的点击）
    toggle.addEventListener('click', (e) => {
      if (e.target.closest('label')) return; // 点击 switch 区域不处理
      switchInput.checked = !switchInput.checked;
      switchInput.dispatchEvent(new Event('change'));
    });

    // 点击上传区域选择文件
    dropZone.addEventListener('click', () => {
      fileInput.click();
    });

    // 文件选择变化
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handleSplitFile(e.target.files[0]);
      }
    });

    // 拖拽事件
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      
      if (e.dataTransfer.files.length > 0) {
        handleSplitFile(e.dataTransfer.files[0]);
      }
    });

    // 开始分割
    confirmBtn.addEventListener('click', () => {
      if (splitFileData) {
        executeSplitImage(splitFileData);
      }
    });

    // 取消
    cancelBtn.addEventListener('click', () => {
      resetSplitModule();
    });
  }

  function handleSplitFile(file) {
    if (!file.type.startsWith('image/')) {
      showToast('请选择图片文件', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      splitFileData = {
        name: file.name,
        data: e.target.result  // base64数据
      };

      // 显示预览
      document.getElementById('isSplitPreviewImg').src = e.target.result;
      document.getElementById('isSplitDropZone').style.display = 'none';
      document.getElementById('isSplitPreview').style.display = 'block';
    };
    reader.readAsDataURL(file);
  }

  function resetSplitModule() {
    splitFileData = null;
    document.getElementById('isSplitDropZone').style.display = 'block';
    document.getElementById('isSplitPreview').style.display = 'none';
    document.getElementById('isSplitProgress').style.display = 'none';
    document.getElementById('isSplitFileInput').value = '';
  }

  async function executeSplitImage(fileData) {
    if (!serverOnline) {
      showToast('服务器未连接，请先启动本地服务器', 'error');
      return;
    }

    const serverUrl = document.getElementById('isServerUrl').value;

    // 显示进度
    document.getElementById('isSplitPreview').style.display = 'none';
    document.getElementById('isSplitProgress').style.display = 'block';
    document.getElementById('isSplitProgressFill').style.width = '30%';
    document.getElementById('isSplitProgressText').textContent = '正在上传图片...';

    try {
      // 先上传图片到服务器
      const uploadResponse = await fetch(`${serverUrl}/api/save-local-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: fileData.name,
          fileData: fileData.data
        }),
        signal: AbortSignal.timeout(30000)
      });

      const uploadResult = await uploadResponse.json();
      
      if (!uploadResult.success) {
        throw new Error(uploadResult.error || '上传失败');
      }

      document.getElementById('isSplitProgressFill').style.width = '60%';
      document.getElementById('isSplitProgressText').textContent = '正在分割图片...';

      // 调用分割API
      const splitResponse = await fetch(`${serverUrl}/api/split-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imageUrl: uploadResult.url,
          filename: fileData.name
        }),
        signal: AbortSignal.timeout(60000)
      });

      const splitResult = await splitResponse.json();

      document.getElementById('isSplitProgressFill').style.width = '100%';

      if (splitResult.success) {
        document.getElementById('isSplitProgressText').textContent = `分割完成: ${splitResult.count} 张图片`;
        
        // 先清空列表
        images.length = 0;
        
        // 将分割后的图片添加到列表
        for (const splitImg of splitResult.images) {
          images.push({
            src: serverUrl + splitImg.url,
            filename: splitImg.filename,
            width: splitImg.width || 0,
            height: splitImg.height || 0,
            alt: splitImg.filename,
            source: 'split',
            isLocal: true
          });
        }

        renderImageList();
        updateButtons();
        await saveState();

        showToast(`分割完成: ${splitResult.count} 张图片已添加到列表`, 'success');

        // 2秒后重置分割模块
        setTimeout(() => {
          resetSplitModule();
        }, 2000);
      } else {
        throw new Error(splitResult.error || '分割失败');
      }
    } catch (error) {
      console.error('分割图片失败:', error);
      document.getElementById('isSplitProgressFill').style.width = '0%';
      document.getElementById('isSplitProgressText').textContent = '分割失败: ' + error.message;
      showToast('分割失败: ' + error.message, 'error');
      
      // 3秒后重置
      setTimeout(() => {
        resetSplitModule();
      }, 3000);
    }
  }

  // ==================== 下载 ====================

  async function downloadSelected() {
    const selected = getSelectedImages();
    if (selected.length === 0) return;

    // 分离本地图片和远程图片
    const localImages = selected.filter(img => img.source === 'local' || img.source === 'split');
    const remoteImages = selected.filter(img => img.source !== 'local' && img.source !== 'split' && !isImageDownloaded(img.src));

    // 处理本地图片 - 打开文件所在目录
    if (localImages.length > 0) {
      const serverUrl = document.getElementById('isServerUrl').value;
      
      for (const img of localImages) {
        try {
          // 从URL提取文件路径
          const response = await fetch(`${serverUrl}/api/open-file-location`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ imageUrl: img.src }),
            signal: AbortSignal.timeout(10000)
          });
          
          const result = await response.json();
          if (result.success) {
            showToast(`已打开文件所在目录: ${img.filename}`, 'success');
          } else {
            showToast(`打开目录失败: ${result.error}`, 'error');
          }
        } catch (error) {
          console.error('打开目录失败:', error);
          showToast(`打开目录失败: ${error.message}`, 'error');
        }
      }
    }

    // 处理远程图片 - 下载
    if (remoteImages.length === 0) {
      if (localImages.length === 0) {
        showToast('选中的图片无需下载', 'info');
      }
      return;
    }

    const downloadBtn = document.getElementById('isDownloadBtn');
    downloadBtn.disabled = true;

    const progressSection = document.getElementById('isProgressSection');
    progressSection.style.display = 'block';

    let completed = 0;
    let failed = 0;
    const newFiles = [];

    for (const img of remoteImages) {
      try {
        const downloadPath = `qingqing_helper_dir/${getTodayDir()}/${img.filename}`;

        const downloadId = await chrome.downloads.download({
          url: img.src,
          filename: downloadPath,
          saveAs: false
        });

        await waitForDownload(downloadId);
        newFiles.push({ filename: img.filename, url: img.src });
        completed++;
        updateProgress(completed, remoteImages.length);
      } catch (error) {
        console.error('下载失败:', img.src, error);
        failed++;
      }
    }

    downloadedFiles = [...downloadedFiles, ...newFiles];

    const message = failed > 0
      ? `下载完成: ${completed} 成功, ${failed} 失败`
      : `成功下载 ${completed} 张图片`;

    showToast(message, failed > 0 ? 'info' : 'success');
    updateButtons();
    updateDownloadCount();
    renderImageList();
    await saveState();

    setTimeout(() => {
      downloadBtn.disabled = false;
      progressSection.style.display = 'none';
    }, 3000);
  }

  function waitForDownload(downloadId) {
    return new Promise((resolve, reject) => {
      const listener = (delta) => {
        if (delta.id === downloadId) {
          if (delta.state?.current === 'complete') {
            chrome.downloads.onChanged.removeListener(listener);
            resolve();
          }
          if (delta.error) {
            chrome.downloads.onChanged.removeListener(listener);
            reject(new Error(delta.error.current));
          }
        }
      };
      chrome.downloads.onChanged.addListener(listener);
      setTimeout(() => {
        chrome.downloads.onChanged.removeListener(listener);
        reject(new Error('下载超时'));
      }, 60000);
    });
  }

  function updateProgress(current, total) {
    const percent = Math.round((current / total) * 100);
    document.getElementById('isProgressFill').style.width = percent + '%';
    document.getElementById('isProgressText').textContent = `${current} / ${total}`;
  }

  // ==================== Google搜图 ====================

  async function startGoogleSearch() {
    const selected = getSelectedImages();
    if (selected.length === 0) {
      showToast('请先选择图片', 'error');
      return;
    }

    if (!serverOnline) {
      showToast('服务器未连接，请先启动本地服务器', 'error');
      return;
    }

    if (isSearching) {
      showToast('正在处理中，请等待...', 'info');
      return;
    }

    isSearching = true;
    const btn = document.getElementById('isSearchBtn');
    btn.disabled = true;
    btn.textContent = '处理中...';

    const toDownload = selected.filter(img => img.source !== 'local' && !isImageDownloaded(img.src));

    if (toDownload.length > 0) {
      showToast(`正在下载 ${toDownload.length} 张图片...`, 'info');

      for (const img of toDownload) {
        try {
          const downloadPath = `qingqing_helper_dir/${getTodayDir()}/${img.filename}`;
          const downloadId = await chrome.downloads.download({
            url: img.src,
            filename: downloadPath,
            saveAs: false
          });
          await waitForDownload(downloadId);
          downloadedFiles.push({ filename: img.filename, url: img.src });
        } catch (error) {
          console.error('下载失败:', img.src, error);
        }
      }

      await saveState();
      updateDownloadCount();
      renderImageList();
    }

    showToast('开始搜图流程...', 'info');

    chrome.runtime.sendMessage({
      action: 'startGoogleSearch',
      images: selected.map(img => ({
        filename: img.filename,
        isLocal: img.source === 'local'
      }))
    });
  }

  // ==================== Amazon搜图 ====================

  async function startAmazonSearch() {
    const selected = getSelectedImages();
    if (selected.length === 0) {
      showToast('请先选择图片', 'error');
      return;
    }

    if (!serverOnline) {
      showToast('服务器未连接，请先启动本地服务器', 'error');
      return;
    }

    if (isSearching) {
      showToast('正在处理中，请等待...', 'info');
      return;
    }

    isSearching = true;
    const btn = document.getElementById('isAmazonSearchBtn');
    btn.disabled = true;
    btn.textContent = '处理中...';

    const toDownload = selected.filter(img => img.source !== 'local' && !isImageDownloaded(img.src));

    if (toDownload.length > 0) {
      showToast(`正在下载 ${toDownload.length} 张图片...`, 'info');

      for (const img of toDownload) {
        try {
          const downloadPath = `qingqing_helper_dir/${getTodayDir()}/${img.filename}`;
          const downloadId = await chrome.downloads.download({
            url: img.src,
            filename: downloadPath,
            saveAs: false
          });
          await waitForDownload(downloadId);
          downloadedFiles.push({ filename: img.filename, url: img.src });
        } catch (error) {
          console.error('下载失败:', img.src, error);
        }
      }

      await saveState();
      updateDownloadCount();
      renderImageList();
    }

    showToast('开始Amazon搜图流程...', 'info');

    chrome.runtime.sendMessage({
      action: 'startAmazonSearch',
      images: selected.map(img => ({
        filename: img.filename,
        isLocal: img.source === 'local'
      }))
    });
  }

  // ==================== 绑定事件 ====================

  function initImageSearchTab() {
    // 按钮事件
    document.getElementById('isScanBtn').addEventListener('click', scanImages);
    document.getElementById('isSelectLocalBtn').addEventListener('click', selectLocalImages);
    document.getElementById('isClearImagesBtn').addEventListener('click', clearImages);
    document.getElementById('isDownloadBtn').addEventListener('click', downloadSelected);
    document.getElementById('isSearchBtn').addEventListener('click', startGoogleSearch);
    document.getElementById('isAmazonSearchBtn').addEventListener('click', startAmazonSearch);
    document.getElementById('isSelectAll').addEventListener('change', toggleSelectAll);
    document.getElementById('isClearDownloadBtn').addEventListener('click', clearDownloadedFiles);

    // 调试按钮
    document.getElementById('isDebugToggle').addEventListener('click', toggleDebugMode);
    document.getElementById('isDebugTestSelectorBtn').addEventListener('click', debugTestSelector);
    document.getElementById('isDebugInspectPageBtn').addEventListener('click', debugInspectPage);
    document.getElementById('isDebugClearLogBtn').addEventListener('click', debugClearLog);

    document.querySelectorAll('#tab-imagesearch [data-step-btn]').forEach(btn => {
      btn.addEventListener('click', () => debugRunStep(parseInt(btn.getAttribute('data-step-btn'))));
    });

    // 预览关闭
    document.getElementById('isPreviewClose').addEventListener('click', hidePreview);
    document.getElementById('isPreviewOverlay').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) hidePreview();
    });

    // 监听background消息
    chrome.runtime.onMessage.addListener((message) => {
      if (message.type === 'searchProgress') {
        showToast(`搜图进度: ${message.current}/${message.total} - ${message.filename}`, 'info');
      }
      if (message.type === 'searchSkipped') {
        showToast(`跳过 ${message.count} 张已搜图的图片`, 'info');
      }
      if (message.type === 'searchComplete') {
        isSearching = false;
        const msg = message.failCount > 0
          ? `搜图完成: ${message.successCount} 成功, ${message.failCount} 失败`
          : `全部 ${message.successCount} 张图片搜图完成!`;
        showToast(msg, message.failCount > 0 ? 'info' : 'success');
        updateButtons();
        document.getElementById('isSearchBtn').textContent = 'Google搜图';
        document.getElementById('isAmazonSearchBtn').textContent = 'Amazon搜图';
      }
      if (message.type === 'searchError') {
        isSearching = false;
        showToast('搜图失败: ' + message.error, 'error');
        updateButtons();
        document.getElementById('isSearchBtn').textContent = 'Google搜图';
        document.getElementById('isAmazonSearchBtn').textContent = 'Amazon搜图';
      }
    });

    // 状态指示器点击
    document.getElementById('isServerStatusMini').addEventListener('click', onStatusClick);

    // 初始化分割模块
    initSplitModule();

    startStatusListener();
    restoreState();

    if (!checkScriptingAPI()) {
      showToast('警告: scripting API不可用', 'error');
    }
  }

  // 页面加载后初始化
  document.addEventListener('DOMContentLoaded', () => {
    // 从 storage 读取服务器地址
    chrome.storage.local.get(['serverUrl']).then(settings => {
      if (settings.serverUrl) {
        document.getElementById('isServerUrl').value = settings.serverUrl;
      }
      initImageSearchTab();
    });
  });

  window.addEventListener('unload', () => {
    if (statusUpdateInterval) clearInterval(statusUpdateInterval);
  });

})();
