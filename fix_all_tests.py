import sys

# Fix test_htmx_research.py
with open('backend/tests/test_htmx_research.py', 'r') as f:
    lines = f.readlines()

for i in range(len(lines) - 5):
    if "response = client.get(\"/research/\", cookies" in lines[i] and "assert response.status_code == 200" in lines[i+3]:
        lines[i] = '    response = client.get("/research/", cookies={"active_world_id": world_id}, follow_redirects=True)\n'
        lines[i+1] = '    assert response.status_code == 200\n'
        lines[i+2] = '    assert "Database Worlds" in response.text\n'
        break

with open('backend/tests/test_htmx_research.py', 'w') as f:
    f.writelines(lines)

# Fix test_routes.py
with open('backend/tests/test_routes.py', 'r') as f:
    lines = f.readlines()

for i in range(len(lines)):
    if "def test_get_empty(self, api_client):" in lines[i]:
        if "assert len(r.json()) >= TestWorlds.SEED_COUNT" in lines[i+3]:
             lines[i+3] = '        assert len(r.json()) == 0\n'
        break

for i in range(len(lines)):
    if "assert data[\"universe_uuids\"] == payload[\"universe_uuids\"]" in lines[i]:
        lines[i] = '        assert data["uuids"] == payload["universe_uuids"]\n'
        break

with open('backend/tests/test_routes.py', 'w') as f:
    f.writelines(lines)
