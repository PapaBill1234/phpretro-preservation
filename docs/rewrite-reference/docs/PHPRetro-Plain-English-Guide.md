# Plain-English Guide: How This Actually Works

This explains, in normal language, what all those terms meant and exactly what to do —
step by step, assuming you're just using the DeepSeek website and the Claude website
(or apps), typing and uploading files like a normal chat.

---

## First, the words I kept using

| Word I used | What it actually means |
|---|---|
| **Phase** | One chunk of the to-do list. The plan document is split into 10+ numbered sections, each one a self-contained task (e.g. "Phase 4: fix these ~40 files"). |
| **Codebase** | Just means "all the code files that make up the website." |
| **File / files** | The actual `.php` files that make up PHPRetro. Same as any file — could be opened in Notepad and you'd see code. |
| **Repo** (repository) | The whole folder of all the project's files together, usually as a single downloadable/zippable thing (often from GitHub). |
| **Diff** | A before-and-after comparison showing exactly what lines changed in a file. Think "track changes" in Word, but for code. |
| **Deliverable** | The specific thing I asked the AI to hand back when it finishes — a short summary, not the whole pile of code. |
| **Grep / grep check** | A way of **searching text for a specific word or pattern**. That's it. When I said "run this grep command," I meant "search the code for a specific dangerous word/pattern to check if it's gone." You don't need to know how to run one yourself — see below, I'll have the AI do it and just tell you the result. |
| **Acceptance check** | A simple pass/fail test for "did this phase actually get done correctly?" |
| **SQL injection, CSRF, PDO,** etc. | Specific technical security terms from the earlier conversation — you don't need to memorize these, they're just names for specific types of problems/fixes. Treat them as labels, not things you personally need to understand or execute. |

**The most important thing to understand:** you are not expected to run any commands,
open a terminal, or touch code yourself. Everything below is just typing messages and
uploading/downloading files in a normal chat window — the same as what you've already
been doing with me.

---

## The actual workflow, step by step

### Step 1 — Open a chat with DeepSeek

Go to DeepSeek's website/app like normal. Start a new conversation.

### Step 2 — Upload two things to that chat

1. The plan document (`PHPRetro-Modernization-Plan.md`) — upload it as a file attachment.
2. The actual PHPRetro code — either upload it as a zip file if DeepSeek accepts file
   uploads of that type, or give it the GitHub link (`https://github.com/Quackster/PHPRetro`)
   and ask it to work from that.

### Step 3 — Tell DeepSeek what to do, in plain language

Copy-paste something like this into the chat:

> "I've uploaded a modernization plan for this codebase. Please only do Phase 1 right
> now — read the 'Global conventions' section and the 'Phase 1' section of the document,
> and do exactly what that phase describes. Don't touch anything outside that phase's
> scope. When you're done, give me the exact 'Deliverable to reviewer' the document asks
> for, plus the files you changed."

Wait for it to respond. It will do the work and hand back its answer + changed files.

### Step 4 — Copy DeepSeek's answer into a new chat with me (Claude)

Open a new conversation with me. Paste in:
- What DeepSeek said it did (its "deliverable")
- The files it changed (just upload them, or paste the code)
- Say: *"DeepSeek just did Phase 1 of the plan I gave it. Here's what it says it did and
  the files it changed. Can you check if this actually looks right before I move on?"*

I'll look it over and tell you in plain language: "looks fine, go ahead" or "here's a
problem, send this back to DeepSeek."

### Step 5 — Repeat, one phase at a time

Go back to your DeepSeek chat (or start fresh if it's gotten long/confusing), give it
the next phase, bring the result back to me, repeat — until all phases are done.

### Step 6 — The final Fable check

Once every phase is done and I've said things look good, that's when you'd open a
**separate** conversation, switch the model to **Fable 5.1** (there's a model-picker in
the Claude app for this), upload the finished code plus the plan document, and ask it to
do the full detailed security review we talked about — findings report first, then fixes.

---

## A simple checklist you can literally follow

```
[ ] Open DeepSeek chat
[ ] Upload plan document + code
[ ] Say "do Phase 1 only, give me the deliverable + changed files"
[ ] Copy DeepSeek's answer into a Claude chat
[ ] Ask Claude "does this look right?"
[ ] If Claude says yes → go back to DeepSeek, say "do Phase 2"
[ ] If Claude says no → go back to DeepSeek, say "fix this: [paste Claude's concern]"
[ ] Repeat for every phase in the document
[ ] When all phases done → new chat, switch to Fable 5.1, ask for full security review
```

---

## Things you genuinely don't need to worry about

- You don't need to understand SQL injection, CSRF, PDO, or any of the specific
  technical terms to run this process — those are just labels for what DeepSeek is
  fixing behind the scenes.
- You don't need to run any commands yourself. Every "grep check" or "acceptance check"
  can just be something you ask me or DeepSeek to run and report back on in plain words
  — just say "did this pass its check?" and let the AI tell you.
- You don't need to read every line of code that gets changed. That's the whole point of
  the deliverable/summary system — you're reading a short paragraph, not the code itself.

## The one thing worth actually understanding

The reason this is split into phases instead of "just fix everything" in one go is
purely so that **if something goes wrong, you find out quickly and cheaply** — after a
small chunk of work — instead of discovering a mistake buried somewhere in one giant
change to the entire website at the very end.
