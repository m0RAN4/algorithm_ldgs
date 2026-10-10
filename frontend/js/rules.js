/* ============================================================
   规则库管理页：规则的增删改查
   对应实验要求第 5 条——不改推理机即可修改知识库
   ============================================================ */

import { api, escapeHtml, emptyHtml, loadingHtml, openModal, toast } from './api.js';

let allFacts = [];     // 事实字典（供规则编辑器选择）
let currentRules = [];

export async function init() {
  document.getElementById('btn-rule-reload')
    .addEventListener('click', () => loadRules());
  document.getElementById('btn-rule-search')
    .addEventListener('click', () => loadRules());
  document.getElementById('rule-search')
    .addEventListener('keydown', (e) => { if (e.key === 'Enter') loadRules(); });
  document.getElementById('btn-rule-add')
    .addEventListener('click', () => openRuleEditor(null));

  await loadFacts();
  await loadRules();
}

async function loadFacts() {
  try {
    const data = await api.get('/api/facts');
    allFacts = data.facts;
  } catch (err) {
    allFacts = [];
  }
}

async function loadRules() {
  const tbody = document.getElementById('rule-tbody');
  tbody.innerHTML = '<tr><td colspan="7">' + loadingHtml('正在加载规则库…') + '</td></tr>';
  try {
    const keyword = document.getElementById('rule-search').value.trim();
    const rules = await api.get('/api/rules?keyword=' + encodeURIComponent(keyword));
    currentRules = rules;
    renderRules(rules);
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="7">' + emptyHtml('加载失败', err.message) + '</td></tr>';
  }
}

function renderRules(rules) {
  const tbody = document.getElementById('rule-tbody');
  document.getElementById('rule-count').textContent = '共 ' + rules.length + ' 条规则';

  if (!rules.length) {
    tbody.innerHTML = '<tr><td colspan="7">' + emptyHtml('没有匹配的规则') + '</td></tr>';
    return;
  }

  tbody.innerHTML = rules.map((rule) =>
    '<tr>' +
      '<td class="mono nowrap">' + escapeHtml(rule.rule_code) + '</td>' +
      '<td>' + escapeHtml(rule.rule_name) +
        (rule.description ? '<div class="hint">' + escapeHtml(rule.description) + '</div>' : '') +
      '</td>' +
      '<td class="mono">' + rule.priority + '</td>' +
      '<td>' + escapeHtml(rule.condition_text) + '</td>' +
      '<td>' + escapeHtml(rule.conclusion_text) + '</td>' +
      '<td>' + (rule.is_enabled
        ? '<span class="chip ok">启用</span>'
        : '<span class="chip mute">停用</span>') + '</td>' +
      '<td class="nowrap">' +
        '<button class="btn sm" data-act="toggle" data-id="' + rule.rule_id + '">' +
          (rule.is_enabled ? '停用' : '启用') + '</button> ' +
        '<button class="btn sm" data-act="edit" data-id="' + rule.rule_id + '">编辑</button> ' +
        '<button class="btn sm danger" data-act="del" data-id="' + rule.rule_id + '">删除</button>' +
      '</td>' +
    '</tr>').join('');

  tbody.querySelectorAll('button[data-act]').forEach((button) => {
    button.addEventListener('click', () => handleAction(button.dataset.act,
      Number(button.dataset.id)));
  });
}

