# Email Channel Implementation Plan - Stalwart Mail Server

**Date:** 2025-01-19
**Author:** Claude (Sonnet 4.5)
**Status:** Planning Phase
**Related Issue:** N/A

---

## Executive Summary

Add email as a new communication channel for Executive Assistant using **Stalwart Mail Server** - an all-in-one open-source mail & collaboration server.

**Key Features:**
- ✅ Email (IMAP/SMTP) - Send and receive emails
- ✅ Calendar (CalDAV) - Sync and manage calendar events
- ✅ Contacts (CardDAV) - Sync and manage contacts
- ✅ Self-hosted - No third-party API dependencies
- ✅ Static email addresses - Users get `user@executive_assistant.ai`
- ✅ Thread continuity - Conversation tracking via email headers

**Solution:** Stalwart Mail Server + custom EmailChannel implementation

---

## Background

### Why Email?

Users want multiple ways to interact with Executive Assistant:
- **Telegram** - Already implemented, great for quick messages
- **Email** - Needed for:
  - Longer-form conversations
  - File attachments
  - Corporate/enterprise integration
  - Users who prefer email over chat apps

### Why Stalwart?

After researching self-hosted email servers, **Stalwart** emerged as the best choice:

| Feature | Stalwart | Others |
|---------|----------|--------|
| Email (IMAP/SMTP) | ✅ | ✅ |
| Calendar (CalDAV) | ✅ Built-in | ❌ Separate service needed |
| Contacts (CardDAV) | ✅ Built-in | ❌ Separate service needed |
| Modern Language | Rust (safe, fast) | C, Java, Python |
| Active Development | ✅ | ⚠️ Varies |
| Single Service | ✅ All-in-one | ❌ Multiple services |

**Alternatives Considered:**
- **Mail-in-a-Box**: Good for email, requires separate Radicale for CalDAV/CardDAV
- **Postfix + Dovecot**: Complex setup, separate services needed
- **Third-party APIs** (Nylas): Easier but monthly costs, less control

### License: AGPL-3.0

**Stalwart is licensed under AGPL-3.0**, which means:
- ✅ Free to use, modify, and self-host
- ✅ Connecting via standard protocols (IMAP, SMTP, CalDAV, CardDAV) does NOT make Executive Assistant a derivative work
- ✅ No enterprise license required for deploying Executive Assistant with Stalwart
- ⚠️ Only if you modify Stalwart's source code directly must you share those modifications

**Conclusion:** Executive Assistant can integrate with Stalwart via standard protocols without licensing concerns.

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Executive Assistant                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Telegram   │  │    Email     │  │     HTTP     │          │
│  │   Channel    │  │   Channel    │  │   Channel    │          │
│  └──────────────┘  └──────┬───────┘  └──────────────┘          │
│                           │                                     │
│                           ▼                                     │
│                    ┌─────────────┐                              │
│                    │    Agent    │                              │
│                    └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│    Stalwart   │  │   Postgres    │  │  File System  │
│  Mail Server  │  │   Database    │  │  (groups/)    │
└───────────────┘  └───────────────┘  └───────────────┘
     IMAP/SMTP
     CalDAV/CardDAV
```

### Email Channel Components

**EmailChannel Class:**
```python
class EmailChannel(BaseChannel):
    """
    Email channel for Executive Assistant using IMAP/SMTP + CalDAV/CardDAV.

    Features:
    - IMAP polling for incoming emails
    - SMTP for sending responses
    - CalDAV for calendar integration
    - CardDAV for contacts integration
    - Attachment handling
    - Thread tracking via References/In-Reply-To headers
    """

    def __init__(
        self,
        agent: Runnable,
        registry: Any = None,
        imap_server: str = "localhost:993",
        smtp_server: str = "localhost:587",
        caldav_url: str = "http://localhost:8008",
        carddav_url: str = "http://localhost:8008",
    ):
