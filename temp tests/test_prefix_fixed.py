from fastapi import APIRouter
from fastapi.testclient import TestClient
router = APIRouter(prefix='/runs')
def tiering(): return {'ok': True}
router.add_api_route('/tiering', tiering, methods=['POST'])
client = TestClient(router)
r = client.post('/tiering')
print(f"Status: {r.status_code}")
print(f"Text: {r.text}")
