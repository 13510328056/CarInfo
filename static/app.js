async function loadConfig() {
  const resp = await fetch('/api/config');
  const result = await resp.json();
  if (result.success) {
    document.getElementById('channels').value = (result.data.channels || []).join('\n');
    document.getElementById('keywords').value = (result.data.keywords || []).join('\n');
    document.getElementById('categories').value = categoriesToText(result.data.categories || {});
    document.getElementById('rssSources').value = (result.data.rss_sources || []).join('\n');
    return result.data;
  }
  return null;
}

function categoriesToText(categories) {
  return Object.entries(categories)
    .map(([name, keywords]) => `${name}: ${keywords.join(', ')}`)
    .join('\n');
}

/* ─── 分页状态 ─────────────────────────────────────────────── */
const ITEMS_PER_PAGE = 10;
let newsPage = 1;
let newsSearchQuery = '';
let crawlPage = 1;

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function shortenUrl(url, maxLen) {
  if (!url) return '';
  maxLen = maxLen || 30;
  if (url.length <= maxLen + 10) return url;
  try {
    const parsed = new URL(url);
    let domain = parsed.hostname.replace(/^www\./, '');
    let path = parsed.pathname.replace(/\/$/, '');
    if (path.length > 15) path = path.slice(0, 12) + '…';
    let short = domain + path;
    return short.length <= maxLen ? short : short.slice(0, maxLen) + '…';
  } catch(e) {
    return url.length > maxLen ? url.slice(0, maxLen) + '…' : url;
  }
}

function textToCategories(text) {
  const categories = {};
  for (const line of text.split('\n').map(l => l.trim()).filter(Boolean)) {
    const colonIdx = line.indexOf(':');
    if (colonIdx === -1) continue;
    const name = line.slice(0, colonIdx).trim();
    const keywords = line.slice(colonIdx + 1).split(',').map(k => k.trim()).filter(Boolean);
    if (name && keywords.length) categories[name] = keywords;
  }
  return categories;
}

async function saveConfig() {
  const channels = document.getElementById('channels').value.split('\n').map(x => x.trim()).filter(Boolean);
  const keywords = document.getElementById('keywords').value.split('\n').map(x => x.trim()).filter(Boolean);
  const categories = textToCategories(document.getElementById('categories').value);
  const rssSources = document.getElementById('rssSources').value.split('\n').map(x => x.trim()).filter(Boolean);
  const closingStyle = document.getElementById('closingStyle').value;
  // 先读取当前完整配置以保留 template
  const curResp = await fetch('/api/config');
  const curResult = await curResp.json();
  const template = (curResult.data && curResult.data.template) || {};
  template.closing_selected = parseInt(closingStyle);
  const resp = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({channels, keywords, categories, template, rss_sources: rssSources})
  });
  const result = await resp.json();
  alert(result.success ? '配置已保存' : '保存失败');
}

