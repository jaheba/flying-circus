import json
import queue
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .protocol import monty_pb2 as pb

PROTOCOL_VERSION = 5
MAX_FRAME = 64 * 1024 * 1024


def read_exact(stream, length):
    chunks = bytearray()
    while len(chunks) < length:
        chunk = stream.read(length - len(chunks))
        if not chunk:
            raise EOFError('Worker closed stdout during a response')
        chunks.extend(chunk)
    return bytes(chunks)


class WorkloadError(RuntimeError):
    def __init__(self, exc_type, message):
        self.exc_type = exc_type
        self.message = message
        super().__init__(f'{exc_type}: {message}')


class Worker:
    def __init__(self, command, timeout, binary_protocol):
        self.timeout = timeout
        self.binary_protocol = binary_protocol
        self.responses = queue.Queue()
        self.stderr = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        except BaseException:
            self.stderr.close()
            raise
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.outgoing = queue.Queue()
        self.writer = threading.Thread(target=self._write, daemon=True)
        self.writer.start()

    def _read(self):
        try:
            while True:
                if self.binary_protocol:
                    length, = struct.unpack('<I', read_exact(self.process.stdout, 4))
                    if length > MAX_FRAME:
                        raise ValueError(f'Worker frame exceeds {MAX_FRAME} bytes')
                    response = pb.ChildEvent.FromString(read_exact(self.process.stdout, length))
                else:
                    line = self.process.stdout.readline(MAX_FRAME + 1)
                    if not line:
                        raise EOFError('Worker closed stdout')
                    if len(line) > MAX_FRAME:
                        raise ValueError('Worker response too large')
                    response = json.loads(line)
                self.responses.put(response)
        except Exception as error:
            self.responses.put(error)

    def receive(self, deadline):
        try:
            response = self.responses.get(timeout=max(0, deadline - time.perf_counter()))
        except queue.Empty:
            self.close()
            raise TimeoutError('Worker response deadline exceeded') from None
        if isinstance(response, Exception):
            self.close()
            raise RuntimeError(f'Worker response failed: {response}') from response
        return response

    def send(self, request):
        if self.binary_protocol:
            payload = request.SerializeToString()
            frame = struct.pack('<I', len(payload)) + payload
        else:
            frame = (json.dumps(request) + '\n').encode()
        self.outgoing.put(frame)

    def _write(self):
        try:
            while (frame := self.outgoing.get()) is not None:
                self.process.stdin.write(frame)
                self.process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as error:
            self.responses.put(error)

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        self.outgoing.put(None)
        self.reader.join(timeout=1)
        self.writer.join(timeout=1)
        self.process.stdin.close()
        self.process.stdout.close()
        self.stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class MontyWorker(Worker):
    def __init__(self, binary, timeout, arguments=()):
        super().__init__([str(binary), *arguments, 'subprocess'], timeout, True)

    def request(self, request, expected):
        deadline = time.perf_counter() + self.timeout
        self.send(request)
        stdout, stderr = [], []
        while True:
            event = self.receive(deadline)
            kind = event.WhichOneof('kind')
            if kind == 'print':
                for segment in event.print.segments:
                    (stdout if segment.stream == pb.PRINT_STREAM_STDOUT else stderr).append(segment.text)
                continue
            if kind == 'error':
                exception = event.error.exception
                raise WorkloadError(exception.exc_type, exception.message)
            if kind != expected:
                raise RuntimeError(f'Expected {expected}, received {kind}: {event}')
            return ''.join(stdout), ''.join(stderr)

    def configure(self, filename):
        self.request(pb.ParentRequest(configure=pb.Configure(
            script_name=filename, protocol_version=PROTOCOL_VERSION,
            monty_version='flying-circus',
        )), 'ok')

    def reset(self):
        self.request(pb.ParentRequest(reset=pb.Reset()), 'ok')

    def run(self, code, filename):
        return self.request(pb.ParentRequest(feed=pb.Feed(code=code)), 'complete')

    def ready(self):
        self.configure('warmup.py')
        self.reset()


class CPythonWorker(Worker):
    def __init__(self, binary, timeout, arguments=()):
        helper = Path(__file__).with_name('cpython_worker.py')
        super().__init__([str(binary), *arguments, '-u', str(helper)], timeout, False)

    def request(self, request):
        deadline = time.perf_counter() + self.timeout
        self.send(request)
        response = self.receive(deadline)
        if not response.get('ok'):
            raise WorkloadError(response.get('exc_type', 'RuntimeError'), response.get('error', 'Worker request failed'))
        return response

    def ready(self):
        response = self.receive(time.perf_counter() + self.timeout)
        if response != {'ready': True}:
            raise RuntimeError(f'Expected readiness response, received {response}')

    def configure(self, filename):
        self.request({'kind': 'reset'})

    def reset(self):
        pass

    def run(self, code, filename):
        result = self.request({'kind': 'run', 'code': code, 'filename': filename})
        return result['stdout'], result['stderr']
