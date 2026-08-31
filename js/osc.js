// Open-source comments — table, column popover, project record and the
// interactive star chart. Plain script, no build step, no dependencies.
(function () {
'use strict';

var lib = window.oscLib;

var KEYS = window.col_keys || [];
var COLS = window.cols || [];
var RAW = window.osc_data || [];
var HISTORY = window.osc_history || {};
var HISTORY_RANGE = window.osc_history_range || null;
var HISTORY_DEFAULT = window.osc_history_default || [];

var EM_DASH = '—';

/* ── small DOM helpers ─────────────────────────────────────────────── */

function el(tag, attrs, children) {
  var node = document.createElement(tag);
  applyAttrs(node, attrs);
  append(node, children);
  return node;
}

var SVG_NS = 'http://www.w3.org/2000/svg';

function svg(tag, attrs, children) {
  var node = document.createElementNS(SVG_NS, tag);
  applyAttrs(node, attrs);
  append(node, children);
  return node;
}

function applyAttrs(node, attrs) {
  if (!attrs) return;
  Object.keys(attrs).forEach(function (name) {
    var value = attrs[name];
    if (value == null || value === false) return;
    if (name === 'text') node.textContent = value;
    else if (name === 'class') node.setAttribute('class', value);
    else if (name.indexOf('on') === 0) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value);
  });
}

function append(node, children) {
  if (children == null) return;
  (Array.isArray(children) ? children : [children]).forEach(function (child) {
    if (child == null || child === false) return;
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  });
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function pct(value, total) {
  return ((value / total) * 100).toFixed(3) + '%';
}

// Lucide, inlined: no icon font, no sprite.
function icon(name, size) {
  var paths = {
    x: ['<path d="M18 6 6 18M6 6l12 12"></path>', 'none'],
    external: ['<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>', 'none'],
    lock: ['<rect x="3" y="11" width="18" height="11"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path>', 'none'],
    // Sort indicators. Archivo has no ↕ glyph, so all three are drawn rather
    // than set in type — one fallback font in the header would be visible.
    'sort-none': ['<path d="m7 15 5 5 5-5M7 9l5-5 5 5"></path>', 'none'],
    'sort-desc': ['<path d="M12 5v14M19 12l-7 7-7-7"></path>', 'none'],
    'sort-asc': ['<path d="M12 19V5M5 12l7-7 7 7"></path>', 'none'],
  };
  var spec = paths[name];
  var node = svg('svg', {
    width: size || 16,
    height: size || 16,
    viewBox: '0 0 24 24',
    fill: spec[1] === 'fill' ? 'currentColor' : 'none',
    stroke: spec[1] === 'fill' ? 'none' : 'currentColor',
    'stroke-width': spec[1] === 'fill' ? null : 2.2,
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    'aria-hidden': 'true',
  });
  node.innerHTML = spec[0];
  return node;
}

/* ── data ──────────────────────────────────────────────────────────── */

var scratch = document.createElement('div');

// data.js ships each cell as the HTML the build generated from data.yaml.
// Parse it once here so the page keeps data.yaml as its single source of truth.
function parseCell(html) {
  scratch.innerHTML = html == null ? '' : String(html);
  var parts = [];
  var rich = false;

  (function walk(node, href, struck) {
    for (var child = node.firstChild; child; child = child.nextSibling) {
      if (child.nodeType === 3) {
        if (child.nodeValue) parts.push({ v: child.nodeValue, h: href, s: struck });
      } else if (child.nodeType === 1) {
        var tag = child.tagName.toLowerCase();
        if (tag === 'a') {
          rich = true;
          walk(child, child.getAttribute('href'), struck);
        } else if (tag === 's' || tag === 'del' || tag === 'strike') {
          rich = true;
          walk(child, href, true);
        } else {
          walk(child, href, struck);
        }
      }
    }
  })(scratch, null, false);

  return {
    text: scratch.textContent.replace(/\s+/g, ' ').trim(),
    parts: rich ? parts : [],
    marker: scratch.querySelector('.stars-with-extra'),
  };
}

function buildRows() {
  return RAW.map(function (cells, index) {
    var row = { index: index, fields: {}, parts: {} };
    KEYS.forEach(function (key, i) {
      var cell = parseCell(cells[i]);
      row.fields[key] = cell.text;
      if (cell.parts.length) row.parts[key] = cell.parts;
      if (key === 'stars') {
        row.starsAsterisk = !!cell.marker;
        row.starsTitle = cell.marker ? cell.marker.getAttribute('title') || '' : '';
      }
    });
    row.name = row.fields.name || '';
    row.starsNum = parseInt(row.fields.stars, 10);
    if (!isFinite(row.starsNum)) row.starsNum = -1;
    row.difNum = parseInt(row.fields.stars_dif, 10);
    if (!isFinite(row.difNum)) row.difNum = 0;
    return row;
  });
}

var rows = buildRows();
var colTitle = {};
KEYS.forEach(function (key, i) { colTitle[key] = (COLS[i] && COLS[i].title) || key; });

/* ── state ─────────────────────────────────────────────────────────── */

var state = {
  query: '',
  sortKey: 'stars',
  sortDir: 'desc',
  visible: new Set(lib.DEFAULT_VISIBLE),
  columnsOpen: false,
  detailIndex: null,
  seriesRows: HISTORY_DEFAULT.slice(),
  rangeIdx: 2,
  window: null,
  hoverX: null,
  hoverRow: null,
  pinnedRow: null,
  dragFrom: null,
  brush: null,
  plotW: 900,
  narrow: false,
};

var sorted = [];

function visibleKeys() {
  var keys = KEYS.filter(function (key) {
    if (!state.visible.has(key)) return false;
    if (state.narrow && lib.NARROW_HIDDEN.indexOf(key) !== -1) return false;
    return true;
  });
  return lib.orderColumns(keys);
}

/* ── cell rendering ────────────────────────────────────────────────── */

// A cell's link must not open the record behind it.
function stopClick(event) { event.stopPropagation(); }

function renderParts(parts, text, fallback) {
  var nodes = [];
  var source = parts && parts.length
    ? parts
    : [{ v: lib.isEmptyValue(text) ? (fallback == null ? EM_DASH : fallback) : text }];
  source.forEach(function (part) {
    var attrs = { text: part.v };
    if (part.s) attrs.style = 'text-decoration:line-through';
    if (part.h) {
      attrs.href = part.h;
      attrs.onclick = stopClick;
      nodes.push(el('a', attrs));
    } else {
      nodes.push(el('span', attrs));
    }
  });
  return nodes;
}

function renderCell(row, key) {
  if (key === 'stars') {
    var nodes = [el('span', { text: lib.fmtInt(row.starsNum) })];
    if (row.starsAsterisk) {
      nodes.push(el('span', { class: 'stars-extra', title: row.starsTitle }));
    }
    return nodes;
  }
  if (key === 'stars_dif') {
    var delta = lib.fmtDelta(row.fields.stars_dif);
    return [el('span', { class: 'delta-' + delta.tone, text: delta.text })];
  }
  return renderParts(row.parts[key], row.fields[key], EM_DASH);
}

/* ── table ─────────────────────────────────────────────────────────── */

var tableHead = document.getElementById('table-head');
var tableBody = document.getElementById('table-body');
var tableCount = document.getElementById('table-count');
var tableEmpty = document.getElementById('table-empty');
var searchInput = document.getElementById('search');

function renderTable() {
  var keys = visibleKeys();
  sorted = lib.filterSort(rows, {
    query: state.query,
    sortKey: state.sortKey,
    sortDir: state.sortDir,
    searchKeys: keys.concat(lib.SEARCH_ALWAYS),
  });

  clear(tableHead);
  var headRow = el('tr');
  keys.forEach(function (key) {
    var active = state.sortKey === key;
    var th = el('th', {
      class: 'col-' + key + (lib.NUMERIC_KEYS.indexOf(key) !== -1 ? ' num' : ''),
      'data-key': key,
      title: colTitle[key],
      scope: 'col',
      onclick: function () { sortBy(key); },
    }, [
      lib.shortTitle(key, colTitle[key]),
      el('span', { class: 'sort' }, [
        icon(active ? (state.sortDir === 'desc' ? 'sort-desc' : 'sort-asc') : 'sort-none', 11),
      ]),
    ]);
    if (active) th.setAttribute('aria-sort', state.sortDir === 'desc' ? 'descending' : 'ascending');
    headRow.appendChild(th);
  });
  tableHead.appendChild(headRow);

  var body = document.createDocumentFragment();
  sorted.forEach(function (row, position) {
    var tr = el('tr', {
      'data-position': position,
      onclick: function () { openRecord(position); },
    });
    keys.forEach(function (key) {
      var numeric = lib.NUMERIC_KEYS.indexOf(key) !== -1;
      var td = el('td', {
        class: 'col-' + key + ' cell-' + key + (numeric ? ' num' : ''),
        title: key === 'stars' || key === 'stars_dif' ? null : row.fields[key] || null,
      }, renderCell(row, key));
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
  clear(tableBody);
  tableBody.appendChild(body);

  tableCount.textContent = sorted.length === rows.length
    ? rows.length + ' systems · ' + KEYS.length + ' attributes'
    : sorted.length + ' of ' + rows.length + ' systems';

  if (sorted.length) {
    tableEmpty.hidden = true;
  } else {
    tableEmpty.hidden = false;
    tableEmpty.textContent = 'Nothing matches “' + state.query + '”.';
  }
}

function sortBy(key) {
  state.sortDir = state.sortKey === key && state.sortDir === 'desc' ? 'asc' : 'desc';
  state.sortKey = key;
  closeRecord();
  renderTable();
}

/* ── columns popover ───────────────────────────────────────────────── */

var columnsButton = document.getElementById('columns-button');
var columnsCount = document.getElementById('columns-count');
var columnsPopover = document.getElementById('columns-popover');
var columnsBody = document.getElementById('columns-body');

// Built once. Toggling a box only updates state on the existing inputs, so
// keyboard focus survives a change.
var columnInputs = {};

function buildColumns() {
  clear(columnsBody);
  columnInputs = {};
  lib.COLUMN_GROUPS.forEach(function (group) {
    var box = el('div', null, [el('div', { class: 'columns__group-name', text: group.name })]);
    group.keys.forEach(function (key) {
      var input = el('input', {
        type: 'checkbox',
        onchange: function () { toggleColumn(key); },
      });
      columnInputs[key] = input;
      box.appendChild(el('label', { class: 'columns__option' }, [
        input,
        el('span', { text: lib.shortTitle(key, colTitle[key]) }),
      ]));
    });
    columnsBody.appendChild(box);
  });
}

function syncColumns() {
  columnsCount.textContent = state.visible.size;
  Object.keys(columnInputs).forEach(function (key) {
    var on = state.visible.has(key);
    var input = columnInputs[key];
    input.checked = on;
    // The last visible column can never be turned off.
    input.disabled = on && state.visible.size === 1;
  });
}

function renderColumns() {
  columnsButton.setAttribute('aria-expanded', state.columnsOpen ? 'true' : 'false');
  columnsPopover.hidden = !state.columnsOpen;
  syncColumns();
}

function toggleColumn(key) {
  if (state.visible.has(key)) {
    if (state.visible.size === 1) {
      syncColumns();
      return;
    }
    state.visible.delete(key);
  } else {
    state.visible.add(key);
  }
  syncColumns();
  renderTable();
}

function setColumnsOpen(open) {
  state.columnsOpen = open;
  renderColumns();
}

columnsButton.addEventListener('click', function () { setColumnsOpen(!state.columnsOpen); });
document.getElementById('columns-all').addEventListener('click', function () {
  state.visible = new Set(KEYS);
  syncColumns();
  renderTable();
});
document.getElementById('columns-reset').addEventListener('click', function () {
  state.visible = new Set(lib.DEFAULT_VISIBLE);
  syncColumns();
  renderTable();
});
document.getElementById('columns-close').addEventListener('click', function () {
  setColumnsOpen(false);
});
document.addEventListener('click', function (event) {
  if (!state.columnsOpen) return;
  if (columnsPopover.contains(event.target) || columnsButton.contains(event.target)) return;
  setColumnsOpen(false);
});

searchInput.addEventListener('input', function (event) {
  state.query = event.target.value;
  closeRecord();
  renderTable();
});

/* ── project record ────────────────────────────────────────────────── */

var record = document.getElementById('record');
var recordPosition = document.getElementById('record-position');
var recordHead = document.getElementById('record-head');
var recordBody = document.getElementById('record-body');
var recordMissing = document.getElementById('record-missing');

// Shown in the head, so not repeated in the grouped body below it.
var HEAD_KEYS = ['stars', 'stars_dif', 'name', 'description', 'license', 'last_committed'];

function linkButtons(row) {
  var links = [];
  (row.parts.source || []).forEach(function (part) {
    if (part.h) links.push({ label: part.v, href: part.h });
  });
  var demoIndex = 0;
  (row.parts.demo || []).forEach(function (part) {
    if (!part.h) return;
    demoIndex += 1;
    // Bare [1]/[2] labels say nothing on their own.
    links.push({ label: /^\[\d+\]$/.test(part.v.trim()) ? 'demo ' + demoIndex : part.v, href: part.h });
  });
  return links;
}

function renderRecord() {
  var row = state.detailIndex == null ? null : sorted[state.detailIndex];
  if (!row) {
    record.hidden = true;
    return;
  }
  record.hidden = false;
  recordPosition.textContent = 'Record ' + (state.detailIndex + 1) + ' / ' + sorted.length;

  var delta = lib.fmtDelta(row.fields.stars_dif);
  clear(recordHead);
  recordHead.appendChild(el('div', null, [
    el('h2', { class: 'record__name', text: row.name }),
    el('p', { class: 'record__desc' }, renderParts(row.parts.description, row.fields.description, 'No description yet.')),
    el('div', { class: 'record__links' }, linkButtons(row).map(function (link) {
      return el('a', { class: 'record__link', href: link.href }, [link.label, icon('external', 12)]);
    })),
  ]));
  recordHead.appendChild(el('div', { class: 'record__stats' }, [
    stat('Stars', lib.fmtInt(row.starsNum)),
    stat('Last 30 days', delta.text, null, delta.tone === 'up' ? 'color:var(--color-positive)' : null),
    stat('Last commit', row.fields.last_committed || EM_DASH, true),
    stat('License', lib.isEmptyValue(row.fields.license) ? EM_DASH : row.fields.license, true),
  ]));

  clear(recordBody);
  lib.COLUMN_GROUPS.forEach(function (group) {
    var items = group.keys.filter(function (key) {
      return HEAD_KEYS.indexOf(key) === -1 && !lib.isEmptyValue(row.fields[key]);
    });
    if (!items.length) return;
    var box = el('div', null, [el('div', { class: 'record__group-name', text: group.name })]);
    items.forEach(function (key) {
      box.appendChild(el('div', { class: 'record__field' }, [
        el('div', { class: 'record__field-label', text: lib.shortTitle(key, colTitle[key]) }),
        el('div', { class: 'record__field-value' }, renderParts(row.parts[key], row.fields[key])),
      ]));
    });
    recordBody.appendChild(box);
  });

  // Gaps become a contribution prompt instead of a wall of question marks.
  var unknown = KEYS.filter(function (key) { return lib.isEmptyValue(row.fields[key]); });
  if (unknown.length) {
    recordMissing.hidden = false;
    recordMissing.textContent = 'Not documented (' + unknown.length + '): '
      + unknown.map(function (key) { return lib.shortTitle(key, colTitle[key]); }).join(', ')
      + '. Contribute the missing data on GitHub.';
  } else {
    recordMissing.hidden = true;
  }
  record.scrollTop = 0;
}

function stat(label, value, small, style) {
  return el('div', null, [
    el('span', {
      class: 'record__stat-value' + (small ? ' record__stat-value--sm' : ''),
      style: style,
      text: value,
    }),
    el('span', { class: 'record__stat-label', text: label }),
  ]);
}

function openRecord(position) {
  state.detailIndex = position;
  renderRecord();
}

function closeRecord() {
  if (state.detailIndex == null) return;
  state.detailIndex = null;
  renderRecord();
}

function stepRecord(delta) {
  if (state.detailIndex == null || !sorted.length) return;
  state.detailIndex = (state.detailIndex + delta + sorted.length) % sorted.length;
  renderRecord();
}

document.getElementById('record-prev').addEventListener('click', function () { stepRecord(-1); });
document.getElementById('record-next').addEventListener('click', function () { stepRecord(1); });
document.getElementById('record-close').addEventListener('click', closeRecord);

document.addEventListener('keydown', function (event) {
  if (event.key !== 'Escape') return;
  closeRecord();
  setColumnsOpen(false);
});

/* ── chart ─────────────────────────────────────────────────────────── */

var plot = document.getElementById('plot');
var plotSvg = document.getElementById('plot-svg');
var plotOverlay = document.getElementById('plot-overlay');
var plotTip = document.getElementById('plot-tip');
var rangeBox = document.getElementById('range');
var seriesList = document.getElementById('series-list');
var seriesAdd = document.getElementById('series-add');

var PAD = { l: 4, r: 96, t: 18, b: 30 };
var PLOT_H = 320;
var geo = null;

function colorFor(i) { return lib.SERIES_COLORS[i % lib.SERIES_COLORS.length]; }

function chartWindow() {
  if (state.window) return state.window;
  return lib.rangeFor(lib.RANGE_PRESETS[state.rangeIdx], HISTORY_RANGE.first, HISTORY_RANGE.last);
}

function focusRow() {
  return state.pinnedRow != null ? state.pinnedRow : state.hoverRow;
}

// How far everything that is not in focus recedes. Used for both the plot
// lines and the rail rows so the two columns read at the same strength.
var DIM_OPACITY = 0.35;

function emphasis(row) {
  var focus = focusRow();
  if (focus == null) return { opacity: 1, width: 2, weight: 600 };
  // Never recolour the focused line — red read as an error.
  return row === focus
    ? { opacity: 1, width: 3.4, weight: 800 }
    : { opacity: DIM_OPACITY, width: 1.8, weight: 600 };
}

function buildSeries() {
  // Counted over styleless series only, so the first project added always gets
  // the first pattern in the cycle however many defaults are on the chart.
  var styled = 0;
  return state.seriesRows
    .filter(function (row) { return HISTORY[row]; })
    .map(function (row, i) {
      var dash = HISTORY[row].d;
      if (!dash) dash = lib.DASH_CYCLE[styled++ % lib.DASH_CYCLE.length];
      return {
        row: row,
        label: rows[row] ? rows[row].name : String(row),
        points: HISTORY[row].p,
        dash: dash,
        color: colorFor(i),
      };
    });
}

function svgX(event) {
  var box = plotSvg.getBoundingClientRect();
  var view = plotSvg.viewBox.baseVal;
  return ((event.clientX - box.left) / box.width) * (view.width || box.width);
}

function renderChart() {
  var win = chartWindow();
  var w = state.plotW;
  geo = lib.chartGeometry({
    series: buildSeries(), w: w, h: PLOT_H, pad: PAD, from: win.from, to: win.to,
  });

  plotSvg.setAttribute('viewBox', '0 0 ' + w + ' ' + PLOT_H);
  clear(plotSvg);

  geo.yTicks.forEach(function (tick) {
    plotSvg.appendChild(svg('line', {
      class: 'chart__grid-y', x1: geo.x0, x2: geo.x1, y1: tick.y, y2: tick.y, 'stroke-width': 1,
    }));
  });
  geo.xTicks.forEach(function (tick) {
    plotSvg.appendChild(svg('line', {
      class: 'chart__grid-x', x1: tick.x, x2: tick.x, y1: geo.y1, y2: geo.y0, 'stroke-width': 1,
    }));
  });
  plotSvg.appendChild(svg('line', {
    class: 'chart__baseline', x1: geo.x0, x2: geo.x1, y1: geo.y0, y2: geo.y0,
  }));

  var brush = svg('rect', { class: 'chart__brush', y: geo.y1, height: geo.y0 - geo.y1 });
  brush.style.display = 'none';
  plotSvg.appendChild(brush);

  var cursor = svg('line', { class: 'chart__cursor', y1: geo.y1, y2: geo.y0 });
  cursor.style.display = 'none';
  plotSvg.appendChild(cursor);

  var lineNodes = geo.lines.map(function (line, i) {
    var node = svg('path', {
      class: 'chart__line', d: line.d, stroke: colorFor(i), 'stroke-dasharray': line.dash,
    });
    plotSvg.appendChild(node);
    return node;
  });

  // A transparent fat duplicate is the hit target: hovering a 2px stroke does
  // not feel instant.
  geo.lines.forEach(function (line) {
    plotSvg.appendChild(svg('path', {
      class: 'chart__hit',
      d: line.d,
      onmousemove: function () { setHoverRow(line.row); },
      onclick: function (event) {
        event.stopPropagation();
        if (suppressClick) return;
        state.pinnedRow = state.pinnedRow === line.row ? null : line.row;
        applyEmphasis();
        syncSeries();
      },
    }));
  });

  var dots = svg('g');
  plotSvg.appendChild(dots);

  // Axis and end labels are HTML: cheaper to style and they inherit page type.
  clear(plotOverlay);
  geo.yTicks.forEach(function (tick) {
    plotOverlay.appendChild(el('div', {
      class: 'chart__ylabel',
      style: 'left:0;top:' + pct(tick.y, PLOT_H) + ';padding-bottom:2px',
      text: tick.label,
    }));
  });
  geo.xTicks.forEach(function (tick) {
    plotOverlay.appendChild(el('div', {
      class: 'chart__xlabel',
      style: 'left:' + pct(tick.x, w) + ';top:' + pct(geo.y0, PLOT_H) + ';padding-top:5px',
      text: tick.label,
    }));
  });
  var endLabels = geo.lines.map(function (line, i) {
    var node = el('div', {
      class: 'chart__endlabel',
      style: 'left:' + pct(geo.x1 + 8, w) + ';top:' + pct(line.labelY, PLOT_H) + ';color:' + colorFor(i),
      text: line.label,
    });
    plotOverlay.appendChild(node);
    return node;
  });

  geo.nodes = { lines: lineNodes, endLabels: endLabels, dots: dots, cursor: cursor, brush: brush };
  applyEmphasis();
  renderHover();
  syncRange();
  buildSeriesRows();
  syncSeries();
}

function applyEmphasis() {
  if (!geo || !geo.nodes) return;
  geo.lines.forEach(function (line, i) {
    var em = emphasis(line.row);
    geo.nodes.lines[i].setAttribute('stroke-opacity', em.opacity);
    geo.nodes.lines[i].setAttribute('stroke-width', em.width);
    var label = geo.nodes.endLabels[i];
    label.style.opacity = em.opacity;
    label.style.fontWeight = em.weight;
    label.setAttribute('data-focus', em.weight === 800 ? 'on' : 'off');
  });
}

function renderHover() {
  if (!geo || !geo.nodes) return;
  var nodes = geo.nodes;
  clear(nodes.dots);

  if (state.brush) {
    var a = Math.min(state.brush.a, state.brush.b);
    nodes.brush.setAttribute('x', a);
    nodes.brush.setAttribute('width', Math.abs(state.brush.b - state.brush.a));
    nodes.brush.style.display = '';
  } else {
    nodes.brush.style.display = 'none';
  }

  if (state.hoverX == null || state.dragFrom != null) {
    nodes.cursor.style.display = 'none';
    plotTip.hidden = true;
    return;
  }
  nodes.cursor.setAttribute('x1', state.hoverX);
  nodes.cursor.setAttribute('x2', state.hoverX);
  nodes.cursor.style.display = '';

  var cursorTime = geo.xToTime(state.hoverX);
  var items = [];
  geo.lines.forEach(function (line, i) {
    var read = lib.readAt(line, cursorTime, geo.sy);
    if (!read) {
      // The series has no data on this date; say so instead of borrowing the
      // nearest number, and draw no dot.
      items.push({ label: line.label, value: EM_DASH, muted: true });
      return;
    }
    items.push({ label: line.label, value: lib.fmtInt(read.value) });
    nodes.dots.appendChild(svg('circle', {
      class: 'chart__dot',
      cx: state.hoverX,
      cy: read.y,
      r: 3,
      fill: 'var(--color-bg)',
      stroke: colorFor(i),
    }));
  });

  if (!items.length) {
    plotTip.hidden = true;
    return;
  }
  var flip = state.hoverX > (geo.x1 - geo.x0) * 0.6;
  plotTip.hidden = false;
  plotTip.style.left = 'calc(' + ((state.hoverX / state.plotW) * 100).toFixed(2) + '% + '
    + (flip ? '-168px' : '14px') + ')';
  clear(plotTip);
  plotTip.appendChild(el('div', {
    class: 'chart__tooltip-date',
    text: lib.monthYear(cursorTime),
  }));
  items.forEach(function (item) {
    plotTip.appendChild(el('div', {
      class: 'chart__tooltip-row' + (item.muted ? ' chart__tooltip-row--empty' : ''),
    }, [
      el('span', { text: item.label }),
      el('span', { text: item.value }),
    ]));
  });
}

function setHoverRow(row) {
  if (state.hoverRow === row) return;
  state.hoverRow = row;
  applyEmphasis();
}

var suppressClick = false;

plotSvg.addEventListener('mousemove', function (event) {
  var x = svgX(event);
  state.hoverX = x;
  if (state.dragFrom != null) state.brush = { a: state.dragFrom, b: x };
  renderHover();
});
plotSvg.addEventListener('mouseleave', function () {
  state.hoverX = null;
  state.dragFrom = null;
  state.brush = null;
  state.hoverRow = null;
  applyEmphasis();
  renderHover();
});
plotSvg.addEventListener('mousedown', function (event) {
  var x = svgX(event);
  state.dragFrom = x;
  state.brush = { a: x, b: x };
  renderHover();
});
plotSvg.addEventListener('mouseup', function (event) {
  var from = state.dragFrom;
  var x = svgX(event);
  state.dragFrom = null;
  state.brush = null;
  if (from == null || Math.abs(x - from) < 12) {
    renderHover();
    return;
  }
  // A drag that committed a zoom must not also land as a click on a line.
  suppressClick = true;
  setTimeout(function () { suppressClick = false; }, 0);
  state.window = {
    from: lib.isoDate(geo.xToTime(Math.min(from, x))),
    to: lib.isoDate(geo.xToTime(Math.max(from, x))),
  };
  state.hoverX = null;
  renderChart();
});
plotSvg.addEventListener('dblclick', function () {
  state.window = null;
  state.brush = null;
  state.dragFrom = null;
  state.pinnedRow = null;
  renderChart();
});

var rangeButtons = [];

function buildRange() {
  clear(rangeBox);
  rangeButtons = lib.RANGE_PRESETS.map(function (preset, i) {
    var button = el('button', {
      type: 'button',
      'aria-pressed': 'false',
      text: preset.label,
      onclick: function () {
        state.rangeIdx = i;
        state.window = null;
        state.brush = null;
        state.hoverX = null;
        renderChart();
      },
    });
    rangeBox.appendChild(button);
    return button;
  });
}

function syncRange() {
  rangeButtons.forEach(function (button, i) {
    var active = !state.window && state.rangeIdx === i;
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}

var seriesNodes = [];

function buildSeriesRows() {
  clear(seriesList);
  seriesNodes = geo.lines.map(function (line, i) {
    var swatch = lib.SWATCH[dashName(line.dash)];
    var stroke = svg('line', {
      x1: 0, x2: swatch.length, y1: 4, y2: 4,
      stroke: colorFor(i),
      'stroke-width': 2,
      'stroke-dasharray': swatch.dash,
    });
    var lock = lockGlyph();
    var node = el('div', {
      class: 'series__row',
      onmouseenter: function () { setHoverRow(line.row); },
      onmouseleave: function () { setHoverRow(null); },
      onclick: function () {
        state.pinnedRow = state.pinnedRow === line.row ? null : line.row;
        applyEmphasis();
        syncSeries();
      },
    }, [
      svg('svg', { class: 'series__swatch', width: 26, height: 8 }, [stroke]),
      el('span', { class: 'series__name', text: line.label }),
      lock,
      el('span', { class: 'series__stars', text: lib.fmtInt(line.endValue) }),
      el('button', {
        type: 'button',
        class: 'series__remove',
        title: 'Remove series',
        onclick: function (event) {
          event.stopPropagation();
          state.seriesRows = state.seriesRows.filter(function (row) { return row !== line.row; });
          if (state.pinnedRow === line.row) state.pinnedRow = null;
          if (state.hoverRow === line.row) state.hoverRow = null;
          renderChart();
          renderAddable();
        },
      }, [icon('x', 12)]),
    ]);
    seriesList.appendChild(node);
    return { row: line.row, node: node, stroke: stroke, lock: lock };
  });
}

// The rail follows the lock only. Tying it to hover as well made the whole
// column flicker while the pointer crossed the plot.
function syncSeries() {
  var anyLocked = state.pinnedRow != null;
  seriesNodes.forEach(function (entry) {
    var locked = state.pinnedRow === entry.row;
    entry.node.setAttribute('data-locked', locked ? 'true' : 'false');
    entry.node.setAttribute(
      'title',
      locked ? 'Locked — click to release this series' : 'Click to isolate this series'
    );
    entry.node.style.opacity = anyLocked && !locked ? String(DIM_OPACITY) : '';
    entry.stroke.setAttribute('stroke-width', locked ? 3.4 : 2);
    entry.lock.style.display = locked ? '' : 'none';
  });
}

function lockGlyph() {
  var node = icon('lock', 12);
  node.setAttribute('class', 'series__lock');
  node.setAttribute('stroke', 'var(--color-accent)');
  return node;
}

function dashName(dash) {
  var names = Object.keys(lib.DASH);
  for (var i = 0; i < names.length; i++) {
    if (lib.DASH[names[i]] === dash) return names[i];
  }
  return 'solid';
}

function renderAddable() {
  clear(seriesAdd);
  seriesAdd.appendChild(el('option', { value: '', text: '+ Add a project…' }));
  Object.keys(HISTORY)
    .map(Number)
    .filter(function (row) { return state.seriesRows.indexOf(row) === -1 && rows[row]; })
    .sort(function (a, b) { return rows[b].starsNum - rows[a].starsNum; })
    .forEach(function (row) {
      seriesAdd.appendChild(el('option', {
        value: String(row),
        text: rows[row].name + ' · ' + lib.fmtInt(rows[row].starsNum),
      }));
    });
  seriesAdd.value = '';
}

seriesAdd.addEventListener('change', function (event) {
  var row = parseInt(event.target.value, 10);
  if (!isFinite(row)) return;
  state.seriesRows = state.seriesRows.concat([row]);
  renderChart();
  renderAddable();
});


/* ── layout ────────────────────────────────────────────────────────── */

function measure() {
  var narrow = window.matchMedia('(max-width: 880px)').matches;
  var width = Math.max(420, plot.clientWidth || 900);
  var changedTable = narrow !== state.narrow;
  var changedPlot = Math.abs(width - state.plotW) > 0.5;
  state.narrow = narrow;
  state.plotW = width;
  if (changedTable) {
    closeRecord();
    renderTable();
  }
  if (changedPlot) renderChart();
}

var resizeTimer = null;
window.addEventListener('resize', function () {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(measure, 80);
});

/* ── Isso vote counters ────────────────────────────────────────────── */

// Isso prints a bare JavaScript number, so a negative score arrives as an
// ASCII hyphen and a positive one carries no sign at all. Rewrite both to
// match the table: a real minus sign, and an explicit + when the score is up.
var MINUS_SIGN = '\u2212';

function formatVotes(scope) {
  if (!scope || !scope.querySelectorAll) return;
  var nodes = scope.querySelectorAll('.isso-votes');
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    var count = parseInt(node.textContent.replace(/\u2212/g, '-').replace(/[+\s]/g, ''), 10);
    if (!isFinite(count)) continue;
    var text = count > 0 ? '+' + count : count < 0 ? MINUS_SIGN + Math.abs(count) : '0';
    // Writing only on a real change keeps the observer below from looping.
    if (node.textContent !== text) node.textContent = text;
  }
}

var issoThread = document.getElementById('isso-thread');
if (issoThread && window.MutationObserver) {
  formatVotes(issoThread);
  // The thread is rendered after this script runs, and re-rendered on a vote.
  new MutationObserver(function () { formatVotes(issoThread); })
    .observe(issoThread, { childList: true, subtree: true, characterData: true });
}

/* ── start ─────────────────────────────────────────────────────────── */

state.narrow = window.matchMedia('(max-width: 880px)').matches;
state.plotW = Math.max(420, plot.clientWidth || 900);

renderTable();
buildColumns();
renderColumns();
if (HISTORY_RANGE && state.seriesRows.length) {
  buildRange();
  renderChart();
  renderAddable();
}
// Web fonts change the plot width; re-measure once they land.
if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
})();
