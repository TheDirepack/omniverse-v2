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

    print("\n--- Testing Worlds API ---")
    # Test GET worlds
    test_endpoint("GET", "/api/worlds")

    # Test POST world
    new_world = {
        "world_name": "Test Universe",
        "franchise": "Test Franchise",
        "category": "Test Category"
    }
    test_endpoint("POST", "/api/worlds", json=new_world)

    # Test GET worlds again
    test_endpoint("GET", "/api/worlds")

    print("\n--- Testing Artifacts API ---")
    # Test GET artifacts
    test_endpoint("GET", "/api/artifacts")

    print("\n--- Testing Settings API ---")
    # Test GET settings
    test_endpoint("GET", "/api/settings")

    print("\n--- Testing Settings Providers API ---")
    # Test GET settings providers
    test_endpoint("GET", "/api/settings/providers")

    print("\n--- Testing Settings Routes API ---")
    # Test GET settings routes
    test_endpoint("GET", "/api/settings/routes")

