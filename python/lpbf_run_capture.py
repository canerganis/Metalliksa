"""Internal, read-only completed-job capture. No browser paths or new job queue.

The application owns the directory; hostile concurrent filesystem mutation is
outside this boundary. Import must recheck bytes after a dry run.
"""
import hashlib
import json
from pathlib import Path
import re
from lpbf_evidence import enforce_thermal_balances

MAX_JSON_BYTES = 16 * 1024 * 1024
EXCLUDED = {'result.json', 'result.tmp', 'progress.log'}
RUN_KINDS = {'analytical-screening', 'build-screening', 'transient-thermal',
             'bounded-material-screening', 'gpu-thermal-pilot', 'legacy-unspecified'}


def _validate_bounded_material_screening(result):
    """Validate IN625 bare-plate archive identity without claiming LPBF validity."""
    from in625_bareplate_field import BareplateConfig, _validate
    from in625_thermal_material import (
        LIQUIDUS_K, REFERENCE_TEMPERATURE_K, in625_lpbf_thermal_snapshot,
    )
    settings = result.get('settings')
    material = result.get('material')
    solver = result.get('solver')
    if (not isinstance(settings, dict) or settings.get('jobType') != 'in625-bareplate-field'
            or result.get('jobType') != 'in625-bareplate-field'
            or not isinstance(material, dict) or material != in625_lpbf_thermal_snapshot()
            or result.get('validationStatus') != 'unvalidated-literature-model-screening'
            or result.get('productionReady') is not False
            or not isinstance(solver, dict) or solver.get('id') != 'in625-bareplate-field-v1'
            or solver.get('modelId') != 'in625-bareplate-enthalpy-conduction-v1'
            or solver.get('revision') != '1'
            or not isinstance(solver.get('actualBackend'), str) or not solver['actualBackend']):
        raise ValueError('Invalid bounded IN625 material-screening identity')
    backend = settings.get('backend')
    if (backend != 'cpu' and (not isinstance(backend, str)
            or not re.fullmatch(r'cuda:[0-9]+', backend))):
        raise ValueError('Invalid bounded IN625 backend identity')
    if solver['actualBackend'] != backend:
        raise ValueError('Bounded IN625 backend identity mismatch')
    provenance = result.get('provenance')
    identity = provenance.get('implementationIdentity') if isinstance(provenance, dict) else None
    if (not isinstance(identity, dict) or identity.get('modelId') != solver['modelId']
            or identity.get('solverRevision') != solver['revision']
            or identity.get('materialRevisionSha256') != material['materialRevisionSha256']
            or identity.get('backend') != backend or identity.get('device') != backend):
        raise ValueError('Bounded IN625 provenance identity mismatch')
    config = settings.get('config')
    config_fields = {'shapeXYZ', 'cellSizeM', 'initialTemperatureK', 'dtS', 'steps',
                     'absorbedPowerW', 'spotSigmaM', 'scanStartXM', 'scanYM', 'scanVelocityXMS'}
    if (set(settings) != {'jobType', 'backend', 'config'}
            or not isinstance(config, dict) or set(config) != config_fields):
        raise ValueError('Invalid bounded IN625 settings')
    shape = config.get('shapeXYZ')
    if (not isinstance(shape, list) or len(shape) != 3
            or any(type(n) is not int or n < 2 for n in shape)
            or shape[0] * shape[1] * shape[2] > 1_000_000):
        raise ValueError('Invalid bounded IN625 field dimensions')
    try:
        model_config = BareplateConfig(
            shape_xyz=tuple(shape), cell_size_m=tuple(config['cellSizeM']),
            initial_temperature_K=config['initialTemperatureK'], dt_s=config['dtS'],
            steps=config['steps'], absorbed_power_W=config['absorbedPowerW'],
            spot_sigma_m=config['spotSigmaM'], scan_start_x_m=config['scanStartXM'],
            scan_y_m=config['scanYM'], scan_velocity_x_m_s=config['scanVelocityXMS'],
        )
        if model_config.steps * shape[0] * shape[1] * shape[2] > 2_000_000:
            raise ValueError('IN625 model work exceeds archive limit')
        _validate(model_config)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('Invalid bounded IN625 model inputs') from error
    steps, dt = config.get('steps'), config.get('dtS')
    power = config.get('absorbedPowerW')
    if (type(steps) is not int or steps < 1 or type(dt) not in (int, float) or dt <= 0
            or type(power) not in (int, float) or power < 0):
        raise ValueError('Invalid bounded IN625 energy inputs')
    metrics = result.get('metrics')
    if (not isinstance(metrics, dict) or type(metrics.get('cells')) is not int
            or metrics['cells'] != shape[0] * shape[1] * shape[2]
            or type(metrics.get('peakTemperature_K')) not in (int, float)
            or not REFERENCE_TEMPERATURE_K <= metrics['peakTemperature_K'] <= LIQUIDUS_K
            or type(metrics.get('finalTime_s')) not in (int, float)
            or abs(metrics['finalTime_s'] - steps * dt) > max(1e-15, steps * dt * 1e-12)):
        raise ValueError('Invalid bounded IN625 metrics')
    balance = result.get('energyBalance')
    expected_input = power * dt * steps
    measured_relative = abs(balance['input_J'] - balance['losses_J'] - balance['stored_J']) / max(abs(balance['input_J']), 1e-30) if isinstance(balance, dict) and all(type(balance.get(k)) in (int, float) for k in ('input_J', 'losses_J', 'stored_J')) else float('inf')
    if (not isinstance(balance, dict)
            or any(type(balance.get(k)) not in (int, float) for k in
                   ('input_J', 'losses_J', 'stored_J', 'relativeError'))
            or balance['losses_J'] != 0
            or abs(balance['input_J'] - expected_input) > max(1e-15, abs(expected_input) * 1e-12)
            or balance['stored_J'] < 0 or balance['relativeError'] < 0
            or balance['relativeError'] > 1e-8 or measured_relative > 1e-8
            or abs(balance['relativeError'] - measured_relative) > 1e-12):
        raise ValueError('Invalid bounded IN625 energy closure')
    field = result.get('field')
    if (not isinstance(field, dict) or field.get('artifact') != 'in625-temperature-field-f64le.bin'
            or field.get('shapeXYZ') != shape or field.get('dtype') != 'float64'
            or field.get('encoding') != 'little-endian'
            or field.get('arrayOrder') != 'z,y,x'
            or field.get('scope') != 'final cell-centered temperature field only; no interface interpolation'):
        raise ValueError('Invalid bounded IN625 field artifact identity')


