import html


STYLE = """
:root{color-scheme:light dark;--ink:#172b3a;--accent:#087ca7;--sky:#dff3ff;--circus-red:#c92b38;--paper:#fffdf9;--page:#eef3f6;--card-shadow:0 12px 36px #172b3a14;--stripe-white:#fffdf9;--table:#fff;--header-ink:#16405a;--line:#dfedf5;--outline:#bddded;--row:#f4faff;--hover:#e9f6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.6 system-ui,sans-serif}
main{width:calc(100% - 48px);max-width:1180px;min-width:0;overflow-wrap:anywhere;position:relative;z-index:1;margin:-64px auto;padding:38px max(4vw,24px) 70px;background:var(--paper);border:1px solid var(--outline);border-top:5px solid #64c7f2;border-radius:8px;box-shadow:var(--card-shadow)}
body::before,body::after{content:"";display:block;height:112px;background:repeating-linear-gradient(90deg,var(--circus-red) 0 24px,var(--stripe-white) 24px 48px)}
h1{font:700 36px/1.2 Georgia,serif;letter-spacing:-.025em;margin:0 0 24px}
h2{font-size:21px;margin:40px 0 16px}
p{max-width:960px}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(270px,100%),1fr));gap:16px 30px;margin:24px 0}
.facts div{border-bottom:1px solid var(--line);padding-bottom:10px}
.facts dt{font:700 11px ui-monospace,monospace;text-transform:uppercase;color:var(--accent)}
.facts dd{margin:6px 0 0;font:13px/1.6 ui-monospace,monospace}
a{color:var(--accent)}
a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
details{margin-top:24px}summary{cursor:pointer;color:var(--accent)}
.table-wrap{max-width:100%;overflow-x:auto;margin:20px 0 40px;border:1px solid var(--outline);border-radius:8px;overflow-wrap:normal}
table{border-collapse:collapse;width:100%;background:var(--table);font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;font-variant-numeric:tabular-nums}
th,td{text-align:center;padding:14px 18px;border-bottom:1px solid var(--line);white-space:nowrap}
th{background:var(--sky);color:var(--header-ink);font-size:12px}
.runtime-info{font:13px/1.6 ui-monospace,monospace;color:var(--ink)}
table:not(.startup) th:first-child,table:not(.startup) td:first-child{text-align:left}
td:first-child{font-weight:500}
td.unavailable{text-align:center}
tbody tr:nth-child(even){background:var(--row)}
tbody tr:hover{background:var(--hover)}
td[title]{cursor:help;text-decoration:underline dotted;text-underline-offset:4px}
th button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer;text-align:inherit}
th button+button{margin-left:12px}
th button:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
th .sort-controls{display:block;margin-top:6px;font-size:10px;font-weight:400}
strong{font-weight:800}
code{font-size:12px;overflow-wrap:anywhere}
[hidden]{display:none!important}
.diff-filter{display:flex;align-items:center;flex-wrap:wrap;gap:12px 24px;margin-top:24px}
.diff-filter label{cursor:pointer}.diff-filter input{accent-color:var(--accent);margin-right:8px}
#benchmark-count{font-size:13px;color:var(--accent)}
.chart-legend{font-size:12px;color:var(--accent)}
.inline-measurement{display:inline-flex;align-items:center;gap:7px}
.inline-chart{display:inline-block;position:relative;width:9px;height:28px;background:var(--row);border-radius:2px;vertical-align:middle}
.chart-bar{position:absolute;left:0;width:100%;background:var(--accent);border-radius:2px}
.inline-chart.better .chart-bar{background:#269bd0}
.inline-chart.worse .chart-bar{background:#dd5967}
.chart-reference{position:absolute;bottom:50%;left:-2px;right:-2px;border-top:1px solid var(--ink);z-index:1}
@media(max-width:850px){th,td{padding:12px}main{width:calc(100% - 24px);margin:-64px auto;padding:26px 18px 40px}h1{font-size:28px}}
@media(max-width:600px){main{padding:24px 12px 32px}h2{font-size:18px}th,td{padding:10px 12px}table:not(.startup) th:first-child,table:not(.startup) td:first-child{position:sticky;left:0;z-index:1;min-width:120px;max-width:150px;white-space:normal;overflow-wrap:anywhere;background:var(--table);border-right:1px solid var(--outline)}table:not(.startup) th:first-child{background:var(--sky)}table:not(.startup) tbody tr:nth-child(even) td:first-child{background:var(--row)}table:not(.startup) tbody tr:hover td:first-child{background:var(--hover)}}
@media screen and (prefers-color-scheme:dark){:root{--ink:#e5edf3;--accent:#7dd3fc;--sky:#203a4e;--circus-red:#8c3a46;--paper:#17212b;--page:#0e151d;--card-shadow:0 12px 36px #0004;--stripe-white:#c8c3ba;--table:#1c2936;--header-ink:#d3efff;--line:#344b5c;--outline:#456174;--row:#20303e;--hover:#294255}}
@media print{:root{color-scheme:light}body::before,body::after{display:none}body{background:white;border:0}main{width:100%;max-width:none;margin:0;padding:20px;border:0;box-shadow:none}th{background:#eee;color:#222}}
"""

