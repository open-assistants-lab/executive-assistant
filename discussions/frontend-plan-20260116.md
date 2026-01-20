# Executive Assistant Frontend Plan (Next.js + shadcn/ui)

## Objective

Build a web frontend for Executive Assistant using Next.js and shadcn/ui, allowing users to:
- Chat with Executive Assistant via browser
- Access their own user space (conversations, KB, DB, files, reminders)
- Manage their data and settings

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Browser (Next.js)                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │ Chat UI    │  │ Knowledge  │  │ Database   │  │ Files      │   │
│  │ (shadcn)   │  │ Base       │  │ Viewer     │  │ Manager    │   │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘   │
│           │               │              │              │           │
│           └───────────────┴──────────────┴──────────────┘           │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │ API Layer   │                                  │
│                    │ (fetch/TS)  │                                  │
│                    └──────┬──────┘                                  │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Executive Assistant Backend (FastAPI)                       │
│  POST /message              │  Send message, stream response       │
│  GET /conversations/{id}    │  Get conversation history            │
│  GET /health                 │  Health check                        │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  TODO: Add user-specific data endpoints                       │ │
│  │  GET /user/{user_id}/kb          │  List KB collections          │ │
│  │  GET /user/{user_id}/db          │  List DB tables               │ │
│  │  GET /user/{user_id}/files       │  List files                   │ │
│  │  GET /user/{user_id}/reminders   │  List reminders               │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Frontend
| Technology | Purpose | Version |
|------------|---------|---------|
| **Next.js** | React framework | 15 (App Router) |
| **TypeScript** | Type safety | 5.x |
| **shadcn/ui** | UI component library | Latest |
| **Tailwind CSS** | Styling | 4.x (bundled with shadcn) |
| **TanStack Query** | Server state management | 5.x |
| **Zustand** | Client state | 4.x |
| **React Hook Form** | Form handling | 7.x |
| **Zod** | Schema validation | 3.x |

### Backend Additions (Required)
| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `GET /user/{user_id}/kb` | List KB collections | New |
| `GET /user/{user_id}/kb/{collection}` | Get collection details | New |
| `DELETE /user/{user_id}/kb/{collection}` | Delete collection | New |
| `GET /user/{user_id}/db` | List DB tables | New |
| `GET /user/{user_id}/db/{table}` | Query DB table | New |
| `GET /user/{user_id}/files` | List files | New |
| `GET /user/{user_id}/files/*` | Download file | New |
| `DELETE /user/{user_id}/files/*` | Delete file | New |
| `GET /user/{user_id}/reminders` | List reminders | New |
| `POST /user/{user_id}/reminders` | Create reminder | New |
| `DELETE /user/{user_id}/reminders/{id}` | Delete reminder | New |

---

## User Identification Strategy

### Web Visitor Thread ID
- **No authentication required** for MVP
- Executive Assistant assigns a visitor thread ID: `http:visitor_{uuid}`
- Stored in browser localStorage + session cookie
- All user data (files, KB, DB, reminders) scoped to this thread_id

### Merge Flow: Web Visitor → Telegram User

**Step 4: Code Confirmation (Security)**

```
┌─────────────────────────────────────────────────────────────────────┐
│  A. Telegram Initiate Merge                                         │
│  ─────────────────────────────────                                  │
│  User in Telegram: "/merge"                                        │
│  Executive Assistant: "I'll generate a code. Enter it in your web browser to    │
│          confirm merging your web data with this Telegram account."│
│  Executive Assistant generates: 6-digit code (e.g., "ABC123")                   │
│  Code valid for: 10 minutes                                        │
│  Stored in DB with expiry                                          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  B. Web User Enters Code                                           │
│  ─────────────────────────────────                                  │
│  Frontend: Shows "Enter merge code" input (in settings or modal)    │
│  User enters: "ABC123"                                             │
│  Frontend: POST /api/merge/verify { code: "ABC123", thread_id }    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  C. Verification & Merge                                           │
│  ─────────────────────────────────                                  │
│  Backend:                                                           │
│  1. Validates code, checks expiry                                  │
│  2. Links web thread_id to Telegram user_id                       │
│  3. Calls merge_threads([web_thread_id], telegram_user_id)        │
│  4. Returns success to both frontend and Telegram                  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  D. Confirmation                                                   │
│  ─────────────────────────────────                                  │
│  Telegram: "✅ Merge complete! Your web data is now linked."        │
│  Web: Shows success banner, updates UI to show merged status       │
└─────────────────────────────────────────────────────────────────────┘
```

### Database Schema for Merge Codes

