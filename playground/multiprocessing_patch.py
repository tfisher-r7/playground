#: Monkey-patch the multiprocessing.freeze_support() function in order to support posix_spawn().
from subprocess import _args_from_interpreter_flags

import _multiprocessing
import multiprocessing.semaphore_tracker
import multiprocessing.spawn as spawn
import multiprocessing.process
import multiprocessing.util
import multiprocessing
import threading
import warnings
import sys
import os


class _SemaphoreTrackingThread(threading.Thread):
    DEFAULT_SEMAPHORE_TRACKING_THREAD_NAME = "semaphore_tracking_thread"
    IS_DAEMON_THREAD = True

    def __init__(self, read_fd, thread_name=DEFAULT_SEMAPHORE_TRACKING_THREAD_NAME):
        super(_SemaphoreTrackingThread, self).__init__(name=thread_name, daemon=self.IS_DAEMON_THREAD)

        self._shutdown_evt = threading.Event()
        self._read_fd = read_fd

    def run(self):
        cache = set()
        try:
            with open(self._read_fd, 'rb') as f:
                for line in f:
                    try:
                        cmd, name = line.strip().split(b':')
                        if cmd == b'REGISTER':
                            cache.add(name)
                        elif cmd == b'UNREGISTER':
                            cache.remove(name)
                        else:
                            raise RuntimeError('[{}] Unrecognized command {}'.format(self.__class__.__name__, cmd))
                    except Exception:
                        try:
                            sys.excepthook(*sys.exc_info())
                        except:
                            pass
        finally:
            if cache:
                try:
                    warnings.warn("[{}] There appear to be {} leaked semaphores".format(
                        self.__class__.__name__, len(cache)
                    ))
                except Exception:
                    pass

                for name in cache:
                    name = name.decode('ascii')
                    try:
                        _multiprocessing.sem_unlink(name)
                    except Exception as e:
                        warnings.warn('[{}] {}: {}'.format(self.__class__.__name__, name, e))


class SemaphoreTracker(multiprocessing.semaphore_tracker.SemaphoreTracker):
    def __init__(self):
        self._lock = threading.Lock()
        self._tracker = None
        self._read_fd = None
        self._write_fd = None

    @property
    def _fd(self):
        return self._write_fd

    @_fd.setter
    def _fd(self, fd):
        self._write_fd = fd

    def ensure_running(self):
        with self._lock:
            if self._tracker is not None:
                return

            #: Create a pipe which will be used to track the creation/deletion of semaphores.
            r, w = os.pipe()
            print("Created pipe (R: {}, W: {})".format(r, w))

            self._read_fd = r
            self._write_fd = w

            self._tracker = _SemaphoreTrackingThread(read_fd=r)
            self._tracker.start()


class MultiprocessingPatch:
    SIG_STARTING_FORK_SERVER = 'from multiprocessing.forkserver import main'

    def __init__(self, stdout=sys.stdout, stderr=sys.stderr):
        self.stdout = stdout
        self.stderr = stderr

    def freeze_support(self):
        #: Prevent the "spawn" subprocess creation routines from reading the __main__ method of the target module.
        multiprocessing.process.ORIGINAL_DIR = None

        #: Define a function for determining if the interpreter is executing inlined Python code.
        def _is_executing_inline_python_code():
            return \
                len(sys.argv) >= 2 and \
                set(sys.argv[1:-2]) == set(_args_from_interpreter_flags()) and sys.argv[-2] == '-c'

        if _is_executing_inline_python_code():
            code = sys.argv[-1]
            if code.startswith(self.SIG_STARTING_FORK_SERVER):
                exec(sys.argv[-1])
                sys.exit()

        if spawn.is_forking(sys.argv):
            kwargs = {}
            for arg in sys.argv[2:]:
                k, v = arg.split('=')
                if v == 'None':
                    kwargs[k] = None
                else:
                    kwargs[k] = int(v)

            spawn.spawn_main(**kwargs)
            sys.exit()


def mp_posix_spawn_support():
    multiprocessing.semaphore_tracker._semaphore_tracker = semaphore_tracker = SemaphoreTracker()
    for attr in "ensure_running", "register", "unregister", "getfd":
        setattr(multiprocessing.semaphore_tracker, attr, getattr(semaphore_tracker, attr))

    multiprocessing.freeze_support = spawn.freeze_support = MultiprocessingPatch().freeze_support