async function handleAction(action, ruleId) {
  const rule = currentRules.find((r) => r.rule_id === ruleId);
  if (!rule) return;

  if (action === 'edit') {
    openRuleEditor(rule);
    return;
  }

  if (action === 'toggle') {
    try {
      await api.post('/api/rules/' + ruleId + '/toggle', { is_enabled: !rule.is_enabled });
      toast('规则 ' + rule.rule_code + (rule.is_enabled ? ' 已停用' : ' 已启用'), 'ok');
      loadRules();
    } catch (err) {
      toast(err.message, 'err');
    }
    return;
  }

  if (action === 'del') {
    openModal({
      title: '删除规则',
      narrow: true,
      bodyHtml: '<p>确定要删除规则 <b>' + escapeHtml(rule.rule_code) + ' ' +
        escapeHtml(rule.rule_name) + '</b> 吗？</p>' +
        '<p class="muted">删除后规则库立即生效，下一次推理就不会再用到它。</p>',
      footerHtml: '<button class="btn" data-close>取消</button>' +
        '<button class="btn danger" id="confirm-del">确认删除</button>',
      onMount(root, close) {
        root.querySelector('#confirm-del').addEventListener('click', async () => {
          try {
            await api.del('/api/rules/' + ruleId);
            close();
            toast('规则已删除', 'ok');
            loadRules();
          } catch (err) {
            toast(err.message, 'err');
          }
        });
      },
    });
  }
}

/* ---------------------------------------------------------- 规则编辑器 */

function openRuleEditor(rule) {
  const isEdit = Boolean(rule);
  const conditions = new Map();   // fact_code -> is_negate
  const conclusions = new Set();

  if (isEdit) {
    rule.conditions.forEach((c) => conditions.set(c.fact_code, c.is_negate));
    rule.conclusions.forEach((c) => conclusions.add(c));
  }

  const inputFacts = allFacts.filter((f) => f.fact_type === 'input');
  const derivedFacts = allFacts.filter((f) => f.fact_type === 'derived');

  const body =
    '<div class="form-grid">' +
      '<div class="form-row"><label>规则编号</label>' +
        '<input class="input" id="f-code" value="' +
          escapeHtml(rule ? rule.rule_code : '(自动生成)') + '"' +
          (isEdit ? ' readonly' : '') + '></div>' +
      '<div class="form-row"><label>优先级（数值越大越优先）</label>' +
        '<input class="input" id="f-priority" type="number" min="0" max="9999" value="' +
          (rule ? rule.priority : 50) + '"></div>' +
    '</div>' +
    '<div class="form-row"><label>规则名称</label>' +
      '<input class="input" id="f-name" value="' + escapeHtml(rule ? rule.rule_name : '') +
      '" placeholder="例如：面试高频——动态规划"></div>' +
    '<div class="form-row"><label>说明（可选）</label>' +
      '<input class="input" id="f-desc" value="' +
        escapeHtml(rule ? rule.description : '') + '"></div>' +

    '<div class="form-row"><label>IF 前件（点击切换：未选 → 选中 → 取反"非"）</label>' +
      '<div class="picker" id="cond-picker">' + renderPicker(inputFacts) + '</div>' +
      '<div class="selected-preview" id="cond-preview"></div></div>' +

    '<div class="form-row"><label>THEN 后件（可多选）</label>' +
      '<div class="picker" id="conc-picker">' + renderPicker(derivedFacts) + '</div>' +
      '<div class="selected-preview" id="conc-preview"></div></div>' +

    '<div class="form-row"><label><input type="checkbox" id="f-enabled"' +
      (rule && !rule.is_enabled ? '' : ' checked') + '> 启用该规则</label></div>';

  openModal({
    title: isEdit ? '编辑规则 ' + rule.rule_code : '新增规则',
    bodyHtml: body,
    footerHtml: '<button class="btn" data-close>取消</button>' +
      '<button class="btn primary" id="save-rule">保存</button>',
    onMount(root, close) {
      bindPicker(root.querySelector('#cond-picker'), conditions, true);
      bindPicker(root.querySelector('#conc-picker'), conclusions, false);

      //新增时把下一个可用编号查出来填上，比"(自动生成)"占位符明确；
      //查不到就保留占位符，后端也会自动生成一个
      if (!isEdit) {
        api.get('/api/rules/next-code').then((data) => {
          const input = root.querySelector('#f-code');
          if (input && input.value.trim() === '(自动生成)') {
            input.value = data.rule_code;
          }
        }).catch(() => {});
      }

      const refresh = () => {
        root.querySelector('#cond-preview').innerHTML = conditions.size
          ? Array.from(conditions.entries()).map(([code, negate]) => {
              const fact = allFacts.find((f) => f.fact_code === code);
              return '<span class="chip' + (negate ? ' warn' : '') + '">' +
                (negate ? '非 ' : '') + escapeHtml(fact ? fact.fact_name : code) + '</span>';
            }).join(' ')
          : '<span class="muted">至少选择一个条件</span>';
        root.querySelector('#conc-preview').innerHTML = conclusions.size
          ? Array.from(conclusions).map((code) => {
              const fact = allFacts.find((f) => f.fact_code === code);
              return '<span class="chip ok">' +
                escapeHtml(fact ? fact.fact_name : code) + '</span>';
            }).join(' ')
          : '<span class="muted">至少选择一个结论</span>';
      };

      root.querySelector('#cond-picker').addEventListener('pick-change', refresh);
      root.querySelector('#conc-picker').addEventListener('pick-change', refresh);
      refresh();

      root.querySelector('#save-rule').addEventListener('click', async () => {
        const payload = {
          rule_code: isEdit ? rule.rule_code
            : (root.querySelector('#f-code').value.trim().replace('(自动生成)', '') || ''),
          rule_name: root.querySelector('#f-name').value.trim(),
          priority: Number(root.querySelector('#f-priority').value || 0),
          description: root.querySelector('#f-desc').value.trim(),
          is_enabled: root.querySelector('#f-enabled').checked,
          conditions: Array.from(conditions.entries())
            .map(([fact_code, is_negate]) => ({ fact_code, is_negate })),
          conclusions: Array.from(conclusions),
        };

        if (!payload.rule_code) delete payload.rule_code;

        const button = root.querySelector('#save-rule');
        button.disabled = true;
        button.textContent = '保存中…';
        try {
          const saved = isEdit
            ? await api.put('/api/rules/' + rule.rule_id, payload)
            : await api.post('/api/rules', payload);
          close();
          //把最终使用的编号显示出来，自动生成的时候用户也能看到是哪个
          toast('规则 ' + saved.rule_code + ' 已保存，下一次推理立即生效', 'ok');
          loadRules();
        } catch (err) {
          toast(err.message, 'err');
          button.disabled = false;
          button.textContent = '保存';
        }
      });
    },
  });
}