SORT_SCRIPT = """
<script>
document.querySelectorAll('table').forEach(table => {
  const body = table.tBodies[0];
  if (!body) return;
  const headers = Array.from(table.querySelectorAll('thead th'));
  headers.forEach((header, column) => {
    const version = header.querySelector('.runtime-version');
    if (version) version.remove();
    const label = header.textContent.trim();
    const paired = table.dataset.paired === 'true' && column > 0;
    if (paired) {
      header.textContent = label;
      if (version) header.append(version);
      const controls = document.createElement('span');
      controls.className = 'sort-controls';
      header.append(controls);
    } else header.textContent = '';
    const target = paired ? header.querySelector('.sort-controls') : header;
    (paired ? ['oneShot', 'repeated'] : ['']).forEach(part => {
      const button = document.createElement('button');
      const name = part === 'oneShot' ? 'One-shot' : part === 'repeated' ? 'Repeated' : label;
      button.type = 'button';
      button.dataset.label = name;
      button.textContent = name + ' ↕';
      button.setAttribute('aria-label', 'Sort ' + label + (part ? ' ' + name : ''));
      target.append(button);
      button.addEventListener('click', () => {
        const ascending = button.dataset.direction !== 'ascending';
        headers.forEach(h => {
          h.removeAttribute('aria-sort');
          h.querySelectorAll('button').forEach(b => {
            delete b.dataset.direction;
            b.textContent = b.dataset.label + ' ↕';
          });
        });
        button.dataset.direction = ascending ? 'ascending' : 'descending';
        header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
        button.textContent = name + (ascending ? ' ↑' : ' ↓');
        const rows = Array.from(body.rows);
        rows.sort((a, b) => {
          const cell = row => {
            const td = row.cells[column];
            const relative = part === 'oneShot' ? 'relativeOneShot' : part === 'repeated' ? 'relativeRepeated' : 'relative';
            if (Object.hasOwn(td.dataset, relative)) return td.dataset[relative];
            return part ? td.dataset[part] : td.textContent.trim();
          };
          const x = cell(a), y = cell(b);
          const missing = v => v === 'n/a' || v === '—' || v === '';
          if (missing(x) || missing(y)) return Number(missing(x)) - Number(missing(y));
          const number = v => Number(v.replace(/[%×]$/, ''));
          const result = Number.isFinite(number(x)) && Number.isFinite(number(y))
            ? number(x) - number(y) : x.localeCompare(y, undefined, {numeric:true});
          return ascending ? result : -result;
        });
        body.append(...rows);
      });
    });
    if (version && !paired) header.append(version);
  });
});
const filter = document.getElementById('significant-only');
if (filter) {
  const rows = Array.from(document.querySelectorAll('tr[data-significant]'));
  const benchmarkRows = rows.filter(row => row.dataset.benchmark !== undefined);
  const total = new Set(benchmarkRows.map(row => row.dataset.benchmark)).size;
  const update = () => {
    rows.forEach(row => { row.hidden = filter.checked && row.dataset.significant !== 'true'; });
    document.querySelectorAll('[data-diff-section]').forEach(section => {
      section.hidden = !Array.from(section.querySelectorAll('tbody tr')).some(row => !row.hidden);
    });
    const visible = new Set(benchmarkRows.filter(row => !row.hidden).map(row => row.dataset.benchmark)).size;
    document.getElementById('benchmark-count').textContent = visible + ' of ' + total + ' benchmarks';
  };
  filter.addEventListener('change', update);
  update();
}
</script>
"""


def page(title, content):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>'
        f'<main>{content}</main>' + SORT_SCRIPT + '</body></html>\n'
    )
