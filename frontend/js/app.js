/* ============================================================
   入口：视图切换 + 各模块按需初始化
   ============================================================ */

import { api, escapeHtml, toast } from './api.js';

import * as consult from './consult.js';
import * as rules from './rules.js';
import * as facts from './facts.js';
import * as history from './history.js';
import * as stats from './stats.js';

const VIEWS = { consult, rules, facts, history, about: stats };
const started = new Set();

function switchView(name) {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.view === name);
  });
  document.querySelectorAll('.view').forEach((section) => {
    section.classList.toggle('active', section.id === 'view-' + name);
  });

  const module = VIEWS[name];
  if (module && !started.has(name)) {
    started.add(name);
    Promise.resolve(module.init()).catch((err) => {
      toast('页面初始化失败：' + err.message, 'err');
    });
  }
  location.hash = name;
}

document.getElementById('nav').addEventListener('click', (event) => {
  const button = event.target.closest('.nav-item');
  if (button) switchView(button.dataset.view);
});

/* ---------------------------------------------------------- 状态显示 */

async function refreshStatus() {
  const box = document.getElementById('side-status');
  try {
    const health = await api.get('/api/health');
    const db = health.database;
    const source = health.knowledge_source === 'file' ? '内置文件知识库' : 'MySQL';
    box.innerHTML =
      '<div><span class="dot ' + (db.ok ? 'ok' : 'bad') + '"></span> ' +
        escapeHtml(source) + '</div>' +
      '<div class="hint" style="color:#7c88a8">' + escapeHtml(
        db.ok ? shortDbMessage(db.message) : '数据库未连接') + '</div>';
  } catch (err) {
    box.innerHTML = '<div><span class="dot bad"></span> 服务不可用</div>';
  }
}

function shortDbMessage(message) {
  const match = /MySQL\s+([\d.]+)/.exec(message || '');
  return match ? 'MySQL ' + match[1] : (message || '');
}

/* ---------------------------------------------------------- 启动 */

const initial = (location.hash || '#consult').slice(1);
switchView(VIEWS[initial] ? initial : 'consult');

refreshStatus();
setInterval(refreshStatus, 30000);
