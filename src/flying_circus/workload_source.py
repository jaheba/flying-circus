MARKER = '# --- benchmark ---\n'


def split_source(source):
    setup, marker, code = source.partition(MARKER)
    return (setup, code) if marker else ('', source)


def prepare(worker, setup, filename):
    if setup:
        stdout, stderr = worker.run(setup, filename)
        if stdout or stderr:
            raise ValueError('Fixture setup produced unexpected output')
