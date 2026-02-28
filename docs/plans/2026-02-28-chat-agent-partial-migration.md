# Chat Agent Partial Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the core full-page SendaTradie agent chat experience into this Vite project using the same core frontend packages and runtime design, while removing widget, auth, onboarding, and unrelated app coupling.

**Architecture:** Build a dedicated `frontend/src/modules/chat/` module that preserves the old agent’s core layering: page shell, runtime provider, model adapter, thread/message persistence, and API boundary. Keep only the core chat path for this phase: threads, message history, SSE streaming, and basic tool rendering. Defer attachments, interrupt/resume UI, and human review UI until the Python backend contract is in place.

**Tech Stack:** React, Vite, @assistant-ui/react, @assistant-ui/react-markdown, @assistant-ui/styles, lucide-react, zod

---

### Task 1: Freeze the migration scope and target module structure

**Files:**
- Modify: `README.md`
- Create: `frontend/src/modules/chat/`
- Create: `frontend/src/pages/ChatPage.jsx`

**Step 1: Document the migration scope**

Update the README to state that the frontend target is:

- full-page chat only
- no auth
- no AI widget
- no popup onboarding
- no human review UI in phase 1

**Step 2: Create the target chat module directories**

Create:

```text
frontend/src/modules/chat/
frontend/src/modules/chat/api/
frontend/src/modules/chat/components/
frontend/src/modules/chat/runtime/
frontend/src/modules/chat/services/
frontend/src/modules/chat/models/
frontend/src/modules/chat/utils/
```

**Step 3: Create the page entry**

Create:

```jsx
import ChatScreen from "../modules/chat/ChatScreen";

export default function ChatPage() {
  return <ChatScreen />;
}
```

**Step 4: Commit**

```bash
git add README.md frontend/src/pages/ChatPage.jsx frontend/src/modules/chat
git commit -m "chore: define chat migration scope"
```

### Task 2: Add the exact core chat package dependencies from the old project

**Files:**
- Modify: `frontend/package.json`

**Step 1: Add the core packages used by the old chat module**

Add these exact versions:

```json
{
  "@assistant-ui/react": "^0.11.58",
  "@assistant-ui/react-markdown": "^0.11.10",
  "@assistant-ui/styles": "^0.3.3",
  "lucide-react": "^0.453.0",
  "zod": "^4.0.14"
}
```

Do not add the widget-only or human-review-only packages in this phase.

**Step 2: Install frontend dependencies**

Run:

```bash
cd frontend && npm install
```