```sql
CREATE TABLE merge_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL,           -- 6-digit code
    source_thread_id VARCHAR(255),        -- Web thread to merge
    target_thread_id VARCHAR(255),        -- Telegram thread initiating
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,        -- code expiry
    consumed_at TIMESTAMP,                -- NULL until used
    status VARCHAR(20) DEFAULT 'pending'  -- pending, consumed, expired
);
```

### How Merge Works

```python
# Existing implementation in src/executive_assistant/storage/user_registry.py
await registry.merge_threads(
    source_thread_ids=["http:visitor_abc123"],
    target_user_id="user@example.com"  # Or any persistent user_id
)
```

**What happens:**
1. `conversations.user_id` updated to `target_user_id`
2. `file_paths.user_id` updated to `target_user_id`
3. `db_paths.user_id` updated to `target_user_id`
4. Audit log recorded in `user_registry` table

**What doesn't happen:**
- LangGraph checkpoints remain separate (conversation state not migrated)
- Physical files/databases NOT moved (still in original thread directories)

### Data Access After Merge

```python
# After merge, user's data is accessible via user_id
user_files = await registry.get_user_files(user_id="user@example.com")
user_dbs = await registry.get_user_dbs(user_id="user@example.com")
user_conversations = await registry.get_user_conversations(user_id="user@example.com")
```

The frontend would fetch merged data via new user-specific endpoints.

---

## Multi-Browser Question: Safari + Chrome = Two Threads?

### The Problem

```
Safari (first visit)  → thread_id = "http:visitor_abc123"  (in Safari localStorage)
Chrome (first visit) → thread_id = "http:visitor_def456"  (in Chrome localStorage)
```

**Yes, currently each browser gets its own visitor thread.** This is because:
- `thread_id` is stored in browser localStorage (not shared across browsers)
- No server-side session to link browsers
- No cross-browser cookie mechanism exists

### Solutions

| Approach | Pros | Cons | Complexity |
|----------|------|------|------------|
| **Accept (merge later)** | Simple, private | Scattered data, manual merge | Low |
| **Browser linking via code** | User controls linking | Manual step required | Medium |
| **Email-based session** | Unified across devices | Requires email upfront | Medium |
| **Fingerprinting** | Automatic | Privacy concerns, inaccurate | High |

### Recommended: Browser Linking via Code

Similar to the merge flow, but for linking browsers:

```
┌─────────────────────────────────────────────────────────────────────┐
│  User in Safari: Settings → "Link another browser"                │
│  Frontend generates: code "LINK789"                                │
│  User opens Chrome, goes to executive_assistant.com → "Enter link code"        │
│  Backend links both threads to a "user_id" (e.g., "user_xyz")     │
│  Both browsers now share the same user_id                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementation: Browser Linking

```sql
-- Extended merge_codes table
CREATE TABLE merge_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    source_thread_id VARCHAR(255),        -- Thread being linked
    target_user_id VARCHAR(255),          -- Persistent user_id
    link_type VARCHAR(20),                -- 'merge' or 'link'
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    consumed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending'
);
```

```python
# Backend: Link handler
async def link_browser_thread(code: str, thread_id: str):
    """Link a visitor thread to a persistent user_id via code."""
    # 1. Validate code
    # 2. Get target_user_id from code
    # 3. Update conversations.user_id = target_user_id
    # 4. Return user_id to frontend
    pass
```

### Alternative: Email-First (If You Want Unified ID)

```
First visit: executive_assistant.com
├── "Enter your email to continue"
├── User: user@example.com
├── Backend: Creates thread_id = "http:user@example.com"
└── Stores user_id in cookie

