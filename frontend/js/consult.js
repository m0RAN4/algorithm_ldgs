/* ============================================================
   智能咨询页：勾选事实 -> 调用推理接口 -> 展示结论与推理轨迹
   ============================================================ */

import { api, escapeHtml, emptyHtml, loadingHtml, toast } from './api.js';

const state = {
  catalog: null,        // /api/catalog 返回的事实目录
  selected: new Set(),  // 已勾选的事实编码
  keyword: '',
};

const DEMO_FACTS = [
  'level_beginner', 'base_programming', 'ds_basic', 'goal_interview',
  'time_plenty', 'habit_practice',
];

/* ---------------------------------------------------------- 初始化 */

export async function init() {
  document.getElementById('fact-search')
    .addEventListener('input', (e) => {
      state.keyword = e.target.value.trim().toLowerCase();
      renderFactGroups();
    });

  document.getElementById('btn-clear-facts')
    .addEventListener('click', () => {
      state.selected.clear();
      renderFactGroups();
    });

  document.getElementById('btn-demo')
    .addEventListener('click', () => {
      state.selected = new Set(DEMO_FACTS);
      renderFactGroups();
      runInference();
    });

  document.getElementById('btn-run')
    .addEventListener('click', runInference);

  await loadCatalog();
}

async function loadCatalog() {
  try {
    state.catalog = await api.get('/api/catalog');
    renderFactGroups();
  } catch (err) {
    document.getElementById('fact-groups').innerHTML =
      emptyHtml('事实库加载失败', err.message);
  }
}

/* ---------------------------------------------------------- 条件选择 */

function renderFactGroups() {
  const container = document.getElementById('fact-groups');
  if (!state.catalog) return;

  const groups = state.catalog.input_categories
    .map((group) => ({ ...group,
      facts: group.facts.filter(matchesKeyword) }))
    .filter((group) => group.facts.length > 0);

  if (groups.length === 0) {
    container.innerHTML = emptyHtml('没有匹配的条件', '换个关键词试试');
    updateSelectedBar();
    return;
  }

  container.innerHTML = groups.map((group) =>
    '<div class="fact-group">' +
      '<div class="fact-group-title">' + escapeHtml(group.category_name) + '</div>' +
      '<div class="fact-list">' +
        group.facts.map((fact) =>
          '<button class="fact-opt' + (state.selected.has(fact.code) ? ' on' : '') +
            '" data-code="' + escapeHtml(fact.code) +
            '" title="' + escapeHtml(fact.description || fact.name) + '">' +
            escapeHtml(fact.name) + '</button>').join('') +
      '</div>' +
    '</div>').join('');

  container.querySelectorAll('.fact-opt').forEach((button) => {
    button.addEventListener('click', () => {
      const code = button.dataset.code;
      if (state.selected.has(code)) state.selected.delete(code);
      else state.selected.add(code);
      button.classList.toggle('on');
      updateSelectedBar();
    });
  });

  updateSelectedBar();
}

function matchesKeyword(fact) {
  if (!state.keyword) return true;
  return (fact.name + ' ' + fact.code + ' ' + (fact.description || ''))
    .toLowerCase().includes(state.keyword);
}

function updateSelectedBar() {
  document.getElementById('selected-count').textContent =
    '已选 ' + state.selected.size + ' 项';
  document.getElementById('btn-run').disabled = state.selected.size === 0;
}

/* ---------------------------------------------------------- 执行推理 */

async function runInference() {
  if (state.selected.size === 0) {
    toast('请至少选择一项条件', 'err');
    return;
  }

  const body = document.getElementById('result-body');
  body.innerHTML = loadingHtml('推理机正在匹配规则并消解冲突…');
  document.getElementById('trace-card').style.display = 'none';
  document.getElementById('result-meta').textContent = '';
  document.getElementById('btn-run').disabled = true;

  try {
    const result = await api.post('/api/consult', {
      fact_codes: Array.from(state.selected),
    });
    renderResult(result);
    await loadCatalog();   // 刷新一次，让新事实（如果被加过）也同步
  } catch (err) {
    body.innerHTML = emptyHtml('推理失败', err.message);
  } finally {
    document.getElementById('btn-run').disabled = state.selected.size === 0;
  }
}

function renderResult(result) {
  document.getElementById('result-meta').textContent =
    result.rounds + ' 轮推理 · ' + result.duration_ms + ' ms · 规则库 ' +
    result.rules_loaded + ' 条';

  const parts = [];

  parts.push(
    '<div class="result-summary">' +
      '<span class="chip ok">推理轮次 ' + result.rounds + '</span>' +
      '<span class="chip">载入规则 ' + result.rules_loaded + ' 条</span>' +
      '<span class="chip">输入事实 ' + result.input_facts.length + '</span>' +
      '<span class="chip">推出结论 ' + result.conclusions.length + '</span>' +
      (result.record_id ? '<span class="chip mute">已存为记录 #' +
        result.record_id + '</span>' : '') +
    '</div>');

  parts.push('<div class="card-body">');

  if (result.recommendations.length) {
    parts.push('<h3 class="card-title" style="margin-bottom:10px">按优先顺序建议学习</h3>');
    parts.push('<div class="rec-list">' + result.recommendations
      .map((item, index) => renderRecommendation(item, index + 1)).join('') + '</div>');
  } else if (result.conclusions.length === 0) {
    parts.push(emptyHtml('没有规则被触发', '试试多勾几项条件，或检查规则库'));
  }

  parts.push(renderChipsSection('学习路线', result.routes));
  parts.push(renderChipsSection('阶段判定', result.stages));
  parts.push(renderChipsSection('其他结论', result.advices));

  parts.push('<p class="hint" style="margin-top:16px">' + escapeHtml(result.message) + '</p>');
  parts.push('</div>');

  document.getElementById('result-body').innerHTML = parts.join('');
  renderTraces(result.traces);
}

