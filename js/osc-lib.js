// Shared logic for the open-source-comments page: column grouping, filtering
// and sorting, formatters, chart geometry. Ported from the design handoff.
//
// Plain script rather than an ES module so index.html still opens straight from
// the filesystem, as README describes.

window.oscLib = (function () {
'use strict';
const COLUMN_GROUPS = [
  { name: 'Identity', keys: ['name', 'description', 'language', 'db', 'license', 'static', 'dependency', 'docker', 'provided_hosting', 'english_documentation'] },
  { name: 'Repository', keys: ['stars', 'stars_dif', 'open_issues', 'source', 'created', 'last_committed'] },
  { name: 'Links & weight', keys: ['demo', 'js_kB', 'css_kB', 'rss', 'webmention'] },
  { name: 'Comment features', keys: ['markdown_support', 'nested_comments', 'collapse_comments', 'sort', 'paging', 'hide_long_threads', 'display_images', 'avatar', 'edit', 'vote'] },
  { name: 'Users & moderation', keys: ['social_network_login', 'anonymous_comments', 'moderation', 'antispam', 'bad_words_list', 'rate_limit', 'use_cookies', 'mail_notification', 'import_from_wordpress', 'import_from_disqus'] },
];

const NUMERIC_KEYS = ['stars', 'stars_dif', 'open_issues', 'js_kB', 'css_kB'];
const DEFAULT_VISIBLE = ['stars', 'stars_dif', 'name', 'source', 'demo', 'language', 'db', 'description'];
const NARROW_HIDDEN = ['description'];
const SEARCH_ALWAYS = ['name', 'description', 'language', 'db'];

// Shortened for density in the header; the full title goes into `title`.
const SHORT_TITLES = {
  stars: 'Stars',
  stars_dif: '30 d',
  name: 'Name',
  source: 'Source',
  demo: 'Demo',
  open_issues: 'Issues+PR',
  language: 'Language',
  db: 'Database',
  last_committed: 'Updated',
  created: 'Created',
  description: 'Description',
  markdown_support: 'Markdown',
  social_network_login: 'Social login',
  anonymous_comments: 'Anonymous',
  edit: 'User edits',
  vote: 'User votes',
  moderation: 'Moderation',
  nested_comments: 'Nested',
  mail_notification: 'Mail notify',
  antispam: 'Antispam',
  bad_words_list: 'Bad words',
  use_cookies: 'Cookies',
  avatar: 'Avatar',
  provided_hosting: 'Hosted option',
  collapse_comments: 'Collapse',
  sort: 'Order',
  docker: 'Docker',
  paging: 'Paging',
  rate_limit: 'Rate limit',
  hide_long_threads: 'Hide threads',
  import_from_wordpress: 'WP import',
  import_from_disqus: 'Disqus import',
  english_documentation: 'English docs',
  dependency: 'Dependencies',
  webmention: 'Webmention',
  display_images: 'Images',
  license: 'License',
  rss: 'RSS',
  static: 'Static',
  js_kB: 'js kB',
  css_kB: 'css kB',
};

function shortTitle(key, fallback) {
  if (SHORT_TITLES[key]) return SHORT_TITLES[key];
  const text = String(fallback || key).replace(/ /g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Column order in the table is fixed regardless of the order columns were
// toggled on: Name, Stars, 30 d, the rest in data.js order, Description last.
function orderColumns(keys) {
  const lead = ['name', 'stars', 'stars_dif'];
  const head = lead.filter((key) => keys.includes(key));
  const tail = keys.includes('description') ? ['description'] : [];
  const middle = keys.filter((key) => !head.includes(key) && !tail.includes(key));
  return head.concat(middle, tail);
}

const EMPTY = new Set(['', '?', 'None', 'undefined', '-']);
const isEmptyValue = (v) => v == null || EMPTY.has(String(v).trim());

const fmtInt = (n) => (isFinite(n) && n >= 0 ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : '—');

function fmtDelta(raw) {
  const n = parseInt(raw, 10);
  if (!isFinite(n) || n === 0) return { text: '0', tone: 'flat' };
  return { text: (n > 0 ? '+' : '−') + Math.abs(n), tone: n > 0 ? 'up' : 'down' };
}

function filterSort(rows, { query, sortKey, sortDir, searchKeys }) {
  let out = rows;
  const q = (query || '').trim().toLowerCase();
  if (q && rows.length) {
    const keys = searchKeys && searchKeys.length ? searchKeys : Object.keys(rows[0].fields);
    out = rows.filter((r) => keys.some((k) => (r.fields[k] || '').toLowerCase().includes(q)));
  }
  const numeric = NUMERIC_KEYS.includes(sortKey);
  out = out.slice().sort((a, b) => {
    if (sortKey === 'stars') return a.starsNum - b.starsNum;
    if (sortKey === 'stars_dif') return a.difNum - b.difNum;
    if (numeric) {
      const an = parseFloat(a.fields[sortKey]);
      const bn = parseFloat(b.fields[sortKey]);
      return (isFinite(an) ? an : -1) - (isFinite(bn) ? bn : -1);
    }
    const av = (a.fields[sortKey] || '').toLowerCase();
    const bv = (b.fields[sortKey] || '').toLowerCase();
    return av < bv ? -1 : av > bv ? 1 : 0;
  });
  return sortDir === 'desc' ? out.reverse() : out;
}

/* ── chart ───────────────────────────────────────────────────────────── */

// Categorical, anchored on the accent; assigned by index, cycling.
const SERIES_COLORS = [
  '#ec3013', '#1f5f8b', '#2c7a52', '#a8641c',
  '#6b4d9b', '#0f8a8a', '#8c2f5b', '#4c4644',
];

// The first four are carried over from plot-stars.py so the SVG and this chart
// agree; the rest exist so projects added to the chart stay tellable apart once
// the eight colours start repeating.
const DASH = {
  solid: 'none',
  dotted: '2 5',
  dashed: '10 6',
  dashdot: '12 5 3 5',
  dotpair: '2 5 2 10',
  dotdotdash: '2 5 2 5 12 6',
  dotdashdash: '2 5 12 5 12 7',
};

// The legend swatch values differ on purpose: each is tuned to end on a whole
// dash inside its 26px box rather than be clipped mid-stroke, so a few are
// drawn shorter.
const SWATCH = {
  solid: { length: 26, dash: 'none' },
  dotted: { length: 26, dash: '2 4' },
  dashed: { length: 26, dash: '6 4' },
  dashdot: { length: 17, dash: '11 4 2 4' },
  dotpair: { length: 24, dash: '2 4 2 8' },
  dotdotdash: { length: 21, dash: '2 4 2 4 9 4' },
  dotdashdash: { length: 26, dash: '2 4 8 4 8 4' },
};

// Handed out in turn to series the build gave no style. The three patterns the
// seven defaults never use come first, so the first project you add cannot be
// mistaken for one already on the chart; seven styles against eight colours
// means a pair repeats only after 56 series.
const DASH_CYCLE = [
  'dotpair', 'dotdotdash', 'dotdashdash', 'dashdot', 'dashed', 'dotted', 'solid',
];

const t = (s) => new Date(s + 'T00:00:00Z').getTime();

function niceTicks(min, max, count) {
  const span = max - min || 1;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || 10 * mag;
  const first = Math.ceil(min / step) * step;
  const out = [];
  for (let v = first; v <= max + step * 0.001; v += step) out.push(Math.round(v));
  return out;
}

// Clip one series to [tFrom, tTo], interpolating at the left edge and carrying
// the last known value to the right edge.
function clipPoints(raw, tFrom, tTo) {
  const pts = [];
  for (let i = 0; i < raw.length; i++) {
    const td = t(raw[i][0]);
    const v = raw[i][1];
    if (td >= tFrom && td <= tTo) {
      pts.push([td, v]);
    } else if (td < tFrom && i < raw.length - 1) {
      const td2 = t(raw[i + 1][0]);
      if (td2 > tFrom) {
        const k = (tFrom - td) / (td2 - td);
        pts.push([tFrom, v + (raw[i + 1][1] - v) * k]);
      }
    }
  }
  const last = raw[raw.length - 1];
  if (pts.length && last && t(last[0]) > tTo) {
    const prev = raw.filter(([d]) => t(d) <= tTo).slice(-1)[0];
    if (prev) pts.push([tTo, prev[1]]);
  }
  return pts;
}

function chartGeometry({ series, w, h, pad, from, to }) {
  const x0 = pad.l, x1 = w - pad.r, y0 = h - pad.b, y1 = pad.t;
  const tFrom = t(from), tTo = t(to);

  // Clip first, then take the value range from what is actually drawn, so no
  // line can leave the plot at the window edges.
  const clipped = series.map((s) => ({ s, pts: clipPoints(s.points, tFrom, tTo) }));
  let lo = Infinity, hi = -Infinity;
  clipped.forEach(({ pts }) => pts.forEach(([, v]) => {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }));
  if (!isFinite(lo)) { lo = 0; hi = 100; }
  const padY = (hi - lo) * 0.08 || hi * 0.1 || 10;
  const vMin = Math.max(0, lo - padY), vMax = hi + padY;

  const sxTime = (ms) => x0 + ((ms - tFrom) / (tTo - tFrom || 1)) * (x1 - x0);
  const sx = (d) => sxTime(t(d));
  const sy = (v) => y0 - ((v - vMin) / (vMax - vMin || 1)) * (y0 - y1);
  const xToTime = (px) => tFrom + ((px - x0) / (x1 - x0 || 1)) * (tTo - tFrom);

  const lines = clipped.map(({ s, pts }) => {
    const d = pts
      .map((p, i) => (i ? 'L' : 'M') + sxTime(p[0]).toFixed(1) + ' ' + sy(p[1]).toFixed(1))
      .join(' ');
    const endPt = pts[pts.length - 1];
    return {
      row: s.row,
      label: s.label,
      color: s.color,
      d,
      dash: DASH[s.dash || 'solid'],
      endX: endPt ? sxTime(endPt[0]) : x1,
      endY: endPt ? sy(endPt[1]) : y0,
      endValue: endPt ? endPt[1] : null,
      points: pts,
    };
  });

  // De-overlap the end labels: push each down to at least 15px below the last.
  const order = lines.slice().sort((a, b) => a.endY - b.endY);
  const minGap = 15;
  for (let i = 1; i < order.length; i++) {
    if (order[i].endY - order[i - 1].endY < minGap) order[i].endY = order[i - 1].endY + minGap;
  }
  order.forEach((l) => { l.labelY = Math.min(Math.max(l.endY, y1 + 6), y0 + 4); });

  const yTicks = niceTicks(vMin, vMax, 5).map((v) => ({ v, y: sy(v), label: fmtInt(v) }));
  const xTicks = [];
  const yStart = new Date(tFrom).getUTCFullYear();
  const yEnd = new Date(tTo).getUTCFullYear();
  const spanYears = yEnd - yStart;
  for (let y = yStart; y <= yEnd; y++) {
    const px = sx(y + '-01-01');
    if (px >= x0 - 1 && px <= x1 + 1) xTicks.push({ x: px, label: String(y) });
  }
  if (spanYears <= 2) {
    xTicks.length = 0;
    const d = new Date(tFrom);
    d.setUTCDate(1);
    while (d.getTime() <= tTo) {
      const px = sxTime(d.getTime());
      if (px >= x0 - 1 && px <= x1 + 1) {
        xTicks.push({
          x: px,
          label: d.toLocaleString('en', { month: 'short', timeZone: 'UTC' })
            + (d.getUTCMonth() === 0 ? ' ’' + String(d.getUTCFullYear()).slice(2) : ''),
        });
      }
      d.setUTCMonth(d.getUTCMonth() + (spanYears <= 1 ? 2 : 3));
    }
  }
  return { lines, xTicks, yTicks, x0, x1, y0, y1, tFrom, tTo, sx, sxTime, sy, xToTime };
}

// One line read at the pointer's date, for the readout dot and the tooltip.
// Returns null before the series starts or after it ends — a project that was
// not on GitHub yet has no star count, and showing its nearest one instead
// would invent a number.
//
// `value` is the last count actually recorded on or before that date; `y` is
// the drawn line's own height there, interpolated the way the path is, so the
// dot sits on the stroke rather than beside it.
function readAt(line, ms, sy) {
  const pts = line.points;
  if (!pts.length || ms < pts[0][0] || ms > pts[pts.length - 1][0]) return null;

  let i = 0;
  while (i < pts.length - 1 && pts[i + 1][0] <= ms) i++;
  const [t0, v0] = pts[i];
  const next = pts[i + 1];
  let y = sy(v0);
  if (next && next[0] > t0) {
    const k = (ms - t0) / (next[0] - t0);
    y = sy(v0 + (next[1] - v0) * k);
  }
  return { value: v0, y: y };
}

const RANGE_PRESETS = [
  { label: '1Y', months: 12 },
  { label: '3Y', months: 36 },
  { label: 'All', months: null },
];

function rangeFor(preset, first, last) {
  if (!preset || !preset.months) return { from: first, to: last };
  const d = new Date(last + 'T00:00:00Z');
  d.setUTCMonth(d.getUTCMonth() - preset.months);
  const from = d.toISOString().slice(0, 10);
  return { from: from < first ? first : from, to: last };
}

const isoDate = (ms) => new Date(ms).toISOString().slice(0, 10);

const monthYear = (ms) => new Date(ms).toLocaleString('en', {
  month: 'short', year: 'numeric', timeZone: 'UTC',
});

return {
  COLUMN_GROUPS: COLUMN_GROUPS,
  NUMERIC_KEYS: NUMERIC_KEYS,
  DEFAULT_VISIBLE: DEFAULT_VISIBLE,
  NARROW_HIDDEN: NARROW_HIDDEN,
  SEARCH_ALWAYS: SEARCH_ALWAYS,
  shortTitle: shortTitle,
  orderColumns: orderColumns,
  isEmptyValue: isEmptyValue,
  fmtInt: fmtInt,
  fmtDelta: fmtDelta,
  filterSort: filterSort,
  SERIES_COLORS: SERIES_COLORS,
  DASH: DASH,
  DASH_CYCLE: DASH_CYCLE,
  SWATCH: SWATCH,
  chartGeometry: chartGeometry,
  readAt: readAt,
  RANGE_PRESETS: RANGE_PRESETS,
  rangeFor: rangeFor,
  isoDate: isoDate,
  monthYear: monthYear,
};
})();