async function showNewsList() {
  const resp = await fetch('/api/news');
  const result = await resp.json();
  const container = document.getElementById('newsList');
  if (!result.success) {
    container.innerHTML = '<p>读取资讯列表失败。</p>';
    return;
  }
  const allItems = result.data;
  window.currentNewsItems = allItems;

  if (!allItems.length) {
    container.innerHTML = '<p>暂无资讯，请先抓取或手动录入。</p>';
    document.getElementById('newsPagination').innerHTML = '';
    return;
  }

  // 搜索过滤
  const q = newsSearchQuery.trim().toLowerCase();
  const filtered = q
    ? allItems.filter(item =>
        (item.title || '').toLowerCase().includes(q) ||
        (item.source || '').toLowerCase().includes(q) ||
        (item.content || '').toLowerCase().includes(q) ||
        (item.category || '').toLowerCase().includes(q)
      )
    : allItems;

  // 分页
  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  if (newsPage > totalPages) newsPage = totalPages;
  if (newsPage < 1) newsPage = 1;
  const start = (newsPage - 1) * ITEMS_PER_PAGE;
  const pageItems = filtered.slice(start, start + ITEMS_PER_PAGE);

  if (!filtered.length) {
    container.innerHTML = `<p style="color:var(--text-dim);">未找到匹配「${escapeHtml(q)}」的资讯。</p>`;
    document.getElementById('newsPagination').innerHTML = '';
    return;
  }

  // 渲染当前页
  container.innerHTML = pageItems.map(item => `
    <div class="news-card" id="news-card-${item.id}">
      <div class="news-card-main">
        ${item.image_url ? `<img class="news-thumb" src="${escapeHtml(item.image_url)}" alt="" loading="lazy" onerror="this.style.display='none'">` : ''}
        <div class="news-body">
          <div class="news-title">${escapeHtml(item.title)}</div>
          <div class="news-meta">
            <span>${escapeHtml(item.category)}</span>
            <span>${escapeHtml(item.source)}</span>
            <span>${escapeHtml(item.publish_time)}</span>
            ${item.url ? `<a class="news-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">📎 ${escapeHtml(shortenUrl(item.url))}</a>` : ''}
          </div>
        </div>
      </div>
      <div class="news-content">${escapeHtml(item.content).replace(/\n/g, '<br/>')}</div>
      <div class="news-actions">
        <button onclick="toggleEditForm('${item.id}')">编辑</button>
        <button onclick="deleteNewsItem('${item.id}')">删除</button>
      </div>
      <div class="edit-form" id="edit-form-${item.id}" style="display:none; margin-top:12px;"
        data-image="${escapeHtml(item.image_url || '')}">
        <label>标题<input id="edit-title-${item.id}" type="text" value="${escapeHtml(item.title)}" /></label>
        <label>来源<input id="edit-source-${item.id}" type="text" value="${escapeHtml(item.source)}" /></label>
        <label>发布时间<input id="edit-time-${item.id}" type="text" value="${escapeHtml(item.publish_time)}" /></label>
        <label>分类<select id="edit-category-${item.id}">
          <option${item.category === '政策动态' ? ' selected' : ''}>政策动态</option>
          <option${item.category === '企业落地' ? ' selected' : ''}>企业落地</option>
          <option${item.category === '技术动态' ? ' selected' : ''}>技术动态</option>
          <option${item.category === '招标采购' ? ' selected' : ''}>招标采购</option>
          <option${item.category === '行业观点/海外资讯' ? ' selected' : ''}>行业观点/海外资讯</option>
        </select></label>
        <label>内容<textarea id="edit-content-${item.id}" rows="4">${escapeHtml(item.content)}</textarea></label>
        <button onclick="saveNewsItem('${item.id}')">保存修改</button>
      </div>
    </div>
  `).join('');

  // 分页控件
  const info = q
    ? `找到 ${filtered.length} 条（共 ${allItems.length} 条）`
    : `共 ${allItems.length} 条`;
  let pagHtml = `<span class="page-info">${info}</span>`;
  pagHtml += `<button class="page-btn" onclick="goNewsPage(${newsPage - 1})" ${newsPage <= 1 ? 'disabled' : ''}>‹ 上一页</button>`;
  // 页码按钮（最多显示 7 个）
  const maxPageBtns = 7;
  let pageStart = Math.max(1, newsPage - Math.floor(maxPageBtns / 2));
  let pageEnd = Math.min(totalPages, pageStart + maxPageBtns - 1);
  if (pageEnd - pageStart + 1 < maxPageBtns) pageStart = Math.max(1, pageEnd - maxPageBtns + 1);
  for (let p = pageStart; p <= pageEnd; p++) {
    pagHtml += `<button class="page-btn ${p === newsPage ? 'active-page' : ''}" onclick="goNewsPage(${p})">${p}</button>`;
  }
  pagHtml += `<button class="page-btn" onclick="goNewsPage(${newsPage + 1})" ${newsPage >= totalPages ? 'disabled' : ''}>下一页 ›</button>`;
  pagHtml += `<span class="page-info">第 ${newsPage}/${totalPages} 页</span>`;
  document.getElementById('newsPagination').innerHTML = pagHtml;
}