function renderPicker(facts) {
  const groups = new Map();
  facts.forEach((fact) => {
    const key = fact.category_name || fact.category_code;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(fact);
  });

  return Array.from(groups.entries()).map(([name, items]) =>
    '<div class="picker-group">' +
      '<div class="picker-label">' + escapeHtml(name) + '</div>' +
      '<div class="picker-items">' + items.map((fact) =>
        '<button type="button" class="pick-chip" data-code="' + escapeHtml(fact.fact_code) +
        '" data-label="' + escapeHtml(fact.fact_name) +
        '" title="' + escapeHtml(fact.description || '') + '">' +
        escapeHtml(fact.fact_name) + '</button>').join('') + '</div>' +
    '</div>').join('');
}

/**
 * 绑定选择器。三态：未选 -> 选中 -> 取反（仅前件支持） -> 未选
 */
function bindPicker(container, store, allowNegate) {
  const refresh = () => {
    container.querySelectorAll('.pick-chip').forEach((chip) => {
      const code = chip.dataset.code;
      const base = chip.dataset.label;   // 基础名称，避免反复剥前缀
      chip.classList.remove('on', 'neg');
      if (!store.has(code)) {
        chip.textContent = base;
        return;
      }
      if (allowNegate && store.get(code)) {
        chip.classList.add('neg', 'on');
        chip.textContent = '非 ' + base;
      } else {
        chip.classList.add('on');
        chip.textContent = base;
      }
    });
  };

  container.querySelectorAll('.pick-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const code = chip.dataset.code;
      if (!store.has(code)) {
        store.set ? store.set(code, false) : store.add(code);
      } else if (allowNegate && !store.get(code)) {
        store.set(code, true);
      } else {
        store.delete(code);
      }
      refresh();
      container.dispatchEvent(new Event('pick-change'));
    });
  });
  refresh();
}
