'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { normalize, parseArchive, newRows, saveRows, fetchPages } =
  require('../scripts/a6api-dashboard-auto.user.js');

const raw = (id, second) => ({
  request_id: id,
  created_at: second,
  model_name: 'gpt-6.1-sol',
  prompt_tokens: 1000,
  cache_tokens: 600,
  completion_tokens: 100,
  quota: 850,
  other: JSON.stringify({ cache_creation_tokens: 0, request_path: '/v1/responses' }),
});

class MemoryDirectory {
  constructor() { this.files = new Map(); this.name = 'monitoring'; }
  async queryPermission() { return 'granted'; }
  async requestPermission() { return 'granted'; }
  async getFileHandle(name, options = {}) {
    if (!this.files.has(name)) {
      if (!options.create) throw Object.assign(new Error('missing'), { name: 'NotFoundError' });
      this.files.set(name, '');
    }
    return {
      getFile: async () => ({ text: async () => this.files.get(name) }),
      createWritable: async () => {
        let next = '';
        return {
          write: async text => { next = text; },
          close: async () => { this.files.set(name, next); },
          abort: async () => {},
        };
      },
    };
  }
}

async function browserStartupTest() {
  const files = new MemoryDirectory();
  const values = new Map();
  const db = {
    createObjectStore: () => {}, close: () => {},
    transaction: () => ({ objectStore: () => ({
      get: key => idbRequest(() => values.get(key)),
      put: (value, key) => idbRequest(() => values.set(key, value)),
    }) }),
  };
  const idbRequest = operation => {
    const request = {};
    queueMicrotask(() => { request.result = operation(); request.onsuccess?.(); });
    return request;
  };
  const indexedDB = { open: () => {
    const request = {};
    queueMicrotask(() => {
      request.result = db;
      request.onupgradeneeded?.();
      request.onsuccess?.();
    });
    return request;
  } };
  const elements = [];
  let fetchCount = 0;
  const script = fs.readFileSync(path.join(__dirname, '../scripts/a6api-dashboard-auto.user.js'), 'utf8');
  const makePage = (userId = 42, pathname = '/console/log') => {
    const document = {
      createElement: () => ({ style: {}, hidden: false, listeners: {}, children: [],
        append(...items) { this.children.push(...items); },
        addEventListener(name, handler) { this.listeners[name] = handler; } }),
      body: { append(item) { elements.push(item); } },
    };
    const storage = new Map();
    const context = {
      window: { showDirectoryPicker: async () => files, indexedDB },
      document, indexedDB,
      navigator: { locks: { request: async (_name, _options, callback) => callback({}) } },
      location: { origin: 'https://a6api.com', pathname, reload: () => {} },
      localStorage: { getItem: key => key === 'user' ? JSON.stringify({ id: userId }) : '1000000' },
      sessionStorage: { getItem: key => storage.get(key) ?? null,
        setItem: (key, value) => storage.set(key, value) },
      showDirectoryPicker: async () => files,
      fetch: async () => {
        fetchCount++;
        return { ok: true, json: async () => ({ success: true, data: { page: 1, page_size: 100,
          total: 1, items: [raw('live-one', Math.floor(Date.now() / 1000) - 1)] } }) };
      },
      setTimeout: () => 1, clearTimeout: () => {},
      console: { info: () => {} },
      URLSearchParams, Date, Math,
    };
    vm.runInNewContext(script, context, { filename: 'a6api-dashboard-auto.user.js' });
    return elements.at(-1);
  };
  const first = makePage();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(first.children[0].textContent, /Choose the repository/);
  await first.children[1].listeners.click();
  assert.equal(parseArchive(files.files.get('a6api-dashboard-export.jsonl')).length, 1);
  assert.equal(values.get('accountId'), 42);
  assert.ok(values.get('lastSuccess') > 0);
  const second = makePage();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(second.children[0].textContent, /0 new, 1 archived, \$0\.000850 displayed/);
  assert.equal(parseArchive(files.files.get('a6api-dashboard-export.jsonl')).length, 1);
  assert.equal(fetchCount, 2);
  const changedAccount = makePage(43);
  await new Promise(resolve => setImmediate(resolve));
  assert.match(changedAccount.children[0].textContent, /account changed/);
  assert.equal(fetchCount, 2);
  const trailingSlash = makePage(42, '/console/log/');
  await new Promise(resolve => setImmediate(resolve));
  assert.match(trailingSlash.children[0].textContent, /0 new, 1 archived, \$0\.000850 displayed/);
  assert.equal(fetchCount, 3);
}

async function main() {
  const one = normalize(raw('one', 1_700_000_000), 1_000_000);
  assert.equal(one.displayed_cost_usd, 0.00085);
  assert.equal(one.cache_tokens, 600);
  assert.equal(one.calculated_reference_cost_usd,
    (400 * 0.0264 + 600 * 0.00132 + 100 * 0.132) / 1e6);
  assert.equal(normalize({ ...raw('other', 1_700_000_001), model_name: 'unknown' }, 1_000_000)
    .calculated_reference_cost_usd, null);
  assert.equal(normalize({ ...raw('messages', 1_700_000_002),
    other: '{"cache_creation_tokens":0,"request_path":"/v1/messages"}' }, 1_000_000)
    .calculated_reference_cost_usd, null);

  const directory = new MemoryDirectory();
  assert.equal(await saveRows(directory, [one]), 1);
  assert.equal(await saveRows(directory, [one]), 0);
  const two = normalize(raw('two', 1_700_000_001), 1_000_000);
  assert.equal(await saveRows(directory, [one, two, two]), 1);
  const archive = parseArchive(directory.files.get('a6api-dashboard-export.jsonl'));
  assert.deepEqual(archive.map(row => row.request_id), ['one', 'two']);
  assert.equal([...directory.files.keys()].filter(name => name.startsWith('.a6api-backup-')).length, 1);
  assert.deepEqual(newRows(archive, [one, two]), []);
  assert.throws(() => parseArchive('{bad json}\n'));

  const seen = [];
  const fetcher = async (url, options) => {
    const page = Number(new URL(url, 'https://a6api.com').searchParams.get('p'));
    seen.push({ url, options });
    return { ok: true, json: async () => ({ success: true,
      data: { page, page_size: 100, total: 2, items: [raw(String(page), 1_700_000_000 + page)] } }) };
  };
  const pages = await fetchPages(1_699_999_999, 1_700_000_010, 42, fetcher);
  assert.deepEqual(pages.map(row => row.request_id), ['1', '2']);
  assert.equal(seen.length, 2);
  assert.equal(seen[0].options.credentials, 'same-origin');
  assert.equal(seen[0].options.headers['New-API-User'], '42');
  assert.match(seen[0].url, /start_timestamp=1699999999/);
  await assert.rejects(fetchPages(1, 2, 42, async () => ({ ok: false, status: 401 })), /HTTP 401/);
  await assert.rejects(fetchPages(1, 2, 42, async () => ({ ok: true,
    json: async () => ({ success: true, data: { page: 2, page_size: 100, total: 1, items: [] } })
  })), /pagination changed/);
  await browserStartupTest();
  console.log('PASS: A6API userscript startup, resume, normalization, pagination, deduplication, backup, and failure stops');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