function renderCrawlPage() {
  const container = document.getElementById('crawlResult');
  const items = window.currentCrawlItems || [];
  if (!items.length) return;

  const totalPages = Math.max(1, Math.ceil(items.length / ITEMS_PER_PAGE));
  if (crawlPage > totalPages) crawlPage = totalPages;
  if (crawlPage < 1) crawlPage = 1;
  const from = (crawlPage - 1) * ITEMS_PER_PAGE;
  const pageItems = items.slice(from, from + ITEMS_PER_PAGE);

  var cards = pageItems.map(function(item) {
    var badge = item._from_rss
      ? '<span style="display:inline-block;background:#ffedd5;color:#c2410c;font-size:11px;padding:1px 6px;border-radius:4px;margin-left:6px;">RSS</span>'
      : '';
    var text = escapeHtml(item.content).replace(/\n/g, '<br/>');
    return '<div class="crawl-card">'
      + '<div><strong>' + escapeHtml(item.title) + '</strong>' + badge + '</div>'
      + '<div>' + escapeHtml(item.source) + ' | \u5206\u7c7b\uff1a' + escapeHtml(item.category) + ' | \u5339\u914d\u5ea6\uff1a' + item.keyword_match + '%</div>'
      + '<div>' + text + '</div>'
      + '<div><a href="' + escapeHtml(item.url) + '" target="_blank" rel="noreferrer">\u539f\u6587\u94fe\u63a5</a></div>'
      + '</div>';
  }).join('');

    var bar = '<div class="pagination-bar" style="margin-top:12px;">';
  bar += '<button class="page-btn" onclick="goCrawlPage(' + (crawlPage - 1) + ')" ' + (crawlPage <= 1 ? 'disabled' : '') + '>\u2039 \u4e0a\u4e00\u9875</button>';
  var maxBtns = 7;
  var pStart = Math.max(1, crawlPage - Math.floor(maxBtns / 2));
  var pEnd = Math.min(totalPages, pStart + maxBtns - 1);
  if (pEnd - pStart + 1 < maxBtns) pStart = Math.max(1, pEnd - maxBtns + 1);
  for (var p = pStart; p <= pEnd; p++) {
    bar += '<button class="page-btn ' + (p === crawlPage ? 'active-page' : '') + '" onclick="goCrawlPage(' + p + ')">' + p + '</button>';
  }
  bar += '<button class="page-btn" onclick="goCrawlPage(' + (crawlPage + 1) + ')" ' + (crawlPage >= totalPages ? 'disabled' : '') + '>\u4e0b\u4e00\u9875 \u203a</button>';
  bar += '<span class="page-info">\u5171 ' + items.length + ' \u6761</span></div>';

  container.innerHTML = (window.currentCrawlSummary || '') + cards + bar;
}
function goCrawlPage(page) { crawlPage = page; renderCrawlPage(); }

function goNewsPage(page) {
  newsPage = page;
  showNewsList();
}

function onNewsSearch(e) {
  newsSearchQuery = e.target.value;
  newsPage = 1;
  showNewsList();
}

