import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { LISTED_CONTRACTS, MODULE_CONTRACTS } from '../src/modules/registry';
import { MODULE_VIEWS } from '../src/modules/views';

const read = (relative: string) => readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8');
const views = read('src/modules/views.ts');
const app = read('src/App.tsx');

const VIEW_ENTRY = /'([a-z0-9-]+)':\s*lazy\(\(\)\s*=>\s*import\('\.\.\/components\/([\w/]+)'\)\.then\(m\s*=>\s*\(\{\s*default:\s*m\.(\w+)\s*\}\)\)\)/g;
const APP_LAZY = /const\s+(\w+)\s*=\s*lazy\(\(\)\s*=>\s*import\(\s*["']\.\/components\/([\w/]+)["']\s*\)\.then\(\s*m\s*=>\s*\(\{\s*default:\s*m\.(\w+)\s*\}\)\s*\)\s*\)/g;

function renderModuleCases(): Map<string, string> {
  const start = app.indexOf('function renderModule');
  assert.ok(start >= 0, 'App.tsx renderModule not found');
  const open = app.indexOf('{', start);
  let depth = 0; let end = open;
  for (; end < app.length; end++) {
    if (app[end] === '{') depth++;
    else if (app[end] === '}' && --depth === 0) break;
  }
  const cases = new Map<string, string>();
  for (const [, id, component] of app.slice(open, end).matchAll(/case\s+'([^']+)':\s*return\s*<(\w+)/g)) {
    assert.ok(!cases.has(id), `duplicate renderModule case ${id}`);
    cases.set(id, component);
  }
  return cases;
}

test('every listed registry module has exactly one view and every view is a listed module', () => {
  const listed = LISTED_CONTRACTS.map(contract => contract.id).sort();
  assert.deepEqual(Object.keys(MODULE_VIEWS).sort(), listed);
  for (const id of listed) assert.equal(typeof MODULE_VIEWS[id as keyof typeof MODULE_VIEWS], 'object', id);
});

test('views.ts imports exactly the component and export named by each contract', () => {
  const entries = [...views.matchAll(VIEW_ENTRY)];
  assert.equal(entries.length, Object.keys(MODULE_VIEWS).length, 'every views.ts entry must match the lazy-import pattern');
  for (const [, id, component, exported] of entries) {
    const contract = MODULE_CONTRACTS.find(item => item.id === id);
    assert.ok(contract, `views.ts names unregistered module ${id}`);
    assert.equal(`src/components/${component}.tsx`, contract.view.component, id);
    assert.equal(exported, contract.view.export, id);
  }
});

test('App.tsx renderModule switch renders the registered view of every listed module and nothing else', () => {
  const lazyImports = new Map([...app.matchAll(APP_LAZY)].map(([, name, component, exported]) => [name, { component, exported }]));
  const cases = renderModuleCases();
  assert.deepEqual([...cases.keys()].sort(), LISTED_CONTRACTS.map(contract => contract.id).sort());
  for (const [id, componentName] of cases) {
    const target = lazyImports.get(componentName);
    assert.ok(target, `${id}: ${componentName} is not a lazy component import in App.tsx`);
    const contract = MODULE_CONTRACTS.find(item => item.id === id)!;
    assert.equal(`src/components/${target.component}.tsx`, contract.view.component, id);
    assert.equal(target.exported, contract.view.export, id);
  }
});
