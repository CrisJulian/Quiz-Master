# Quiz Master

A mobile-friendly quiz builder and quiz-taking app, built with [Flet](https://flet.dev) so the same Python codebase runs on desktop, web, and (eventually) iOS/Android. Create quizzes, add multiple-choice questions, save drafts, and take timed quizzes with instant scoring — all in a clean "Academic Clarity" design.

Your data is saved locally so nothing is lost between runs, and can optionally sync with friends over Firebase.

## Features

- **Dashboard** — search your quizzes, see stats, resume drafts, jump into a quiz
- **Library** — browse/filter quizzes by subject, join a quiz by code
- **Quiz builder** — a 3-step flow (basics → questions → review) to create or edit quizzes, with custom cover colors, difficulty, and time limits
- **Live quiz taking** — countdown timer, skip/answer, instant results with a score ring
- **Answer review** — see exactly which questions you got right/wrong and the correct answers
- **Persistence** — every change is saved to a local JSON file automatically
- **Optional cloud sync** — connect a free Firebase project so quizzes/drafts/subjects sync between your own devices or a small group of friends

## Requirements

- Python 3.10+
- [Flet](https://flet.dev)
- [pyrebase4](https://github.com/nhorvath/Pyrebase4) — only needed if you want cloud sync; the app runs fine without it

## Installation

```bash
pip install flet
pip install pyrebase4   # optional — skip this if you only want local-only mode
```

> **Windows users:** don't add `--break-system-packages` to these commands — that flag is only for Linux distros that lock down the system Python, and using it on Windows just causes errors. If `pip install` seems to succeed but the app still can't find a package, make sure you're installing into the same Python your editor/terminal actually runs (`python -m pip install <package>` guarantees this).

## Files in this project

| File | Committed to git? | Purpose |
|---|---|---|
| `Quiz_Master.py` | ✅ Yes | The whole app |
| `firebase_config.example.py` | ✅ Yes | Placeholder template — safe for a public repo |
| `firebase_config.py` | ❌ No (gitignored) | Your real Firebase credentials — copy from the example file and fill in your own values |
| `quiz_master_cache.json` | ❌ No (gitignored) | Auto-generated local data cache — created the first time you run the app |
| `.gitignore` | ✅ Yes | Keeps the two files above out of version control |

## Running the app

```bash
flet run Quiz_Master.py          # desktop preview
flet run --web Quiz_Master.py    # browser preview
python Quiz_Master.py            # also works — the script calls ft.run(main) directly
```

## How your data is stored

| Layer | What it does | Required? |
|---|---|---|
| **Local cache** (`quiz_master_cache.json`, saved next to the script) | Every create/edit/delete is written here immediately. This is what makes the app usable offline and remembers your data between launches. | Always on |
| **Firebase Realtime Database** (via `CloudStore`) | Syncs quizzes, drafts, and subjects between everyone using the same Firebase project, signed in anonymously. Runs in a background thread so it never blocks the UI. | Optional |

If Firebase isn't configured (or `pyrebase4` isn't installed, or you're offline), the app silently falls back to local-only mode — no crashes, no blocking.

## Setting up cloud sync (optional)

1. Create a free project at [console.firebase.google.com](https://console.firebase.google.com)
2. **Build → Realtime Database → Create Database** (start in locked mode)
3. In the **Rules** tab, set and **Publish**:
   ```json
   { "rules": { ".read": "auth != null", ".write": "auth != null" } }
   ```
4. **Build → Authentication → Sign-in method → Anonymous → Enable**
5. **Project settings → General → Your apps → Add app → Web**, then copy your project's config into a new file called `firebase_config.py` (copy `firebase_config.example.py` as a starting point):
   ```python
   FIREBASE_CONFIG = {
       "apiKey": "...",
       "authDomain": "...",
       "databaseURL": "...",
       "projectId": "...",
       "storageBucket": "...",
       "appId": "...",
   }
   ```
   `firebase_config.py` is listed in `.gitignore` and is **never committed** — this is what makes it safe to keep `Quiz_Master.py` in a public repo. `Quiz_Master.py` imports from `firebase_config.py` if it exists, and quietly falls back to local-only mode if it doesn't.
6. Send your `firebase_config.py` directly to whoever you want to share data with (chat/email, not the repo). When it connects successfully you'll see a **"☁ Synced with the cloud"** toast on launch.

The `apiKey` is a public project identifier, not a secret by itself — but combined with the anonymous-sign-in rules above, anyone who has your full config can read and write your database. That's exactly why it's kept out of the public repo rather than relying on the key being "safe."

## Project structure (single file: `Quiz_Master.py`)

- **Design tokens** — colors, fonts, and shared UI helpers (`card`, `pill`, `kebab_menu`, etc.)
- **`CloudStore`** — thin wrapper around Firebase Realtime Database + Anonymous Auth; every method is best-effort and never raises
- **`ProfQuizzerApp`** — the whole app, organized by screen:
  1. Dashboard
  2. Library
  3. Create/Edit Quiz — Basics
  4. Add/Edit Questions
  5. Review & Publish
  6. Quiz Overview (intro)
  7. Live Quiz Taking
  8. Results
  9. Answer Review
- Navigation swaps `self.body.content` between screens; there's no router/URL, just method calls like `self.goto_dashboard()`.

## Building for mobile

```bash
flet build apk    # Android
flet build ipa    # iOS
```

Heads up: the local cache currently writes `quiz_master_cache.json` next to the script, which works great for desktop but won't be writable the same way inside a packaged mobile app. Before shipping a mobile build, that path should be swapped for a proper writable directory (e.g. via `ft.StoragePaths`) — ask if you want help with that when you get there.

## Troubleshooting

- **"Unknown control: SharedPreferences" / coroutine warnings** — fixed; the app no longer uses `ft.SharedPreferences` at all, just a plain JSON file, which is more consistent across Flet versions.
- **`pip install` errors mentioning a package called `system-packages`** — you likely typed `--break system-packages` (space) instead of `--break-system-packages` (hyphen), or you're on Windows where you don't need that flag at all.
- **Red squiggly under `import pyrebase` in your editor** — usually just means your editor's selected Python interpreter isn't the one you installed `pyrebase4` into. Check the interpreter picker in your editor.
- **No "☁ Synced with the cloud" toast** — check that you actually replaced the `"YOUR_..."` placeholders in `FIREBASE_CONFIG`, that you clicked **Publish** on the database rules, and that Anonymous sign-in is enabled.