All subsequent visits:
├── Cookie contains user_id
├── Backend looks up user_id
└── Routes to existing thread
```

**Trade-off:** More friction on first visit, but consistent ID across browsers/devices.

### Recommended Approach for MVP

**Accept the two-thread reality, make merge easy:**

1. Each browser gets its own `http:visitor_{uuid}` thread
2. Frontend shows: "Your data lives in this browser. Link to other devices?"
3. User clicks → generates link code
4. User enters code in another browser → threads linked
5. After linking, both browsers share `user_id`

This keeps the first visit frictionless while offering a path to consolidation.

---

## Pages & Components

### Page Structure (App Router)

```
app/
├── (auth)/
│   ├── login/
│   │   └── page.tsx           # User ID entry (MVP) or login (future)
│   └── layout.tsx
├── (app)/
│   ├── chat/
│   │   ├── page.tsx           # Main chat interface
│   │   └── components/
│   │       ├── chat-input.tsx
│   │       ├── chat-message.tsx
│   │       └── chat-sidebar.tsx
│   ├── kb/
│   │   ├── page.tsx           # Knowledge base management
│   │   └── components/
│   │       ├── kb-list.tsx
│   │       ├── kb-create.tsx
│   │       └── kb-search.tsx
│   ├── db/
│   │   ├── page.tsx           # Database viewer
│   │   └── components/
│   │       ├── db-tables.tsx
│   │       └── db-query.tsx
│   ├── files/
│   │   ├── page.tsx           # File manager
│   │   └── components/
│   │       ├── file-list.tsx
│   │       ├── file-upload.tsx
│   │       └── file-preview.tsx
│   ├── reminders/
│   │   ├── page.tsx           # Reminder management
│   │   └── components/
│   │       ├── reminder-list.tsx
│   │       └── reminder-create.tsx
│   ├── settings/
│   │   ├── page.tsx           # User settings + merge/link
│   │   └── components/
│   │       ├── merge-code-input.tsx    # Enter merge code from Telegram
│   │       ├── link-browser.tsx         # Generate link code
│   │       ├── linked-browsers.tsx      # Show linked browsers/threads
│   │       └── thread-info.tsx          # Show current thread_id
│   └── layout.tsx             # Root layout with nav
├── api/
│   └── chat/
│       └── route.ts           # API route for streaming (optional proxy)
├── layout.tsx                 # Root layout
└── page.tsx                   # Redirect to chat
```

### shadcn/ui Components to Use

```bash
# Core UI
npx shadcn@latest add button
npx shadcn@latest add input
npx shadcn@latest add textarea
npx shadcn@latest add card
npx shadcn@latest add dialog
npx shadcn@latest add dropdown-menu
npx shadcn@latest add tabs
npx shadcn@latest add toast
npx shadcn@latest add separator
npx shadcn@latest add scroll-area
npx shadcn@latest add badge
npx shadcn@latest add alert
npx shadcn@latest add select
npx shadcn@latest add switch
npx shadcn@latest add slider
npx shadcn@latest add form
npx shadcn@latest add table
npx shadcn@latest add skeleton
npx shadcn@latest add avatar
npx shadcn@latest add collapsible
```

---

## Component Design

### Chat Interface

```
┌─────────────────────────────────────────────────────────────┐
│  Executive Assistant                        [KB] [DB] [Files] [⚙️]       │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌──────────────────────────────────────┐  │
│  │ History   │  │  ┌─────────────────────────────────┐  │  │
│  │           │  │  │ AI: Hello! How can I help...    │  │  │
│  │ Today     │  │  │                                 │  │  │
│  │ Yesterday │  │  │ User: What's in my KB?          │  │  │
│  │           │  │  │                                 │  │  │
│  │           │  │  │ AI: You have 3 collections...   │  │  │
│  │           │  │  │                                 │  │  │
│  │           │  │  └─────────────────────────────────┘  │  │
│  │           │  │                                      │  │
│  └───────────┘  │  [Type your message...]          [Send]│  │
│                 └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Navigation (Mobile Responsive)

```tsx
// Desktop: Sidebar
// Mobile: Hamburger menu
<Sidebar>
  <SidebarItem icon={MessageSquare} label="Chat" />
  <SidebarItem icon={Book} label="Knowledge Base" />
  <SidebarItem icon={Database} label="Database" />
  <SidebarItem icon={FolderOpen} label="Files" />
  <SidebarItem icon={Bell} label="Reminders" />
  <SidebarItem icon={Settings} label="Settings" />
</Sidebar>
```

---

## API Integration Strategy

### Streaming Chat

```typescript
// app/chat/page.tsx
async function sendMessage(content: string, userId: string) {
  const response = await fetch('http://localhost:8000/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      user_id: userId,
      stream: true,
    }),
  })

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value)
    // Parse SSE format: "data: {...}\n\n"
    for (const line of chunk.split('\n')) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        if (data.done) break
        appendMessage(data.content, data.role)
      }
    }
  }
}
```

### User Data Fetching

```typescript
// Use TanStack Query for server state
import { useQuery } from '@tanstack/react-query'

function useKBCollections(userId: string) {
  return useQuery({
    queryKey: ['kb', userId],
    queryFn: async () => {
      const res = await fetch(`/api/user/${userId}/kb`)
      return res.json()
    },
  })
}

function useReminders(userId: string) {
  return useQuery({
    queryKey: ['reminders', userId],
    queryFn: async () => {
      const res = await fetch(`/api/user/${userId}/reminders`)
      return res.json()
    },
  })
}
```

---

## State Management

### Client State (Zustand)

