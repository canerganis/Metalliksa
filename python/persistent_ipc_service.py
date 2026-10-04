#!/usr/bin/env python3
"""
MetalliX Persistent Python HPC Microservice & IPC Worker Daemon
Maintains scientific calculation modules warm in memory, bypassing Python startup & module import overhead.
Exposes:
 1. Ultra-fast UNIX Domain Socket IPC (/tmp/metallix_python_ipc.sock) for direct Node.js streaming.
 2. High-Performance Loopback HTTP Microservice (http://127.0.0.1:5055) for REST execution & diagnostics.

Security model (both channels):
 - Every request must carry the per-process shared secret METALLIX_IPC_TOKEN that the
   Node supervisor (server/processOrchestrator.ts) generates at spawn and passes through
   the environment. HTTP: ``Authorization: Bearer <token>``; UNIX socket: ``"token"`` field.
   The service refuses to start without a token (at least 32 characters).
 - HTTP: no CORS headers at all; requests carrying an ``Origin`` header (browsers) are
   rejected; the ``Host`` header must name the bound loopback address and port (DNS
   rebinding); POST bodies must be ``application/json``.
 - Scripts: only ``python/<name>.py`` or ``<name>.py`` where <name> is in
   ALLOWED_SCRIPT_NAMES, resolved with realpath and required to stay in SCRIPT_DIR.
 - The UNIX socket is created with mode 0o600.
 - A non-loopback METALLIX_IPC_HOST is refused unless METALLIX_IPC_ALLOW_REMOTE=1.
"""

import sys
import os
import io
import re
import hmac
import ipaddress
import json
import time
import socket
import socketserver
import http.server
import threading
import traceback
import signal
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from concurrent.futures.process import BrokenProcessPool
from typing import Dict, Any, Optional, Iterable, Tuple

# Add script directory to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

UNIX_SOCKET_PATH = os.environ.get("METALLIX_IPC_SOCK", "/tmp/metallix_python_ipc.sock")
HTTP_PORT = int(os.environ.get("METALLIX_IPC_PORT", "5055"))
HTTP_HOST = os.environ.get("METALLIX_IPC_HOST", "127.0.0.1")
ALLOW_REMOTE = os.environ.get("METALLIX_IPC_ALLOW_REMOTE", "") == "1"
# Read once and removed from os.environ before the worker pool is created, so neither pool
# workers nor the solver scripts executed in them inherit the secret.
IPC_TOKEN: Optional[str] = os.environ.pop("METALLIX_IPC_TOKEN", None)
MIN_TOKEN_LENGTH = 32

# Number of parallel workers (defaults to CPU count clamped between 2 and 4)
DEFAULT_WORKERS = max(2, min(4, (os.cpu_count() or 2)))
NUM_WORKERS = int(os.environ.get("METALLIX_IPC_WORKERS", DEFAULT_WORKERS))

# List of scientific modules to keep warm in memory
WARM_MODULE_NAMES = [
    "calphad_solver",
    "dft_property_calculator",
    "cnls_fitting_solver",
    "xrd_peak_deconvolution",
    "lpbf_thermal_solver",
    "inverse_alloy_optimizer",
    "pourbaix_solver",
    "battery_corrosion_eis_solver",
    "kinetics_ttt_cct_solver",
    "icme_multiscale_pipeline_solver",
    "stochastic_uq_mmpds_solver",
    "marangoni_pore_instability_solver",
    "part_scale_inherent_strain_solver",
    "stl_slicer_build_time_solver",
    "lpbf_build_job_solver",
    "tafel_corrosion_rate_solver",
    "engine_dispatcher",
]

# Scripts the service may execute: the warm modules plus the scripts that routes/*.ts
# dispatch through runPythonScript without keeping them warm. Anything else in python/
# (tools, tests, this service itself) is refused. test_persistent_ipc_security checks
# this list against the literal script paths in routes/*.ts.
EXTRA_ALLOWED_SCRIPT_NAMES = [
    "battery_corrosion_python_ingest",
    "lpbf_bayesian_optimizer",
]
ALLOWED_SCRIPT_NAMES = frozenset(WARM_MODULE_NAMES) | frozenset(EXTRA_ALLOWED_SCRIPT_NAMES)

