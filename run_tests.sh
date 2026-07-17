#!/bin/bash

# Run all tests - backend and UI
set -e

echo "=== Running API Tests ==="
pytest backend/tests/backend/ -v --asyncio-mode=auto

echo ""
echo "=== Running UI Tests ==="
pytest backend/tests/ui/ -v --asyncio-mode=auto

echo ""
echo "=== All Tests Passed ==="
