/* ============================================================
   咨询记录页：回看历史推理
   ============================================================ */

import { api, escapeHtml, emptyHtml, fmtTime, loadingHtml, openModal, toast } from './api.js';

export async function init() {
  document.getElementById('btn-history-reload')
    .addEventListener('click', load);
  await load();
}

async function load() {
  const tbody = document.getElementById('history-tbody');
  tbody.innerHTML = '<tr><td colspan="8">' + loadingHtml('正在加载记录…') + '</td></tr>';
  try {
    const data = await api.get('/api/consults?limit=100');
    render(data.records);
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="8">' + emptyHtml('加载失败', err.message) + '</td></tr>';
  }
}

function render(records) {
  const tbody = document.getElementById('history-tbody');
  if (!records.length) {
    tbody.innerHTML = '<tr><td colspan="8">' +
      emptyHtml('还没有咨询记录', '去「智能咨询」跑一次推理就会在这里留下记录') + '</td></tr>';
    return;
  }

  tbody.innerHTML = records.map((record, index) =>
    '<tr>' +
      '<td class="muted">' + (index + 1) + '</td>' +
      '<td class="mono">' + escapeHtml(record.session_no) + '</td>' +
      '<td>' + record.input_count + '</td>' +
      '<td>' + record.conclusion_count + '</td>' +
      '<td>' + record.round_count + '</td>' +
      '<td class="nowrap">' + record.duration_ms + ' ms</td>' +
      '<td class="nowrap muted">' + fmtTime(record.created_at) + '</td>' +
      '<td class="nowrap">' +
        '<button class="btn sm" data-act="view" data-id="' + record.record_id + '">详情</button> ' +
        '<button class="btn sm danger" data-act="del" data-id="' + record.record_id + '">删除</button>' +
      '</td>' +
    '</tr>').join('');

  tbody.querySelectorAll('button[data-act]').forEach((button) => {
    const id = Number(button.dataset.id);
    if (button.dataset.act === 'view') {
      button.addEventListener('click', () => openDetail(id));
    } else {
      button.addEventListener('click', () => remove(id));
    }
  });
}

async function remove(recordId) {
  try {
    await api.del('/api/consults/' + recordId);
    toast('记录已删除', 'ok');
    load();
  } catch (err) {
    toast(err.message, 'err');
  }
}

async function openDetail(recordId) {
  let record;
  try {
    record = await api.get('/api/consults/' + recordId);
  } catch (err) {
    toast(err.message, 'err');
    return;
  }

  const inputs = record.facts.filter((f) => f.fact_role === 'input');
  const derived = record.facts.filter((f) => f.fact_role === 'derived');

  const body =
    '<div class="result-summary" style="border-radius:10px;margin-bottom:16px">' +
      '<span class="chip ok">' + escapeHtml(record.session_no) + '</span>' +
      '<span class="chip">' + record.round_count + ' 轮推理</span>' +
      '<span class="chip">' + record.duration_ms + ' ms</span>' +
      '<span class="chip">载入规则 ' + record.rules_loaded + ' 条</span>' +
      '<span class="chip mute">' + fmtTime(record.created_at) + '</span>' +
    '</div>' +

    section('输入的条件事实', inputs.map((f) => f.fact_name)) +
    section('推出的结论（按顺序）', derived.map((f) => f.fact_name)) +

    '<h3 class="card-title" style="margin:18px 0 10px">推理轨迹</h3>' +
    '<div class="trace-timeline">' + record.traces.map((trace) =>
      '<div class="trace-step is-resolved"><div class="trace-dot"></div>' +
        '<div class="trace-head">' +
          '<span class="trace-round">第 ' + trace.round_no + ' 轮</span>' +
          '<span class="trace-rule">' + escapeHtml(trace.rule_code) + ' ' +
            escapeHtml(trace.rule_name) + '</span>' +
          '<span class="chip mute">优先级 ' + trace.priority + '</span>' +
        '</div>' +
        '<div class="trace-body">' +
          '<div class="trace-line">匹配事实：' +
            (trace.matched_facts.map((f) => escapeHtml(f.name || f)).join(' ∧ ') || '（无）') +
          '</div>' +
          '<div class="trace-line">推出结论：<b>' +
            trace.derived_facts.map((f) => escapeHtml(f.name || f)).join(' ∧ ') + '</b></div>' +
          '<div class="trace-line muted">' + escapeHtml(trace.resolution) + '</div>' +
          '<div class="trace-line muted">冲突集 ' + trace.candidate_count + ' 条规则</div>' +
        '</div>' +
      '</div>').join('') + '</div>';

  openModal({ title: '咨询详情', bodyHtml: body });
}

function section(title, names) {
  if (!names.length) return '';
  return '<h3 class="card-title" style="margin:0 0 9px">' + escapeHtml(title) +
    ' <span class="muted" style="font-weight:400">（' + names.length + '）</span></h3>' +
    '<div class="fact-list" style="margin-bottom:16px">' +
    names.map((name) => '<span class="chip">' + escapeHtml(name) + '</span>').join('') +
    '</div>';
}