function toggleEditForm(id) {
  const form = document.getElementById(`edit-form-${id}`);
  if (!form) return;
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function saveNewsItem(id) {
  const title = document.getElementById(`edit-title-${id}`).value.trim();
  const source = document.getElementById(`edit-source-${id}`).value.trim();
  const publish_time = document.getElementById(`edit-time-${id}`).value.trim();
  const category = document.getElementById(`edit-category-${id}`).value;
  const content = document.getElementById(`edit-content-${id}`).value.trim();
  if (!title || !content) {
    alert('标题和内容不能为空');
    return;
  }
  const resp = await fetch(`/api/news/${id}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, source, publish_time, category, content})
  });
  const result = await resp.json();
  if (result.success) {
    alert('保存成功');
    await showNewsList();
  } else {
    alert('保存失败');
  }
}

async function deleteNewsItem(id) {
  if (!confirm('确认删除这条资讯吗？')) return;
  const resp = await fetch(`/api/news/${id}`, {method: 'DELETE'});
  const result = await resp.json();
  if (result.success) {
    alert('已删除');
    await showNewsList();
  } else {
    alert('删除失败');
  }
}

async function clearNews() {
  if (!confirm('确认清空全部资讯吗？此操作不可恢复！')) return;
  const resp = await fetch('/api/news/clear', {method: 'POST'});
  const result = await resp.json();
  if (result.success) {
    document.getElementById('newsList').innerHTML = '<p>资讯列表已清空。</p>';
    document.getElementById('newsPagination').innerHTML = '';
    document.getElementById('crawlResult').innerHTML = '';
    newsPage = 1;
    alert('已清空');
  } else {
    alert('清空失败');
  }
}

async function crawlNews() {
  const btn = document.getElementById('crawlBtn');
  const origText = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 抓取中...';
  btn.classList.add('is-loading');

  const container = document.getElementById('crawlResult');
  container.innerHTML = '<p style="color:#888;">⏳ 正在抓取各渠道及 RSS 资讯，请稍候...</p>';

  try {
    const channels = document.getElementById('channels').value.split('\n').map(x => x.trim()).filter(Boolean);
    const rssUrls = document.getElementById('rssSources').value.split('\n').map(x => x.trim()).filter(Boolean);
    const keywords = document.getElementById('keywords').value.split('\n').map(x => x.trim()).filter(Boolean);
    const categories = textToCategories(document.getElementById('categories').value);
    const resp = await fetch('/api/news/crawl', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({channel_urls: channels, rss_urls: rssUrls, keywords, category_keywords: categories})
    });
    const result = await resp.json();
    if (!result.success) {
      container.innerHTML = '<p>抓取失败。</p>';
      return;
    }
    const items = result.data;
    const crawlInfo = result.crawl_info || {};
    if (!items.length) {
      container.innerHTML = '<p>未获取到符合关键词的资讯。</p>';
      return;
    }
    const rssInfo = crawlInfo.rss_total > 0
      ? `，RSS 订阅 ${crawlInfo.rss_total} 个源`
      : '';
    const summary = `<div style="margin-bottom:12px;color:#333;">✅ 抓取到 ${items.length} 条资讯，来源 ${crawlInfo.total || 0} 个网页渠道${rssInfo}。已保存 ${result.added_count || 0} 条新资讯。</div>`;
        window.currentCrawlItems = items;
    window.currentCrawlSummary = summary;
    crawlPage = 1;
    renderCrawlPage();
    // 抓取后重置搜索和分页
    newsSearchQuery = '';
    const searchInput = document.getElementById('newsSearch');
    if (searchInput) searchInput.value = '';
    newsPage = 1;
    await showNewsList();
  } catch (err) {
    container.innerHTML = `<p>抓取异常：${err.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
    btn.classList.remove('is-loading');
  }
}

async function clearHistory() {
  if (!confirm('确认清空全部历史报告吗？此操作不可恢复！')) return;
  const resp = await fetch('/api/history', {method: 'DELETE'});
  const result = await resp.json();
  if (result.success) {
    document.getElementById('historyList').innerHTML = '<p>历史报告已清空。</p>';
    alert('已清空');
  } else {
    alert('清空失败');
  }
}

async function loadHistory() {
  const resp = await fetch('/api/history');
  const result = await resp.json();
  const container = document.getElementById('historyList');
  if (!result.success) {
    container.innerHTML = '<p>历史记录读取失败。</p>';
    return;
  }
  const items = result.data;
  if (!items.length) {
    container.innerHTML = '<p>暂无历史报告。</p>';
    return;
  }
  container.innerHTML = items.map(item => `
    <div class="history-card">
      <div><strong>${escapeHtml(item.date)}</strong> - ${escapeHtml(item.saved_at)}</div>
      <div>格式：${escapeHtml(item.report.format)}</div>
      <details style="margin-top:8px;"><summary>查看内容</summary>
        <pre>${escapeHtml(item.report.report)}</pre>
      </details>
    </div>
  `).join('');
}

async function addManualNews() {
  const title = document.getElementById('manualTitle').value.trim();
  const source = document.getElementById('manualSource').value.trim();
  const publish_time = document.getElementById('manualTime').value.trim();
  const category = document.getElementById('manualCategory').value;
  const content = document.getElementById('manualContent').value.trim();
  if (!title || !content) {
    alert('请输入标题和内容。');
    return;
  }
  const resp = await fetch('/api/news', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({title, source, publish_time, category, content})
  });
  const result = await resp.json();
  if (result.success) {
    alert('资讯已保存');
    document.getElementById('manualTitle').value = '';
    document.getElementById('manualContent').value = '';
    showNewsList();
  } else {
    alert('保存失败');
  }
}

async function exportReport() {
  const format = document.getElementById('exportFormat').value;
  const closingStyle = document.getElementById('closingStyle').value;
  const attentionText = document.getElementById('attentionText').value.trim();
  const resp = await fetch('/api/news');
  const result = await resp.json();
  if (!result.success) {
    alert('读取资讯失败');
    return;
  }
  const news_items = result.data;
  if (!news_items.length) {
    alert('请先添加或抓取资讯');
    return;
  }
  const exportResp = await fetch('/api/export', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({format, news_items, attention_text: attentionText, closing_style: closingStyle})
  });
  const exportResult = await exportResp.json();
  const container = document.getElementById('exportResult');
  const copyBtn = document.getElementById('copyExportBtn');
  const publishBtn = document.getElementById('publishBtn');
  if (!exportResult.success) {
    container.innerHTML = '<p>导出失败。</p>';
    copyBtn.style.display = 'none';
    publishBtn.style.display = 'none';
    return;
  }
  if (format === 'mp') {
    // 存储纯文本和 HTML 用于复制
    const plainText = exportResult.data.report;
    const htmlText = exportResult.data.report_html || plainText;
    copyBtn.dataset.text = plainText;
    copyBtn.dataset.html = htmlText;
    copyBtn.style.display = 'inline-block';

    container.innerHTML = `<div class="mp-preview">${htmlText}</div>`;

    // 检查是否配置了微信发布
    const appid = document.getElementById('wechatAppid').value.trim();
    if (appid) {
      publishBtn.style.display = 'inline-block';
      publishBtn.dataset.attentionText = attentionText;
      publishBtn.dataset.closingStyle = closingStyle;
    } else {
      publishBtn.style.display = 'none';
    }
  } else if (format === 'html') {
    container.innerHTML = exportResult.data.report;
    copyBtn.style.display = 'none';
    publishBtn.style.display = 'none';
  } else {
    container.innerHTML = `<pre>${exportResult.data.report}</pre>`;
    copyBtn.style.display = 'none';
    publishBtn.style.display = 'none';
  }
}

