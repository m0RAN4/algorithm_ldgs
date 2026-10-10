/* ============================================================
   系统概览页：知识库规模、使用统计、架构说明
   ============================================================ */

import { api, escapeHtml, emptyHtml, loadingHtml } from './api.js';

export async function init() {
  try {
    const stats = await api.get('/api/stats');
    renderStats(stats);
    renderHot('hot-facts', stats.hot_facts, (item) => item.fact_name,
      (item) => item.times + ' 次');
    renderHot('hot-rules', stats.hot_rules, (item) => item.rule_code + ' ' + item.rule_name,
      (item) => item.times + ' 次');
  } catch (err) {
    document.getElementById('stat-grid').innerHTML =
      '<div class="card"><div class="card-body">' +
      emptyHtml('统计加载失败', err.message) + '</div></div>';
  }

  try {
    const arch = await api.get('/api/architecture');
    renderArchitecture(arch);
  } catch (err) {
    document.getElementById('arch-body').innerHTML =
      emptyHtml('架构信息加载失败', err.message);
  }
}

function renderStats(stats) {
  const tiles = [
    ['规则总数', stats.rule_count, '其中启用 ' + stats.enabled_rule_count + ' 条'],
    ['事实总数', stats.fact_count, '用户输入 ' + stats.input_fact_count + ' 条'],
    ['算法主题', stats.topic_count, '挂在推荐结论上'],
    ['累计咨询', stats.consult_count, stats.last_consult_at
      ? '最近 ' + String(stats.last_consult_at).replace('T', ' ').slice(0, 16) : '暂无记录'],
  ];

  document.getElementById('stat-grid').innerHTML = tiles.map(([label, value, sub]) =>
    '<div class="stat-tile">' +
      '<div class="stat-num">' + value + '</div>' +
      '<div class="stat-label">' + escapeHtml(label) + '</div>' +
      '<div class="hint" style="margin-top:4px">' + escapeHtml(sub) + '</div>' +
    '</div>').join('') +
    (stats.readonly
      ? '<div class="stat-tile" style="border-color:#f2ddb6;background:#fdf9f1">' +
        '<div class="stat-num" style="font-size:16px">只读模式</div>' +
        '<div class="stat-label">当前使用内置文件知识库<br>不保存历史记录</div></div>'
      : '');
}

function renderHot(elementId, items, nameOf, valueOf) {
  const container = document.getElementById(elementId);
  if (!items || !items.length) {
    container.innerHTML = emptyHtml('暂无数据', '多跑几次咨询就会有统计了');
    return;
  }
  const max = Math.max(...items.map((i) => i.times));
  container.innerHTML = items.map((item) =>
    '<div style="margin-bottom:9px">' +
      '<div style="display:flex;gap:10px;align-items:baseline">' +
        '<span style="font-size:13px">' + escapeHtml(nameOf(item)) + '</span>' +
        '<div class="spacer"></div>' +
        '<span class="hint nowrap">' + escapeHtml(valueOf(item)) + '</span>' +
      '</div>' +
      '<div style="height:5px;background:#eef1f8;border-radius:3px;margin-top:5px">' +
        '<div style="height:100%;width:' + Math.round(item.times / max * 100) +
          '%;background:var(--accent);border-radius:3px"></div>' +
      '</div>' +
    '</div>').join('');
}

function renderArchitecture(arch) {
  const labels = {
    inference_engine: '推理机（backend/inference）',
    knowledge_base: '知识库（backend/knowledge）',
    composition_root: '组装层（backend/service）',
  };

  document.getElementById('arch-body').innerHTML = Object.entries(arch).map(([key, value]) =>
    '<div class="arch-block">' +
      '<h4>' + escapeHtml(labels[key] || key) + '</h4>' +
      '<ul>' + value.files.map((f) => '<li>' + escapeHtml(f) + '</li>').join('') +
        '<li style="color:var(--ok)">依赖：' + escapeHtml(value.depends_on) + '</li>' +
        (value.forbidden
          ? '<li style="color:var(--danger)">约束：' + escapeHtml(value.forbidden) + '</li>' : '') +
      '</ul>' +
    '</div>').join('') +
    '<p class="hint">推理机通过 <span class="mono">RuleProvider</span> 接口取得规则，' +
    '知识库负责实现该接口。两者只通过数据结构耦合，因此可以整体替换知识库' +
    '（MySQL ↔ 内置文件）而不改动推理机一行代码。</p>';
}
