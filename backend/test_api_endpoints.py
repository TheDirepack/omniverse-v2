import requests
import time

BASE_URL = "http://localhost:8000"

def test_endpoint(method, path, json=None):
    url = f"{BASE_URL}{path}"
    print(f"Testing {method} {path}...", end=" ", flush=True)
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=json)
        elif method == "PUT":
            response = requests.put(url, json=json)
        elif method == "DELETE":
            response = requests.delete(url)
        
        if response.status_code < 300:
            print(f"SUCCESS ({response.status_code})")
            return response.json()
        else:
            print(f"FAILED ({response.status_code})")
            print(response.text)
            return None
    except Exception as e:
        print(f"ERROR ({type(e).__name__})")
        print(e)
        return None

if __name__ == "__main__":
    # Wait for server to be ready
    print("Waiting for server to start...")
    for _ in range(10):
        try:
            r = requests.get(f"{BASE_URL}/api/health")
            if r.status_code == 200:
                print("Server is up!")
                break
        except:
            pass
        time.sleep(1)
    else:
        print("Server failed to start.")
        exit(1)

    print("\n--- Testing New V1 API ---")
    # Test GET worlds (v1)
    test_endpoint("GET", "/api/v1/db/worlds/list")

    # Test POST world (v1)
    new_world = {
        "world_name": "Test Universe",
        "franchise": "Test Franchise",
        "category": "Test Category"
    }
    test_endpoint("POST", "/api/v1/db/worlds/create", json=new_world)

    # Test GET worlds again (v1)
    test_endpoint("GET", "/api/v1/db/worlds/list")

    print("\n--- Testing Artifacts API (v1) ---")
    # Test GET artifacts (v1)
    test_endpoint("GET", "/api/v1/db/artifacts/search?limit=10")

    print("\n--- Testing Settings API (v1) ---")
    # Test GET settings (v1)
    test_endpoint("GET", "/api/v1/settings/general")

    print("\n--- Testing Settings Providers API (v1) ---")
    # Test GET settings providers (v1)
    test_endpoint("GET", "/api/v1/settings/providers/list")

    print("\n--- Testing Settings Routes API (v1) ---")
    # Test GET settings routes (v1)
    test_endpoint("GET", "/api/v1/settings/routes/list")