function copyExport() {
  const btn = document.getElementById('copyExportBtn');
  const plainText = btn.dataset.text;
  const htmlText = btn.dataset.html;
  if (!plainText) return;

  if (navigator.clipboard && navigator.clipboard.write) {
    // 同时写入纯文本和 HTML，粘贴到微信编辑器时自动使用 HTML 格式
    navigator.clipboard.write([
      new ClipboardItem({
        'text/plain': new Blob([plainText], {type: 'text/plain'}),
        'text/html': new Blob([htmlText], {type: 'text/html'})
      })
    ]).then(() => {
      const orig = btn.textContent;
      btn.textContent = '✅ 已复制（含格式）';
      setTimeout(() => { btn.textContent = orig; }, 2500);
    }).catch(() => {
      // Fallback to plain text only
      navigator.clipboard.writeText(plainText).then(() => {
        btn.textContent = '✅ 已复制（纯文本）';
        setTimeout(() => { btn.textContent = '一键复制（含格式）'; }, 2000);
      });
    });
  } else {
    // Fallback: select from a temporary textarea
    const ta = document.createElement('textarea');
    ta.value = plainText;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    const orig = btn.textContent;
    btn.textContent = '✅ 已复制';
    setTimeout(() => { btn.textContent = orig; }, 2000);
  }
}

