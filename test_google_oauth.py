#!/usr/bin/env python3
"""Test Google OAuth manager initialization."""

import os
import sys

# Add src to path
sys.path.insert(0, "src")

def test_oauth_manager():
    """Test Google OAuth manager can be instantiated."""
    print("=" * 60)
    print("Testing Google OAuth Manager")
    print("=" * 60)

    # Test 1: Import module
    print("\n1. Testing import...")
    try:
        from executive_assistant.auth.google_oauth import GoogleOAuthManager, get_google_oauth_manager
        print("   ✓ Module imported successfully")
    except Exception as e:
        print(f"   ✗ Import failed: {e}")
        return False

    # Test 2: Check settings
    print("\n2. Checking environment variables...")
    from executive_assistant.config.settings import settings

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)
    redirect_uri = getattr(settings, "GOOGLE_REDIRECT_URI", None)
    encryption_key = getattr(settings, "EMAIL_ENCRYPTION_KEY", None)

    print(f"   GOOGLE_CLIENT_ID: {'✓ Set' if client_id else '✗ Not set'}")
    print(f"   GOOGLE_CLIENT_SECRET: {'✓ Set' if client_secret else '✗ Not set'}")
    print(f"   GOOGLE_REDIRECT_URI: {'✓ Set' if redirect_uri else '✗ Not set'}")
    print(f"   EMAIL_ENCRYPTION_KEY: {'✓ Set' if encryption_key else '✗ Not set'}")

    # Test 3: Create authorization URL (only if configured)
    if client_id and client_secret and redirect_uri:
        print("\n3. Testing authorization URL creation...")
        try:
            oauth_manager = GoogleOAuthManager(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri
            )

            auth_url = oauth_manager.create_authorization_url(state="test_thread_id")
            print(f"   ✓ Authorization URL created")
            print(f"   URL: {auth_url[:80]}...")
            print(f"   State parameter: test_thread_id")
            return True

        except Exception as e:
            print(f"   ✗ Failed to create authorization URL: {e}")
            return False
    else:
        print("\n3. Skipping authorization URL test (OAuth not configured)")
        print("\n   To test OAuth flow:")
        print("   1. Create Google Cloud project")
        print("   2. Enable Gmail, Calendar, People APIs")
        print("   3. Configure OAuth consent screen")
        print("   4. Add OAuth scopes")
        print("   5. Create OAuth client ID")
        print("   6. Add credentials to .env:")
        print("      GOOGLE_CLIENT_ID=your-client-id")
        print("      GOOGLE_CLIENT_SECRET=your-client-secret")
        print("      GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback/google")
        print("   7. Generate encryption key:")
        print("      python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        print()

        # Generate encryption key for them
        print("\n   Generating encryption key for you:")
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        print(f"   EMAIL_ENCRYPTION_KEY={key}")
        print()

        return False

    print("\n✅ All tests passed!")
    return True


if __name__ == "__main__":
    success = test_oauth_manager()
    sys.exit(0 if success else 1)
