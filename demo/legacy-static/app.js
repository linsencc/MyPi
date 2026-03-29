/**
 * 静态演示：仅用于 UI/交互评估，无持久化与真实接口。
 */
const UNITS = [
  {
    id: "u1",
    name: "早间天气卡片",
    typeKey: "image-weather",
    typeLabel: "图片生成 · 天气卡片",
    enabled: true,
    nextRefresh: "2026-03-29 08:05:00",
    lastStatus: { ok: true, text: "成功 · 1.2s" },
  },
  {
    id: "u2",
    name: "客厅月历",
    typeKey: "image-calendar",
    typeLabel: "图片生成 · 月历",
    enabled: true,
    nextRefresh: "2026-03-29 09:00:00",
    lastStatus: { ok: true, text: "成功 · 0.8s" },
  },
  {
    id: "u3",
    name: "水墨屏主输出",
    typeKey: "output-screen",
    typeLabel: "屏幕输出",
    enabled: true,
    nextRefresh: "—",
    lastStatus: { ok: false, text: "失败 · 尺寸校验" },
  },
  {
    id: "u4",
    name: "夜间 RSS（停用）",
    typeKey: "image-weather",
    typeLabel: "图片生成 · 天气卡片",
    enabled: false,
    nextRefresh: "—",
    lastStatus: { ok: true, text: "成功 · 2.0s" },
  },
];

const PARAM_SCHEMA = {
  "image-weather": [
    { key: "canvas_w", label: "画布宽度", type: "number", required: true, default: 800, min: 400, max: 1200, hint: "须匹配屏幕分辨率" },
    { key: "canvas_h", label: "画布高度", type: "number", required: true, default: 480, min: 300, max: 800 },
    { key: "theme", label: "主题", type: "enum", required: false, default: "light", options: ["light", "dark", "high-contrast"], hint: "枚举示例" },
    { key: "data_url", label: "数据来源地址", type: "string", required: true, default: "https://api.example/weather", hint: "字符串 · 必填" },
    { key: "dither", label: "启用抖动", type: "boolean", required: false, default: true },
  ],
  "image-calendar": [
    { key: "orientation", label: "方向", type: "enum", required: true, default: "landscape", options: ["landscape", "portrait"] },
    { key: "font_scale", label: "字体缩放", type: "number", required: false, default: 1, min: 0.8, max: 1.4, step: 0.1 },
    { key: "locale", label: "区域", type: "string", required: false, default: "zh-CN" },
  ],
  "output-screen": [
    { key: "device_path", label: "设备路径", type: "string", required: true, default: "/dev/epd0" },
    { key: "full_refresh_every", label: "每 N 次全刷", type: "number", required: true, default: 5, min: 1, max: 20, hint: "局刷/全刷策略" },
    { key: "dedupe", label: "相同内容去重", type: "boolean", required: false, default: true },
  ],
};

const RUN_LOGS = {
  u1: [
    { start: "2026-03-29 07:55:01", end: "2026-03-29 07:55:02", ms: 1200, ok: true, err: "", path: "/var/epd/out/weather_20260329_0755.png" },
    { start: "2026-03-29 07:25:00", end: "2026-03-29 07:25:01", ms: 980, ok: true, err: "", path: "/var/epd/out/weather_20260329_0725.png" },
  ],
  u2: [
    { start: "2026-03-29 07:00:00", end: "2026-03-29 07:00:01", ms: 810, ok: true, err: "", path: "/var/epd/out/cal_202603.png" },
  ],
  u3: [
    { start: "2026-03-29 06:58:12", end: "2026-03-29 06:58:12", ms: 320, ok: false, err: "校验失败：宽度 810 与设备 800 不一致", path: "—" },
  ],
  u4: [
    { start: "2026-03-28 22:00:00", end: "2026-03-28 22:00:02", ms: 2000, ok: true, err: "", path: "/var/epd/out/rss_20260328.png" },
  ],
};

let state = {
  filter: "all",
  editingId: null,
  isNew: false,
};

const tbody = document.getElementById("unit-tbody");
const drawer = document.getElementById("drawer");
const backdrop = document.getElementById("drawer-backdrop");
const fName = document.getElementById("f-name");
const fType = document.getElementById("f-type");
const fEnabled = document.getElementById("f-enabled");
const fRefreshMode = document.getElementById("f-refresh-mode");
const fInterval = document.getElementById("f-interval");
const dynamicParams = document.getElementById("dynamic-params");
const logList = document.getElementById("log-list");
const drawerTitle = document.getElementById("drawer-title");
const toast = document.getElementById("toast");

function showToast(msg) {
  toast.textContent = msg;
  toast.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toast.hidden = true;
  }, 2200);
}

function filteredUnits() {
  if (state.filter === "on") return UNITS.filter((u) => u.enabled);
  if (state.filter === "off") return UNITS.filter((u) => !u.enabled);
  return UNITS;
}