_SCRIPT_FILE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.py\Z")
MAX_SCRIPT_ARGS = 64
MAX_TIMEOUT_MS = 600000


class IPCRequestRejected(Exception):
    """A request refused before any script runs; ``status`` is the HTTP status to send."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def as_result(self) -> Dict[str, Any]:
        return {"stdout": "", "stderr": self.message, "exitCode": 1, "error": self.message,
                "code": self.code, "status": self.status}


def _same_dir(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def resolve_script_path(script_dir: str, script: Any,
                        allowed: Iterable[str] = ALLOWED_SCRIPT_NAMES) -> str:
    """Map a request's script reference to an allowlisted file directly inside script_dir.

    Accepted forms are exactly ``python/<name>.py`` and ``<name>.py``. Traversal, absolute
    paths, drive letters, UNC paths, backslashes and nested directories are refused (400);
    names outside the allowlist and symlinks resolving outside script_dir are refused (403).
    """
    if not isinstance(script, str) or not script.strip():
        raise IPCRequestRejected(400, "MISSING_SCRIPT", "Missing script path")
    ref = script.strip()
    if len(ref) > 200 or any(ch in ref for ch in ("\\", ":", "\x00")) or ref.startswith("/"):
        raise IPCRequestRejected(400, "INVALID_SCRIPT_PATH", "Invalid script path")
    parts = ref.split("/")
    if len(parts) == 2 and parts[0] == "python":
        file_name = parts[1]
    elif len(parts) == 1:
        file_name = parts[0]
    else:
        raise IPCRequestRejected(400, "INVALID_SCRIPT_PATH", "Invalid script path")
    if not _SCRIPT_FILE_RE.match(file_name):
        raise IPCRequestRejected(400, "INVALID_SCRIPT_PATH", "Invalid script path")
    if file_name[:-3] not in allowed:
        raise IPCRequestRejected(403, "SCRIPT_NOT_ALLOWED", f"Script not allowed: {file_name}")
    base = os.path.realpath(script_dir)
    full_path = os.path.realpath(os.path.join(base, file_name))
    if not _same_dir(os.path.dirname(full_path), base):
        raise IPCRequestRejected(403, "SCRIPT_OUTSIDE_SCRIPT_DIR",
                                 f"Script resolves outside the scripts directory: {file_name}")
    if not os.path.isfile(full_path):
        raise IPCRequestRejected(404, "SCRIPT_NOT_FOUND", f"Script not found: {script}")
    return full_path


def validate_exec_request(req: Any) -> Tuple[Any, Any, list, int]:
    """Shape checks shared by both channels; returns (script, payload, args, timeout_ms)."""
    if not isinstance(req, dict):
        raise IPCRequestRejected(400, "INVALID_REQUEST", "Request body must be a JSON object")
    args = req.get("args", [])
    if args is None:
        args = []
    if (not isinstance(args, list) or len(args) > MAX_SCRIPT_ARGS
            or not all(isinstance(a, str) for a in args)):
        raise IPCRequestRejected(400, "INVALID_ARGS", "args must be a list of strings")
    timeout_ms = req.get("timeoutMs", 15000)
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, (int, float)) \
            or not (0 < timeout_ms <= MAX_TIMEOUT_MS):
        raise IPCRequestRejected(400, "INVALID_TIMEOUT", f"timeoutMs must be in (0, {MAX_TIMEOUT_MS}]")
    return req.get("script", ""), req.get("payload"), args, int(timeout_ms)


def token_matches(presented: Any, expected: Optional[str]) -> bool:
    """Constant-time comparison; fails closed when no token is configured."""
    if not expected or not isinstance(presented, str):
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def bearer_token(header_value: Optional[str]) -> Optional[str]:
    if not header_value:
        return None
    scheme, _, value = header_value.strip().partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def is_loopback_host(host: str) -> bool:
    if host.strip().lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip().strip("[]")).is_loopback
    except ValueError:
        return False


def allowed_host_headers(bind_host: str, port: int) -> frozenset:
    """Host header values accepted by the HTTP service (anything else: DNS rebinding)."""
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    h = bind_host.strip().lower()
    hosts.add(f"[{h.strip('[]')}]:{port}" if ":" in h.strip("[]") else f"{h}:{port}")
    return frozenset(hosts)


def check_http_headers(headers: Any, *, token: Optional[str], allowed_hosts: Iterable[str],
                       require_json: bool) -> None:
    """Raise IPCRequestRejected unless the request passes Host, Origin, auth and type checks."""
    hosts = headers.get_all("Host") or []
    if len(hosts) != 1 or hosts[0].strip().lower() not in allowed_hosts:
        raise IPCRequestRejected(403, "HOST_NOT_ALLOWED", "Host header not allowed")
    if headers.get("Origin") is not None:
        raise IPCRequestRejected(403, "ORIGIN_NOT_ALLOWED", "Browser-originated requests are not allowed")
    auths = headers.get_all("Authorization") or []
    if len(auths) != 1 or not token_matches(bearer_token(auths[0]), token):
        raise IPCRequestRejected(401, "UNAUTHORIZED", "Missing or invalid IPC token")
    if require_json:
        media_type = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise IPCRequestRejected(415, "UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json")


def validate_startup_config(host: str, token: Optional[str], allow_remote: bool) -> None:
    """Refuse to serve without a usable token or on a non-loopback address unless allowed."""
    if not token or len(token) < MIN_TOKEN_LENGTH:
        raise SystemExit(
            f"[PersistentIPC] Refusing to start: METALLIX_IPC_TOKEN must be set (>= {MIN_TOKEN_LENGTH} "
            "characters). The Node supervisor generates it; set it yourself when launching by hand.")
    if not is_loopback_host(host):
        if not allow_remote:
            raise SystemExit(
                f"[PersistentIPC] Refusing to bind non-loopback METALLIX_IPC_HOST={host!r}; "
                "set METALLIX_IPC_ALLOW_REMOTE=1 to override.")
        sys.stderr.write(
            "[PersistentIPC] WARNING ************************************************************\n"
            f"[PersistentIPC] WARNING: binding NON-LOOPBACK host {host!r} (METALLIX_IPC_ALLOW_REMOTE=1).\n"
            "[PersistentIPC] WARNING: the IPC service executes Python solvers for any client holding the token.\n"
            "[PersistentIPC] WARNING ************************************************************\n")

# =========================================================================
# Worker Subprocess Routines (Run in isolated multi-core processes)
# =========================================================================
_worker_compiled_cache: Dict[str, Any] = {}
_worker_modules: Dict[str, Any] = {}


def _worker_init(script_dir: str, module_names: list):
    """Initializes each process pool worker by adding paths and pre-warming modules."""
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    global _worker_modules, _worker_compiled_cache
    _worker_modules = {}
    _worker_compiled_cache = {}

    for mod_name in module_names:
        # realpath: the key execute_script submits (resolve_script_path returns realpaths).
        py_file = os.path.realpath(os.path.join(script_dir, f"{mod_name}.py"))
        try:
            mod = __import__(mod_name)
            _worker_modules[mod_name] = mod
            if os.path.exists(py_file):
                with open(py_file, "r", encoding="utf-8") as f:
                    _worker_compiled_cache[py_file] = compile(f.read(), py_file, "exec")
        except Exception:
            pass


def _worker_run_script(full_path: str, input_str: str, args: list) -> Dict[str, Any]:
    """
    Executes a script inside an isolated worker process.
    Guarantees independent sys.stdin / sys.stdout / sys.stderr and full CPU concurrency.
    """
    global _worker_compiled_cache

    if full_path not in _worker_compiled_cache:
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                _worker_compiled_cache[full_path] = compile(f.read(), full_path, "exec")
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Compilation failed: {str(e)}",
                "exitCode": 1,
            }

    compiled = _worker_compiled_cache[full_path]

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    old_argv = sys.argv

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    sys.stdin = io.StringIO(input_str)
    sys.stdout = captured_stdout
    sys.stderr = captured_stderr
    sys.argv = [os.path.basename(full_path)] + (args or [])

    env = {
        "__name__": "__main__",
        "__file__": full_path,
        "__package__": None,
    }

    exit_code = 0
    try:
        exec(compiled, env)
    except SystemExit as se:
        exit_code = se.code if isinstance(se.code, int) else 0
    except Exception:
        exit_code = 1
        captured_stderr.write(traceback.format_exc())
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        sys.argv = old_argv

    return {
        "stdout": captured_stdout.getvalue(),
        "stderr": captured_stderr.getvalue(),
        "exitCode": exit_code,
    }


class ConcurrentModuleRegistry:
    """
    Manages warm module imports, pre-compilation, and a high-concurrency ProcessPoolExecutor
    to execute scientific metallurgy & physics computations in parallel across all CPU cores.
    """

    def __init__(self, script_dir: str, num_workers: int = NUM_WORKERS):
        self.script_dir = script_dir
        self.num_workers = num_workers
        self.modules: Dict[str, Any] = {}
        self.compiled_code: Dict[str, Any] = {}
        self.import_times: Dict[str, float] = {}
        self.stats_lock = threading.Lock()
        self.fallback_lock = threading.Lock()
        self.request_count = 0
        self.active_jobs = 0
        self.total_duration_ms = 0.0
        self.start_time = time.time()
        self.pool: Optional[ProcessPoolExecutor] = None

        self.warmup()
        self._init_pool()

    def warmup(self):
        """Eagerly imports all modules and compiles their source code in master process."""
        sys.stderr.write("[PersistentIPC] Warming up scientific modules in memory...\n")
        t0 = time.time()
        for mod_name in WARM_MODULE_NAMES:
            py_file = os.path.realpath(os.path.join(self.script_dir, f"{mod_name}.py"))
            t_mod0 = time.time()
            try:
                mod = __import__(mod_name)
                self.modules[mod_name] = mod
                if os.path.exists(py_file):
                    with open(py_file, "r", encoding="utf-8") as f:
                        code_str = f.read()
                    compiled = compile(code_str, py_file, "exec")
                    self.compiled_code[py_file] = compiled
                    self.compiled_code[f"python/{mod_name}.py"] = compiled
                    self.compiled_code[f"{mod_name}.py"] = compiled

                dt = (time.time() - t_mod0) * 1000.0
                self.import_times[mod_name] = round(dt, 2)
            except Exception as e:
                sys.stderr.write(f"[PersistentIPC] Warning: Failed to pre-warm {mod_name}: {e}\n")

        total_dt = (time.time() - t0) * 1000.0
        sys.stderr.write(
            f"[PersistentIPC] Successfully loaded {len(self.modules)} modules into RAM in {total_dt:.1f}ms\n"
        )

    def _init_pool(self):
        """Spawns or recycles the multi-process worker pool."""
        try:
            if self.pool:
                try:
                    self.pool.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass
            self.pool = ProcessPoolExecutor(
                max_workers=self.num_workers,
                initializer=_worker_init,
                initargs=(self.script_dir, WARM_MODULE_NAMES),
            )
            sys.stderr.write(
                f"[PersistentIPC] ProcessPoolExecutor initialized with {self.num_workers} warm worker processes.\n"
            )
        except Exception as e:
            sys.stderr.write(f"[PersistentIPC] Worker pool creation error: {e}\n")
            self.pool = None

    def execute_script(
        self,
        script_rel_path: str,
        payload: Any,
        args: Optional[list] = None,
        timeout_ms: int = 15000,
    ) -> Dict[str, Any]:
        """
        Executes a script concurrently in a worker process, bypassing GIL constraints.
        Automatically enforces timeouts and falls back to in-process execution if needed.
        """
        start_time = time.perf_counter()
        args = args or []

        # Resolve path: allowlisted names only, contained in script_dir (no traversal).
        try:
            full_path = resolve_script_path(self.script_dir, script_rel_path)
        except IPCRequestRejected as rejected:
            result = rejected.as_result()
            result["durationMs"] = round((time.perf_counter() - start_time) * 1000.0, 2)
            result["warm"] = True
            return result

        # Prepare JSON input string
        if payload is not None:
            input_str = payload if isinstance(payload, str) else json.dumps(payload)
        else:
            input_str = ""

        timeout_sec = max(1.0, float(timeout_ms) / 1000.0)

        with self.stats_lock:
            self.active_jobs += 1

        try:
            # 1. Primary execution via ProcessPoolExecutor
            if self.pool is not None:
                try:
                    future = self.pool.submit(_worker_run_script, full_path, input_str, args)
                    res = future.result(timeout=timeout_sec)
                    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                    with self.stats_lock:
                        self.request_count += 1
                        self.total_duration_ms += duration_ms
                    return {
                        "stdout": res["stdout"],
                        "stderr": res["stderr"],
                        "exitCode": res["exitCode"],
                        "durationMs": duration_ms,
                        "warm": True,
                        "concurrency": "process_pool",
                    }
                except TimeoutError:
                    return {
                        "stdout": "",
                        "stderr": f"Execution timed out after {timeout_ms}ms",
                        "exitCode": 124,
                        "durationMs": round((time.perf_counter() - start_time) * 1000.0, 2),
                        "warm": True,
                        "concurrency": "process_pool",
                    }
                except BrokenProcessPool:
                    sys.stderr.write("[PersistentIPC] BrokenProcessPool detected! Recycling pool...\n")
                    self._init_pool()
                    # Fall through to in-process execution fallback

            # 2. Resilient In-Process Fallback if pool is recovering
            with self.fallback_lock:
                compiled = self.compiled_code.get(full_path)
                if not compiled:
                    with open(full_path, "r", encoding="utf-8") as f:
                        compiled = compile(f.read(), full_path, "exec")
                    self.compiled_code[full_path] = compiled

                old_stdin = sys.stdin
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                old_argv = sys.argv

                captured_stdout = io.StringIO()
                captured_stderr = io.StringIO()
                sys.stdin = io.StringIO(input_str)
                sys.stdout = captured_stdout
                sys.stderr = captured_stderr
                sys.argv = [os.path.basename(full_path)] + args

                env = {
                    "__name__": "__main__",
                    "__file__": full_path,
                    "__package__": None,
                }

                exit_code = 0
                try:
                    exec(compiled, env)
                except SystemExit as se:
                    exit_code = se.code if isinstance(se.code, int) else 0
                except Exception:
                    exit_code = 1
                    captured_stderr.write(traceback.format_exc())
                finally:
                    sys.stdin = old_stdin
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    sys.argv = old_argv

                duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                with self.stats_lock:
                    self.request_count += 1
                    self.total_duration_ms += duration_ms

                return {
                    "stdout": captured_stdout.getvalue(),
                    "stderr": captured_stderr.getvalue(),
                    "exitCode": exit_code,
                    "durationMs": duration_ms,
                    "warm": True,
                    "concurrency": "in_process_fallback",
                }
        finally:
            with self.stats_lock:
                self.active_jobs = max(0, self.active_jobs - 1)

    def get_status(self) -> Dict[str, Any]:
        with self.stats_lock:
            req_count = self.request_count
            tot_duration = self.total_duration_ms
            active_jobs = self.active_jobs

        uptime_sec = round(time.time() - self.start_time, 1)
        avg_latency = round(tot_duration / max(1, req_count), 2) if req_count > 0 else 0.0

        return {
            "status": "online",
            "concurrencyModel": "ProcessPoolExecutor",
            "workerCount": self.num_workers,
            "activeJobs": active_jobs,
            "ipcChannels": {
                "unixSocket": UNIX_SOCKET_PATH,
                "httpMicroservice": f"http://{HTTP_HOST}:{HTTP_PORT}",
            },
            "warmModules": list(self.modules.keys()),
            "compiledScripts": len(self.compiled_code),
            "requestsProcessed": req_count,
            "avgDurationMs": avg_latency,
            "uptimeSeconds": uptime_sec,
            "pythonVersion": sys.version.split()[0],
            "moduleImportTimesMs": self.import_times,
        }

    def shutdown(self):
        """Closes the worker pool cleanly."""
        if self.pool:
            try:
                self.pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass


# Global Registry Singleton
registry = ConcurrentModuleRegistry(SCRIPT_DIR)
WarmModuleRegistry = ConcurrentModuleRegistry


# =========================================================================
# 1. UNIX Domain Socket IPC Server (Low-Latency Binary / JSON Streaming)
# =========================================================================
class UnixIPCServer:
    def __init__(self, sock_path: str, reg: ConcurrentModuleRegistry, token: Optional[str] = None):
        self.sock_path = sock_path
        self.reg = reg
        self.token = token
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.running = False
        self.thread = None

    def start(self):
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass

        # Owner-only from creation (umask) and explicitly afterwards; never world-writable.
        old_umask = os.umask(0o177)
        try:
            self.sock.bind(self.sock_path)
        finally:
            os.umask(old_umask)
        os.chmod(self.sock_path, 0o600)
        self.sock.listen(64)
        self.running = True

        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()
        sys.stderr.write(f"[PersistentIPC] UNIX domain socket listening at {self.sock_path}\n")

    def _accept_loop(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception:
                if not self.running:
                    break

    def _handle_client(self, conn: socket.socket):
        buffer = b""
        try:
            while self.running:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buffer += chunk

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line_str = line.strip().decode("utf-8")
                    if not line_str:
                        continue

                    try:
                        req = json.loads(line_str)
                    except Exception as e:
                        resp = {"error": f"Invalid JSON payload: {str(e)}", "exitCode": 1}
                        conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")
                        continue

                    if not isinstance(req, dict) or not token_matches(req.get("token"), self.token):
                        resp = {"error": "Missing or invalid IPC token", "code": "UNAUTHORIZED",
                                "status": 401, "exitCode": 1}
                        conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")
                        return  # finally closes the connection

                    action = req.get("action", "execute")
                    req_id = req.get("id")

                    if action == "status":
                        status_res = self.reg.get_status()
                        if req_id is not None:
                            status_res["id"] = req_id
                        conn.sendall(json.dumps(status_res).encode("utf-8") + b"\n")
                    elif action == "ping":
                        conn.sendall(json.dumps({"pong": True, "id": req_id}).encode("utf-8") + b"\n")
                    else:
                        try:
                            script, payload, args, timeout_ms = validate_exec_request(req)
                            resolve_script_path(self.reg.script_dir, script)
                            result = self.reg.execute_script(script, payload, args, timeout_ms)
                        except IPCRequestRejected as rejected:
                            result = rejected.as_result()
                        if req_id is not None:
                            result["id"] = req_id

                        conn.sendall(json.dumps(result).encode("utf-8") + b"\n")
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            sys.stderr.write(f"[PersistentIPC] Client connection error: {e}\n")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass


# =========================================================================
# 2. Loopback HTTP Microservice (REST endpoints on 127.0.0.1:5055)
# =========================================================================
class MicroserviceHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Loopback REST handler. No CORS: browsers are not clients of this service.

    Security configuration lives on the server object (see ThreadedHTTPServer):
    ``ipc_token``, ``allowed_hosts`` and ``registry``.
    """

    def log_message(self, format, *args):
        # Silence default access log to keep stdout/stderr clean
        pass

    @property
    def _registry(self) -> "ConcurrentModuleRegistry":
        return getattr(self.server, "registry", None) or registry

    def _send_json(self, status_code: int, data: Any):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if status_code == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="metallix-ipc"')
        self.end_headers()
        self.wfile.write(body)

    _MAX_DRAIN_BYTES = 1 << 20

    def _reject(self, rejected: IPCRequestRejected):
        # Drain a small unread body first: closing a socket with unread data makes some
        # stacks (Windows) reset the connection before the client reads the error.
        if self.command == "POST" and not getattr(self, "_body_read", False):
            try:
                pending = int(self.headers.get("Content-Length", 0))
            except ValueError:
                pending = 0
            if 0 < pending <= self._MAX_DRAIN_BYTES:
                try:
                    self.rfile.read(pending)
                except OSError:
                    pass
        self.close_connection = True
        self._send_json(rejected.status, {"error": rejected.message, "code": rejected.code})

    def _guard(self, require_json: bool) -> bool:
        try:
            check_http_headers(self.headers, token=getattr(self.server, "ipc_token", None),
                               allowed_hosts=getattr(self.server, "allowed_hosts", frozenset()),
                               require_json=require_json)
            return True
        except IPCRequestRejected as rejected:
            self._reject(rejected)
            return False

    def do_GET(self):
        if not self._guard(require_json=False):
            return
        if self.path in ["/status", "/health", "/api/status", "/api/health"]:
            self._send_json(200, self._registry.get_status())
        elif self.path == "/ping":
            self._send_json(200, {"pong": True, "timestamp": time.time()})
        else:
            self._send_json(404, {"error": "Endpoint not found", "path": self.path})

    def do_POST(self):
        self._body_read = False
        if not self._guard(require_json=True):
            return
        if self.path in ["/execute", "/run", "/api/execute", "/api/run"]:
            try:
                content_len = int(self.headers.get("Content-Length", 0))
            except ValueError:
                content_len = -1
            if content_len <= 0:
                return self._reject(IPCRequestRejected(400, "MISSING_BODY", "Missing JSON body"))

            body_bytes = self.rfile.read(content_len)
            self._body_read = True
            try:
                req = json.loads(body_bytes.decode("utf-8"))
            except Exception as e:
                return self._reject(IPCRequestRejected(400, "INVALID_JSON", f"JSON parse error: {str(e)}"))

            try:
                script, payload, args, timeout_ms = validate_exec_request(req)
                resolve_script_path(self._registry.script_dir, script)
            except IPCRequestRejected as rejected:
                return self._reject(rejected)

            result = self._registry.execute_script(script, payload, args, timeout_ms)
            if "id" in req:
                result["id"] = req["id"]
            self._send_json(200, result)

        elif self.path == "/warmup":
            self._registry.warmup()
            self._send_json(200, self._registry.get_status())
        else:
            self._send_json(404, {"error": "Endpoint not found", "path": self.path})


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    ipc_token: Optional[str] = None
    allowed_hosts: frozenset = frozenset()
    registry: Optional["ConcurrentModuleRegistry"] = None


