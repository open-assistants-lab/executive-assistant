#!/bin/bash
# Google OAuth Setup Script
# This script guides you through setting up Google OAuth for local testing

set -e

echo "=========================================="
echo "Google OAuth Setup for Executive Assistant"
echo "=========================================="
echo ""
echo "This script will guide you through:"
echo "1. Creating a Google Cloud project"
echo "2. Enabling APIs"
echo "3. Configuring OAuth consent screen"
echo "4. Creating OAuth client ID"
echo "5. Configuring environment variables"
echo ""

# Check if required tools are installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Step 1: Open Google Cloud Console
echo "=========================================="
echo "Step 1: Create Google Cloud Project"
echo "=========================================="
echo ""
echo "1. Opening Google Cloud Console..."
echo "2. Create a new project named 'Executive Assistant'"
echo "3. Note your Project ID (usually auto-generated)"
echo ""
echo "Press ENTER when ready to continue..."
read -r

echo "https://console.cloud.google.com/projectcreate"
open "https://console.cloud.google.com/projectcreate" 2>/dev/null || echo "Manually open: https://console.cloud.google.com/projectcreate"

echo ""
echo "✅ Once project is created, press ENTER to continue..."
read -r

# Step 2: Enable APIs
echo ""
echo "=========================================="
echo "Step 2: Enable Required APIs"
echo "=========================================="
echo ""
echo "Enabling Gmail API..."
echo "Open this URL and enable Gmail API:"
echo "https://console.cloud.google.com/apis/library/gmail-api"
open "https://console.cloud.google.com/apis/library/gmail-api" 2>/dev/null || echo "Manually open: https://console.cloud.google.com/apis/library/gmail-api"

echo ""
echo "Enabling Calendar API..."
echo "Open this URL and enable Calendar API:"
echo "https://console.cloud.google.com/apis/library/calendar-json"
open "https://console.cloud.google.com/apis/library/calendar-json" 2>/dev/null || echo "Manually open: https://console.cloud.google.com/apis/library/calendar-json"

echo ""
echo "Enabling People API (Contacts)..."
echo "Open this URL and enable People API:"
echo "https://console.cloud.google.com/apis/library/people.googleapis.com"
open "https://console.cloud.google.com/apis/library/people.googleapis.com" 2>/dev/null || echo "Manually open: https://console.cloud.google.com/apis/library/people.googleapis.com"

echo ""
echo "✅ Press ENTER when all 3 APIs are enabled..."
read -r

# Step 3: Configure OAuth Consent Screen
echo ""
echo "=========================================="
echo "Step 3: Configure OAuth Consent Screen"
echo "=========================================="
echo ""
echo "1. Opening OAuth consent screen configuration..."
echo "2. Choose 'External' (for testing)"
echo "3. Fill in:"
echo "   - App name: Executive Assistant (Local)"
echo "   - User support email: your email"
echo "   - Developer contact: your email"
echo "4. Click 'SAVE AND CONTINUE'"
echo ""
echo "https://console.cloud.google.com/apis/credentials/consent"
open "https://console.cloud.google.com/apis/credentials/consent" 2>/dev/null || echo "Manually open: https://console.cloud.google.com/apis/credentials/consent"

echo ""
echo "✅ Press ENTER when consent screen is configured..."
read -r

# Step 4: Add OAuth Scopes
echo ""
echo "=========================================="
echo "Step 4: Add OAuth Scopes (CRITICAL!)"
echo "=========================================="
echo ""
echo "IMPORTANT: Add ALL 5 scopes at once to avoid re-authorization!"
echo ""
echo "Add these scopes one by one:"
echo ""
echo "1. Gmail Readonly:"
echo "   https://www.googleapis.com/auth/gmail.readonly"
echo ""
echo "2. Gmail Send:"
echo "   https://www.googleapis.com/auth/gmail.send"
echo ""
echo "3. Gmail Modify:"
echo "   https://www.googleapis.com/auth/gmail.modify"
echo ""
echo "4. Calendar:"
echo "   "https://www.googleapis.com/auth/calendar"
echo ""
echo "5. Contacts:"
echo "   https://www.googleapis.com/auth/contacts"
echo ""
echo "https://console.cloud.google.com/apis/credentials/consent"
open "https://console.cloud.google.com/apis/credentials/consent" 2>/dev/null || echo "Manually open: https://console.cloud.google.com/apis/credentials/consent"

echo ""
echo "✅ Press ENTER when all scopes are added..."
read -r

