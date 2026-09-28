## Before coding: Ask questions

Before starting implementation, ask clarifying questions:
- Fully understand the codebase. 
- What is the desired end behavior?
- Are there existing patterns in the project to follow?
- Which edge cases are relevant?
- Are there constraints (performance, browser compatibility, dependencies)?

Do not start coding immediately if the requirement is unclear or ambiguous.

## Workflow: Small steps

- Implement in manageable, commit-ready units
- After each major change: Brief summary of what was changed
- When refactoring across multiple files: Complete one file as reference, then replicate pattern
- With unfamiliar technologies: Start with minimal working example, then iterate

## No hallucinating APIs

- If uncertain about an API, method, or configuration option: Say so
- Do not invent function names or parameters
- For version conflicts or breaking changes: Point out potential differences
- Suggest checking official documentation rather than guessing

## Refactoring behavior

When asked to replicate changes across multiple files:
- Ask for an already refactored example as reference
- Apply the pattern consistently
- List all modified files at the end

## Dependency updates

When asked about breaking changes after package updates:
- Explain what may have changed between versions
- Note that explanations should be verified against official migration guides
- Name specific places in code that could be affected

## Self-criticism

- Do not overestimate your abilities
- If a solution becomes "too clever": Suggest the simpler variant
- For complex changes: Point out risks and recommend manual review
- Treat your own output as if it came from a stranger on the internet

## Finishing a Task

When the user asks to "finish the task", this means that you
- review the code you've written and look if it needs to be cleaned up or refactored to be simpler, more elegant, more maintainable.
- create or update the markdown file status.md which tracks our current process, what we've accomplished and what is ahead for us for the next steps. 

## Running servers: the user decides

`npm run dev` belongs to the user. Never start, restart or stop it, and never
kill a process on its port — not to pick up a config change, not to verify a
fix, not "briefly". If a change needs a restart to take effect, say so and let
the user do it.

For anything the agent needs to try out itself, there is a second server:

```bash
npm run dev:sandbox   # port 5177, against data/sandbox.db
```

It is the only one the agent starts and stops. Rules for it:

- Announce it before starting it, and stop it again when done.
- Delete `data/sandbox.db*` afterwards — leftover test accounts otherwise turn
  up in the game as things the character faithfully repeats.
- Never point a test at `data/labrador.db`. That is where people are playing.

The same goes for anything else long-lived the agent starts for itself, such as
a headless browser: announce it, and clean it up.

## Technology

If the project already has a tech stack, use that and do not introduce new libraries or other technology without asking the user first.

When no web UI is needed, prefer python as programming language. When creating a python project, always use a virtual environment venv and create a requirements.txt document.

When a web UI is needed, prefer Svelte 5 with runes and vite with TypeScript. If a database is needed, prefer the simple solution e.g. a sqllite database over the more complex ones, or use SvelteKit is backend is needed.

Always greate a .gitignore file and add the appropriate files and folders to exclude like DS_Store, node_modules and so on.

When creating UI, choose a lightweight CSS approach. If no framework is beneficial, don't use one. If the App gets quite complex, opt for Tailwind.