function renderTable() {
  const rows = filteredUnits();
  tbody.innerHTML = rows
    .map(
      (u) => `
    <tr data-id="${u.id}">
      <td><strong>${escapeHtml(u.name)}</strong></td>
      <td><span class="badge">${escapeHtml(u.typeLabel)}</span></td>
      <td><span class="badge ${u.enabled ? "badge-on" : "badge-off"}">${u.enabled ? "启用" : "停用"}</span></td>
      <td class="mono">${escapeHtml(u.nextRefresh)}</td>
      <td class="${u.lastStatus.ok ? "status-ok" : "status-err"}">${escapeHtml(u.lastStatus.text)}</td>
      <td class="cell-actions" onclick="event.stopPropagation()">
        <button type="button" class="btn btn-ghost btn-sm btn-edit" data-id="${u.id}">调整</button>
        <button type="button" class="btn btn-ghost btn-sm btn-toggle" data-id="${u.id}">${u.enabled ? "停用" : "启用"}</button>
        <button type="button" class="btn btn-ghost btn-sm btn-copy" data-id="${u.id}">复制</button>
        <button type="button" class="btn btn-ghost btn-sm btn-del" data-id="${u.id}">删除</button>
      </td>
    </tr>
  `
    )
    .join("");

  tbody.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => openDrawer(tr.dataset.id, false));
  });
  tbody.querySelectorAll(".btn-edit").forEach((b) => b.addEventListener("click", () => openDrawer(b.dataset.id, false)));
  tbody.querySelectorAll(".btn-toggle").forEach((b) =>
    b.addEventListener("click", () => {
      const u = UNITS.find((x) => x.id === b.dataset.id);
      if (u) {
        u.enabled = !u.enabled;
        showToast(u.enabled ? "好的，已开启" : "好的，先停一停");
        renderTable();
        updateChipCounts();
      }
    })
  );
  tbody.querySelectorAll(".btn-copy").forEach((b) =>
    b.addEventListener("click", () => {
      const u = UNITS.find((x) => x.id === b.dataset.id);
      if (!u) return;
      const copy = {
        ...u,
        id: "u" + Date.now(),
        name: u.name + "（副本）",
        enabled: false,
        nextRefresh: "—",
      };
      UNITS.push(copy);
      showToast("已多出一个副本");
      renderTable();
      updateChipCounts();
    })
  );
  tbody.querySelectorAll(".btn-del").forEach((b) =>
    b.addEventListener("click", () => {
      const idx = UNITS.findIndex((x) => x.id === b.dataset.id);
      if (idx >= 0) {
        UNITS.splice(idx, 1);
        showToast("这一条已移出列表");
        renderTable();
        updateChipCounts();
      }
    })
  );
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function updateChipCounts() {
  document.querySelector('.chip[data-filter="all"] .count').textContent = UNITS.length;
  document.querySelector('.chip[data-filter="on"] .count').textContent = UNITS.filter((u) => u.enabled).length;
  document.querySelector('.chip[data-filter="off"] .count').textContent = UNITS.filter((u) => !u.enabled).length;
}

function openDrawer(id, isNew) {
  if (!isNew) state.editingId = id;
  state.isNew = isNew;
  const u = isNew
    ? { name: "", typeKey: "image-weather", enabled: true, nextRefresh: "—", lastStatus: { ok: true, text: "—" } }
    : UNITS.find((x) => x.id === id);
  if (!u) return;

  drawerTitle.textContent = isNew ? "添一块新画面" : "轻轻改这一块";
  fName.value = u.name;
  fType.value = u.typeKey;
  fEnabled.checked = u.enabled;
  fRefreshMode.value = "interval";
  fInterval.value = 300;

  renderParams(u.typeKey);
  renderLogs(isNew ? null : id);

  backdrop.hidden = false;
  drawer.setAttribute("aria-hidden", "false");
  drawer.classList.add("open");
  switchTab("schedule");
}

function closeDrawer() {
  backdrop.hidden = true;
  drawer.setAttribute("aria-hidden", "true");
  drawer.classList.remove("open");
  state.editingId = null;
}

