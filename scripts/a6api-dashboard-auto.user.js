// ==UserScript==
// @name         A6API local cost log collector
// @namespace    local.codex.a6api
// @version      0.1.2
// @description  Save new A6API request-log rows to a local JSONL archive.
// @match        https://a6api.com/console/log*
// @run-at       document-idle
// @noframes
// @grant        none
// ==/UserScript==

(() => {
  'use strict';

  const ARCHIVE = 'a6api-dashboard-export.jsonl';
  const DB_NAME = 'a6api-local-log-collector';
  const POLL_MS = 60_000;
  const OVERLAP_SECONDS = 120;
  const FIRST_LOOKBACK_SECONDS = 86_400;
  const PAGE_SIZE = 100;
  const MAX_PAGES = 1000;
  const RELOAD_AFTER_NEW_ROWS_MS = 300_000;
  const rates = {
    'gpt-6.1-sol': { input: 0.0264, cache: 0.00132, output: 0.132, write: null },
    'gpt-6-luna': { input: 0.0072, cache: 0.00072, output: 0.036, write: 0.009 },
  };

  const number = value => {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
  };
  const integer = value => {
    const parsed = number(value);
    return parsed !== null && Number.isSafeInteger(parsed) ? parsed : null;
  };
  const localTime = seconds => {
    const date = new Date(seconds * 1000);
    if (!Number.isFinite(date.getTime())) return null;
    const two = value => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())} ` +
      `${two(date.getHours())}:${two(date.getMinutes())}:${two(date.getSeconds())}`;
  };
  const otherFields = raw => {
    if (raw.other && typeof raw.other === 'object') return raw.other;
    if (typeof raw.other !== 'string') return {};
    try {
      const parsed = JSON.parse(raw.other);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch { return {}; }
  };
  const price = (raw, other, field, fallback) => {
    const direct = raw[field] ?? other[field];
    if (direct !== null && direct !== undefined && direct !== '') return number(direct);
    if (number(other.model_price) !== null) return null;
    const ratio = number(other.model_ratio);
    if (ratio !== null) {
      const multiplier = name => other.long_context_applied === true ? (number(other[name]) || 1) : 1;
      if (field === 'input_price_per_million') return ratio * 2 * multiplier('long_context_in_multiplier');
      if (field === 'output_price_per_million' && number(other.completion_ratio) !== null)
        return ratio * 2 * number(other.completion_ratio) * multiplier('long_context_out_multiplier');
      if (field === 'cache_read_price_per_million' && number(other.cache_ratio) !== null)
        return ratio * 2 * number(other.cache_ratio) * multiplier('long_context_cache_read_multiplier');
    }
    return fallback;
  };
  const normalize = (raw, quotaPerUnit) => {
    const other = otherFields(raw);
    const model = raw.model_name ?? raw.model ?? null;
    const profile = rates[model] ?? { input: null, cache: null, output: null, write: null };
    const five = integer(other.cache_creation_tokens_5m);
    const hour = integer(other.cache_creation_tokens_1h);
    let write = integer(other.cache_creation_tokens ?? raw.cache_creation_tokens);
    if (write === null && (five !== null || hour !== null)) write = (five ?? 0) + (hour ?? 0);
    const input = integer(raw.prompt_tokens ?? raw.input_tokens);
    const cache = integer(raw.cache_tokens ?? other.cache_tokens);
    const output = integer(raw.completion_tokens ?? raw.output_tokens);
    const path = raw.request_path ?? other.request_path ?? null;
    const quota = number(raw.quota);
    const mode = raw.gating_mode ?? other.gating_mode;
    const row = {
      timestamp: typeof raw.timestamp2string === 'string' ? raw.timestamp2string : localTime(Number(raw.created_at)),
      request_id: raw.request_id ?? null,
      model,
      channel: raw.channel ? `${raw.channel} - ${raw.channel_name ?? '[unknown]'}` : null,
      reasoning_effort: raw.reasoning_effort ?? null,
      request_path: path,
      input_tokens: input,
      cache_tokens: cache,
      output_tokens: output,
      cache_write_tokens: write,
      input_price_per_million: price(raw, other, 'input_price_per_million', profile.input),
      cache_read_price_per_million: price(raw, other, 'cache_read_price_per_million', profile.cache),
      output_price_per_million: price(raw, other, 'output_price_per_million', profile.output),
      cache_write_price_per_million: price(raw, other, 'cache_write_price_per_million', profile.write),
      displayed_cost_usd: quota !== null && quotaPerUnit !== null && quotaPerUnit > 0
        ? Number((quota / quotaPerUnit).toFixed(6)) : null,
      calculated_reference_cost_usd: null,
      mode: ['gated', 'ungated', 'escalated'].includes(mode) ? mode : 'unknown',
      source: 'a6api-console',
    };
    const needed = [input, cache, output, write, row.input_price_per_million,
      row.cache_read_price_per_million, row.output_price_per_million];
    if (path !== '/v1/messages' && needed.every(value => value !== null) &&
        (write === 0 || row.cache_write_price_per_million !== null) && input >= cache + write) {
      row.calculated_reference_cost_usd = ((input - cache - write) * row.input_price_per_million +
        cache * row.cache_read_price_per_million + output * row.output_price_per_million +
        write * (row.cache_write_price_per_million ?? 0)) / 1e6;
    }
    return row;
  };
  const parseArchive = text => {
    const rows = [];
    for (const line of text.split(/\r?\n/)) {
      if (!line.trim()) continue;
      let row;
      try { row = JSON.parse(line); } catch { throw new Error('Existing archive has invalid JSON; stopped without changing it.'); }
      if (!row || !row.request_id) throw new Error('Existing archive has a row without request_id; stopped.');
      rows.push(row);
    }
    return rows;
  };
  const newRows = (existing, incoming) => {
    const ids = new Set(existing.map(row => String(row.request_id)));
    const novel = [];
    for (const row of incoming) {
      if (!row.request_id || !row.timestamp) continue;
      const id = String(row.request_id);
      if (ids.has(id)) continue;
      ids.add(id);
      novel.push(row);
    }
    return novel;
  };
  const readFile = async (directory, name) => {
    try { return await (await directory.getFileHandle(name)).getFile().then(file => file.text()); }
    catch (error) { if (error.name === 'NotFoundError') return ''; throw error; }
  };
  const writeFile = async (directory, name, contents) => {
    const handle = await directory.getFileHandle(name, { create: true });
    const writable = await handle.createWritable();
    try { await writable.write(contents); await writable.close(); }
    catch (error) { try { await writable.abort(); } catch {} throw error; }
  };
  const saveRows = async (directory, rows) => {
    const original = await readFile(directory, ARCHIVE);
    const existing = parseArchive(original);
    const novel = newRows(existing, rows);
    if (!novel.length) return 0;
    if (original) {
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      const suffix = Math.random().toString(36).slice(2, 10);
      await writeFile(directory, `.a6api-backup-${stamp}-${suffix}.jsonl`, original);
    }
    await writeFile(directory, ARCHIVE, existing.concat(novel).map(row => JSON.stringify(row)).join('\n') + '\n');
    return novel.length;
  };
  const archiveSummary = async directory => {
    const rows = parseArchive(await readFile(directory, ARCHIVE));
    const displayed = rows.reduce((sum, row) => sum + (number(row.displayed_cost_usd) ?? 0), 0);
    return { archived: rows.length, displayed: Number(displayed.toFixed(6)) };
  };
  const fetchPages = async (start, end, userId, fetcher) => {
    const rows = [];
    let total = null;
    for (let page = 1; page <= MAX_PAGES; page++) {
      const params = new URLSearchParams({ p: String(page), page_size: String(PAGE_SIZE), type: '0',
        token_name: '', model_name: '', start_timestamp: String(start), end_timestamp: String(end),
        group: '', request_id: '' });
      const response = await fetcher(`/api/log/self/?${params}`, { method: 'GET', credentials: 'same-origin',
        cache: 'no-store', headers: { 'New-API-User': String(userId) } });
      if (!response.ok) throw new Error(`Dashboard request failed (HTTP ${response.status}); collection stopped.`);
      const result = await response.json();
      const data = result?.data;
      if (result?.success !== true || !Array.isArray(data?.items) || data.items.length > PAGE_SIZE ||
          Number(data.page) !== page || Number(data.page_size) !== PAGE_SIZE ||
          data.total === null || data.total === undefined ||
          !Number.isSafeInteger(Number(data.total)) || Number(data.total) < 0)
        throw new Error('Dashboard response or pagination changed; collection stopped.');
      total = Number(data.total);
      rows.push(...data.items);
      if (rows.length >= total) return rows;
      if (!data.items.length) throw new Error('Dashboard returned an empty page before the end; collection stopped.');
    }
    throw new Error(`More than ${MAX_PAGES} pages; collection stopped without writing partial data.`);
  };

  // Node tests import the pure functions without starting browser work.
  if (typeof window === 'undefined') {
    module.exports = { normalize, parseArchive, newRows, saveRows, fetchPages, archiveSummary };
    return;
  }
  const box = document.createElement('div');
  box.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;max-width:350px;' +
    'background:#17212b;color:#fff;padding:12px;border-radius:8px;box-shadow:0 3px 18px #0008;font:13px sans-serif';
  const status = document.createElement('div');
  status.textContent = 'A6API collector: starting…';
  const action = document.createElement('button');
  action.textContent = 'Choose monitoring folder';
  action.style.cssText = 'margin:8px 8px 0 0;padding:5px 8px;cursor:pointer';
  const pause = document.createElement('button');
  pause.textContent = 'Pause';
  pause.style.cssText = action.style.cssText;
  const change = document.createElement('button');
  change.textContent = 'Change folder';
  change.style.cssText = action.style.cssText;
  box.append(status, action, pause, change);
  (document.body ?? document.documentElement).append(box);
  if (location.origin !== 'https://a6api.com' || !/^\/console\/log\/?$/.test(location.pathname)) {
    status.textContent = `A6API collector inactive on ${location.pathname}; open /console/log.`;
    action.hidden = true;
    pause.hidden = true;
    change.hidden = true;
    return;
  }
  if (!('locks' in navigator) || !('showDirectoryPicker' in window) || !('indexedDB' in window)) {
    status.textContent = 'A6API collector needs Chrome or Edge with folder access and browser locks.';
    action.hidden = true;
    pause.hidden = true;
    change.hidden = true;
    return;
  }
  const state = { directory: null, timer: null, stopped: false, lastSuccess: null, busy: false };

  const openDb = () => new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('settings');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  const setting = async (key, value) => {
    const db = await openDb();
    try {
      return await new Promise((resolve, reject) => {
        const transaction = db.transaction('settings', value === undefined ? 'readonly' : 'readwrite');
        const request = value === undefined
          ? transaction.objectStore('settings').get(key)
          : transaction.objectStore('settings').put(value, key);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
    } finally { db.close(); }
  };
  const fail = error => {
    state.stopped = true;
    clearTimeout(state.timer);
    status.textContent = `A6API collector stopped: ${error.message}`;
    action.textContent = 'Retry after fixing issue';
    action.hidden = false;
  };
  const schedule = () => {
    if (!state.stopped) state.timer = setTimeout(poll, POLL_MS);
  };
  const poll = async () => {
    if (state.stopped || state.busy) return;
    state.busy = true;
    try {
      const permission = await state.directory.queryPermission({ mode: 'readwrite' });
      if (permission !== 'granted') {
        state.stopped = true;
        status.textContent = 'A6API collector paused: folder access needs renewal.';
        action.textContent = 'Restore folder access';
        action.hidden = false;
        return;
      }
      let userId;
      try { userId = JSON.parse(localStorage.getItem('user') ?? 'null')?.id; } catch {}
      if (!Number.isSafeInteger(Number(userId)) || Number(userId) <= 0)
        throw new Error('Sign in to A6API normally, then retry.');
      const previousUser = await setting('accountId');
      if (previousUser !== undefined && previousUser !== null && Number(previousUser) !== Number(userId))
        throw new Error('The signed-in A6API account changed; stopped to avoid mixing accounts.');
      const end = Math.floor(Date.now() / 1000);
      const start = Math.max(0, (state.lastSuccess ?? end - FIRST_LOOKBACK_SECONDS) - OVERLAP_SECONDS);
      status.textContent = 'A6API collector: checking new logs…';
      const result = await navigator.locks.request('a6api-local-log-archive', { ifAvailable: true }, async lock => {
        if (!lock) return { busy: true };
        const raw = await fetchPages(start, end, userId, fetch.bind(window));
        const quotaPerUnit = number(localStorage.getItem('quota_per_unit'));
        const normalized = raw.filter(row => {
          const second = number(row.created_at);
          return second !== null && second >= start && second <= end;
        }).map(row => normalize(row, quotaPerUnit));
        const saved = await saveRows(state.directory, normalized);
        const archive = await archiveSummary(state.directory);
        await setting('accountId', Number(userId));
        await setting('lastSuccess', end);
        state.lastSuccess = end;
        return { seen: raw.length, saved, archive };
      });
      if (result.busy) {
        status.textContent = 'A6API collector: another log tab is writing; waiting.';
      } else {
        status.textContent = `A6API collector: ${result.seen} checked, ${result.saved} new, ` +
          `${result.archive.archived} archived, $${result.archive.displayed.toFixed(6)} displayed. ` +
          `Last check ${new Date().toLocaleTimeString()}.`;
        if (result.saved > 0) {
          const lastReload = Number(sessionStorage.getItem('a6apiCollectorLastReload') || 0);
          if (Date.now() - lastReload >= RELOAD_AFTER_NEW_ROWS_MS) {
            sessionStorage.setItem('a6apiCollectorLastReload', String(Date.now()));
            setTimeout(() => location.reload(), 1500);
          }
        }
      }
      schedule();
    } catch (error) { fail(error); }
    finally { state.busy = false; }
  };
  const begin = async directory => {
    if (directory.name !== 'monitoring') throw new Error('Choose the repository monitoring folder.');
    state.directory = directory;
    state.stopped = false;
    state.lastSuccess = number(await setting('lastSuccess'));
    action.hidden = true;
    await poll();
  };
  action.addEventListener('click', async () => {
    if (state.busy) return;
    try {
      let directory = state.directory;
      if (directory) {
        const granted = await directory.requestPermission({ mode: 'readwrite' });
        if (granted !== 'granted') throw new Error('Folder permission was not granted.');
      } else {
        directory = await showDirectoryPicker({ id: 'a6api-monitoring', mode: 'readwrite' });
        if (directory.name !== 'monitoring') throw new Error('Choose the repository monitoring folder.');
        await setting('directory', directory);
        await setting('lastSuccess', null);
        await setting('accountId', null);
      }
      await begin(directory);
    } catch (error) { fail(error); }
  });
  pause.addEventListener('click', () => {
    state.stopped = true;
    clearTimeout(state.timer);
    status.textContent = 'A6API collector paused.';
    action.textContent = 'Resume';
    action.hidden = false;
  });
  change.addEventListener('click', async () => {
    if (state.busy) {
      status.textContent = 'Wait for the current check to finish before changing folders.';
      return;
    }
    try {
      const directory = await showDirectoryPicker({ id: 'a6api-monitoring', mode: 'readwrite' });
      if (directory.name !== 'monitoring') throw new Error('Choose the repository monitoring folder.');
      state.stopped = true;
      clearTimeout(state.timer);
      await setting('directory', directory);
      await setting('lastSuccess', null);
      await begin(directory);
    } catch (error) { fail(error); }
  });
  (async () => {
    try {
      const directory = await setting('directory');
      if (!directory) {
        status.textContent = 'Choose the repository monitoring folder once to start automatic collection.';
        return;
      }
      state.directory = directory;
      if (await directory.queryPermission({ mode: 'readwrite' }) !== 'granted') {
        status.textContent = 'Folder access needs renewal. Click Restore folder access.';
        action.textContent = 'Restore folder access';
        return;
      }
      await begin(directory);
    } catch (error) { fail(error); }
  })();
})();
