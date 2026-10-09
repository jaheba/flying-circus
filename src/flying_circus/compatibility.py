from .workers import WorkloadError


def probe_workload(cls, binary, timeout, code, filename, expected, known_missing=()):
    try:
        with cls(binary, timeout) as worker:
            worker.ready()
            worker.configure(filename)
            stdout, stderr = worker.run(code, filename)
        if stdout != expected or stderr:
            return {'status': 'failed', 'reason': f'Output mismatch: stdout={stdout!r}, stderr={stderr!r}'}
        return {'status': 'supported', 'reason': ''}
    except WorkloadError as error:
        missing_feature = error.exc_type in ('ImportError', 'ModuleNotFoundError', 'NotImplementedError')
        missing_feature |= error.exc_type == 'SyntaxError' and any(
            word in error.message.lower() for word in ('not supported', 'unsupported', 'not implemented'))
        missing_feature |= any(item['type'] == error.exc_type and item['message'] == error.message
                               for item in known_missing)
        return {'status': 'unsupported' if missing_feature else 'failed',
                'reason': str(error), 'exception_type': error.exc_type}
    except (OSError, RuntimeError, TimeoutError) as error:
        return {'status': 'failed', 'reason': str(error)}


def select_workloads(manifest, suite, requested):
    if requested:
        names = list(dict.fromkeys(requested))
    else:
        names = [name for name, spec in manifest.items()
                 if spec.get('suite') != 'internal' and (suite == 'all' or spec.get('suite', 'applications') == suite)]
    unknown = set(names) - manifest.keys()
    if unknown:
        raise ValueError(f'Unknown workloads: {", ".join(sorted(unknown))}')
    return names
