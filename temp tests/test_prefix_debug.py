from fastapi import APIRouter
from fastapi.testclient import TestClient
router = APIRouter(prefix='/runs')
def tiering(): return {'ok': True}
router.add_api_route('/tiering', tiering, methods=['POST'])
client = TestClient(router)
for route in router.routes:
    print(f"Path: {route.path}, Methods: {route.methods}")
print(f"Test call /tiering: {client.post('/tiering').status_code}")
print(f"Test call /runs/tiering: {client.post('/runs/tiering').status_code}")
