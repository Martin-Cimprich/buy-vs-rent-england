// End-to-end smoke test of the BUILT calculator.
//
// engine.test.mjs checks the engine's arithmetic. This checks the shipped
// index.html: that it is genuinely self-contained so it works from a download,
// that every control is actually wired to a recompute, that the defaults are
// the paper's baseline, and that no superseded claim survives in the copy.
//
// The wiring checks exist because b_fix once shipped as a select with no
// listener: it rendered, it looked functional, and changing it did nothing.
//
// Run: node calculator/smoke.test.mjs
import { readFileSync } from 'fs';

const html = readFileSync(new URL('./index.html', import.meta.url), 'utf-8');
const FX = JSON.parse(readFileSync(new URL('./engine.fixtures.json', import.meta.url), 'utf-8'));

let failures = 0;
function check(name, ok, detail) {
  if (!ok) failures++;
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${detail !== undefined ? ': ' + detail : ''}`);
}

// ---- 1. It must work from a file:// URL with no network ----
const externalSrc = [...html.matchAll(/\b(?:src|href)\s*=\s*"([^"#]+)"/g)]
  .map(m => m[1])
  .filter(u => !u.startsWith('mailto:'));
const remote = externalSrc.filter(u => /^(https?:)?\/\//.test(u));
const remoteNonLink = remote.filter(u => !html.includes(`href="${u}"`));
check('no external scripts or stylesheets', remoteNonLink.length === 0, remoteNonLink.join(', ') || 'none');
check('no <script src>', !/<script[^>]+\bsrc=/i.test(html));
check('no <link rel=stylesheet>', !/<link[^>]+stylesheet/i.test(html));
check('engine inlined', html.includes('function simulateBuy'));
check('data inlined', html.includes('const CALC_DATA'));
check('no build placeholders left', !html.includes('__ENGINE__') && !html.includes('__DATA__'));
check('has viewport meta for phones', /name="viewport"[^>]*width=device-width/.test(html));

// ---- 2. The same-model claim, and no build/process cruft ----
check('states it runs the paper\'s model', /same model as the paper/i.test(html));
check('links the paper and code', html.includes('github.com/Martin-Cimprich/buy-vs-rent-england'));
check('no FAQ section', !/<h2>FAQ<\/h2>/.test(html));
for (const [phrase, why] of [
  ['never have beaten', 'a cash buyer wins 8% of cohorts'],
  ['never beaten a renter', 'a cash buyer wins 8% of cohorts'],
  ['smaller deposit help', 'the deposit gradient is not monotonic'],
  ['April 2026', 'the sample ends in June 2026'],
  ['entry quarter', 'cohorts are monthly, held five years'],
  ['user-cost literature (2%', 'that figure is from structure-value studies and does not transfer'],
]) {
  check(`no stale claim: "${phrase}"`, !html.includes(phrase), why);
}

// ---- 3. Form wiring: every input the params reader expects must exist ----
const ids = [
  'f_region', 'f_price', 'f_rent', 'f_dep', 'f_rate', 'f_term', 'f_hor',
  'f_maint', 'f_pc', 'f_sc', 'f_g', 'f_opp', 'f_rg',
  'b_region', 'b_start', 'b_dep', 'b_term', 'b_maint', 'b_pc', 'b_sc', 'b_fix',
  'f_chart', 'b_chart', 'b_cohorts', 'pane-forward', 'pane-backtest', 'pane-method',
];
const missing = ids.filter(id => !html.includes(`id="${id}"`));
check('all referenced element ids present', missing.length === 0, missing.join(', ') || 'none');

// readParams reads _dep/_term/_maint/_pc/_sc for both prefixes, and _fix where present
for (const p of ['f', 'b']) {
  for (const f of ['dep', 'term', 'maint', 'pc', 'sc']) {
    check(`${p}_${f} exists for readParams`, html.includes(`id="${p}_${f}"`));
  }
}

// ---- 4. Defaults must be the paper's baseline ----
const B = FX.baseline;
const defaults = [
  ['f_dep', B.deposit_share * 100], ['b_dep', B.deposit_share * 100],
  ['f_term', B.amort_years], ['b_term', B.amort_years],
  ['f_maint', B.maintenance_pct_of_value * 100], ['b_maint', B.maintenance_pct_of_value * 100],
  ['f_pc', +(B.purchase_costs_pct * 100).toFixed(2)], ['b_pc', +(B.purchase_costs_pct * 100).toFixed(2)],
  ['f_sc', +(B.selling_costs_pct * 100).toFixed(2)], ['b_sc', +(B.selling_costs_pct * 100).toFixed(2)],
];
for (const [id, want] of defaults) {
  const m = html.match(new RegExp(`id="${id}"[^>]*value="([^"]+)"`));
  check(`default ${id} = ${want}`, m && Math.abs(parseFloat(m[1]) - want) < 1e-9,
        m ? m[1] : 'not found');
}
const fixSel = html.match(/id="b_fix"[\s\S]{0,240}?<\/select>/);
check('rate-type defaults to the five-year fix',
      !!fixSel && /value="5"\s+selected/.test(fixSel[0]));

// Every control must be wired to a recompute. b_fix shipped once as a <select>
// with no listener, so the five-year fix, the two-year fix and the floating
// rate all returned identical numbers: the control looked functional and did
// nothing. Inputs are wired with 'input', selects with 'change'.
const wired = id => {
  if (new RegExp(`\\['[^\\]]*'${id}'[^\\]]*\\]\\.forEach`).test(html)) return true;
  if (new RegExp(`\\$\\('${id}'\\)\\.addEventListener`).test(html)) return true;
  return new RegExp(`${id}\\b[\\s\\S]{0,80}addEventListener`).test(html);
};
for (const id of ['b_dep', 'b_term', 'b_maint', 'b_pc', 'b_sc', 'b_fix', 'b_region', 'b_start']) {
  check(`${id} triggers a recompute`, wired(id));
}
check('selects bound with change, inputs with input',
      /\['b_region','b_start','b_fix'\]\.forEach\(id => \$\(id\)\.addEventListener\('change'/.test(html));

// ---- 5. Canvas sizing must not be able to bake in a stale width ----
check('canvases sized through prepCanvas', html.includes('function prepCanvas'));
check('prepCanvas refuses an unmeasurable canvas', /if \(!\(W > 40\)/.test(html));

// The design height must come from a cached copy, never from the height
// attribute. Assigning canvas.height WRITES that attribute, so reading the
// design height back from it multiplies by the device pixel ratio on every
// redraw. At dpr 2 that doubles the backing store each time: 360px reached
// 188,743,680px within twenty redraws and the canvas ran out of memory.
check('design height cached, not re-read from the attribute',
      html.includes('canvas.dataset.designHeight'));
check("prepCanvas does not read H from getAttribute('height')",
      !/const H = \+canvas\.getAttribute\('height'\)/.test(html));
check('redraws when a chart container resizes', html.includes('new ResizeObserver'));
check('observes containers, not the canvas itself', html.includes('ro.observe(el.parentElement)'));
check('redraws on load and on font load',
      html.includes("addEventListener('load', redrawGuarded)") && html.includes('document.fonts.ready'));
check('redraws synchronously, not via rAF',
      !/ResizeObserver\(\(\) => \{[\s\S]{0,120}requestAnimationFrame/.test(html));

console.log(failures === 0 ? '\nALL SMOKE TESTS PASSED' : `\n${failures} FAILURES`);
process.exit(failures === 0 ? 0 : 1);
