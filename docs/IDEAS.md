## 2025-06-14

I've been having some more thoughts on memory, and have started a new project heare-memory to capture *specifically* global long term memory. We're preserving the file-tree concept, and will implement it atop git/github for simplicity to get started. 

I'm thinking now of 3 tiers of memory: session, project, and global.

### session

This is information that is specific to a session, and may or may not persist past the session. things like "we're working on task X", or "don't use this patter for this problem" — this is important, but not necessarily something that will come up again. It is, however, something that should be persisted past compactions. These are the important details that we don't want squashed by context management strategies. Management of session memory is an explicit choice made by the agent (via tool use), and can also be invoked explicitly by the user. Use of this memory is a core functionality of the agent harness (not a choice made by the model or the user, but a consequence of data ending up in this tier).

### project

Most agent implementations have expanded `CLAUDE.md` to a generic `AGENTS.md` concept. This is a file that is curated by both humans and the agent, keeping track of things like project setup, testing practices, and framework choices that are specific to the project. It is checked in with the project itself (or, theoretically just part of the filesystem, if your agent is not a code repository, but just an agent within a scratch dir). Management of project memory is an explicit choice made by the agent (via tool use), can be explicitly invoked by the user, and can also have an out-of-band (agent driven) channel for revising and reorganizing (sometimes called `critique`). Memory is read or search by explicit agent invocation.

### global

Global memory should contain concepts that are broader than a project (but may be conventions that pop up across multiple projects). Global memory can be read (and possibly written, with conflict resolution) by multiple disparate (and concurrent) instances of the agent. It represents explicit knowledge of the user (or user group) with whom an agent is aligned, as well as the agent's derived view of the world.

Global memory has both explicit read and write interfaces, but its primary interaction model will be ***implicit*** — global memory will have the opportunity to observe all interactions that go past and synthesize additions or updates to global memory. This synthesis will not necessarily happen in real time.

Global memory will also enable implicit *reads*, where observed interactions surface related content. An apt metaphor for this might be the concept of `brings to mind` — ongoing interactions invoking memories of past interactions. A first implementation might look like:

1. agent passes contents of turn to memory for observation
2. memory accepts contents for ingestion, responds with semantic search results across all of memory (limit some reasonable N)
3. agent tracks N results over time, performs RRF to keep a manageable M (&lt;N) results as part of conversational context. 