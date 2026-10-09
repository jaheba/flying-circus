import os
import platform
import subprocess
from pathlib import Path


def cpu_info():
    model = platform.processor()
    if platform.system() == 'Darwin':
        try:
            model = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    elif platform.system() == 'Linux':
        try:
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                if line.startswith('model name'):
                    model = line.partition(':')[2].strip()
                    break
        except OSError:
            pass
    cores = os.cpu_count()
    return f'{model or platform.machine()} · {cores if cores is not None else "unknown"} logical CPUs'