function renderParams(typeKey) {
  const defs = PARAM_SCHEMA[typeKey] || [];
  dynamicParams.innerHTML = defs
    .map((d) => {
      const id = `param-${d.key}`;
      let input = "";
      if (d.type === "enum") {
        input = `<select class="input" id="${id}" data-key="${d.key}">${d.options.map((o) => `<option value="${o}" ${o === d.default ? "selected" : ""}>${o}</option>`).join("")}</select>`;
      } else if (d.type === "boolean") {
        input = `<label class="switch-wrap" style="margin-top:0.25rem"><input type="checkbox" class="switch" id="${id}" data-key="${d.key}" ${d.default ? "checked" : ""} /><span class="switch-ui"></span></label>`;
      } else if (d.type === "number") {
        const step = d.step != null ? ` step="${d.step}"` : "";
        input = `<input type="number" class="input mono" id="${id}" data-key="${d.key}" value="${d.default}" min="${d.min ?? ""}" max="${d.max ?? ""}"${step} />`;
      } else {
        input = `<input type="text" class="input mono" id="${id}" data-key="${d.key}" value="${escapeAttr(String(d.default))}" />`;
      }
      const req = d.required ? "（必填）" : "";
      return `<div class="field full">
        <span class="label">${escapeHtml(d.label)}${req}</span>
        ${input}
        ${d.hint ? `<p class="param-hint">${escapeHtml(d.hint)}</p>` : ""}
      </div>`;
    })
    .join("");
}

function escapeAttr(s) {
  return s.replace(/"/g, "&quot;");
}

function renderLogs(unitId) {
  const logs = RUN_LOGS[unitId] || [
    { start: "—", end: "—", ms: 0, ok: true, err: "", path: "尚无记录" },
  ];
  logList.innerHTML = logs
    .map(
      (l) => `
    <li class="log-item ${l.ok ? "" : "err"}">
      <div class="log-meta">
        <span>开始 ${escapeHtml(l.start)}</span>
        <span>结束 ${escapeHtml(l.end)}</span>
        <span>耗时 ${l.ms} ms</span>
        <span>${l.ok ? "成功" : "失败"}</span>
      </div>
      ${l.err ? `<div class="status-err">${escapeHtml(l.err)}</div>` : ""}
      <div class="log-path">输出：${escapeHtml(l.path)}</div>
    </li>
  `
    )
    .join("");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.tab === name;
    t.classList.toggle("tab-active", on);
    t.setAttribute("aria-selected", on);
  });
  document.getElementById("panel-schedule").classList.toggle("hidden", name !== "schedule");
  document.getElementById("panel-schedule").hidden = name !== "schedule";
  document.getElementById("panel-params").classList.toggle("hidden", name !== "params");
  document.getElementById("panel-params").hidden = name !== "params";
  document.getElementById("panel-logs").classList.toggle("hidden", name !== "logs");
  document.getElementById("panel-logs").hidden = name !== "logs";
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));

document.getElementById("drawer-close").addEventListener("click", closeDrawer);
document.getElementById("btn-cancel").addEventListener("click", closeDrawer);
backdrop.addEventListener("click", closeDrawer);

document.getElementById("btn-add-unit").addEventListener("click", () => {
  state.editingId = "new-" + Date.now();
  openDrawer(state.editingId, true);
});

document.getElementById("btn-save").addEventListener("click", () => {
  const name = fName.value.trim() || "未命名单元";
  const typeKey = fType.value;
  const typeOpt = fType.options[fType.selectedIndex];
  const typeLabel = typeOpt ? typeOpt.text : typeKey;

  if (state.isNew) {
    UNITS.push({
      id: "u" + Date.now(),
      name,
      typeKey,
      typeLabel,
      enabled: fEnabled.checked,
      nextRefresh: fEnabled.checked && fRefreshMode.value === "interval" ? "计算中…" : "—",
      lastStatus: { ok: true, text: "尚未执行" },
    });
    showToast("新画面已记下");
  } else {
    const u = UNITS.find((x) => x.id === state.editingId);
    if (u) {
      u.name = name;
      u.typeKey = typeKey;
      u.typeLabel = typeLabel;
      u.enabled = fEnabled.checked;
    }
    showToast("改动已记下");
  }
  renderTable();
  updateChipCounts();
  closeDrawer();
});

document.getElementById("btn-copy-unit").addEventListener("click", () => {
  if (!state.editingId || state.isNew) {
    showToast("请先保存，再在列表里复制");
    return;
  }
  const u = UNITS.find((x) => x.id === state.editingId);
  if (!u) return;
  UNITS.push({
    ...u,
    id: "u" + Date.now(),
    name: u.name + "（副本）",
    enabled: false,
    nextRefresh: "—",
  });
  showToast("副本已加到列表");
  renderTable();
  updateChipCounts();
});

document.querySelectorAll(".chip").forEach((c) =>
  c.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((x) => x.classList.remove("chip-active"));
    c.classList.add("chip-active");
    state.filter = c.dataset.filter;
    renderTable();
  })
);

const modalBackdrop = document.getElementById("modal-backdrop");
const modal = document.getElementById("modal-constraints");

function openModal() {
  modalBackdrop.hidden = false;
  modal.hidden = false;
}

function closeModal() {
  modalBackdrop.hidden = true;
  modal.hidden = true;
}

document.getElementById("btn-help").addEventListener("click", openModal);
document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-ok").addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", closeModal);

fType.addEventListener("change", () => renderParams(fType.value));

updateChipCounts();
renderTable();
