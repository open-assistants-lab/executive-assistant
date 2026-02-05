# Google Workspace Integration Plan

Complete guide for integrating Gmail, Google Calendar, and Google Contacts for the Executive Assistant (2025).

**Latest Updates:**
- `google-api-python-client` v2.189.0 (Feb 2026)
- `google-auth-oauthlib` v1.2.3 (Oct 2025)
- Official quickstarts updated Dec 11, 2025

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Google Workspace Setup](#google-workspace-setup)
3. [OAuth2 Authentication](#oauth2-authentication)
4. [Gmail Integration](#gmail-integration)
5. [Google Calendar Integration](#google-calendar-integration)
6. [Google Contacts Integration](#google-contacts-integration)
7. [Implementation Roadmap](#implementation-roadmap)
8. [References](#references)

---

## Executive Summary

This document provides a complete plan for integrating Google Workspace services (Gmail, Calendar, Contacts) into the Executive Assistant using the latest 2025 methods and libraries.

### Target Users

| User Type | Authentication Method | Use Case |
|-----------|----------------------|-----------|
| **Individual Users** | OAuth2 (User Consent) | Personal Gmail (@gmail.com) |
| **Google Workspace Domain** | OAuth2 + Admin Consent | Organization (@company.com) |
| **Service Account** | Domain-Wide Delegation | Backend processing, scheduled tasks |

### Key Design Principles

1. **Thread-Scoped**: `data/users/{thread_id}/auth/google/`
2. **Multi-Account**: Support multiple Google accounts per user
3. **Token Refresh**: Automatic token refresh (1-hour expiry)
4. **Rate Limiting**: Proper quota management (250 units/sec)
5. **Security**: Fernet encryption for token storage

---

## Google Workspace Setup

### Option A: Google Cloud Project (Recommended)

**Best for**: All use cases (individual + enterprise)

#### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click project dropdown → **"NEW PROJECT"**
3. Name: `Executive Assistant`
4. Click **"CREATE"**

#### Step 2: Enable APIs (Latest 2025)

```bash
# Enable using gcloud CLI or Console UI
gcloud services enable gmail-api.googleapis.com
gcloud services enable calendar-json.googleapis.com
gcloud services enable people.googleapis.com
```

Or in Console:
- **APIs & Services** → **Library**
- Search and enable:
  - **Gmail API**
  - **Calendar API**
  - **People API** (Contacts)

#### Step 3: Configure OAuth Consent Screen (Dec 2025 Updated)

1. **APIs & Services** → **OAuth consent screen**
2. Choose **"External"** (for any Google user)
3. Fill in:
   - **App name**: `Executive Assistant`
   - **User support email**: Your email
   - **Developer contact**: Your email
4. Click **"SAVE AND CONTINUE"**

#### Step 4: Add OAuth Scopes (Critical!)

Add ALL scopes from the start to avoid re-authorization:

**Scopes for Gmail:**
```python
'https://www.googleapis.com/auth/gmail.readonly'     # Read emails
'https://www.googleapis.com/auth/gmail.send'          # Send emails
'https://www.googleapis.com/auth/gmail.modify'        # Manage labels
```

**Scopes for Calendar:**
```python
'https://www.googleapis.com/auth/calendar'             # Full calendar access
'https://www.googleapis.com/auth/calendar.events'     # Create/edit events
```

**Scopes for Contacts:**
```python
'https://www.googleapis.com/auth/contacts'            # Full contacts access
'https://www.googleapis.com/auth/contacts.other.readonly'  # Read other contacts
```

#### Step 5: Create OAuth 2.0 Client ID

1. **APIs & Services** → **Credentials**
2. **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. **Application type**: **"Web application"**
4. **Name**: `Executive Assistant OAuth Client`
5. **Authorized redirect URIs**:
   ```
   http://localhost:8000/auth/callback/google
   https://your-domain.com/auth/callback/google
   ```
6. Click **"CREATE"**
7. Save **Client ID** and **Client Secret**

---

### Option B: Google Workspace Marketplace (Enterprise)

**Best for**: Organization-wide deployment

1. Go to [Google Workspace Marketplace SDK](https://developers.google.com/workspace)
2. Create new app integration
3. Configure OAuth scopes (same as above)
4. Submit for verification
5. Install to Workspace domain via admin console

---

## OAuth2 Authentication

### Latest Libraries (2025)

```toml
[project.dependencies]
google-api-python-client = "^2.189.0"  # Latest as of Feb 2026
google-auth-oauthlib = "^1.2.3"        # Latest as of Oct 2025
google-auth = "^2.20.0"
cryptography = "^41.0.0"
```

### OAuth2 Flow Implementation (2025 Standard)

**File**: `src/executive_assistant/auth/google_oauth.py`

```python
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from cryptography.fernet import Fernet
import json
from pathlib import Path
from datetime import datetime

class GoogleOAuthManager:
    """Manage Google OAuth2 flow with token refresh."""

    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/contacts'
    ]

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def create_authorization_url(self, state: str) -> str:
        """Create OAuth authorization URL with PKCE."""
        flow = Flow.from_client_config(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "scopes": self.SCOPES
            }
        )

        flow.redirect_uri = self.redirect_uri
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Force consent to get refresh token
        )

        return authorization_url

    async def exchange_code_for_tokens(self, code: str) -> Credentials:
        """Exchange authorization code for credentials."""
        flow = Flow.from_client_config(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "scopes": self.SCOPES
            }
        )

        flow.redirect_uri = self.redirect_uri
        flow.fetch_token(code=code)

        return flow.credentials

    async def save_tokens(self, thread_id: str, credentials: Credentials) -> None:
        """Save encrypted tokens to thread-scoped storage."""
        from executive_assistant.config.settings import settings

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }

        auth_dir = Path(f"data/users/{thread_id}/auth/google")
        auth_dir.mkdir(parents=True, exist_ok=True)

        # Encrypt with Fernet
        fernet = Fernet(settings.EMAIL_ENCRYPTION_KEY.encode())
        encrypted = fernet.encrypt(json.dumps(token_data).encode())

        cred_file = auth_dir / "credentials.json"
        with open(cred_file, "wb") as f:
            f.write(encrypted)

    async def load_credentials(self, thread_id: str) -> Credentials:
        """Load and refresh credentials if expired."""
        from executive_assistant.config.settings import settings

        auth_dir = Path(f"data/users/{thread_id}/auth/google")
        cred_file = auth_dir / "credentials.json"

        if not cred_file.exists():
            return None

        # Decrypt
        fernet = Fernet(settings.EMAIL_ENCRYPTION_KEY.encode())
        with open(cred_file, "rb") as f:
            decrypted = fernet.decrypt(f.read())

        token_data = json.loads(decrypted)

        # Create credentials object
        credentials = Credentials(
            token=token_data["token"],
            refresh_token=token_data["refresh_token"],
            token_uri=token_data["token_uri"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            scopes=token_data["scopes"],
            expiry=datetime.fromisoformat(token_data["expiry"]) if token_data.get("expiry") else None
        )

        # Auto-refresh if expired (standard google-auth behavior)
        if credentials.expired:
            credentials.refresh(Request())
            await self.save_tokens(thread_id, credentials)

        return credentials
```

### OAuth Callback (Latest 2025 Pattern)

**Both HTTP and Telegram channels use the SAME callback endpoint:**

**File**: `src/executive_assistant/channels/http.py`

```python
from fastapi import Request, Response
from starlette.responses import RedirectResponse

@app.get("/auth/callback/google")
async def google_auth_callback(
    request: Request,
    code: str,
    state: str,
    error: str = None
):
    """Handle Google OAuth2 callback for BOTH HTTP and Telegram channels."""
    if error:
        # Redirect back to appropriate channel based on thread_id in state
        if state.startswith("telegram:"):
            return RedirectResponse(url=f"https://t.me/{BOT_USERNAME}?start=auth_failed")
        return RedirectResponse(url=f"/?auth_error={error}")

    from executive_assistant.auth.google_oauth import GoogleOAuthManager

    # Exchange code for tokens
    oauth_manager = GoogleOAuthManager(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )

    credentials = await oauth_manager.exchange_code_for_tokens(code)

    # Get thread_id from state parameter
    thread_id = state

    # Save encrypted tokens
    await oauth_manager.save_tokens(thread_id, credentials)

    # Redirect back to appropriate channel
    if state.startswith("telegram:"):
        return RedirectResponse(url=f"https://t.me/{BOT_USERNAME}?start=auth_success")
    return RedirectResponse(url="/?auth=success")
```

### User OAuth Flow (HTTP Channel)

**User clicks link in web interface:**

```
1. User (in browser): "Connect my Gmail"
   ↓
2. App redirects to Google OAuth URL
   ↓
3. User signs in → Approves permissions
   ↓
4. Google redirects back to: https://your-domain.com/auth/callback/google
   ↓
5. Backend saves tokens → Redirects to /?auth=success
```

### User OAuth Flow (Telegram Channel)

**User clicks link in Telegram chat:**

```
1. User (in Telegram): "Connect my Gmail"
   ↓
2. Bot sends message with clickable URL:
   "Click here to connect Gmail: https://your-domain.com/auth/google/start?thread_id=telegram:123456"
   ↓
3. User clicks link → Opens in browser
   ↓
4. User signs in → Approves permissions
   ↓
5. Google redirects back to: https://your-domain.com/auth/callback/google
   ↓
6. Backend saves tokens → Redirects to Telegram bot
   ↓
7. Bot sends confirmation: "✅ Gmail connected!"
```

### Telegram OAuth Implementation

**File**: `src/executive_assistant/channels/telegram.py`

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from executive_assistant.auth.google_oauth import GoogleOAuthManager

async def connect_gmail_command(update: Update, context):
    """Handle /connect_gmail command in Telegram."""
    thread_id = f"telegram:{update.effective_message.chat_id}"

    # Create OAuth manager
    oauth_manager = GoogleOAuthManager(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )

    # Create authorization URL with thread_id in state
    auth_url = oauth_manager.create_authorization_url(
        state=thread_id  # Encode thread_id in state parameter
    )

    # Send clickable link button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Connect Gmail", url=auth_url)]
    ])

    await update.message.reply_text(
        "📧 **Connect Your Gmail Account**\n\n"
        "Click the button below to connect your Gmail.\n"
        "You'll be redirected to Google to sign in and grant permissions.\n\n"
        "After approving, you'll be redirected back here.",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
```

**Key Point:** Both channels use the SAME standard OAuth flow. The only difference is:
- **HTTP**: Link shown in web interface, redirects back to web page
- **Telegram**: Link sent as button in chat, redirects back to Telegram bot

---

## Gmail Integration

### Latest Gmail API Setup (2025)

**Version**: `gmail` v1 (via `google-api-python-client` v2.189.0)

```python
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

class GmailProvider:
    """Gmail API provider with OAuth2 (2025 standard)."""

    def __init__(self, credentials: Credentials):
        self.service = build('gmail', 'v1', credentials=credentials)

    async def list_emails(
        self,
        label_ids: list = None,
        max_results: int = 20,
        query: str = None
    ) -> List[EmailMessage]:
        """List emails from Gmail using latest API."""
        try:
            results = self.service.users().messages().list(
                userId='me',
                labelIds=label_ids or ['INBOX'],
                maxResults=max_results,
                q=query
            ).execute()

            messages = results.get('messages', [])

            # Fetch full details for each message
            return [await self._get_email_detail(msg['id']) for msg in messages]

        except HttpError as error:
            print(f"Gmail API Error: {error}")
            return []

    async def _get_email_detail(self, message_id: str) -> EmailMessage:
        """Get full email message with headers and body."""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full',  # Get full message with payload
                metadataHeaders=['From', 'To', 'Subject', 'Date']
            ).execute()

            # Parse email
            payload = message['payload']
            headers = {h['name']: h['value'] for h in payload.get('headers', [])}

            # Extract body
            body = self._extract_body(payload)

            return EmailMessage(
                id=message_id,
                thread_id=message.get('threadId'),
                subject=headers.get('Subject', ''),
                from_address=headers.get('From', ''),
                to_address=headers.get('To', ''),
                date=headers.get('Date', ''),
                body=body,
                snippet=message.get('snippet', '')
            )

        except HttpError as error:
            print(f"Error fetching message {message_id}: {error}")
            return None

    def _extract_body(self, payload: dict) -> str:
        """Extract email body from payload (handles text/html)."""
        body = payload.get('body', {})
        if 'data' in body:
            return self._decode_base64(body['data'])

        # Check multipart
        parts = payload.get('parts', [])
        for part in parts:
            if part['mimeType'] == 'text/html':
                return self._decode_base64(part['body']['data'])
            elif part['mimeType'] == 'text/plain':
                return self._decode_base64(part['body']['data'])

        return ""

    @staticmethod
    def _decode_base64(data: str) -> str:
        """Decode URL-safe base64 data."""
        import base64
        return base64.urlsafe_b64decode(data).decode('utf-8')

    async def send_email(self, email: EmailDraft) -> str:
        """Send email via Gmail API (2025 standard)."""
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import base64

        # Create message
        message = MIMEMultipart('alternative')
        message['to'] = email.to
        message['from'] = email.from_address
        message['subject'] = email.subject

        # Add HTML body
        html_part = MIMEText(email.body, 'html')
        message.attach(html_part)

        # Encode and send
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            result = self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()

            return result['id']

        except HttpError as error:
            print(f"Error sending email: {error}")
            raise
```

### Gmail Tools (2025)

**File**: `src/executive_assistant/tools/gmail_tools.py`

| Tool | Description |
|------|-------------|
| `connect_gmail` | Start OAuth2 flow (returns auth URL) |
| `list_emails` | List recent emails with filters |
| `get_email` | Get full email by ID |
| `search_emails` | Search with Gmail query syntax |
| `draft_email` | Create draft response |
| `send_draft` | Send approved draft |
| `reply_to_email` | Reply to thread |
| `forward_email` | Forward email |
| `get_thread` | Get full conversation thread |
| `mark_read` | Mark as read |

### Gmail Query Examples (2025)

```python
# Urgent emails
"is:urgent"

# Unread with attachments
"is:unread has:attachment"

# From specific sender
"from:john@company.com"

# Emails in last 24 hours
"after:2025-01-03"

# Important emails
"is:important OR label:urgent"

# Attachments larger than 1MB
"larger:1M"
```

---

## Google Calendar Integration

### Calendar Provider (2025)

```python
from googleapiclient.discovery import build
from datetime import datetime, timedelta

class GoogleCalendarProvider:
    """Google Calendar API provider (2025 standard)."""

    def __init__(self, credentials: Credentials):
        self.service = build('calendar', 'v3', credentials=credentials)

    async def list_events(
        self,
        calendar_id: str = 'primary',
        time_min: datetime = None,
        time_max: datetime = None,
        max_results: int = 100
    ) -> List[CalendarEvent]:
        """List events (Dec 2025 updated API)."""
        time_min_str = time_min.isoformat() + 'Z' if time_min else None
        time_max_str = time_max.isoformat() + 'Z' if time_max else None

        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'  # 2025 best practice
            ).execute()

            events = events_result.get('items', [])
            return [self._parse_event(event) for event in events]

        except HttpError as error:
            print(f"Calendar API Error: {error}")
            return []

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendees: List[str] = None,
        description: str = None,
        create_meet: bool = False,
        timezone: str = 'UTC'
    ) -> str:
        """Create event with optional Google Meet (2025 standard)."""

        event_body = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start.isoformat(),
                'timeZone': timezone
            },
            'end': {
                'dateTime': end.isoformat(),
                'timeZone': timezone
            }
        }

        # Add attendees
        if attendees:
            event_body['attendees'] = [
                {'email': email} for email in attendees
            ]

        # Add Google Meet (2025 best practice)
        if create_meet:
            event_body['conferenceData'] = {
                'createRequest': {
                    'requestId': f"meeting-{int(datetime.now().timestamp())}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }

            # Use conferenceDataVersion=1 for 2025 API
            result = self.service.events().insert(
                calendarId='primary',
                body=event_body,
                conferenceDataVersion=1
            ).execute()
        else:
            result = self.service.events().insert(
                calendarId='primary',
                body=event_body
            ).execute()

        return result['id']

    async def find_free_time(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int,
        work_hours_start: str = "09:00",
        work_hours_end: str = "18:00"
    ) -> List[TimeSlot]:
        """Find available time slots (2025 efficient algorithm)."""
        from datetime import time

        events = await self.list_events(
            time_min=start_date,
            time_max=end_date
        )

        # Sort by start time
        events.sort(key=lambda e: e.start)

        # Find gaps
        free_slots = []
        current_time = start_date

        for event in events:
            if current_time + timedelta(minutes=duration_minutes) <= event.start:
                # Check if within work hours
                current_hour = current_time.hour
                if int(work_hours_start[:2]) <= current_hour < int(work_hours_end[:2]):
                    free_slots.append(TimeSlot(current_time, event.start))

            current_time = max(current_time, event.end)

        return free_slots
```

---

## Google Contacts Integration

### People API Provider (2025)

```python
from googleapiclient.discovery import build

class GoogleContactsProvider:
    """Google People API provider (Dec 2025 updated)."""

    def __init__(self, credentials: Credentials):
        self.service = build('people', 'v1', credentials=credentials)

    async def list_contacts(
        self,
        limit: int = 50,
        search_query: str = None
    ) -> List[Contact]:
        """List or search contacts (2025 API standard)."""

        try:
            if search_query:
                # Search contacts (2025 method)
                results = self.service.people().searchContacts().query(
                    query=search_query,
                    readMask='names,emailAddresses,phoneNumbers,organizations,photos'
                ).execute()
            else:
                # List all connections (2025 method)
                results = self.service.people().connections().list(
                    resourceName='people/me',
                    pageSize=limit,
                    personFields='names,emailAddresses,phoneNumbers,organizations,photos'
                ).execute()

            connections = results.get('connections', [])
            return [self._parse_contact(conn) for conn in connections]

        except HttpError as error:
            print(f"People API Error: {error}")
            return []

    def _parse_contact(self, person: dict) -> Contact:
        """Parse People API person object (2025 schema)."""
        names = person.get('names', [])
        primary_name = next((n['displayName'] for n in names if n.get('metadata', {}).get('primary')), None)

        emails = person.get('emailAddresses', [])
        primary_email = next((e['value'] for e in emails if e.get('metadata', {}).get('primary')), None)

        phones = person.get('phoneNumbers', [])
        primary_phone = next((p['value'] for p in phones if p.get('metadata', {}).get('primary')), None)

        organizations = person.get('organizations', [])
        company = next((o['name'] for o in organizations if o.get('current')), None)

        photos = person.get('photos', [])
        photo_url = next((p['url'] for p in photos), None)

        return Contact(
            name=primary_name,
            email=primary_email,
            phone=primary_phone,
            company=company,
            photo_url=photo_url
        )
```

---

## Implementation Roadmap

### Phase 1: OAuth Foundation (Week 1)

- [ ] Google Cloud project setup with latest APIs
- [ ] OAuth consent screen with all scopes
- [ ] Token storage with Fernet encryption
- [ ] FastAPI callback endpoint
- [ ] Token refresh mechanism
- [ ] Multi-account support

### Phase 2: Gmail Integration (Weeks 2-3)

- [ ] Gmail provider (v2.189.0)
- [ ] Core Gmail tools (list, get, search)
- [ ] Email draft and send tools
- [ ] Attachment handling
- [ ] Thread retrieval
- [ ] Rate limit handling

### Phase 3: Calendar Integration (Weeks 4-5)

- [ ] Calendar provider (2025 API)
- [ ] Event listing and creation
- [ ] Google Meet integration
- [ ] Availability checking
- [ ] Multi-attendee scheduling

### Phase 4: Contacts Integration (Weeks 6-7)

- [ ] People API provider (Dec 2025)
- [ ] Contact search and lookup
- [ ] Contact creation
- [ ] Domain-based search

### Phase 5: Cross-Service Integration (Week 8)

- [ ] Extract events from emails
- [ ] Smart email composition with contacts
- [ ] Unified search across all services

### Total Timeline: ~8 weeks

---

## Rate Limits & Quotas (2025)

### Gmail API (Latest)

| Resource | Limit |
|----------|-------|
| Quota per day | 1 billion units |
| Per second | 250 units |
| Per user per second | 1 unit |

**Operation Costs:**
- `messages.list`: 5-10 units
- `messages.get`: 5 units
- `messages.send`: 100 units
- `threads.get`: 10 units

### Google Calendar API (2025)

| Resource | Limit |
|----------|-------|
| Queries per day | 10,000 per user |
| Per 100 seconds | 500 per user |

### Google People API (2025)

| Resource | Limit |
|----------|-------|
| Requests per day | 10,000 per user |
| Per 100 seconds | 500 per user |

---

## Security Considerations

### Token Storage

- **Encryption**: Fernet (AES-128-CBC + HMAC)
- **File Permissions**: `chmod 600`
- **Key Management**: Environment variable only
- **Rotation**: Automatic on refresh

### OAuth Best Practices (2025)

1. **PKCE** (Recommended for public clients)
2. **State Parameter**: CSRF protection
3. **HTTPS Only**: Production callbacks must be HTTPS
4. **Token Binding**: Associate with thread_id
5. **Short-lived tokens**: 1-hour expiry, auto-refresh

---

## Python Dependencies (Latest 2025)

```toml
[project.dependencies]
# Google APIs (Latest)
google-api-python-client = "^2.189.0"
google-auth-oauthlib = "^1.2.3"
google-auth = "^2.20.0"

# Encryption
cryptography = "^41.0.0"

# Web Framework (if using FastAPI)
fastapi = "^0.104.0"
starlette = "^0.27.0"
```

---

## References

### Official Documentation
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) (Updated Dec 11, 2025)
- [Google Calendar API Python Quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python) (Updated Dec 11, 2025)
- [People API Python Quickstart](https://developers.google.com/people/quickstart/python) (Updated Dec 11, 2025)
- [OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server) (Updated Dec 19, 2025)

### Libraries
- [google-api-python-client GitHub](https://github.com/googleapis/google-api-python-client) (v2.189.0 - Feb 2026)
- [google-auth-oauthlib GitHub](https://github.com/googleapis/google-auth-library-python-oauthlib) (v1.2.3 - Oct 2025)
- [PyPI: google-api-python-client](https://pypi.org/project/google-api-python-client/)
- [PyPI: google-auth-oauthlib](https://pypi.org/project/google-auth-oauthlib/)

### Client Libraries Docs
- [Google API Client Library for Python Docs](https://googleapis.github.io/google-api-python-client/docs/)
- [Python Client for Calendar](https://googleapis.github.io/google-api-python-client/docs/dyn/calendar_v1.html)
- [Python Client for People](https://googleapis.github.io/google-api-python-client/docs/dyn/people_v1.html)
