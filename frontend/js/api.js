/* ============================================================
   API 封装 + 通用 UI 工具
   ============================================================ */

async function request(method, path, body) {
  const options = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) options.body = JSON.stringify(body);

  let response;
  try {
    response = await fetch(path, options);
  } catch (err) {
    throw new Error('无法连接服务，请确认 python app.py 仍在运行');
  }

  let payload;
  try {
    payload = await response.json();
  } catch (err) {
    throw new Error('服务返回了非 JSON 内容（HTTP ' + response.status + '）');
  }

  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || ('请求失败（HTTP ' + response.status + '）'));
  }
  return payload.data;
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  del: (path) => request('DELETE', path),
};

/* ---------------------------------------------------------- 提示条 */

let toastTimer = null;

export function toast(message, kind = '') {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.className = 'show ' + kind;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = kind; }, 2600);
}

/* ---------------------------------------------------------- 工具 */

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export function loadingHtml(text) {
  return '<div class="loading"><span class="spin"></span>' + escapeHtml(text) + '</div>';
}

export function emptyHtml(title, hint) {
  return '<div class="empty"><div class="empty-icon">◷</div>' + escapeHtml(title) +
    (hint ? '<div class="hint" style="margin-top:6px">' + escapeHtml(hint) + '</div>' : '') +
    '</div>';
}

export function fmtTime(value) {
  if (!value) return '—';
  return String(value).replace('T', ' ').slice(0, 19);
}

/* ---------------------------------------------------------- 模态框 */

export function openModal({ title, bodyHtml, footerHtml = '', narrow = false,
                            onMount }) {
  const root = document.getElementById('modal-root');
  root.innerHTML =
    '<div class="modal-mask"><div class="modal' + (narrow ? ' narrow' : '') + '">' +
      '<div class="modal-head"><h3 class="modal-title">' + escapeHtml(title) + '</h3>' +
        '<div class="spacer"></div>' +
        '<button class="btn sm" data-close>关闭</button></div>' +
      '<div class="modal-body">' + bodyHtml + '</div>' +
      (footerHtml ? '<div class="modal-foot">' + footerHtml + '</div>' : '') +
    '</div></div>';

  const mask = root.querySelector('.modal-mask');
  const close = () => { root.innerHTML = ''; document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };

  mask.addEventListener('click', (e) => { if (e.target === mask) close(); });
  root.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', close));
  document.addEventListener('keydown', onKey);

  if (onMount) onMount(root, close);
  return close;
}
