from fastapi import APIRouter
from fastapi.testclient import TestClient
router = APIRouter(prefix='/runs')
def tiering(): return {'ok': True}
router.add_api_route('/tiering', tiering, methods=['POST'])
client = TestClient(router)
print(client.post('/tiering').json())