Expected: the new packages are installed successfully.

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add core chat runtime dependencies"
```

### Task 3: Create the shared API client layer for the migrated chat module

**Files:**
- Create: `frontend/src/modules/chat/api/client.js`
- Create: `frontend/src/modules/chat/api/threadsApi.js`
- Create: `frontend/src/modules/chat/api/messagesApi.js`
- Create: `frontend/src/modules/chat/api/streamingApi.js`
- Create: `frontend/src/modules/chat/api/index.js`
- Test: future integration through the chat page

**Step 1: Create the base API client**

Create a single fetch wrapper that:

- uses `/api` as the local Vite-facing prefix
- defaults to JSON requests
- has no auth dependency
- supports explicit streaming requests

**Step 2: Create thread API functions**

Add functions for:

- `getThreads()`
- `createThread(data)`
- `updateThread(threadId, data)`
- `deleteThread(threadId)`

Mapping:

- `GET /api/agent/threads`
- `POST /api/agent/threads`
- `PATCH /api/agent/threads/:threadId`
- `DELETE /api/agent/threads/:threadId`

**Step 3: Create message API functions**

Add functions for:

- `getMessages(threadId)`
- `saveMessage(threadId, message)`

Mapping:

- `GET /api/agent/threads/:threadId/messages`
- `POST /api/agent/threads/:threadId/messages`

**Step 4: Create streaming API functions**

Add functions for:

- `streamChat(body, signal)`
- optional `sendInterrupt(sessionId, reason)` stub for phase 2

Mapping:

- `POST /api/agent/stream`
- `POST /api/agent/interrupt`

**Step 5: Commit**

```bash
git add frontend/src/modules/chat/api
git commit -m "feat: add chat api layer"
```

### Task 4: Migrate the core runtime and message model

**Files:**
- Create: `frontend/src/modules/chat/runtime/RuntimeProvider.jsx`
- Create: `frontend/src/modules/chat/runtime/ChatModelAdapter.js`
- Create: `frontend/src/modules/chat/runtime/threadHydration.js`
- Create: `frontend/src/modules/chat/runtime/userMessageContent.js`
- Create: `frontend/src/modules/chat/models/thread.js`
- Create: `frontend/src/modules/chat/models/message.js`

**Step 1: Port the runtime provider design**

Migrate the old runtime shape from the SendaTradie module:

- local assistant runtime provider
- assistant-ui runtime wiring
- thread hydration support
- adapter injection through a dedicated model adapter

Remove these old dependencies:

- Redux user state
- auth token lookup
- page-context sidecar
- widget/onboarding coupling

**Step 2: Port the model adapter**

Create a simplified adapter that preserves:

- SSE request/response handling
- assistant-ui `run()` generator shape
- streaming text assembly
- basic tool event rendering

Remove these old concerns:

- onboarding runtime state
- page context injection
- human review resume stream handling
- widget-specific global events

**Step 3: Port user message conversion helpers**

Keep the message content conversion structure aligned with the old agent so future backend migration does not require data-shape rewrites.

**Step 4: Commit**

```bash
git add frontend/src/modules/chat/runtime frontend/src/modules/chat/models
git commit -m "feat: migrate core chat runtime"
```

### Task 5: Migrate the core chat UI components only

**Files:**
- Create: `frontend/src/modules/chat/ChatScreen.jsx`
- Create: `frontend/src/modules/chat/components/AssistantComposer.jsx`
- Create: `frontend/src/modules/chat/components/AssistantThread.jsx`
- Create: `frontend/src/modules/chat/components/WelcomeScreen.jsx`
- Create: `frontend/src/modules/chat/components/ThreadSidebar.jsx`
- Create: `frontend/src/modules/chat/components/ToolCallGroup.jsx`
- Create: `frontend/src/modules/chat/components/chat.css`

**Step 1: Port the page-level chat shell**

The page should support:

- full-height layout
- thread sidebar
- main thread area
- composer input

Do not port:

- widget shell
- FAB
- minimized chat
- popup sidebar

**Step 2: Port the thread and composer components**

Keep the old interaction design principles:

- assistant-ui driven thread rendering
- composer-based message input
- welcome state when thread is empty

**Step 3: Port basic tool rendering**

Keep only the core non-business-specific tool visuals:

- thinking status
- generic tool call rendering
- todo/task progress if low-coupling

Do not port business-specific review UI in this phase.

**Step 4: Commit**

```bash
git add frontend/src/modules/chat/ChatScreen.jsx frontend/src/modules/chat/components
git commit -m "feat: migrate core chat ui"
```

### Task 6: Rebuild thread state management for the standalone Vite app

**Files:**
- Create: `frontend/src/modules/chat/services/threadService.js`
- Modify: `frontend/src/modules/chat/ChatScreen.jsx`
- Modify: `frontend/src/pages/ChatPage.jsx`
- Modify: `frontend/src/App.jsx`

**Step 1: Implement standalone thread lifecycle logic**

Recreate the minimal page logic from the old agent page:

- load threads on mount
- create a new thread
- select a thread
- load thread history
- rename/delete thread if kept in phase 1

If rename/delete slows the migration, defer them and keep only:

- list threads
- create thread
- load thread

**Step 2: Connect the chat page as the app’s main screen**

Replace the temporary scaffold page with the standalone chat page.

**Step 3: Commit**

```bash
git add frontend/src/modules/chat/services/threadService.js frontend/src/modules/chat/ChatScreen.jsx frontend/src/pages/ChatPage.jsx frontend/src/App.jsx
git commit -m "feat: connect standalone chat page"
```

### Task 7: Define the frontend-to-Python backend contract

**Files:**
- Create: `frontend/src/modules/chat/api/CONTRACT.md`
- Modify: `README.md`

**Step 1: Document the required backend endpoints**

Document these as the phase 1 backend contract:

- `GET /api/agent/threads`
- `POST /api/agent/threads`
- `GET /api/agent/threads/:threadId/messages`
- `POST /api/agent/threads/:threadId/messages`
- `POST /api/agent/stream`

Document these as phase 2:

- `PATCH /api/agent/threads/:threadId`
- `DELETE /api/agent/threads/:threadId`
- `POST /api/agent/interrupt`
- `POST /api/agent/resume`
- `POST /api/messages/chatFileLink`

**Step 2: Record the streaming contract**

Document that the frontend expects:

- `text/event-stream`
- incremental `data:` chunks
- assistant text deltas
- optional tool events
- terminal done event

**Step 3: Commit**

```bash
git add frontend/src/modules/chat/api/CONTRACT.md README.md
git commit -m "docs: define chat backend contract"
```

### Task 8: Verify the standalone migrated frontend shell

**Files:**
- No file changes required

**Step 1: Install root and frontend dependencies**

Run:

```bash
npm install
cd frontend && npm install
```

Expected: all dependencies install successfully.

**Step 2: Run the frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: the migrated chat shell builds successfully.

**Step 3: Run the frontend dev server**

Run:

```bash
cd frontend && npm run dev
```

Expected: the full-page chat screen renders without widget or auth dependencies.

**Step 4: Commit**

```bash
git add .
git commit -m "chore: verify chat partial migration"
```

### Task 9: Explicitly defer non-core migration work

**Files:**
- No immediate file changes required

**Step 1: Do not migrate these in phase 1**

Leave out:

1. `sendaTradieAgentPopup/`
2. widget bridge logic
3. popup onboarding integration
4. Redux auth integration
5. `HumanReviewUI` and job review dialogs
6. attachment upload UI
7. business-specific page context actions

**Step 2: Preserve code shape for later expansion**

Expected: the new chat module stays small, but its runtime and API boundaries remain compatible with later Python backend migration.
