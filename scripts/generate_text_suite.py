import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'src/flying_circus/workloads'
manifest = json.loads((root / 'manifest.json').read_text())
CSV_CODE = r'''
def parse_csv(text):
    rows = []
    row = []
    field = []
    quoted = False
    closed = False
    started = False
    skip_lf = False
    for char in text:
        if skip_lf:
            skip_lf = False
            if char == '\n':
                continue
        if quoted:
            if char == '"':
                quoted = False
                closed = True
            else:
                field.append(char)
        elif closed and char == '"':
            field.append('"')
            quoted = True
            closed = False
        elif char == ',':
            row.append(''.join(field))
            field = []
            closed = False
            started = False
        elif char == '\n' or char == '\r':
            if row or started or closed or field:
                row.append(''.join(field))
            rows.append(row)
            row = []
            field = []
            closed = False
            started = False
            skip_lf = char == '\r'
        elif closed:
            raise ValueError('Unexpected character after closing quote')
        elif char == '"':
            if started:
                raise ValueError('Quote inside unquoted field')
            quoted = True
            started = True
        else:
            field.append(char)
            started = True
    if quoted:
        raise ValueError('Unterminated quoted field')
    if row or started or closed or field:
        row.append(''.join(field))
        rows.append(row)
    return rows


def csv_records(text):
    rows = parse_csv(text)
    if not rows:
        return []
    header = rows[0]
    records = []
    for values in rows[1:]:
        if not values:
            continue
        if len(values) != len(header):
            raise ValueError('CSV field count differs from header')
        records.append(dict(zip(header, values)))
    return records


def csv_row(fields):
    encoded = []
    for field in fields:
        if (len(fields) == 1 and field == '') or ',' in field or '"' in field or '\n' in field or '\r' in field:
            field = '"' + field.replace('"', '""') + '"'
        encoded.append(field)
    return ','.join(encoded) + '\n'

'''

tasks = {
'line_logs': r"""counts = {}
errors = {}
malformed = 0
for line in TEXT.splitlines():
    fields = line.split(' ', 3)
    if len(fields) != 4:
        malformed += 1
        continue
    _, level, service, message = fields
    counts[service] = counts.get(service, 0) + 1
    if level == 'ERROR':
        errors[service] = errors.get(service, 0) + 1
print(malformed)
for service in sorted(counts):
    print(service, counts[service], errors.get(service, 0))
""",
'regex_logs': r"""import re
pattern = re.compile(r'^(\S+) (\S+) "([A-Z]+) ([^" ]+)" ([0-9]{3}) ([0-9]+) ([0-9]+)$')
statuses = {}
latencies = []
malformed = 0
total_bytes = 0
for line in TEXT.splitlines():
    match = pattern.match(line)
    if match is None:
        malformed += 1
        continue
    status = match.group(5)
    statuses[status] = statuses.get(status, 0) + 1
    total_bytes += int(match.group(6))
    latencies.append(int(match.group(7)))
latencies.sort()
print(malformed, total_bytes, latencies[len(latencies) // 2], latencies[len(latencies) * 95 // 100])
for status in sorted(statuses):
    print(status, statuses[status])
""",
'csv_aggregate': CSV_CODE + r"""totals = {}
rejected = 0
for row in csv_records(TEXT):
    if not row['customer'] or not row['cents'].isdigit():
        rejected += 1
        continue
    key = row['month'] + '/' + row['customer']
    totals[key] = totals.get(key, 0) + int(row['cents'])
print(rejected)
for key in sorted(totals):
    print(key, totals[key])
""",
'csv_cleanup': CSV_CODE + r"""output = [csv_row(['id', 'name', 'note'])]
rows = 0
missing = 0
for row in csv_records(TEXT):
    name = row['name'].strip()
    note = row['note'].strip().replace('\n', ' ')
    if not name:
        missing += 1
        continue
    output.append(csv_row([row['id'], name, note]))
    rows += 1
cleaned = ''.join(output)
parsed = parse_csv(cleaned)
assert len(parsed) == rows + 1
print(rows, missing, len(cleaned), sum(len(row[2]) for row in parsed[1:]))
""",
'json_parse': r"""import json
records = json.loads(TEXT)['records']
print(len(records), sum(row['amount_cents'] for row in records), sum(len(row['tags']) for row in records))
""",
'json_transform': r"""import json
records = json.loads(TEXT)['records']
selected = [row for row in records if row['active'] and row['amount_cents'] >= 5000]
selected.sort(key=lambda row: (-row['amount_cents'], row['id']))
totals = {}
for row in selected:
    key = row['team']
    totals[key] = totals.get(key, 0) + row['amount_cents']
result = {'count': len(selected), 'totals': totals, 'top_ids': [row['id'] for row in selected[:10]]}
encoded = json.dumps(result, sort_keys=True)
assert json.loads(encoded) == result
print(encoded)
""",
'json_lines': r"""import json
seen = set()
totals = {}
duplicates = 0
malformed = 0
for line in TEXT.splitlines():
    try:
        row = json.loads(line)
    except ValueError:
        malformed += 1
        continue
    event_id = row['id']
    if event_id in seen:
        duplicates += 1
        continue
    seen.add(event_id)
    team = row['team']
    totals[team] = totals.get(team, 0) + row['amount_cents']
output = []
for team in sorted(totals):
    output.append(json.dumps({'team': team, 'amount_cents': totals[team]}, sort_keys=True))
print(duplicates, malformed, len(seen))
print('\n'.join(output))
""",
}