def make_http_server(host: str, port: int, token: Optional[str],
                     reg: Optional["ConcurrentModuleRegistry"] = None) -> ThreadedHTTPServer:
    """Builds the HTTP service with its security configuration (port 0 picks a free port)."""
    httpd = ThreadedHTTPServer((host, port), MicroserviceHTTPHandler)
    httpd.ipc_token = token
    httpd.allowed_hosts = allowed_host_headers(host, httpd.server_address[1])
    httpd.registry = reg
    return httpd


def run_services():
    """Starts both UNIX socket IPC and HTTP microservice."""
    try:
        validate_startup_config(HTTP_HOST, IPC_TOKEN, ALLOW_REMOTE)
    except SystemExit:
        registry.shutdown()
        raise

    # 1. Start UNIX domain socket IPC (skipped on Windows — AF_UNIX bind is unreliable)
    ipc_server = None
    if os.name != "nt":
        try:
            ipc_server = UnixIPCServer(UNIX_SOCKET_PATH, registry, IPC_TOKEN)
            ipc_server.start()
        except Exception as e:
            sys.stderr.write(f"[PersistentIPC] UNIX socket unavailable ({e}); HTTP loopback only.\n")
            ipc_server = None
    else:
        sys.stderr.write("[PersistentIPC] UNIX socket skipped on Windows; HTTP loopback only.\n")

    # 2. Start HTTP microservice
    try:
        httpd = make_http_server(HTTP_HOST, HTTP_PORT, IPC_TOKEN)
        sys.stderr.write(
            f"[PersistentIPC] HTTP microservice listening at http://{HTTP_HOST}:{HTTP_PORT}\n"
        )
    except Exception as e:
        sys.stderr.write(f"[PersistentIPC] HTTP microservice port {HTTP_PORT} bind error: {e}\n")
        httpd = None

    # Handle graceful termination signals
    def handle_signal(sig, frame):
        sys.stderr.write(f"\n[PersistentIPC] Received signal {sig}, shutting down cleanly...\n")
        if ipc_server:
            ipc_server.stop()
        registry.shutdown()
        if httpd:
            threading.Thread(target=httpd.shutdown).start()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Inform supervisor on stdout that microservice is fully ready
    ready_msg = {
        "status": "ready",
        "unixSocket": UNIX_SOCKET_PATH,
        "http": f"http://{HTTP_HOST}:{HTTP_PORT}",
        "modulesWarm": len(registry.modules),
        "warmModules": list(registry.modules.keys()),
        "pythonVersion": sys.version.split()[0],
        "unixSocketActive": ipc_server is not None,
        "httpActive": httpd is not None,
        "workers": registry.num_workers,
        "concurrency": "ProcessPoolExecutor",
    }
    sys.stdout.write(json.dumps(ready_msg) + "\n")
    sys.stdout.flush()

    if httpd:
        httpd.serve_forever()
    else:
        # Keep process alive for UNIX socket if HTTP couldn't bind
        while True:
            time.sleep(1)


if __name__ == "__main__":
    run_services()