```typescript
// stores/user-store.ts
interface UserStore {
  userId: string | null
  setUserId: (id: string) => void
  conversations: Conversation[]
  currentConversation: string | null
  setCurrentConversation: (id: string) => void
}

export const useUserStore = create<UserStore>((set) => ({
  userId: localStorage.getItem('executive_assistant_user_id'),
  setUserId: (id) => {
    localStorage.setItem('executive_assistant_user_id', id)
    set({ userId: id })
  },
  conversations: [],
  currentConversation: null,
  setCurrentConversation: (id) => set({ currentConversation: id }),
}))
```

### Server State (TanStack Query)

- KB collections
- DB tables
- File listings
- Reminders
- Conversation history

---

## Deployment

### Docker Compose Setup

```yaml
services:
  executive_assistant-backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - EXECUTIVE_ASSISTANT_CHANNELS=http
      - POSTGRES_URL=postgresql://executive_assistant:password@postgres:5432/executive_assistant_db
    depends_on:
      - postgres

  executive_assistant-frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - executive_assistant-backend

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_DB=executive_assistant_db
      - POSTGRES_USER=executive_assistant
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Directory Structure

```
executive_assistant/
├── docker-compose.yml
├── Dockerfile              # Backend (FastAPI)
├── frontend/
│   ├── Dockerfile          # Frontend (Next.js)
│   ├── package.json
│   ├── next.config.js
│   └── src/
└── src/executive_assistant/             # Backend code
```

---

## Implementation Phases

### Phase 1: MVP Chat Interface
- [ ] Next.js project setup with shadcn/ui
- [ ] Basic chat UI (input, messages, streaming)
- [ ] User ID selection (stored in localStorage)
- [ ] Connect to existing `/message` endpoint

### Phase 2: Data Views
- [ ] KB collections list and search
- [ ] DB tables viewer
- [ ] File manager (list, upload, download)

### Phase 3: Management
- [ ] Reminder CRUD
- [ ] Settings page
- [ ] Conversation history

### Phase 4: Polish
- [ ] Responsive design
- [ ] Dark mode
- [ ] Loading states
- [ ] Error handling

---

## Backend Additions Required

### New Endpoints to Add

```python
# src/executive_assistant/channels/http.py - Add these endpoints

@self.app.get("/user/{user_id}/kb")
async def list_kb_collections(user_id: str):
    """List all KB collections for a user."""
    # Query user's KB data and return collections
    pass

@self.app.get("/user/{user_id}/kb/{collection_name}")
async def get_kb_collection(user_id: str, collection_name: str):
    """Get collection details and documents."""
    pass

@self.app.delete("/user/{user_id}/kb/{collection_name}")
async def delete_kb_collection(user_id: str, collection_name: str):
    """Delete a KB collection."""
    pass

@self.app.get("/user/{user_id}/db")
async def list_db_tables(user_id: str):
    """List all DB tables for a user."""
    pass

@self.app.get("/user/{user_id}/db/{table_name}")
async def query_db_table(user_id: str, table_name: str, limit: int = 100):
    """Get data from a DB table."""
    pass

@self.app.get("/user/{user_id}/files")
async def list_files(user_id: str, path: str = ""):
    """List files in user's workspace."""
    pass

@self.app.get("/user/{user_id}/reminders")
async def list_reminders(user_id: str):
    """List all reminders for a user."""
    pass

@self.app.post("/user/{user_id}/reminders")
async def create_reminder(user_id: str, ...):
    """Create a new reminder."""
    pass
```

---

## Open Questions

1. **Authentication** - MVP uses simple user_id, when to add proper auth?
2. **Real-time updates** - WebSocket for live reminders, or polling?
3. **File uploads** - Direct to backend or through Next.js API route?
4. **Rate limiting** - How to prevent abuse on public endpoints?
5. **Multi-user** - User isolation in backend (thread_id mapping)

---

## Dependencies to Add

### Frontend (package.json)
```json
{
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@tanstack/react-query": "^5.0.0",
    "zustand": "^5.0.0",
    "react-hook-form": "^7.0.0",
    "zod": "^3.0.0",
    "@hookform/resolvers": "^3.0.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.0.0",
    "lucide-react": "^0.450.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "tailwindcss": "^4.0.0",
    "eslint": "^9.0.0",
    "eslint-config-next": "^15.0.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0"
  }
}
```

### Backend (pyproject.toml - may need additions)
- Currently no changes needed for Phase 1
- Future: CORS configuration if deploying separately

---

## Sources

- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui Documentation](https://ui.shadcn.com)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [SSE (Server-Sent Events) MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