# Step 5: Create OAuth Client ID
echo ""
echo "=========================================="
echo "Step 5: Create OAuth Client ID"
echo "=========================================="
echo ""
echo "1. Opening Credentials page..."
echo "2. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'"
echo "3. Application type: 'Web application'"
echo "4. Name: Executive Assistant Local"
echo "5. Authorized redirect URIs:"
echo "   http://localhost:8000/auth/callback/google"
echo "6. Click 'CREATE'"
echo ""
echo "⚠️  SAVE THE Client ID and Client Secret!"
echo ""
echo "https://console.cloud.google.com/apis/credentials"
open "https://console.cloud.google.com/apis/credentials" 2>/dev/null || echo "Manually open: https://console.cloud.google.com/apis/credentials"

echo ""
echo "✅ Press ENTER when you have your Client ID and Secret..."
read -r

# Get credentials from user
echo ""
echo "=========================================="
echo "Step 6: Enter Your Credentials"
echo "=========================================="
echo ""
echo "Enter your Google OAuth credentials:"
echo ""

read -p "Client ID: " client_id
read -p "Client Secret: " client_secret

# Validate format
if [[ ! $client_id =~ .*\.apps\.googleusercontent\.com ]]; then
    echo "⚠️  Warning: Client ID doesn't look like a valid Google Client ID"
    echo "   Expected format: xxxxx.apps.googleusercontent.com"
    echo ""
    read -p "Continue anyway? (y/n): " confirm
    if [[ $confirm != "y" ]]; then
        exit 1
    fi
fi

# Step 7: Update .env file
echo ""
echo "=========================================="
echo "Step 7: Configure Environment"
echo "=========================================="
echo ""
echo "Adding Google OAuth configuration to docker/.env..."
echo ""

# Backup existing .env
if [ -f "docker/.env" ]; then
    cp docker/.env docker/.env.backup
    echo "✅ Backed up existing .env to docker/.env.backup"
fi

# Add Google OAuth configuration to .env
cat >> docker/.env <<EOF

# ============================================================================
# Google Workspace Integration (Gmail, Calendar, Contacts)
# ============================================================================
# Get credentials: https://console.cloud.google.com/apis/credentials
# Guide: features/GOOGLE_OAUTH_LOCAL_SETUP.md

# OAuth2 Credentials
GOOGLE_CLIENT_ID=$client_id
GOOGLE_CLIENT_SECRET=$client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback/google

# Token encryption (pre-generated for your convenience)
EMAIL_ENCRYPTION_KEY=BcDs8pn941kcMCC6Ud1xi7yMKYIztYdVwZx-80_RpZA=
EOF

echo "✅ Added Google OAuth configuration to docker/.env"
echo ""

# Step 8: Generate encryption key
echo ""
echo "=========================================="
echo "Step 8: Test Configuration"
echo "=========================================="
echo ""
echo "Testing Google OAuth manager..."
echo ""

# Test the OAuth manager
python3 <<EOF
import sys
sys.path.insert(0, "src")

try:
    from executive_assistant.auth.google_oauth import get_google_oauth_manager

    oauth_manager = get_google_oauth_manager()
    auth_url = oauth_manager.create_authorization_url(state="test_thread_id")

    print("✅ Google OAuth manager configured successfully!")
    print(f"   Authorization URL: {auth_url[:80]}...")
    print(f"   State parameter: test_thread_id")
    print("")
    print("✅ Configuration is ready!")
    print("")
    print("Next steps:")
    print("1. Start the app: uv run executive_assistant")
    print("2. Test HTTP flow: http://localhost:8000/auth/google/start?user_id=testuser")
    print("3. Test Telegram: /connect_gmail")
    print("4. Approve permissions in Google")
    print("5. Verify tokens: ls data/users/http_testuser/auth/google/")

except Exception as e:
    print(f"❌ Configuration test failed: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Your Google OAuth is now configured and ready to test!"
    echo ""
    echo "To test:"
    echo "  1. uv run executive_assistant"
    echo "  2. Open: http://localhost:8000/auth/google/start?user_id=testuser"
    echo ""
    echo "Or in Telegram, send: /connect_gmail"
else
    echo ""
    echo "❌ Setup failed. Please check the error messages above."
    exit 1
fi
echo ""
echo "Documentation:"
echo "  - Local setup guide: features/GOOGLE_OAUTH_LOCAL_SETUP.md"
echo "  - Full integration plan: features/google-workspace-integration.md"
