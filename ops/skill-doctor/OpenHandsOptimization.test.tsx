// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OpenHandsOptimization } from '../../web/src/pages/OpenHandsOptimization';
import { I18nProvider } from '../../web/src/i18n';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const row = { id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', runtime: 'openhands', unit: 'F61', role: 'reviewer', model: 'deepseek-v4.1-flash', status: 'failed', rc: 1, started: 1, tokens: 17571, input: 4771, cached: 4608, output: 8192, reasoning: 8192, complete: false, context_complete: false, context: {}, context_requests: [], unused_tools: [], cost: { usd: null, basis: 'Unknown' }, resources: [{ name: 'Full review diff', kind: 'instructions', required: true, tokens: null }], suggestions: [{ id: 'reviewer-thinking', title: 'Request a direct DeepSeek review verdict', role: 'reviewer', available: true, enabled: false, detail: 'Full diff remains required', reason: 'Savings unmeasured' }] };
const overview = { sessions: [row], period_start: 1, period_end: 2, settings: { revision: 'default', values: {} }, operations: [] as any[], evidence: 'Missing counters remain unknown' };
function fake(sessions = [row]) {
  const calls: any[] = []; const operations: any[] = [];
  vi.stubGlobal('fetch', vi.fn(async (_url, init) => {
    const body = JSON.parse(init?.body || '{}'); calls.push(body);
    let response: any = { ...overview, sessions, operations: [...operations] };
    if (body.action === 'preview') response = { id: 'preview', confirmation: 'confirm', before: false, enabled: true, detail: 'Full diff remains required', scope: 'Future SDK reviewers' };
    if (body.action === 'apply') { response = { id: 'operation', target: 'reviewer-thinking', enabled: true, status: 'applied', created_at: 2, session_id: row.id }; operations.push(response); }
    if (body.action === 'verify') response = { status: 'pending', reason: 'Waiting for a new session', measured_savings: null };
    if (body.action === 'undo') { operations[0] = { ...operations[0], status: 'restored' }; response = operations[0]; }
    return { ok: true, json: async () => response };
  })); return calls;
}
function show(view: 'current' | 'recommendations' | 'evidence' = 'recommendations',platform:'all'|'claude'|'openhands'='all') {
  vi.stubGlobal('localStorage', { getItem: () => 'en-US', setItem: vi.fn() });
  return render(<I18nProvider><OpenHandsOptimization view={view} setView={() => {}} platform={platform} /></I18nProvider>);
}
it('uses the original wizard layout with period totals and actual role/session evidence', async () => {
  const calls = fake(); show();
  await screen.findByRole('heading', { name: 'Where would you like to start?' });
  expect(document.querySelector('.opt-decision-grid .opt-choices')).toBeTruthy();
  expect(document.querySelector('.opt-decision-grid .opt-impact')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Review session costs' }));
  await screen.findByRole('heading', { name: 'Period usage and cost' });
  expect(document.querySelectorAll('.opt-cost-metrics > div')).toHaveLength(4);
  expect(screen.getAllByText('17,571').length).toBeGreaterThan(0);
  expect(screen.getByText(/F61 · reviewer · deepseek-v4.1-flash · failed/, { selector: 'small' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'This week' }));
  await waitFor(() => expect(calls.some(call => call.period === 'week')).toBe(true));
});
it('has current-context navigation and required resources instead of separate view tabs', async () => {
  fake(); show('current');
  await screen.findByText('Full review diff');
  expect(screen.getByRole('heading', { name: 'Current usage' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'View optimization suggestions' })).toBeTruthy();
  expect(screen.queryAllByRole('tab')).toHaveLength(0);
  expect(screen.getByText('Required for this role')).toBeTruthy();
});
it('previews, applies, verifies and confirms undo without inference or Codex writes', async () => {
  const calls = fake(); show();
  fireEvent.click(await screen.findByRole('checkbox', { name: row.suggestions[0].title }));
  fireEvent.click(screen.getByRole('button', { name: 'Review change' }));
  await screen.findByLabelText('Optimization preview');
  expect(calls.some(call => call.action === 'apply')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Apply to future SDK runs' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Check subsequent sessions' }));
  await screen.findByText('Waiting for a new session');
  fireEvent.click(screen.getByRole('button', { name: 'Undo this change' }));
  expect(calls.some(call => call.action === 'undo')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Confirm undo' }));
  await screen.findByRole('heading', { name: 'Change restored' });
  expect(calls.map(call => call.action)).toEqual(expect.arrayContaining(['overview', 'preview', 'apply', 'verify', 'undo']));
  expect(calls.some(call => call.action === 'scan' || call.action === 'resume')).toBe(false);
});
it('keeps common SDK controls visibly disabled and non-SDK controls unavailable', async () => {
  fake([{ ...row, runtime: 'codex', suggestions: row.suggestions.map(item => ({ ...item, available: false })) }]); show();
  const checkbox = await screen.findByRole('checkbox', { name: row.suggestions[0].title });
  expect((checkbox as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByRole('checkbox', { name: 'Hide the automatic skill catalog' }) as HTMLInputElement).disabled).toBe(true);
  expect(screen.getAllByText('Runtime control unavailable')).toHaveLength(3);
  expect(screen.queryByText('Already isolated')).toBeNull();
});
it('preserves error/empty-state distinctions and unknown savings', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ error: 'Sign in required' }) }));
  const result = show();
  expect((await screen.findByText('Sign in required')).closest('[role="alert"]')).not.toBeNull();
  expect(screen.queryByText('No sessions to analyze yet', { selector: 'h2' })).toBeNull(); result.unmount();
  fake([]); show(); await screen.findByText(/This does not mean usage was zero/);
});
it('shows Claude receipts in the original wizard without relabelling OpenHands history', async()=>{
  const native={...row,id:'native-receipt',runtime:'claude-code',unit:'F62',model:'claude-sonnet-5-5',
    suggestions:row.suggestions.map(item=>({...item,available:false,reason:'Native CLI control unavailable'}))};
  fake([row,native]);show('recommendations','claude');
  await screen.findByRole('heading',{name:'Where would you like to start?'});
  const select=screen.getByRole('combobox',{name:'Optimization session'}) as HTMLSelectElement;
  expect(select.options.length).toBe(1);expect(select.value).toBe('native-receipt');
  expect(document.querySelector('.opt-steps')).toBeTruthy();expect(document.querySelector('.opt-session-bar')).toBeTruthy();
  expect(screen.getAllByText('Already isolated')).toHaveLength(3);
  expect((screen.getByRole('checkbox',{name:'Hide the automatic skill catalog'}) as HTMLInputElement).disabled).toBe(true);
});
it('shows no pending native configuration change when verifying without an apply',async()=>{
  fake([{...row,runtime:'claude-code',suggestions:[]}]);show('evidence','claude');
  await screen.findByRole('heading',{name:'No pending change'});
  expect(screen.queryByRole('button',{name:'Apply to future SDK runs'})).toBeNull();
});