async function publishToWeChat() {
  const btn = document.getElementById('publishBtn');
  btn.disabled = true;
  btn.textContent = '⏳ 发布中...';
  const resultDiv = document.getElementById('publishResult');
  resultDiv.style.display = 'block';
  resultDiv.innerHTML = '<p>正在发布到微信公众号草稿箱...</p>';

  try {
    const resp = await fetch('/api/news');
    const newsResult = await resp.json();
    if (!newsResult.success || !newsResult.data.length) {
      resultDiv.innerHTML = '<p style="color:red;">没有可发布的资讯</p>';
      return;
    }

    const publishResp = await fetch('/api/wechat/publish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        news_items: newsResult.data,
        attention_text: btn.dataset.attentionText || '',
        closing_style: btn.dataset.closingStyle || '0'
      })
    });
    const result = await publishResp.json();
    if (result.success) {
      resultDiv.innerHTML = `<p style="color:#07c160;">✅ 发布成功！草稿已保存到微信公众号后台「草稿箱」，media_id: ${result.data.media_id}</p>
        <p style="font-size:13px;color:#888;">前往 <a href="https://mp.weixin.qq.com/" target="_blank" rel="noreferrer">mp.weixin.qq.com</a> → 草稿箱 查看和发布</p>`;
    } else {
      resultDiv.innerHTML = `<p style="color:red;">❌ 发布失败: ${result.message}</p>`;
    }
  } catch (err) {
    resultDiv.innerHTML = `<p style="color:red;">❌ 发布异常: ${err.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '📤 一键发布到公众号';
  }
}

async function saveWechatConfig() {
  const appid = document.getElementById('wechatAppid').value.trim();
  const appsecret = document.getElementById('wechatSecret').value.trim();
  const name = document.getElementById('wechatName').value.trim();
  const statusEl = document.getElementById('wechatConfigStatus');

  const curResp = await fetch('/api/config');
  const curResult = await curResp.json();
  const wechat = appid || appsecret || name ? {appid, appsecret, name} : {};

  const saveResp = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      channels: (curResult.data && curResult.data.channels) || [],
      keywords: (curResult.data && curResult.data.keywords) || [],
      categories: (curResult.data && curResult.data.categories) || {},
      template: (curResult.data && curResult.data.template) || {},
      wechat
    })
  });
  const result = await saveResp.json();
  statusEl.textContent = result.success ? '✅ 已保存' : '❌ 保存失败';
  statusEl.style.color = result.success ? '#07c160' : '#dc3545';
  setTimeout(() => { statusEl.textContent = ''; }, 3000);
}

async function verifyChannels() {
  const channels = document.getElementById('channels').value.split('\n').map(x => x.trim()).filter(Boolean);
  const keywords = document.getElementById('keywords').value.split('\n').map(x => x.trim()).filter(Boolean);
  const container = document.getElementById('channelStatus');
  container.innerHTML = '<p>正在验证渠道连通性...</p>';
  console.log('verifyChannels start', {channels, keywords});
  try {
    const resp = await fetch('/api/channels/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({channel_urls: channels, keywords})
    });
    if (!resp.ok) {
      const errorText = await resp.text();
      console.error('verifyChannels HTTP error', resp.status, resp.statusText, errorText);
      container.innerHTML = `<p>验证失败：HTTP ${resp.status}</p>`;
      return;
    }
    const result = await resp.json();
    console.log('verifyChannels response', result);
    if (!result.success) {
      container.innerHTML = `<p>验证失败：${result.message || '未知错误'}</p>`;
      return;
    }
    const {summary, data} = result;
    let html = `<div style="margin-bottom:8px;">
      <span class="badge badge-pass">通过 ${summary.ok}</span>
      <span class="badge badge-weak">弱 ${summary.weak}</span>
      <span class="badge badge-fail">失败 ${summary.fail}</span>
      <span style="color:#888;font-size:12px;">共 ${summary.total} 个渠道</span>
    </div><ul style="list-style:none;padding:0;font-size:13px;">`;
    for (const ch of data) {
      let badge = 'badge-pass';
      let label = 'PASS';
      if (ch.status === 'weak') { badge = 'badge-weak'; label = 'WEAK'; }
      else if (ch.status === 'fail') { badge = 'badge-fail'; label = 'FAIL'; }
      const info = ch.message || ch.status;
      html += `<li style="padding:4px 0;border-bottom:1px solid #eee;">
        <span class="badge ${badge}" style="margin-right:8px;">${label}</span>
        <code style="font-size:12px;word-break:break-all;">${ch.url}</code>
        <span style="color:#666;margin-left:8px;font-size:12px;">${info}</span>
      </li>`;
    }
    html += '</ul>';
    container.innerHTML = html;
  } catch (error) {
    console.error('verifyChannels error', error);
    container.innerHTML = `<p>验证异常：${error.message || error}</p>`;
  }
}

async function resetDefaultConfig() {
  const resp = await fetch('/api/config');
  const result = await resp.json();
  if (!result.success) return;
  const defaults = {
    channels: [
      'https://cn.bing.com/search?q=园区无人车+园区自动驾驶&setlang=zh-Hans',
      'https://www.baidu.com/s?wd=园区无人车+园区自动驾驶&ie=utf-8',
      'https://www.thepaper.cn/tag/47646',
      'https://www.baidu.com/s?tn=news&rtt=1&bsst=1&wd=专业资讯+无人车&cl=2'
    ],
    keywords: [
      '无人驾驶','自动驾驶','园区无人车', '园区自动驾驶', '无人接驳车', '无人车巡检', '无人车配送',
      '无人环卫车', '低速无人车', '自动驾驶 园区', '无人配送车','无人出租车',
    ],
    categories: {
      '政策动态': ['政策', '新规', '补贴', '路测', '试点', '规范', '公告', '安全运营',
                  'regulation', 'policy', 'legislation', 'regulatory', 'permit', 'approval',
                  'certification', 'NHTSA', 'safety standard', 'government', 'legal', 'law'],
      '企业落地': ['园区', '上线', '合作', '签约', '落地', '投放', '运营', '项目',
                  'launch', 'deploy', 'partnership', 'rollout', 'commercial', 'pilot',
                  'investment', 'funding', 'service', 'delivery', 'operation'],
      '技术动态': ['传感器', '调度', '算法', '平台', '车路协同', '续航', '避障', 'AI',
                  'LiDAR', 'radar', 'computer vision', 'deep learning', 'perception',
                  'HD map', 'V2X', 'connectivity', 'chip', 'SoC', 'software', 'simulation',
                  'neural network', 'sensor', 'algorithm', 'transformer', 'OTA'],
      '招标采购': ['招标', '中标', '预算', '采购', '公告', '服务需求',
                  'tender', 'bid', 'procurement', 'contract', 'RFP', 'vendor', 'supplier'],
      '行业观点/海外资讯': ['专家', '趋势', '海外', '解读', '观点', '案例', '行业观察',
                      'analysis', 'opinion', 'report', 'forecast', 'market', 'research',
                      'insight', 'survey', 'outlook', 'trend']
    },
    rss_sources: []
  };
  document.getElementById('channels').value = defaults.channels.join('\n');
  document.getElementById('keywords').value = defaults.keywords.join('\n');
  document.getElementById('categories').value = categoriesToText(defaults.categories);
  document.getElementById('rssSources').value = defaults.rss_sources.join('\n');
  const saveResp = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(defaults)
  });
  const saveResult = await saveResp.json();
  alert(saveResult.success ? '已恢复默认配置并保存' : '保存失败');
}



async function verifyRssFeeds() {
  const btn = document.getElementById('verifyRssBtn');
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = '\u23f3 \u9a8c\u8bc1\u4e2d...';
  const container = document.getElementById('rssVerifyResult');
  container.innerHTML = '<p style="color:var(--text-dim);">\u6b63\u5728\u9a8c\u8bc1RSS\u6e90\u8fde\u901a\u6027...</p>';
  try {
    const urls = document.getElementById('rssSources').value.split('\n').filter(Boolean);
    if (!urls.length) { container.innerHTML = '<p>\u8bf7\u5148\u6dfb\u52a0RSS\u8ba2\u9605\u6e90URL\u3002</p>'; return; }
    const resp = await fetch('/api/rss/verify', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({urls})});
    const result = await resp.json();
    if (!result.success) { container.innerHTML = '<p>\u9a8c\u8bc1\u5931\u8d25\u3002</p>'; return; }
    var html = '<div style="margin-bottom:8px;"><span class="badge badge-pass">\u901a\u8fc7 ' + result.summary.ok + '</span> <span class="badge badge-fail">\u5931\u8d25 ' + result.summary.fail + '</span> <span style="color:var(--text-dim);font-size:12px;">\u5171 ' + result.summary.total + ' \u4e2a\u6e90</span></div><ul style="list-style:none;padding:0;font-size:13px;">';
    for (var i = 0; i < result.data.length; i++) {
      var feed = result.data[i];
      if (feed.status === 'ok') {
        html += '<li style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);"><span class="badge badge-pass" style="margin-right:8px;">PASS</span><strong>' + escapeHtml(feed.feed_title) + '</strong><span style="color:var(--text-dim);margin-left:6px;">' + feed.entry_count + ' \u6761</span><br/><code style="font-size:11px;color:var(--text-dim);word-break:break-all;">' + escapeHtml(feed.url) + '</code></li>';
      } else {
        html += '<li style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);"><span class="badge badge-fail" style="margin-right:8px;">FAIL</span><code style="font-size:12px;word-break:break-all;color:var(--text-muted);">' + escapeHtml(feed.url) + '</code><span style="color:#ff6b6b;margin-left:8px;font-size:12px;">' + escapeHtml(feed.error) + '</span></li>';
      }
    }
    html += '</ul>';
    container.innerHTML = html;
  } catch (err) { container.innerHTML = '<p>\u9a8c\u8bc1\u5f02\u5e38\uff1a' + err.message + '</p>';
  } finally { btn.disabled = false; btn.textContent = orig; }
}
async function deleteRssSource(url) {
  if (!confirm('确认删除此 RSS 源？\n' + url)) return;
  try {
    const resp = await fetch('/api/rss/remove', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url})});
    const result = await resp.json();
    if (!result.success) { alert(result.message || '删除失败'); return; }
    document.getElementById('rssSources').value = result.data.rss_sources.join('\n');
    document.getElementById('rssVerifyResult').innerHTML = '<p style="color:var(--text-dim);">已删除，可重新验证查看结果。</p>';
    alert('已删除');
  } catch (err) { alert('删除异常: ' + err.message); }
}

window.addEventListener('DOMContentLoaded', async () => {
  const config = await loadConfig();
  await showNewsList();

  // ── 通用 Sheet 切换 ──
  function switchSheetInWrapper(barId, sheetName) {
    const bar = document.getElementById(barId);
    bar.querySelectorAll('.sheet-btn').forEach(b => b.classList.remove('active'));
    const activeBtn = bar.querySelector(`.sheet-btn[data-sheet="${sheetName}"]`);
    if (activeBtn) activeBtn.classList.add('active');
    const wrapper = bar.closest('.sheet-wrapper');
    wrapper.querySelectorAll('.sheet-panel').forEach(p => p.classList.add('hidden'));
    const panel = wrapper.querySelector(`.sheet-panel[data-sheet="${sheetName}"]`);
    if (panel) panel.classList.remove('hidden');
  }

  function bindSheetBar(barId) {
    const bar = document.getElementById(barId);
    if (!bar) return;
    bar.addEventListener('click', e => {
      const btn = e.target.closest('.sheet-btn');
      if (btn) {
        e.preventDefault();
        switchSheetInWrapper(barId, btn.dataset.sheet);
      }
    });
  }

  bindSheetBar('sourceSheetBar');
  bindSheetBar('sheetBar');

  // ── 搜索（带防抖） ──
  const searchInput = document.getElementById('newsSearch');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', e => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => onNewsSearch(e), 250);
    });
  }
  // 同步保存的结尾话术
  if (config && config.template) {
    const cs = config.template.closing_selected;
    if (cs !== undefined) document.getElementById('closingStyle').value = String(cs);
  }
  // 加载微信配置
  if (config && config.wechat) {
    if (config.wechat.appid) document.getElementById('wechatAppid').value = config.wechat.appid;
    if (config.wechat.appsecret) document.getElementById('wechatSecret').value = config.wechat.appsecret;
    if (config.wechat.name) document.getElementById('wechatName').value = config.wechat.name;
  }
  document.getElementById('saveConfig').addEventListener('click', saveConfig);
  document.getElementById('verifyRssBtn').addEventListener('click', verifyRssFeeds);
  document.getElementById('crawlBtn').addEventListener('click', crawlNews);
  document.getElementById('refreshNewsBtn').addEventListener('click', showNewsList);
  document.getElementById('clearNewsBtn').addEventListener('click', clearNews);
  document.getElementById('loadHistoryBtn').addEventListener('click', loadHistory);
  document.getElementById('clearHistoryBtn').addEventListener('click', clearHistory);
  document.getElementById('addNewsBtn').addEventListener('click', addManualNews);
  document.getElementById('exportBtn').addEventListener('click', exportReport);
  document.getElementById('copyExportBtn').addEventListener('click', copyExport);
  document.getElementById('publishBtn').addEventListener('click', publishToWeChat);
  document.getElementById('saveWechatConfig').addEventListener('click', saveWechatConfig);
  document.getElementById('verifyChannelsBtn').addEventListener('click', verifyChannels);
  document.getElementById('resetDefaultChannelsBtn').addEventListener('click', resetDefaultConfig);
});
