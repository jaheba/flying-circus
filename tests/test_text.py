import contextlib
import hashlib
import io
import json
import unittest

from flying_circus.bench import ROOT
from flying_circus.workload_source import split_source, prepare


class TextWorkloadTests(unittest.TestCase):
    def evaluate(self, task, text):
        _, code = split_source((ROOT / 'workloads' / f'text_{task}_small.py').read_text())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(code, {'TEXT': text})
        return output.getvalue()

    def test_line_logs_handle_unicode_and_malformed_lines(self):
        self.assertEqual(self.evaluate('line_logs', 't INFO api hello\nbad\nt ERROR api café 東京\n'),
                         '1\napi 2 1\n')

    def test_regex_logs_aggregate_status_bytes_and_percentiles(self):
        text = '192.0.2.1 t "GET /a" 200 5 10\nbad\n192.0.2.2 t "GET /b" 503 7 90\n'
        self.assertEqual(self.evaluate('regex_logs', text), '1 12 90 90\n200 1\n503 1\n')

    def test_csv_aggregation_handles_quoted_newlines_and_rejections(self):
        text = 'customer,month,cents,note\nx,2026-01,12,"hi,there"\nx,2026-01,8,"a\nb"\n,2026-01,3,no\nx,2026-01,bad,no\n'
        self.assertEqual(self.evaluate('csv_aggregate', text), '2\n2026-01/x 20\n')

    def test_csv_cleanup_preserves_escaped_quotes(self):
        text = 'id,name,note\n1, Zoë ,"said ""yes"", café"\n2,,skip\n'
        self.assertEqual(self.evaluate('csv_cleanup', text), '1 1 40 16\n')

    def test_json_transform_and_parse(self):
        rows = [{'id': 1, 'team': 'a', 'amount_cents': 6000, 'active': True, 'tags': ['東京']},
                {'id': 2, 'team': 'b', 'amount_cents': 9000, 'active': False, 'tags': []}]
        text = json.dumps({'records': rows})
        self.assertEqual(self.evaluate('json_parse', text), '2 15000 1\n')
        result = json.loads(self.evaluate('json_transform', text))
        self.assertEqual(result, {'count': 1, 'totals': {'a': 6000}, 'top_ids': [1]})

    def test_jsonl_deduplicates_and_skips_malformed_records(self):
        row = json.dumps({'id': 1, 'team': 'a', 'amount_cents': 7})
        result = self.evaluate('json_lines', row + '\n{bad\n' + row)
        self.assertEqual(result, '1 1 1\n{"amount_cents": 7, "team": "a"}\n')

    def test_fixture_hashes_and_sizes_are_recorded(self):
        manifest = json.loads((ROOT / 'workloads/manifest.json').read_text())
        names = [name for name, spec in manifest.items() if spec.get('suite') == 'text']
        self.assertEqual(len(names), 14)
        for name in names:
            spec = manifest[name]
            setup, code = split_source((ROOT / 'workloads' / spec['file']).read_text())
            namespace = {}
            exec(setup, namespace)
            data = namespace['TEXT'].encode()
            self.assertEqual(len(data), spec['input_bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), spec['fixture_sha256'])
            self.assertNotIn('TEXT = ', code)

    def test_fixture_preparation_validates_output(self):
        class Worker:
            def run(self, code, filename):
                return 'unexpected', ''
        with self.assertRaisesRegex(ValueError, 'Fixture setup'):
            prepare(Worker(), 'TEXT = "hello"', 'fixture.py')

    def test_one_shot_excludes_fixture_loading_from_latency(self):
        from unittest.mock import patch
        from flying_circus.warm import one_shot_worker
        clock = [0]
        calls = []

        class Worker:
            def __init__(self, *args):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def ready(self):
                clock[0] += 100000000

            def configure(self, filename):
                calls.append('configure')
                clock[0] += 10000000

            def run(self, code, filename):
                calls.append(code)
                clock[0] += 500000000 if code == 'fixture' else 1000000
                return ('', '') if code == 'fixture' else ('checked', '')

        with patch('flying_circus.warm.time.perf_counter_ns', side_effect=lambda: clock[0]):
            stdout, stderr, latency, setup, readiness = one_shot_worker(
                Worker, 'binary', 30, 'benchmark', 'test.py', 'fixture')
        self.assertEqual(calls, ['configure', 'fixture', 'benchmark'])
        self.assertEqual(stdout, 'checked')
        self.assertEqual(latency, 0.001)
        self.assertEqual(setup, 0.51)
        self.assertEqual(readiness, 0.1)

    def native_csv(self):
        _, code = split_source((ROOT / 'workloads/text_csv_cleanup_small.py').read_text())
        definitions = code[:code.index("output = [")]
        namespace = {}
        exec(definitions, namespace)
        return namespace

    def test_native_csv_matches_standard_reader(self):
        import csv
        parser = self.native_csv()['parse_csv']
        cases = ['', '\n', 'a,b,', 'a,b\r\n1,2\r\n', '"",x\n',
                 '"a,b","said ""yes""","first\nsecond"\n',
                 '"a\r\nb",東京," café "\r\n']
        for text in cases:
            with self.subTest(text=text):
                expected = list(csv.reader(io.StringIO(text, newline='')))
                self.assertEqual(parser(text), expected)

    def test_native_csv_writer_round_trips_complex_fields(self):
        import csv
        import random
        native = self.native_csv()
        rng = random.Random(0)
        alphabet = 'abc, "\r\n東京é'
        for fields in ([''], ['single'], ['', ''], ['a', '']):
            encoded = native['csv_row'](fields)
            self.assertEqual(list(csv.reader(io.StringIO(encoded, newline=''))), [fields])
            self.assertEqual(native['parse_csv'](encoded), [fields])
        for _ in range(100):
            fields = [''.join(rng.choice(alphabet) for _ in range(rng.randrange(20))) for _ in range(3)]
            encoded = native['csv_row'](fields)
            self.assertEqual(list(csv.reader(io.StringIO(encoded, newline=''))), [fields])
            self.assertEqual(native['parse_csv'](encoded), [fields])

    def test_native_csv_rejects_invalid_quoting(self):
        parser = self.native_csv()['parse_csv']
        for text in ('"unterminated', 'a"b,c', '"closed"x,y'):
            with self.assertRaises(ValueError):
                parser(text)
