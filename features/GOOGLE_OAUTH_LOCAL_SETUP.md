# Google OAuth Setup - Local Testing Guide

Complete guide for setting up and testing Google OAuth integration locally.

---

## Quick Start (5 Minutes)

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click project dropdown → **"NEW PROJECT"**
3. Name: `Executive Assistant` → Click **"CREATE"**

### Step 2: Enable APIs

In Cloud Console, search for and enable:
- **Gmail API**
- **Google Calendar API**
- **People API** (Contacts)

### Step 3: Configure OAuth Consent Screen

1. **APIs & Services** → **OAuth consent screen**
2. Choose **"External"** → Click **"CREATE"**
3. Fill in:
   - **App name**: `Executive Assistant (Local)`
   - **User support email**: Your email
   - **Developer contact**: Your email
4. Click **"SAVE AND CONTINUE"**

### Step 4: Add OAuth Scopes

Add the following scopes (critical - add ALL to avoid re-authorization):

```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/contacts
```

Click **"SAVE AND CONTINUE"** (skip test users if asked).

### Step 5: Create OAuth Client ID

1. **APIs & Services** → **Credentials**
2. **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. **Application type**: **"Web application"**
4. **Name**: `Executive Assistant Local`
5. **Authorized redirect URIs**:
   ```
   http://localhost:8000/auth/callback/google
   ```
6. Click **"CREATE"**
7. Save **Client ID** and **Client Secret**

---

## Configure Environment Variables

Add to `docker/.env`:

```bash
# Google Workspace Integration
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback/google

# Generate encryption key (Python):
# from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
EMAIL_ENCRYPTION_KEY=your-fernet-key-here
```

---

## Generate Encryption Key

Run this Python command to generate a secure encryption key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output to `EMAIL_ENCRYPTION_KEY` in `.env`.

---

## Test the OAuth Flow

### Option 1: Test with HTTP Channel

1. Start the application:
   ```bash
   uv run executive_assistant
   ```

2. Open browser to:
   ```
   http://localhost:8000/auth/google/start?user_id=test123
   ```

3. Complete Google sign-in flow

4. Check tokens saved:
   ```bash
   ls -la data/users/http_test123/auth/google/
   ```

### Option 2: Test with Telegram Channel

1. Start the application (Telegram channel must be running)

2. In Telegram, send: `/connect_gmail`

3. Click the "Connect Gmail" button

4. Complete Google sign-in flow

5. Bot confirms: "✅ Gmail connected!"

---

## Verify Token Storage

Check that tokens were saved encrypted:

```bash
# Find your thread directory
ls -la data/users/

# Check for Google auth file
ls -la data/users/telegram_*<your_id>/auth/google/

# Should see: credentials.json (encrypted)
```

---

## Troubleshooting

### Error: "Google OAuth not configured"

**Cause**: Missing or invalid `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, or `GOOGLE_REDIRECT_URI`

**Fix**: Ensure all three are set in `.env` and match Google Cloud Console

### Error: "redirect_uri_mismatch"

**Cause**: Redirect URI in Google Console doesn't match what you're using

**Fix**: Ensure `GOOGLE_REDIRECT_URI` in `.env` exactly matches what's in Google Cloud Console

**Common mismatch**: `http://` vs `https://` or missing port number

### Error: "access_denied"

**Cause**: User denied permissions

**Fix**: User must click "Allow" on Google consent screen

### Error: "invalid_client"

**Cause**: Wrong Client ID or Client Secret

**Fix**: Copy values directly from Google Cloud Console

### Error: "Fernet key not valid"

**Cause**: `EMAIL_ENCRYPTION_KEY` is not a valid Fernet key

**Fix**: Generate using:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Production Deployment

For production, update redirect URIs in Google Cloud Console:

```
http://localhost:8000/auth/callback/google  # Local testing
https://your-domain.com/auth/callback/google  # Production
https://your-domain.com/auth/callback/google  # With www.
```

Update `GOOGLE_REDIRECT_URI` in `.env`:
```bash
GOOGLE_REDIRECT_URI=https://your-domain.com/auth/callback/google
```

---

## Testing Checklist

- [ ] Google Cloud project created
- [ ] APIs enabled (Gmail, Calendar, People)
- [ ] OAuth consent screen configured
- [ ] OAuth scopes added (all 5 scopes)
- [ ] OAuth client ID created
- [ ] Redirect URI added to Google Console
- [ ] Environment variables set in `.env`
- [ ] Encryption key generated
- [ ] HTTP channel OAuth tested
- [ ] Telegram channel OAuth tested
- [ ] Tokens saved to `data/users/{thread_id}/auth/google/credentials.json`
- [ ] Tokens are encrypted (can verify by checking file content)

---

## Next Steps

Once OAuth is working:

1. Test loading credentials:
   ```python
   from executive_assistant.auth.google_oauth import get_google_oauth_manager

   manager = get_google_oauth_manager()
   credentials = await manager.load_credentials("http:test123")

   if credentials:
       print("✅ OAuth working!")
   ```

2. Implement Gmail provider (see `features/google-workspace-integration.md`)
3. Implement Calendar provider
4. Implement Contacts provider
5. Add tools to tool registry
