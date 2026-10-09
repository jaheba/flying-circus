import html


STYLE = """
:root{color-scheme:light;--ink:#172b3a;--accent:#087ca7;--sky:#dff3ff;--circus-red:#c92b38;--paper:#fffdf9}
*{box-sizing:border-box}
body{margin:0;background:repeating-linear-gradient(90deg,var(--circus-red) 0 28px,var(--paper) 28px 56px);color:var(--ink);font:15px/1.6 system-ui,sans-serif}
main{width:calc(100% - 48px);max-width:1450px;margin:32px auto;padding:38px max(4vw,24px) 70px;background:var(--paper);border-top:5px solid #64c7f2;box-shadow:0 8px 32px #49202b26}
h1{font:700 36px/1.2 Georgia,serif;letter-spacing:-.025em;margin:0 0 24px}
h2{font-size:21px;margin:40px 0 16px}
p{max-width:960px}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px 30px;margin:24px 0}
.facts div{border-bottom:1px solid #d5e8f2;padding-bottom:10px}
.facts dt{font:700 11px ui-monospace,monospace;text-transform:uppercase;color:var(--accent)}
.facts dd{margin:6px 0 0;font:13px/1.6 ui-monospace,monospace}
a{color:var(--accent)}
a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
details{margin-top:24px}summary{cursor:pointer;color:var(--accent)}
.table-wrap{overflow-x:auto;margin:20px 0 40px;border:1px solid #bddded;border-radius:8px}
table{border-collapse:collapse;width:100%;background:white;font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:14px 18px;border-bottom:1px solid #dfedf5;white-space:nowrap}
th{background:var(--sky);color:#16405a;font-size:12px}
.runtime-info{font:13px/1.6 ui-monospace,monospace;color:var(--ink)}
th:first-child,td:first-child{text-align:left}
td:first-child{font-weight:500}
tbody tr:nth-child(even){background:#f4faff}
tbody tr:hover{background:#e9f6ff}
td[title]{cursor:help;text-decoration:underline dotted;text-underline-offset:4px}
th button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer;text-align:inherit}
th button+button{margin-left:12px}
th button:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
th .sort-controls{display:block;margin-top:6px;font-size:10px;font-weight:400}
strong{font-weight:800}
code{font-size:12px;overflow-wrap:anywhere}
@media(max-width:850px){th,td{padding:12px}main{width:calc(100% - 24px);margin:20px auto;padding:26px 18px 40px}h1{font-size:28px}}
@media print{body{background:white;border:0}main{width:100%;max-width:none;margin:0;padding:20px;border:0;box-shadow:none}th{background:#eee;color:#222}}
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
          const cell = row => part ? row.cells[column].dataset[part] : row.cells[column].textContent.trim();
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
</script>
"""


def page(title, content):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>'
        f'<main>{content}</main>' + SORT_SCRIPT + '</body></html>\n'
    )
