import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from flying_circus.bench import ROOT
from flying_circus.compare import main as compare_main
from flying_circus.memory_collect import collect
from test_compare import run


class MemoryCollectionTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform in ('linux', 'darwin'), 'OS peak accounting')
    def test_worker_peak_rss_and_output_validation(self):
        source = ROOT / 'workloads/startup.py'
        value = collect(sys.executable, 'cpython', 'warm_worker_one_shot', source, 'ready\n', 5)
        self.assertGreater(value, 0)
        with self.assertRaisesRegex(ValueError, 'output mismatch'):
            collect(sys.executable, 'cpython', 'warm_worker_one_shot', source, 'wrong\n', 5)

    def test_report_uses_na_and_keeps_reason_in_tooltip(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            monty, cpython = run(), run()
            for data in (monty, cpython):
                data.update(revision='test', timestamp='test', build_info='', configuration={})
            monty['benchmarks']['app'].update(status='unsupported', median_wall_seconds=None,
                                             median_peak_rss_bytes=None,
                                             compatibility={'reason': 'missing yield'})
            for engine, data in (('monty', monty), ('cpython', cpython)):
                (root / f'{engine}.json').write_text(json.dumps(data))
            compare_main(['--monty-results', str(root / 'monty.json'), '--cpython-results', str(root / 'cpython.json'),
                          '--output', str(root / 'report.html')])
            report = (root / 'report.html').read_text()
            self.assertIn('<td title="missing yield">n/a</td>', report)
            self.assertNotIn('not yet supported', report)
            self.assertIn('whole interpreter process', report)