def fixture(task, target):
    if task.startswith('json'):
        rows = []
        size = 0
        i = 0
        while size < target:
            row = {'id': i, 'team': ('payments', 'search', 'support')[i % 3],
                   'amount_cents': (i * 97) % 10000, 'active': i % 4 != 0,
                   'tags': ['café', '東京'], 'profile': {'name': 'Zoë', 'note': 'quoted "text"'}}
            if task == 'json_lines':
                row['id'] = i - 1 if i % 17 == 1 else i
            text = json.dumps(row, ensure_ascii=False)
            if task == 'json_lines' and i % 101 == 100:
                text = '{invalid'
            rows.append(text)
            size += len(text.encode()) + 1
            i += 1
        return '\n'.join(rows) if task == 'json_lines' else '{"records":[' + ','.join(rows) + ']}'
    if task.startswith('csv'):
        output = io.StringIO()
        writer = csv.writer(output, lineterminator='\n')
        writer.writerow(['id', 'name', 'note'] if task == 'csv_cleanup' else ['customer', 'month', 'cents', 'note'])
        i = 0
        while output.tell() < target:
            note = ('hello, world', 'said "yes"', 'first line\nsecond line', '東京 café')[i % 4]
            if task == 'csv_cleanup':
                writer.writerow([i, '' if i % 23 == 0 else ' Zoë ' + str(i % 31), note])
            else:
                writer.writerow(['' if i % 37 == 0 else 'customer-' + str(i % 20),
                                 '2026-' + str(1 + i % 12).zfill(2),
                                 'invalid' if i % 29 == 0 else str(i * 17 % 10000), note])
            i += 1
        return output.getvalue()
    rows = []
    size = 0
    i = 0
    while size < target:
        if i % 53 == 52:
            line = 'malformed'
        elif task == 'line_logs':
            line = f'2026-01-01T12:00:00Z {("INFO", "WARN", "ERROR")[i % 3]} {("api", "worker", "billing", "search")[i % 4]} request={i} message=café 東京'
        else:
            line = f'192.0.2.{i % 200} 2026-01-01T12:00:00Z "GET /items/{i}" {(200, 404, 503)[i % 3]} {i * 11 % 10000} {i * 7 % 500}'
        rows.append(line)
        size += len(line.encode()) + 1
        i += 1
    return '\n'.join(rows) + '\n'


for task, code in tasks.items():
    for size, target in (('small', 10000), ('medium', 1000000)):
        text = fixture(task, target)
        name = f'text_{task}_{size}'
        path = root / f'{name}.py'
        path.write_text('TEXT = ' + repr(text) + '\n# --- benchmark ---\n' + code)
        result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, check=True)
        manifest[name] = {'file': path.name, 'suite': 'text', 'stdout': result.stdout,
                          'compatibility_probe': True, 'input_bytes': len(text.encode()),
                          'fixture_sha256': hashlib.sha256(text.encode()).hexdigest()}
        print(name, len(text.encode()))
(root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
