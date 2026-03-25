#!/usr/bin/env python
"""Test analysis routes directly using FastAPI TestClient."""

import sys
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

print("\nTesting Analysis Routes:")
print("=" * 60)

# Test 1: GET /api/analysis/{id}/repo
print("\n1. GET /api/analysis/test-id/repo")
response = client.get("/api/analysis/test-id/repo")
print("   Status: " + str(response.status_code))
if response.status_code >= 400:
    print("   Error: " + response.text[:200])

# Test 2: POST /api/analysis/create-pr-safe
print("\n2. POST /api/analysis/create-pr-safe")
test_payload = {
    "analysisId": "test-id",
    "repo": "owner/repo",
    "title": "test",
    "description": "test",
    "baseBranch": "main",
    "sourceBranch": "feature",
    "draft": False,
    "userId": "test-user",
    "commitMessage": "test commit"
}
response = client.post("/api/analysis/create-pr-safe", json=test_payload)
print("   Status: " + str(response.status_code))
if response.status_code >= 400:
    print("   Error: " + response.text[:200])

# Test 3: GET /api/analysis/{id}/github-status
print("\n3. GET /api/analysis/test-id/github-status")
response = client.get("/api/analysis/test-id/github-status")
print("   Status: " + str(response.status_code))
if response.status_code >= 400:
    print("   Error: " + response.text[:200])

print("\n" + "=" * 60)
print("If status codes are 404, the routes are NOT registered.")
print("If status codes are 400+ but not 404, the routes ARE working.")
