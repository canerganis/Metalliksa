import json
import subprocess
import time

def test_transient_3d_gpu():
    payload = {
        "method": "transient-3d-gpu",
        "payload": {
            "nx": 64,
            "ny": 64,
            "nz": 32,
            "dx": 2e-6,
            "dy": 2e-6,
            "dz": 2e-6,
            "power_W": 200.0,
            "T_preheat_K": 300.0,
            "alloyId": "ti6al4v",
            "toolpath": {
                "t": [0.0, 100e-6],
                "x": [32e-6, 96e-6],
                "y": [32e-6, 32e-6],
                "p": [200.0, 200.0]
            }
        },
        "id": "test-123"
    }

    print("Running RPC call to lpbf_worker.py with transient-3d-gpu...")
    
    start = time.time()
    proc = subprocess.Popen(
        ['python', 'python/lpbf_worker.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout, stderr = proc.communicate(input=json.dumps(payload) + "\n")
    
    if proc.returncode != 0:
        print("Worker error:", stderr)
        assert False, "Worker exited with error"

    print("Worker Output:")
    print(stdout)
    
    try:
        lines = stdout.strip().split('\n')
        # last line should be the json response
        response = json.loads(lines[-1])
        if "error" in response:
            print("RPC Error:", response["error"])
            assert False, "RPC returned error"
            
        data = response["data"]
        print("Success! Got result:")
        print(f"  Melt volume: {data.get('melt_volume_um3')} um3")
        print(f"  Max temp: {data.get('max_temperature_K')} K")
        print(f"  Keyhole depth: {data.get('keyhole_depth_um')} um")
        print(f"  Device: {data.get('device')}")
        print(f"  Time: {data.get('sim_time_s')} s")
        print(f"  Steps: {data.get('steps')}")
        
    except Exception as e:
        print("Failed to parse response:", e)
        assert False, "Parse error"

if __name__ == "__main__":
    test_transient_3d_gpu()
    print("Test passed successfully.")
