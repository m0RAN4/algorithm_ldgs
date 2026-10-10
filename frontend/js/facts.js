/* ============================================================
   事实字典页：查看推理机可用的全部原子命题
   ============================================================ */

import { api, escapeHtml, emptyHtml, loadingHtml } from './api.js';

let facts = [];

export async function init() {
  document.getElementById('fact-dict-search')
    .addEventListener('input', render);

  const tbody = document.getElementById('fact-tbody');
  tbody.innerHTML = '<tr><td colspan="5">' + loadingHtml('正在加载事实字典…') + '</td></tr>';

  try {
    const data = await api.get('/api/facts');
    facts = data.facts;
    render();
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5">' + emptyHtml('加载失败', err.message) + '</td></tr>';
  }
}

function render() {
  const keyword = document.getElementById('fact-dict-search').value.trim().toLowerCase();
  const rows = facts.filter((fact) => !keyword ||
    (fact.fact_name + ' ' + fact.fact_code + ' ' + (fact.description || ''))
      .toLowerCase().includes(keyword));

  document.getElementById('fact-count').textContent =
    '输入事实 ' + facts.filter((f) => f.fact_type === 'input').length +
    ' 条 · 结论事实 ' + facts.filter((f) => f.fact_type === 'derived').length + ' 条';

  const tbody = document.getElementById('fact-tbody');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="5">' + emptyHtml('没有匹配的事实') + '</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map((fact) =>
    '<tr>' +
      '<td class="mono">' + escapeHtml(fact.fact_code) + '</td>' +
      '<td>' + escapeHtml(fact.fact_name) + '</td>' +
      '<td><span class="chip">' + escapeHtml(fact.category_name || fact.category_code) +
        '</span></td>' +
      '<td>' + (fact.fact_type === 'input'
        ? '<span class="chip ok">输入</span>'
        : '<span class="chip warn">推导</span>') + '</td>' +
      '<td class="muted">' + escapeHtml(fact.description || '') + '</td>' +
    '</tr>').join('');
}
