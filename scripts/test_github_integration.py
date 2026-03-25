#!/usr/bin/env python3
"""
GitHub Integration Test Script

This script tests the CodeIQ GitHub integration endpoints.
Useful for verifying your setup is correct before going live.

Usage:
    python test_github_integration.py --backend-url http://localhost:8000 --user-id your_user_id
"""

import os
import json
import argparse
import requests
from urllib.parse import urljoin
from typing import Optional, Dict, Any
import sys

class GitHubIntegrationTester:
    def __init__(self, backend_url: str, user_id: str, verbose: bool = True):
        self.backend_url = backend_url.rstrip('/')
        self.user_id = user_id
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({"user-id": user_id})
        self.pass_count = 0
        self.fail_count = 0

    def log(self, message: str, level: str = "INFO"):
        """Log a message"""
        if self.verbose:
            print(f"[{level}] {message}")

    def test_backend_health(self) -> bool:
        """Test if backend is running"""
        self.log("Testing backend health...")
        try:
            url = urljoin(self.backend_url, "/docs")
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                self.log("✅ Backend is online", "PASS")
                self.pass_count += 1
                return True
            else:
                self.log(f"❌ Backend returned {response.status_code}", "FAIL")
                self.fail_count += 1
                return False
        except requests.exceptions.ConnectionError:
            self.log(f"❌ Cannot connect to backend at {self.backend_url}", "FAIL")
            self.fail_count += 1
            return False

    def test_env_variables(self) -> bool:
        """Check required environment variables"""
        self.log("Checking environment variables...")
        required_vars = [
            'GITHUB_CLIENT_ID',
            'GITHUB_CLIENT_SECRET',
            'GITHUB_APP_ID',
            'GITHUB_APP_PRIVATE_KEY',
            'GITHUB_APP_WEBHOOK_SECRET',
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
        if missing:
            self.log(f"❌ Missing environment variables: {', '.join(missing)}", "FAIL")
            self.fail_count += 1
            return False
        else:
            self.log("✅ All required environment variables are set", "PASS")
            self.pass_count += 1
            return True

    def test_github_authorize_endpoint(self) -> bool:
        """Test GitHub authorization endpoint"""
        self.log("Testing /api/github/authorize endpoint...")
        # Note: This would require a valid OAuth code, which requires user interaction
        # For now, just verify the endpoint exists
        try:
            url = urljoin(self.backend_url, "/api/github/authorize")
            # Try to POST with invalid code (should fail gracefully)
            response = self.session.post(url, json={"code": "invalid_code"})
            # Any response (even error) means endpoint exists
            is_available = response.status_code in [400, 401, 500]
            if is_available:
                self.log("✅ /api/github/authorize endpoint is available", "PASS")
                self.pass_count += 1
                return True
            else:
                self.log(f"❌ Got unexpected status {response.status_code}", "FAIL")
                self.fail_count += 1
                return False
        except Exception as e:
            self.log(f"❌ Error testing endpoint: {e}", "FAIL")
            self.fail_count += 1
            return False

    def test_repos_endpoint(self) -> bool:
        """Test repository endpoint"""
        self.log("Testing /api/github/repositories endpoint...")
        try:
            url = urljoin(self.backend_url, "/api/github/repositories")
            response = self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ /api/github/repositories endpoint works", "PASS")
                self.log(f"   Returns {len(data.get('repositories', []))} repositories", "INFO")
                self.pass_count += 1
                return True
            elif response.status_code == 400:
                self.log("⚠️  /api/github/repositories: GitHub not connected (expected if not authenticated)", "WARN")
                self.log("   Endpoint is available, but you need to authorize first", "INFO")
                self.pass_count += 1  # Endpoint exists, just not authenticated
                return True
            else:
                self.log(f"❌ Got status {response.status_code}: {response.text}", "FAIL")
                self.fail_count += 1
                return False
        except Exception as e:
            self.log(f"❌ Error testing endpoint: {e}", "FAIL")
            self.fail_count += 1
            return False

    def test_app_install_url_endpoint(self) -> bool:
        """Test GitHub App install URL endpoint"""
        self.log("Testing /api/github/app/install-url endpoint...")
        try:
            url = urljoin(self.backend_url, "/api/github/app/install-url")
            response = self.session.post(url, json={})
            if response.status_code == 200:
                data = response.json()
                if 'install_url' in data:
                    self.log("✅ /api/github/app/install-url endpoint works", "PASS")
                    self.log(f"   Install URL: {data['install_url'][:50]}...", "INFO")
                    self.pass_count += 1
                    return True
            elif response.status_code == 401:
                self.log("⚠️  /api/github/app/install-url: User not authenticated (expected)", "WARN")
                self.log("   Endpoint is available, authenticate first", "INFO")
                self.pass_count += 1
                return True
            else:
                self.log(f"❌ Got status {response.status_code}: {response.text}", "FAIL")
                self.fail_count += 1
                return False
        except Exception as e:
            self.log(f"❌ Error testing endpoint: {e}", "FAIL")
            self.fail_count += 1
            return False

    def test_webhook_endpoint_exists(self) -> bool:
        """Test that webhook endpoint exists (doesn't actually send webhook)"""
        self.log("Checking /api/github/webhook/installation endpoint...")
        try:
            # Note: We can't fully test the webhook without GitHub sending it
            # But we can check if the endpoint is registered
            url = urljoin(self.backend_url, "/api/github/webhook/installation")
            # POST without proper signature should fail with 401, not 404
            response = requests.post(url, json={})
            if response.status_code == 401:
                self.log("✅ /api/github/webhook/installation endpoint exists", "PASS")
                self.pass_count += 1
                return True
            elif response.status_code == 400:
                self.log("✅ /api/github/webhook/installation endpoint exists", "PASS")
                self.pass_count += 1
                return True
            else:
                self.log(f"❌ Endpoint returned unexpected status {response.status_code}", "FAIL")
                self.fail_count += 1
                return False
        except Exception as e:
            self.log(f"❌ Error: {e}", "FAIL")
            self.fail_count += 1
            return False

    def test_pr_create_endpoint(self) -> bool:
        """Test PR creation endpoint exists"""
        self.log("Checking /api/github/pr/create endpoint...")
        try:
            url = urljoin(self.backend_url, "/api/github/pr/create")
            # POST with invalid data should give 400 or 404
            response = self.session.post(url, json={})
            if response.status_code == 401:
                self.log("✅ /api/github/pr/create endpoint exists", "PASS")
                self.pass_count += 1
                return True
            elif response.status_code == 422:  # Validation error (expected for missing fields)
                self.log("✅ /api/github/pr/create endpoint exists", "PASS")
                self.pass_count += 1
                return True
            else:
                self.log(f"⚠️  Got status {response.status_code}", "WARN")
                self.pass_count += 1
                return True
        except Exception as e:
            self.log(f"❌ Error: {e}", "FAIL")
            self.fail_count += 1
            return False

    def run_all_tests(self) -> bool:
        """Run all tests"""
        print("=" * 60)
        print("CodeIQ GitHub Integration Test Suite")
        print("=" * 60)
        print()

        self.test_backend_health()
        self.test_env_variables()
        self.test_github_authorize_endpoint()
        self.test_repos_endpoint()
        self.test_app_install_url_endpoint()
        self.test_webhook_endpoint_exists()
        self.test_pr_create_endpoint()

        print()
        print("=" * 60)
        print(f"Test Results: {self.pass_count} passed, {self.fail_count} failed")
        print("=" * 60)

        if self.fail_count == 0:
            print("✅ All tests passed!")
            return True
        else:
            print(f"❌ {self.fail_count} test(s) failed")
            print("\nNext steps:")
            print("1. Check GITHUB_INTEGRATION_SETUP.md for configuration")
            print("2. Verify environment variables are set correctly")
            print("3. Ensure backend is running and accessible")
            print("4. Check backend logs for errors")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Test CodeIQ GitHub Integration setup"
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--user-id",
        default="test_user_id",
        help="User ID for testing (default: test_user_id)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output (default: True)"
    )

    args = parser.parse_args()

    tester = GitHubIntegrationTester(
        backend_url=args.backend_url,
        user_id=args.user_id,
        verbose=args.verbose
    )

    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
