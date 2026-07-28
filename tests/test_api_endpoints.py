from fastapi.testclient import TestClient
from autonomous_media.main import app

client = TestClient(app)

def run_tests():
    print("=== Testing Phase 5 Dashboard API Endpoints ===")
    
    endpoints = [
        "/api/workflows",
        "/api/clips/pending-review",
        "/api/assets"
    ]
    
    for endpoint in endpoints:
        response = client.get(endpoint)
        if response.status_code == 200:
            print(f"[OK] GET {endpoint} -> returned {len(response.json())} items")
        else:
            print(f"[FAIL] GET {endpoint} -> Status {response.status_code}")
            
    # Test POST
    post_resp = client.post("/api/clips/c1/approve")
    if post_resp.status_code == 200:
        print(f"[OK] POST /api/clips/c1/approve -> {post_resp.json()['message']}")
    else:
        print(f"[FAIL] POST /api/clips/c1/approve -> Status {post_resp.status_code}")

if __name__ == "__main__":
    run_tests()