```

**Key Modules:**
1. **IMAP Poller** - Background task that checks for new emails
2. **Email Parser** - Converts emails to MessageFormat
3. **SMTP Sender** - Sends Executive Assistant's responses
4. **CalDAV Client** - Syncs calendar events
5. **CardDAV Client** - Syncs contacts

---

## Message Flow

### Incoming Email Flow

```
1. User sends email → john@executive_assistant.ai
2. Stalwart receives via SMTP (port 25)
3. Stalwart stores in IMAP inbox
4. EmailChannel IMAP poller detects new email
5. EmailChannel parses to MessageFormat:
   - user_id: "email:john@executive_assistant.ai"
   - conversation_id: "email:{thread_id}"
   - content: Email body (HTML/text)
   - attachments: List of files
6. EmailChannel.handle_message() → Agent
7. Agent processes → Response
8. EmailChannel.send_message() → SMTP → User's inbox
```

### Threading Detection

Emails are grouped into conversations using standard headers:
- **Message-ID** - Unique identifier for each email
- **In-Reply-To** - Points to parent email's Message-ID
- **References** - Full thread chain

Example:
```
Email 1: Message-ID: <msg1@executive_assistant.ai>
Email 2: Message-ID: <msg2@executive_assistant.ai>
         In-Reply-To: <msg1@executive_assistant.ai>
         References: <msg1@executive_assistant.ai>
Email 3: Message-ID: <msg3@executive_assistant.ai>
         In-Reply-To: <msg2@executive_assistant.ai>
         References: <msg1@executive_assistant.ai> <msg2@executive_assistant.ai>
```

### User Identification

```python
# Extract user email from "From:" header
from_email = "john@executive_assistant.ai"

# Map to user_id
user_id = f"email:{from_email}"  # "email:john@executive_assistant.ai"

# Validate against allowed list
if from_email not in ALLOWED_EMAILS:
    logger.warning(f"Email from unauthorized address: {from_email}")
    return
```

---

## Implementation Plan

### Phase 1: Infrastructure Setup (Week 1)

**1.1 Deploy Stalwart Mail Server**

Docker deployment:
```bash
docker run -d \
  --name stalwart-mail \
  -p 25:25 -p 587:587 -p 993:993 -p 8008:8008 \
  -v /opt/stalwart-mail:/data \
  -e STALWART_DOMAIN=executive_assistant.ai \
  stalwartlabs/mail-server:latest
```

**1.2 Configure DNS Records**

```dns
# MX Record (receives email for @executive_assistant.ai)
executive_assistant.ai.  IN  MX  10  mail.executive_assistant.ai.

# A Record (mail server IP)
mail.executive_assistant.ai.  IN  A  YOUR_SERVER_IP

# SPF (prevents spam)
executive_assistant.ai.  IN  TXT  "v=spf1 mx include:spf.mx.cloudflare.net ~all"

# DKIM (email authentication)
selector1._domainkey.executive_assistant.ai.  IN  TXT  "p=YOUR_DKIM_KEY"

# dmarc (policy)
_dmarc.executive_assistant.ai.  IN  TXT  "v=DMARC1; p=none; rua=mailto:dmarc@executive_assistant.ai"
```

**1.3 Create Email Accounts**

```bash
# Executive Assistant's account
hello@executive_assistant.ai

# Test users
alice@executive_assistant.ai
bob@executive_assistant.ai
```

**1.4 Test IMAP/SMTP Connectivity**

```bash
# Test with swaks (email tool)
swaks --to hello@executive_assistant.ai \
      --from alice@executive_assistant.ai \
      --server localhost:25 \
      --body "Test email"

