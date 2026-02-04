# Email, Calendar & Contacts Integration Plan

Complete guide for implementing email, calendar, and contacts integration for the Executive Assistant.

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Part 1: OAuth2 Setup Guide](#part-1-oauth2-setup-guide)
3. [Part 2: Email Integration](#part-2-email-integration)
4. [Part 3: Calendar & Contacts Integration](#part-3-calendar--contacts-integration)
5. [Shared Implementation Details](#shared-implementation-details)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Testing Strategy](#testing-strategy)

---

## Executive Summary

This document provides a complete plan for integrating email, calendar, and contacts capabilities into the Executive Assistant. Users connect their accounts through **existing channels** (Telegram/HTTP), enabling the agent to:

- **Email**: Read, draft, send, and learn user's writing style
- **Calendar**: Schedule meetings, check availability, manage events
- **Contacts**: Look up contacts, find people, manage contact information

### Key Design Principles

1. **Channel Agnostic**: All services work through Telegram OR HTTP (not separate channels)
2. **Single OAuth2**: Google/Microsoft use one authorization for all services
3. **Thread-Scoped**: Credentials stored in `data/users/{thread_id}/auth/{service}/`
4. **Approval Workflow**: Drafts/events require user approval before sending
5. **Privacy-First**: Encrypted credential storage
6. **Progressive Enhancement**: Email first, then calendar/contacts

---

# Part 1: OAuth2 Setup Guide

This section walks you through setting up OAuth2 authentication for email, calendar, and contacts providers.

**Important**: Include all scopes (email, calendar, contacts) from the start. This avoids requiring users to re-authorize later when you add these features.

## Supported Providers

### Recommended (Priority Order)

| Provider | Coverage | Email | Calendar | Contacts | OAuth Support |
|----------|----------|-------|----------|----------|---------------|
| **Google** | 1.8B+ users | ✅ Gmail API | ✅ Calendar API | ✅ People API | ✅ Single auth |
| **Microsoft** | 400M+ users | ✅ Graph Mail | ✅ Graph Calendar | ✅ Graph Contacts | ✅ Single auth |
| **iCloud** | 850M+ users | ✅ IMAP/SMTP | ✅ CalDAV | ✅ CardDAV | ⚠️ App passwords |
| **Generic IMAP** | Universal | ✅ | ❌ | ❌ | ⚠️ App passwords |

**Recommendation**: Start with Google + Microsoft + iCloud. This covers 95%+ of users.

---

## Google Cloud Console Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click the project dropdown at the top
4. Click **"NEW PROJECT"**
5. Enter project name: `Executive Assistant`
6. Click **"CREATE"**

### Step 2: Enable APIs

Enable all APIs you'll need (even if you're starting with email only):

1. In the left sidebar, go to **"APIs & Services"** → **"Library"**
2. Search for and enable these APIs:
   - **"Gmail API"** - Click and press **"ENABLE"**
   - **"Calendar API"** - Click and press **"ENABLE"**
   - **"People API"** (Contacts) - Click and press **"ENABLE"**

### Step 3: Configure OAuth Consent Screen

1. Go to **"APIs & Services"** → **"OAuth consent screen"**
2. Choose **"External"** (since anyone will use this)
3. Click **"CREATE"**
4. Fill in required fields:
   - **App name**: `Executive Assistant`
   - **User support email**: Your email
   - **Developer contact information**: Your email
5. Click **"SAVE AND CONTINUE"** through all screens

### Step 4: Add OAuth Scopes

1. Still on **"OAuth consent screen"**
2. Click **"EDIT APP"** or go to **"Scopes"** tab
3. Click **"ADD SCOPE"**
4. Add these scopes:

**Email (Gmail):**
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails
- `https://www.googleapis.com/auth/gmail.send` - Send emails
- `https://www.googleapis.com/auth/gmail.modify` - Manage labels, archive (optional)

**Calendar:**
- `https://www.googleapis.com/auth/calendar` - Full calendar access
- `https://www.googleapis.com/auth/calendar.events` - Create/edit events (recommended alternative)

**Contacts:**
- `https://www.googleapis.com/auth/contacts` - Full contacts access
- `https://www.googleapis.com/auth/contacts.other.readonly` - Read other contacts

5. Click **"UPDATE"**

**Note**: Include all scopes from the start, even if you're only implementing email initially. This prevents users from needing to re-authorize when you add calendar/contacts features.

### Step 5: Create OAuth 2.0 Credentials

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. **Application type**: Select **"Web application"**
4. **Name**: `Executive Assistant`
5. **Authorized redirect URIs** (click **"ADD URI"**):
   - `http://localhost:8000/email/callback/gmail` (development)
   - `https://your-domain.com/email/callback/gmail` (production)
6. Click **"CREATE"**

### Step 6: Save Credentials

1. Copy the **Client ID** (looks like: `123456789-abc123def456.apps.googleusercontent.com`)
2. Copy the **Client Secret** (looks like: `GOCSPX-xxxxxxxxxxxxxxxxx`)
3. Store these securely - you'll need them for the `.env` file

---

## Microsoft Azure Portal Setup

### Step 1: Register App in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com/)
2. Sign in with your Microsoft account (use personal account for Outlook/Hotmail)
3. Search for **"App registrations"** in the search bar
4. Click **"App registrations"**

### Step 2: New Registration

1. Click **"New registration"**
2. Fill in the form:
   - **Name**: `Executive Assistant`
   - **Supported account types**: Select **"Accounts in any organizational directory and personal Microsoft accounts"** (this covers Outlook, Hotmail, Live)
   - **Redirect URI**: Select **"Web"** and enter:
     - `http://localhost:8000/email/callback/outlook` (development)
     - `https://your-domain.com/email/callback/outlook` (production)
3. Click **"Register"**

### Step 3: Copy Application ID

1. On the app's overview page, copy the **Application (client) ID**
2. Save this - it's your `OUTLOOK_CLIENT_ID`

### Step 4: Create Client Secret

1. In the left sidebar, click **"Certificates & secrets"**
2. Click **"+ New client secret"**
3. Description: `Executive Assistant Secret`
4. Expires: Select **"180 days"** or **"365 days"** (not never for security)
5. Click **"Add"**
6. **IMPORTANT**: Copy the **Value** immediately (you can't see it again!)
   - Not the "Secret ID" - you need the "Value"
7. Save this as your `OUTLOOK_CLIENT_SECRET`

### Step 5: Configure API Permissions

1. In the left sidebar, click **"API permissions"**
2. Click **"+ Add a permission"**
3. Click **"Microsoft Graph"**
4. Select **"Delegated permissions"**
5. Search for and add these permissions:

**Email:**
- `Mail.Read` - Read user's mail
- `Mail.Send` - Send mail as user

**Calendar:**
- `Calendars.ReadWrite` - Full calendar access

**Contacts:**
- `Contacts.ReadWrite` - Full contacts access

6. Click **"Add permissions"**

### Step 6: Grant Admin Consent

1. Still on **"API permissions"** page
2. Click **"Grant admin consent for [Your Organization]"**
3. Click **"Yes"** to confirm
4. You should see green checkmarks next to permissions

---

## Apple iCloud Setup

Apple iCloud uses **app-specific passwords** and standard protocols. No OAuth2 registration needed.

### What iCloud Users Get

| Service | Protocol | Support |
|---------|----------|---------|
| **Email** | IMAP/SMTP | ✅ Full support with app password |
| **Calendar** | CalDAV | ✅ Full support with app password |
| **Contacts** | CardDAV | ✅ Full support with app password |

### How Users Generate App-Specific Passwords

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in with Apple ID
3. Go to **"Sign-In and Security"**
4. Click **"App-Specific Passwords"**
5. Click **"+"** or **"Generate Password"**
6. Enter a label (e.g., "Executive Assistant")
7. Copy the password (format: `abcd-efgh-ijkl-mnop`)

### User Setup Flow for iCloud

**Email:**
```
User: Connect my iCloud email
Bot: Please provide your @icloud.com address and app-specific password.
User: connect_icloud user@icloud.com abcd-efgh-ijkl-mnop
Bot: ✅ iCloud Mail connected!
```

**Calendar:**
```
User: Connect my iCloud calendar
Bot: Please provide your @icloud.com address and app-specific password.
User: connect_icloud_calendar user@icloud.com abcd-efgh-ijkl-mnop
Bot: ✅ iCloud Calendar connected!
```

**Contacts:**
```
User: Connect my iCloud contacts
Bot: Please provide your @icloud.com address and app-specific password.
User: connect_icloud_contacts user@icloud.com abcd-efgh-ijkl-mnop
Bot: ✅ iCloud Contacts connected!
```

---

## Environment Configuration

### 1. Create Encryption Key

Generate a Fernet encryption key for storing tokens:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the output - you'll need it for `EMAIL_ENCRYPTION_KEY`.

### 2. Update `docker/.env`

```bash
# =====================================================
# EMAIL, CALENDAR & CONTACTS OAUTH2 CONFIGURATION
# =====================================================

# Encryption key (REQUIRED)
EMAIL_ENCRYPTION_KEY=your-generated-fernet-key-here

# Google OAuth2
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret

# Microsoft OAuth2
OUTLOOK_CLIENT_ID=your-microsoft-application-id
OUTLOOK_CLIENT_SECRET=your-client-secret-value
```

### 3. Update `docker/config.yaml`

```yaml
email:
  enabled: true
  encryption_key: ${EMAIL_ENCRYPTION_KEY}
  providers:
    gmail:
      client_id: ${GMAIL_CLIENT_ID}
      client_secret: ${GMAIL_CLIENT_SECRET}
      redirect_uri: http://localhost:8000/email/callback/gmail
    outlook:
      client_id: ${OUTLOOK_CLIENT_ID}
      client_secret: ${OUTLOOK_CLIENT_SECRET}
      redirect_uri: http://localhost:8000/email/callback/outlook

icloud:
  email:
    imap_host: imap.mail.me.com
    imap_port: 993
    smtp_host: smtp.mail.me.com
    smtp_port: 587
  calendar:
    caldav_host: caldav.icloud.com
    caldav_port: 443
    caldav_path: "/"
  contacts:
    carddav_host: contacts.icloud.com
    carddav_port: 443
    carddav_path: "/addressbooks"
```

---

## Testing OAuth2 Setup

### Test 1: Verify Environment Variables

```bash
docker compose exec executive_assistant env | grep -E "(GMAIL|OUTLOOK|EMAIL_ENCRYPTION)"
```

Expected output:
```
GMAIL_CLIENT_ID=123456789-abc123.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxx
OUTLOOK_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
OUTLOOK_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_ENCRYPTION_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Test 2: Test OAuth2 Flow

1. Start the bot: `uv run executive_assistant`
2. In Telegram/HTTP, type: `Connect my Gmail`
3. Click the authorization link
4. Authorize in Google/Microsoft
5. Verify credentials saved:
   ```bash
   ls data/users/<thread_id>/auth/email/credentials.json
   ```

---

# Part 2: Email Integration

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Executive Assistant                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  User chats on Telegram/HTTP: "Check my emails for anything urgent" │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Telegram   │    │     HTTP     │    │   Email      │          │
│  │   Channel    │    │   Channel    │    │   Tools      │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                    │                   │
│         └───────────────────┴────────────────────┘                  │
│                             │                                        │
│                             ▼                                        │
│                  ┌───────────────────┐                              │
│                  │   LangGraph       │                              │
│                  │   Agent           │                              │
│                  └─────────┬─────────┘                              │
│                            │                                         │
│          ┌─────────────────┼─────────────────┐                     │
│          ▼                 ▼                 ▼                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Gmail/      │  │  Auth        │  │  Tone        │              │
│  │  Outlook     │  │  Storage     │  │  Analysis    │              │
│  │  API         │  │  (Thread)    │  │  Storage     │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
data/users/{thread_id}/
├── auth/
│   └── email/
│       └── credentials.json       # Encrypted OAuth tokens
├── email_drafts.json              # Local draft copies
├── email_rules.json               # Automation rules
├── email_style_profile.json       # Learned writing style
└── email_samples/                 # Sample emails for learning
```

## Email Provider Abstraction

**File**: `src/executive_assistant/email/providers/base.py`

```python
class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def authenticate(self, credentials: dict) -> bool:
        """Validate credentials and refresh if needed."""

    @abstractmethod
    async def list_emails(
        self,
        folder: str = "INBOX",
        limit: int = 20,
        unread_only: bool = False
    ) -> List[EmailMessage]:
        """Fetch emails from specified folder."""

    @abstractmethod
    async def get_email(self, message_id: str) -> EmailMessage:
        """Fetch full email content."""

    @abstractmethod
    async def send_email(self, email: EmailDraft) -> str:
        """Send email and return message ID."""

    @abstractmethod
    async def draft_email(self, email: EmailDraft) -> str:
        """Save draft and return draft ID."""

    @abstractmethod
    async def search_emails(self, query: str) -> List[EmailMessage]:
        """Search emails by query."""
```

**Implementations**:
- `src/executive_assistant/email/providers/gmail.py` - Gmail API
- `src/executive_assistant/email/providers/outlook.py` - Microsoft Graph API
- `src/executive_assistant/email/providers/imap.py` - Generic IMAP/SMTP
- `src/executive_assistant/email/providers/icloud.py` - iCloud IMAP/SMTP

## Email Tools

**File**: `src/executive_assistant/tools/email_tools.py`

### Tool List:
1. **`connect_email`** - Start OAuth2 connection flow
2. **`disconnect_email`** - Remove connected email account
3. **`list_email_accounts`** - Show connected accounts
4. **`list_emails`** - Fetch recent emails
5. **`get_email`** - Get full email content
6. **`search_emails`** - Search emails by query
7. **`draft_email`** - Create draft response
8. **`send_draft`** - Send approved draft
9. **`reply_to_email`** - Reply to thread
10. **`forward_email`** - Forward email
11. **`archive_email`** - Archive/remove from inbox
12. **`mark_read`** - Mark as read
13. **`add_label`** - Add label/category (Gmail)
14. **`move_to_folder`** - Move to folder (Outlook)

### Example: User Flow

```
User: Check my emails for anything urgent

Agent: 🔴 **URGENT: Project Deadline**
From: john@acme.com
Date: Jan 3, 2:30 PM
Preview: We need the deliverables by EOD Friday...
ID: `123456`

Found 1 urgent email. Would you like me to draft a response?

User: Yes, draft a reply saying I'll review by Friday

Agent: ✅ **Draft created**

**To:** john@acme.com
**Subject:** Re: Project Deadline

Hi John,
Thanks for the update. I'll review the deliverables by EOD Friday...

Say "send draft 1" to send this email.

User: Send it

Agent: ✅ **Email sent!**
Message ID: `123457`
```

## Tone Learning & Personalization

### Style Profile Structure

```python
class UserStyleProfile(BaseModel):
    """User's email writing style profile."""

    # General characteristics
    formality_level: float  # 0.0 (casual) to 1.0 (formal)
    avg_sentence_length: float
    vocabulary_complexity: float

    # Signature patterns
    greetings: Dict[str, int]  # {"Hi": 45, "Dear": 10, "Hey": 30}
    signoffs: Dict[str, int]   # {"Best": 35, "Thanks": 20, "Regards": 5}
    common_phrases: List[str]  # ["Let's discuss", "Circle back"]

    # Context-specific styles
    recipient_styles: Dict[str, Dict]  # Email -> style adaptations
    category_styles: Dict[str, Dict]   # Category -> style adaptations

    # Metadata
    sample_count: int
    learned_at: datetime
    last_updated: datetime
```

### Tone Analysis Tools

**File**: `src/executive_assistant/tools/tone_analysis_tools.py`

```python
@tool
async def analyze_my_style(
   account: Optional[str] = None,
   sample_size: int = 50
) -> str:
    """Analyze user's writing style from sent emails."""

@tool
async def draft_in_my_style(
    to: Union[str, List[str]],
    subject: str,
    key_points: List[str],
    context: Optional[str] = None,
    tone: Optional[str] = None
) -> str:
    """Draft an email using learned writing style."""

@tool
async def find_similar_emails(
    query: str,
    account: Optional[str] = None,
    limit: int = 5
) -> str:
    """Find similar past emails for reference."""
```

---

# Part 3: Calendar & Contacts Integration

## Key Insight

Google and Microsoft use **single OAuth2 authorization** for all services. When a user connects their Gmail/Outlook account, you get access to Calendar and Contacts too (with proper scopes)!

### Shared Credentials

```
data/users/{thread_id}/
├── auth/
│   ├── email/credentials.json       # Email tokens
│   ├── calendar/credentials.json    # Can symlink to email credentials
│   └── contacts/credentials.json    # Can symlink to email credentials
```

For Google/Microsoft: **single credentials work for all services**. No need for separate auth files!

## Calendar Integration

### Calendar Provider Abstraction

**File**: `src/executive_assistant/calendar/providers/base.py`**

```python
class CalendarProvider(ABC):
    """Abstract base class for calendar providers."""

    @abstractmethod
    async def list_events(
        self,
        start_date: datetime,
        end_date: datetime,
        calendar_id: str = "primary"
    ) -> List[CalendarEvent]:
        """Fetch events within date range."""

    @abstractmethod
    async def create_event(self, event: CalendarEvent) -> str:
        """Create event and return event ID."""

    @abstractmethod
    async def find_free_time(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int,
        attendees: Optional[List[str]] = None
    ) -> List[TimeSlot]:
        """Find available time slots."""

    @abstractmethod
    async def list_calendars(self) -> List[Calendar]:
        """List user's calendars."""
```

**Implementations**:
- `src/executive_assistant/calendar/providers/google.py` - Google Calendar API
- `src/executive_assistant/calendar/providers/microsoft.py` - Microsoft Graph Calendar
- `src/executive_assistant/calendar/providers/icloud.py` - iCloud CalDAV

### Calendar Tools

**File**: `src/executive_assistant/tools/calendar_tools.py`

1. **`check_availability`** - Check when user is free
2. **`list_events`** - List events in date range
3. **`create_event`** - Create new event
4. **`schedule_meeting`** - Schedule meeting with attendees
5. **`find_meeting_time`** - Find time that works for multiple attendees

### Example: User Flow

```
User: When am I free tomorrow for a 1-hour meeting?

Agent: You're free tomorrow:
- 9:00 AM - 11:00 AM
- 2:00 PM - 5:00 PM
- After 6:00 PM

User: Schedule a meeting with John tomorrow at 2pm

Agent: ✅ **Meeting scheduled!**

**Project Review**
Tomorrow, 2:00 PM - 3:00 PM

Attendees:
- John (john@acme.com)
- You

Invites sent! 📧
```

## Contacts Integration

### Contacts Provider Abstraction

**File**: `src/executive_assistant/contacts/providers/base.py`**

```python
class ContactsProvider(ABC):
    """Abstract base class for contacts providers."""

    @abstractmethod
    async def list_contacts(
        self,
        limit: int = 50,
        search_query: Optional[str] = None
    ) -> List[Contact]:
        """Fetch contacts, optionally filtered by search."""

    @abstractmethod
    async def create_contact(self, contact: Contact) -> str:
        """Create contact and return contact ID."""

    @abstractmethod
    async def search_contacts(
        self,
        query: str,
        search_fields: Optional[List[str]] = None
    ) -> List[Contact]:
        """Search contacts by name, email, phone, etc."""
```

**Implementations**:
- `src/executive_assistant/contacts/providers/google.py` - Google People API
- `src/executive_assistant/contacts/providers/microsoft.py` - Microsoft Graph Contacts
- `src/executive_assistant/contacts/providers/icloud.py` - iCloud CardDAV

### Contacts Tools

**File**: `src/executive_assistant/tools/contacts_tools.py`

1. **`find_contact`** - Find contact by name/email/phone
2. **`list_contacts`** - List all contacts or search
3. **`create_contact`** - Create new contact
4. **`get_contact_info`** - Quick lookup (phone, email, etc.)

### Example: User Flow

```
User: What's John's phone number?

Agent: Found John Smith:
📧 Email: john.smith@acme.com
📱 Phone: +1-555-0123
🏢 Company: Acme Corp

User: Email John about the meeting

Agent: [Finds John's email + drafts in user's style]
✅ Draft created for John Smith (john@acme.com)

Say "send" to send this email.
```

## Cross-Service Integration

### Email + Calendar + Contacts Working Together

```
User: Set up a meeting with the sales team

Agent:
1. Searches contacts for "sales team" → Finds 5 people
2. Checks all their calendars → Finds mutual free time
3. Creates calendar event
4. Sends email invites to all attendees

Agent: ✅ Meeting scheduled for Wednesday 2pm.
Invites sent to Sarah, Mike, Jen, and Tom.
```

### Smart Features

**Extract Meetings from Emails:**
```
User: That email from John is a meeting invite, add it to my calendar

Agent: Found meeting in email:
**Project Review**
Date: Friday, Jan 5 at 2:00 PM
Location: Zoom link in email

Should I create this event?
```

**Cross-Service Search:**
```
User: Search for everything about Project Alpha

Agent: Found:
📧 **5 emails**
- Latest from John yesterday about deadline

👥 **2 contacts**
- John Smith (Project Lead)
- Sarah Johnson (Designer)

📅 **3 events**
- Project Alpha kickoff (Jan 1)
- Weekly standup (Mondays 9am)
- Deadline review (Jan 15)
```

---

# Shared Implementation Details

## Auth Storage Helper

**File**: `src/executive_assistant/email/storage.py`

```python
"""
Thread-scoped authentication storage.

Supports multiple services (email, calendar, contacts) with consistent directory structure:
data/users/{thread_id}/auth/{service}/
"""

from executive_assistant.storage.thread_storage import get_thread_id

def get_auth_dir(service: str) -> Path:
    """Get the auth directory for a specific service."""
    thread_id = get_thread_id()
    auth_dir = Path(f"data/users/{thread_id}/auth/{service}")
    auth_dir.mkdir(parents=True, exist_ok=True)
    return auth_dir

async def load_credentials(service: str) -> Dict:
    """Load credentials for a service."""
    auth_dir = get_auth_dir(service)
    cred_file = auth_dir / "credentials.json"

    if not cred_file.exists():
        return {}

    with open(cred_file, "r") as f:
        return json.load(f)

async def save_credentials(service: str, credentials: Dict) -> None:
    """Save credentials for a service."""
    auth_dir = get_auth_dir(service)
    cred_file = auth_dir / "credentials.json"

    with open(cred_file, "w") as f:
        json.dump(credentials, f, indent=2)

async def delete_credentials(service: str) -> None:
    """Delete credentials for a service."""
    auth_dir = get_auth_dir(service)
    cred_file = auth_dir / "credentials.json"

    if cred_file.exists():
        cred_file.unlink()
```

For Google/Microsoft, calendar and contacts can reuse email credentials:

```python
# Calendar credentials (reuses email tokens)
async def get_calendar_credentials() -> Dict:
    from executive_assistant.email.storage import load_email_credentials
    return await load_email_credentials()

# Contacts credentials (reuses email tokens)
async def get_contacts_credentials() -> Dict:
    from executive_assistant.email.storage import load_email_credentials
    return await load_email_credentials()
```

## Security Considerations

### Credential Storage
- **Encryption**: Fernet symmetric encryption (AES-128)
- **Key Management**: Environment variable, never in git
- **Storage Path**: `data/users/{thread_id}/auth/{service}/credentials.json`
- **Rotation**: Automatic token refresh (Gmail: 1 hour, Outlook: 90 minutes)
- **Revocation**: User can disconnect anytime via command

### Data Privacy
- **Thread-Scoped**: Each user's credentials and data isolated
- **No Logging**: Sensitive data never logged to console/files
- **Retention**: User-configurable, default 90 days
- **Right to Deletion**: Commands to delete all data

### OAuth2 Security
- **PKCE**: Use Proof Key for Code Exchange (prevents auth code interception)
- **State Parameter**: CSRF protection with thread_id binding
- **Scopes**: Minimal required scopes only
- **SSL Only**: Redirect URIs must be HTTPS (except localhost)

### Rate Limiting
- **Gmail API**: 250 quota units/second
- **Microsoft Graph**: 10,000 requests/10 minutes
- **Google Calendar API**: 10,000 requests per day per user
- **Google People API**: 10,000 requests per day per user
- **Implementation**: Exponential backoff, request queue

---

# Implementation Roadmap

## Phase 1: Email Foundation (Weeks 1-6)

### Sprint 1-2: Foundation (Weeks 1-2)
- Auth storage helper
- Email provider abstraction layer
- OAuth2 flow for Gmail
- HTTP callback endpoints
- Encrypt/decrypt token utilities

### Sprint 3-4: Core Tools (Weeks 3-4)
- Gmail + Outlook + iCloud provider implementations
- `connect_email`, `disconnect_email`, `list_email_accounts` tools
- `list_emails` and `get_email` tools
- Telegram/HTTP commands for email management

### Sprint 5-6: Draft & Send (Weeks 5-6)
- `draft_email` tool
- `send_draft` tool
- Draft approval workflow
- Local draft storage

## Phase 2: Tone Learning (Weeks 7-8)

- Email sample collection
- Style analysis tools (`analyze_my_style`)
- Enhanced draft generation (`draft_in_my_style`)
- Style profile storage (TDB/VDB)

## Phase 3: Advanced Email Features (Weeks 9-10)

- Email summarization
- Smart reply suggestions
- Scheduling integration
- Multi-account support

## Phase 4: Calendar (Weeks 11-14)

- Calendar provider abstraction (Google, Microsoft, iCloud)
- Core calendar tools (list, create, update, delete)
- Availability checking
- Meeting scheduling with attendees

## Phase 5: Contacts (Weeks 15-16)

- Contacts provider abstraction (Google, Microsoft, iCloud)
- Core contacts tools (list, create, search)
- Contact caching
- Relationship tracking

## Phase 6: Integration & Polish (Weeks 17-18)

- Email + Calendar integration (extract events from emails)
- Email + Contacts integration (smart email composition)
- Cross-service search
- Comprehensive testing
- Documentation
- Security audit

### Total Timeline: ~18 weeks (4.5 months)

**Alternative**: Email only = 12 weeks

---

# Testing Strategy

## Unit Tests

### Email
- OAuth2 flow with mock providers
- Token refresh logic
- Encryption/decryption
- Draft approval workflow
- Style profile updates

### Calendar
- Event CRUD operations
- Availability calculation
- Recurring event logic
- Multi-attendee scheduling

### Contacts
- Contact CRUD operations
- Search functionality
- vCard parsing (for iCloud)

## Integration Tests

- Full OAuth2 flow with test accounts
- Email fetching from real Gmail/Outlook/iCloud test accounts
- Draft creation and sending
- Calendar event creation and management
- Contact creation and lookup
- Style profile generation from sample emails

## VCR Cassettes

- Record real API calls for Gmail/Outlook/Google Calendar
- Replay in tests for consistency
- Prevent rate limiting during development

## Test Fixtures

- Sample emails with various styles
- Sample calendar events
- Sample contacts
- Fake OAuth2 responses
- Encrypted credential samples

## Test Accounts

- Create test Gmail accounts via Google Workspace
- Create test Outlook accounts via Microsoft 365 Developer Program
- Create test iCloud account
- Use dedicated test accounts to avoid affecting real data

---

# Success Metrics

## Technical Metrics

### Email
- OAuth2 success rate: >95%
- Token refresh success rate: >99%
- Email fetch latency: <2 seconds for 50 emails
- Draft generation: <5 seconds
- Style accuracy (user ratings): >4/5

### Calendar
- Events created per user per week: 5+
- Scheduling accuracy: >95%
- Availability check latency: <3 seconds
- Multi-attendee scheduling: <10 seconds

### Contacts
- Contacts searched per user per day: 10+
- Contact creation rate: 2+ per week per user
- Search accuracy: >90%

### Integration
- Cross-service tasks per day: 3+
- "Schedule meeting with X" success rate: >85%

## User Metrics

- Connection completion rate: >80%
- Draft approval rate: >70%
- Daily active users: TBD
- Average emails checked per session: 5-10
- Style improvement over time (measured via user feedback)

---

# Python Dependencies

Add to `pyproject.toml`:

```toml
[project.dependencies]
# Email
google-api-python-client = "^2.100.0"
msgraph-sdk = "^1.0.0"
oauthlib = "^3.2.2"

# Calendar
google-api-python-client = "^2.100.0"  # Includes Calendar
caldav = "^1.3.9"        # CalDAV for iCloud

# Contacts
google-api-python-client = "^2.100.0"  # Includes People API
vobject = "^0.9.7"       # vCard/iCalendar parser

# IMAP/SMTP (already included)
# imaplib, smtplib - stdlib
```

---

# References

## Google
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Google Calendar API](https://developers.google.com/calendar)
- [Google People API (Contacts)](https://developers.google.com/people)
- [OAuth 2.0 for Mobile & Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)

## Microsoft
- [Microsoft Graph Mail](https://docs.microsoft.com/graph/api/resources/mail-api-overview)
- [Microsoft Graph Calendar](https://docs.microsoft.com/graph/api/resources/calendar-api-overview)
- [Microsoft Graph Contacts](https://docs.microsoft.com/graph/api/resources-contacts-overview)
- [Azure App Registration](https://docs.microsoft.com/azure/active-directory/develop/quickstart-register-app)

## Standards
- [CalDAV (RFC 4791)](https://tools.ietf.org/html/rfc4791) - Calendar protocol
- [CardDAV (RFC 6352)](https://tools.ietf.org/html/rfc6352) - Contacts protocol
- [RFC 3501 - IMAP4rev1](https://tools.ietf.org/html/rfc3501) - Email protocol