def _is_analytical_screening(result):
    settings = result.get('settings')
    physics = result.get('resolvedPhysics')
    if not isinstance(physics, dict):
        contract = result.get('coreContract')
        physics = contract.get('resolvedPhysics') if isinstance(contract, dict) else None
    return (isinstance(settings, dict) and settings.get('mode') == 'screening'
            and isinstance(physics, dict) and physics.get('transient') is False)


def _directory(folder):
    folder = Path(folder).absolute()
    for parent in [*reversed(folder.parents), folder]:
        if parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)():
            raise ValueError('Capture directory must not contain links')
        if not parent.is_dir(): raise ValueError('Capture directory unavailable')
    return folder


def _path(name):
    if not isinstance(name, str) or len(name) > 512 or re.search(r'[\\:\x00-\x1f]', name):
        raise ValueError('Invalid capture artifact path')
    for part in name.split('/'):
        if (not part or part in ('.', '..') or part.endswith(('.', ' '))
                or re.match(r'^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', part, re.I)):
            raise ValueError('Invalid capture artifact path')


def capture_run(folder, job_id):
    if not isinstance(job_id, str) or not re.fullmatch('[a-f0-9]{32}', job_id):
        raise ValueError('Invalid capture job id')
    folder = _directory(folder)
    result_path = folder/'result.json'
    if result_path.is_symlink() or not result_path.is_file() or result_path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError('Invalid capture result file')
    result_json = result_path.read_bytes().decode('utf-8')
    result = json.loads(result_json)
    run_kind = result.get('runKind')
    if run_kind is not None and (not isinstance(run_kind, str) or run_kind not in RUN_KINDS):
        raise ValueError('Invalid captured run kind')
    settings = result.get('settings')
    gpu_identity = (run_kind == 'gpu-thermal-pilot'
                    or (result.get('jobType') == 'gpu-thermal-pilot'
                        and isinstance(settings, dict)
                        and settings.get('jobType') == 'gpu-thermal-pilot'))
    if gpu_identity:
        if (not isinstance(settings, dict) or settings.get('jobType') != 'gpu-thermal-pilot'
                or result.get('jobType') != 'gpu-thermal-pilot'
                or run_kind != 'gpu-thermal-pilot'):
            raise ValueError('CUDA pilot capture requires its distinct bound archive contract')
        from lpbf_gpu_thermal import enforce_gpu_pilot_result
        enforce_gpu_pilot_result(result, artifact_dir=folder)
    elif run_kind == 'gpu-thermal-pilot':
        raise ValueError('GPU pilot classification conflicts with captured settings')
    is_gpu_pilot = gpu_identity
    if (isinstance(settings, dict) and settings.get('jobType') == 'in625-bareplate-field'
            and run_kind != 'bounded-material-screening'):
        raise ValueError('IN625 bare-plate fields require bounded material-screening classification')
    if run_kind == 'build-screening' and (not isinstance(settings, dict)
            or settings.get('jobType') != 'build-job'):
        raise ValueError('Build screening classification requires captured build-job settings')
    if run_kind == 'analytical-screening' and not _is_analytical_screening(result):
        raise ValueError('Analytical screening classification requires screening mode without transient physics')
    if run_kind == 'bounded-material-screening':
        _validate_bounded_material_screening(result)
    if run_kind == 'transient-thermal' and (not isinstance(settings, dict)
            or settings.get('jobType') not in (None, 'transient-thermal')
            or _is_analytical_screening(result)):
        raise ValueError('Transient thermal classification conflicts with captured settings')
    if run_kind not in ('bounded-material-screening', 'gpu-thermal-pilot'):
        enforce_thermal_balances(result)
    refs = result.get('artifacts')
    if not isinstance(refs, list) or len(refs) > 10000:
        raise ValueError('Capture requires a bounded complete artifact manifest')
    expected, folded = set(), set()
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'path', 'size_bytes', 'sha256'}:
            raise ValueError('Invalid capture manifest entry')
        name = ref['path']; _path(name)
        size, sha = ref['size_bytes'], ref['sha256']
        if (name.lower() in folded or name in EXCLUDED or type(size) is not int
                or size < 0 or size > 2**53-1 or not isinstance(sha, str)
                or not re.fullmatch('[a-f0-9]{64}', sha)):
            raise ValueError('Invalid or duplicate capture artifact')
        expected.add(name); folded.add(name.lower())
    if run_kind == 'bounded-material-screening':
        field = result['field']
        artifact = next((item for item in refs if item['path'] == field['artifact']), None)
        if (artifact is None or field.get('sha256') != artifact['sha256']
                or artifact['size_bytes'] != 8 * result['metrics']['cells']):
            raise ValueError('Bounded IN625 field artifact manifest mismatch')
    actual = set()
    for file in folder.rglob('*'):
        if file.is_symlink() or getattr(file, 'is_junction', lambda: False)():
            raise ValueError('Capture artifact must not be a link')
        if file.is_dir(): continue
        if not file.is_file(): raise ValueError('Capture requires regular files')
        name = file.relative_to(folder).as_posix()
        if name not in EXCLUDED: actual.add(name)
    if actual != expected: raise ValueError('Capture manifest does not cover all output files')
    for ref in refs:
        file = folder/ref['path']
        before = file.stat()
        digest = hashlib.sha256(); size = 0
        with file.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                digest.update(chunk); size += len(chunk)
        after = file.stat()
        if (size != ref['size_bytes'] or digest.hexdigest() != ref['sha256']
                or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
            raise ValueError('Capture artifact integrity failed')
    encoded = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'),
                                      ensure_ascii=True, allow_nan=False)
    # Reject nonfinite values even in fields outside the numerical evidence guard.
    encoded(result)
    if result_path.read_bytes().decode('utf-8') != result_json:
        raise ValueError('Capture result changed during verification')
    if is_gpu_pilot:
        inputs = result['gpuRunContract']['serializedInputs']
        input_json = inputs['requestJson']
        material_json = inputs['materialJson']
        contract_status = 'gpu-pilot-v1-bound'
    else:
        input_json = encoded(result['settings'])
        material_json = encoded(result['material'])
        contract_status = 'core-v1-bound' if 'coreContract' in result else 'legacy-unbound'
    return dict(schemaVersion=1, jobId=job_id, resultJson=result_json,
                inputJson=input_json, materialJson=material_json,
                contractStatus=contract_status,
                **({'runKind': run_kind} if run_kind is not None else {}))
