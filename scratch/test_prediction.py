import requests
import json

url = "http://localhost:5000/api/predict"
payload = {
    "brand": "HP",
    "cpu_brand": "Intel",
    "cpu_tier": "I5",
    "cpu_cores": 6,
    "cpu_threads": 12,
    "Ram": 16,
    "Ram_type": "DDR4",
    "ROM": 512,
    "ROM_type": "SSD",
    "gpu_brand": "NVIDIA",
    "gpu_vram": 4,
    "display_size": 15.6,
    "resolution_width": 1920,
    "resolution_height": 1080,
    "OS": "Windows 11 OS",
    "warranty": 1
}

try:
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")