# Test IMAP with OpenSSL
openssl s_client -connect localhost:993
```

### Phase 2: EmailChannel Implementation (Week 2-3)

**Files to Create:**

| File | Purpose |
|------|---------|
| `src/executive_assistant/channels/email_channel.py` | EmailChannel class |
| `src/executive_assistant/chapters/email_imap.py` | IMAP polling background task |
| `src/executive_assistant/chapters/email_smtp.py` | SMTP sender |
| `src/executive_assistant/storage/caldav_storage.py` | CalDAV calendar client |
| `src/executive_assistant/storage/carddav_storage.py` | CardDAV contacts client |
| `tests/test_email_channel.py` | Unit tests |

**Files to Modify:**

| File | Changes |
|------|---------|
| `src/executive_assistant/main.py` | Register EmailChannel |
| `src/executive_assistant/config/settings.py` | Add email config |
| `config.yaml` | Add email channel settings |
| `pyproject.toml` | Add dependencies |
| `.env.example` | Add environment variables |

**Key Implementation Tasks:**

1. **IMAP Poller** (Background Task)
   ```python
   async def _imap_poller(self):
       """Background task that polls IMAP for new emails."""
       while self._running:
           for account in self._monitored_accounts:
               await self._check_imap(account)
           await asyncio.sleep(self._poll_interval)
   ```

2. **Email Parser** (Email → MessageFormat)
   ```python
   def _parse_email_to_message(self, email_message) -> MessageFormat:
       """Parse email.raw to MessageFormat."""
       # Extract headers, body, attachments
       # Detect threading via References/In-Reply-To
       # Convert HTML/text to plain text
       # Extract user_id from From: header
   ```

3. **SMTP Sender** (MessageFormat → Email)
   ```python
   async def send_message(self, conversation_id: str, content: str, **kwargs):
       """Send Executive Assistant's response via SMTP."""
       # Build email with In-Reply-To/References
       # Add attachments if any
       # Send via SMTP
   ```

4. **CalDAV Integration**
   ```python
   async def _sync_calendar_events(self):
       """Sync calendar events with Executive Assistant's reminders."""
       # Connect to CalDAV
       # Fetch upcoming events
       # Integrate with reminder system
   ```

5. **CardDAV Integration**
   ```python
   async def _sync_contacts(self):
       """Sync contacts with user profiles."""
       # Connect to CardDAV
       # Fetch contact list
       # Update user metadata
   ```

### Phase 3: Configuration

**Environment Variables (.env):**

```bash
# Email Channel Configuration
EXECUTIVE_ASSISTANT_CHANNELS=email,telegram

# Stalwart IMAP Configuration
EMAIL_IMAP_SERVER=localhost:993
EMAIL_IMAP_USERNAME=hello@executive_assistant.ai
EMAIL_IMAP_PASSWORD=app_password_here
EMAIL_IMAP_USE_TLS=true

# Stalwart SMTP Configuration
EMAIL_SMTP_SERVER=localhost:587
EMAIL_SMTP_USERNAME=hello@executive_assistant.ai
EMAIL_SMTP_PASSWORD=app_password_here
EMAIL_SMTP_USE_TLS=true

# CalDAV/CardDAV Configuration
EMAIL_CALDAV_URL=http://localhost:8008
EMAIL_CARDDAV_URL=http://localhost:8008

# Monitored Accounts (comma-separated)
EMAIL_MONITORED_ACCOUNTS=hello@executive_assistant.ai,alice@executive_assistant.ai,bob@executive_assistant.ai

# Polling Interval (seconds)
EMAIL_POLL_INTERVAL=30
```

**config.yaml additions:**

```yaml
channels:
  email:
    enabled: true
    imap_server: "localhost:993"
    smtp_server: "localhost:587"
    caldav_url: "http://localhost:8008"
    carddav_url: "http://localhost:8008"
    monitored_accounts:
      - hello@executive_assistant.ai
      - alice@executive_assistant.ai
    poll_interval: 30  # seconds
```

### Phase 4: Testing (Week 4)

**Unit Tests:**

1. Email parser (Email → MessageFormat)
2. SMTP sender (MessageFormat → Email)
3. Threading detection (Message-ID, References, In-Reply-To)
4. Attachment handling
5. User identification

**Integration Tests:**

1. Send test email → Verify receipt
2. Executive Assistant reply → Verify delivery
3. Thread continuity (reply chain)
4. CalDAV event sync
5. CardDAV contact sync

**Manual Testing:**

```bash
# 1. Start Executive Assistant with email channel
uv run executive_assistant

# 2. Send test email via command line
swaks --to hello@executive_assistant.ai \
      --from alice@executive_assistant.ai \
      --server localhost:25 \
      --body "Hello Executive Assistant, what's the weather?"