function renderRecommendation(item, rank) {
  const topic = item.topic;
  let html = '<div class="rec-item">' +
    '<div class="rec-head">' +
      '<span class="rec-rank">' + String(rank).padStart(2, '0') + '</span>' +
      '<span class="rec-name">' + escapeHtml(stripPrefix(item.name)) + '</span>' +
      '<div class="spacer"></div>' +
      '<span class="chip mute">第 ' + item.round + ' 轮推出</span>' +
    '</div>';

  if (item.description) {
    html += '<div class="muted" style="margin-top:4px;font-size:13px">' +
      escapeHtml(item.description) + '</div>';
  }

  if (topic) {
    html += '<div class="rec-topic">' +
      '<div class="rec-meta">' +
        '<span class="chip warn">难度 ' + escapeHtml(topic.difficulty) + '</span>' +
        '<span class="chip">建议 ' + topic.estimated_hours + ' 学时</span>' +
      '</div>' +
      '<dl class="kv">' +
        '<dt>核心考点</dt><dd>' + escapeHtml(topic.core_points) + '</dd>' +
        '<dt>学习路径</dt><dd>' + escapeHtml(topic.learning_path) + '</dd>' +
        '<dt>典型题目</dt><dd>' + escapeHtml(topic.typical_problems) + '</dd>' +
      '</dl>' +
    '</div>';
  }

  return html + '</div>';
}

function stripPrefix(name) {
  return String(name).replace(/^(学习|优先学习|建议|推荐路线)：/, '');
}

function renderChipsSection(title, items) {
  if (!items || !items.length) return '';
  return '<h3 class="card-title" style="margin:18px 0 9px">' + escapeHtml(title) + '</h3>' +
    '<div class="fact-list">' + items.map((item) =>
      '<span class="chip">' + escapeHtml(item.name) + '</span>').join('') + '</div>';
}

/* ---------------------------------------------------------- 推理轨迹 */

function renderTraces(traces) {
  const card = document.getElementById('trace-card');
  const list = document.getElementById('trace-list');

  if (!traces || !traces.length) {
    card.style.display = 'none';
    return;
  }
  card.style.display = '';

  list.innerHTML = traces.map((trace) => {
    const conflictRows = trace.candidates.map((candidate) => {
      const isWinner = candidate.rule_code === trace.rule_code;
      return '<tr class="' + (isWinner ? 'win' : 'lose') + '">' +
        '<td class="mono">' + escapeHtml(candidate.rule_code) + '</td>' +
        '<td>' + escapeHtml(candidate.rule_name) + '</td>' +
        '<td>' + candidate.priority + '</td>' +
        '<td>' + candidate.condition_count + '</td>' +
        '<td>' + (isWinner ? '✔ 选中' : '✘ 淘汰') + '</td>' +
      '</tr>';
    }).join('');

    const rejectedList = trace.rejected.length
      ? '<div class="trace-line muted">淘汰原因：' + trace.rejected
          .slice(0, 6).map((r) => escapeHtml(r.rule_code + ' ' + r.detail)).join('；') +
          (trace.rejected.length > 6 ? ' …' : '') + '</div>'
      : '';

    return '<div class="trace-step is-resolved">' +
      '<div class="trace-dot"></div>' +
      '<div class="trace-head">' +
        '<span class="trace-round">第 ' + trace.round_no + ' 轮</span>' +
        '<span class="trace-rule">' + escapeHtml(trace.rule_code) + ' ' +
          escapeHtml(trace.rule_name) + '</span>' +
        '<span class="chip mute">优先级 ' + trace.priority + '</span>' +
        '<span class="chip ok">' + escapeHtml(strategyName(trace.strategy)) + '</span>' +
      '</div>' +
      '<div class="trace-body">' +
        '<div class="trace-line">匹配事实：' +
          (trace.matched_facts.map((f) => escapeHtml(f.name)).join(' ∧ ') || '（无）') +
        '</div>' +
        '<div class="trace-line">推出结论：' +
          '<b>' + trace.derived_facts.map((f) => escapeHtml(f.name)).join(' ∧ ') + '</b>' +
        '</div>' +
        '<div class="trace-line muted">' + escapeHtml(trace.resolution) + '</div>' +
        rejectedList +
        '<details class="trace-conflict">' +
          '<summary>冲突集：本轮共 ' + trace.candidate_count + ' 条规则同时被满足</summary>' +
          '<div class="trace-conflict-body">' +
            '<table class="mini-table"><thead><tr>' +
              '<th>编号</th><th>规则名称</th><th>优先级</th><th>条件数</th><th>结果</th>' +
            '</tr></thead><tbody>' + conflictRows + '</tbody></table>' +
          '</div>' +
        '</details>' +
      '</div>' +
    '</div>';
  }).join('');
}

function strategyName(strategy) {
  const names = {
    priority: '按优先级',
    specificity: '按专一性',
    recency: '按最近性',
    order: '按规则序号',
    single: '无冲突',
  };
  return names[strategy] || strategy;
}