# 3. Verify Executive Assistant responds
# Check IMAP inbox for reply
```

### Phase 5: Production Hardening (Week 5)

**Tasks:**
- Error handling and logging
- Monitoring and alerting
- Security audit
- Performance optimization
- Documentation

---

## Dependencies

### Python Packages

```toml
# pyproject.toml
"imap-tools>=3.0.0",           # IMAP client
"aiosmtplib>=3.0.0",          # Async SMTP
"caldav>=2.0.0",              # CalDAV client
"vobject>=0.9.7",             # vCard (iCalendar) parsing
"email-reply-parser>=0.5.0",  # Email reply parsing
"beautifulsoup4>=4.12.0",     # HTML email parsing
```

### Docker Services

```yaml
# docker-compose.email.yml
services:
  stalwart-mail:
    image: stalwartlabs/mail-server:latest
    ports:
      - "25:25"    # SMTP
      - "587:587"  # SMTP submission
      - "993:993"  # IMAPS
      - "8008:8008"  # CalDAV/CardDAV/WebDAV
    volumes:
      - /opt/stalwart-mail:/data
    environment:
      - STALWART_DOMAIN=executive_assistant.ai
    restart: unless-stopped
```

---

## Security Considerations

1. **App Passwords**: Use app passwords, not real passwords
2. **TLS/SSL**: Enforce encrypted connections (IMAPS, SMTPS, STARTTLS)
3. **Spam Filtering**: Configure Stalwart's spam filters
4. **Rate Limiting**: Limit outgoing emails per minute
5. **Attachment Scanning**: ClamAV integration (optional)
6. **User Validation**: Whitelist allowed email addresses

---

## Performance Considerations

**IMAP Polling Optimization:**
- Use IDLE mode if supported (push instead of poll)
- Batch fetch multiple emails
- Parallel polling for multiple accounts
- Cache IMAP connections

**SMTP Sending:**
- Connection pooling
- Batch sending (if sending multiple replies)
- Retry logic for failed sends
- Queue management (background tasks)

---

## Success Criteria

✅ EmailChannel receives emails via IMAP
✅ EmailChannel sends responses via SMTP
✅ Thread continuity maintained (reply chains)
✅ User identification via email addresses
✅ Attachments handled correctly
✅ CalDAV calendar sync working
✅ CardDAV contacts sync working
✅ Error handling robust (IMAP disconnect, SMTP failures)
✅ Performance acceptable (polling < 30s, response < 10s)
✅ Security hardened (TLS, spam filtering)

---

## Open Questions

1. **Email Address Provisioning**: How will users be assigned `user@executive_assistant.ai` addresses?
   - Manual admin assignment?
   - Self-service registration?
   - Integration with group system?

2. **Storage**: Where will email history be stored?
   - Keep in Stalwart only?
   - Archive to database?
   - Retention policy?

3. **Quotas**: Disk space limits per user?
   - Suggested: 1GB per user, expandable

4. **Backup**: Email backup strategy?
   - Stalwart data backup
   - Off-site backup recommendations

---

## References

**Stalwart Documentation:**
- Website: https://stalw.art/
- GitHub: https://github.com/stalwartlabs/stalwart
- Documentation: https://github.com/stalwartlabs/stalwart/docs

**Email Channel Research:**
- Best Self-Hosted Email Servers 2025: https://runcloud.io/blog/best-self-hosted-email-server
- Self-Hosting Guide: https://mailserverguru.com/self-host-email-server/

**Python Libraries:**
- imap-tools: https://github.com/martinrusev/imap-tools
- aiosmtplib: https://github.com/ecstasyprime/aiosmtplib
- caldav: https://github.com/python-caldav/caldav
- vobject: https://github.com/eventable/vobject

**Existing Architecture:**
- Channel base class: `src/executive_assistant/channels/base.py`
- Telegram implementation: `src/executive_assistant/channels/telegram.py`
- Message format: `src/executive_assistant/channels/base.py` (MessageFormat class)

---

## Appendix: Implementation Notes

**Stalwart as Unified Solution:**
- Single server for email (IMAP/SMTP), calendar (CalDAV), and contacts (CardDAV)
- No need for separate services (unlike Mail-in-a-Box + Radicale)
- Simplified deployment and maintenance

**Calendar & Contacts Integration:**

CalDAV integration point: `src/executive_assistant/storage/reminders.py`
- Sync calendar events to Executive Assistant's reminder system
- Allow Executive Assistant to create events via CalDAV

CardDAV integration point: `src/executive_assistant/storage/group_storage.py`
- Sync contacts to user profiles
- Extract contact metadata (name, email, phone)

---

**End of Document**
