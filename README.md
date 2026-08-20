# Quiz Master

A mobile-friendly quiz builder and quiz-taking app, built with [Flet](https://flet.dev) so the same Python codebase runs on desktop, web, and (eventually) iOS/Android. Create quizzes, add multiple-choice questions, save drafts, and take timed quizzes with instant scoring — all in a clean "Academic Clarity" design.

Data is saved locally so nothing is lost between runs, and can optionally sync across devices over Firebase.

## Features

- **Dashboard** — search quizzes, view stats, resume drafts, jump into a quiz
- **Library** — browse/filter quizzes by subject, join a quiz by code
- **Quiz builder** — a 3-step flow (basics → questions → review) to create or edit quizzes, with custom cover colors, difficulty, and time limits
- **Live quiz taking** — countdown timer, skip/answer, instant results with a score ring
- **Answer review** — see which questions were answered correctly/incorrectly and the correct answers
- **Persistence** — every change is saved to a local JSON file automatically
- **Optional cloud sync** — connect a Firebase project so quizzes/drafts/subjects sync across devices or between a small group of users

## Requirements

- Python 3.10+
- [Flet](https://flet.dev)
- [pyrebase4](https://github.com/nhorvath/Pyrebase4) — only needed for cloud sync; the app runs fine without it

## Installation

```bash
pip install flet
pip install pyrebase4   # optional — skip if only using local-only mode
```

> **Windows:** don't add `--break-system-packages` to these commands — that flag is only relevant on Linux distros that lock down the system Python. If a package installs successfully but the app still can't find it, install with `python -m pip install <package>` to guarantee it lands in the same Python the app runs with.

## Files in this project

| File | Committed to git? | Purpose |
|---|---|---|
| `Quiz_Master.py` | Yes | The whole app |
| `firebase_config.example.py` | Yes | Placeholder template — safe for a public repo |
| `firebase_config.py` | No (gitignored) | Real Firebase credentials — copy from the example file and fill in project-specific values |
| `quiz_master_cache.json` | No (gitignored) | Auto-generated local data cache — created the first time the app runs |
| `.gitignore` | Yes | Keeps the two files above out of version control |

## Running the app

```bash
flet run Quiz_Master.py          # desktop preview
flet run --web Quiz_Master.py    # browser preview
python Quiz_Master.py            # also works — the script calls ft.run(main) directly
```

## How data is stored

| Layer | What it does | Required? |
|---|---|---|
| **Local cache** (`quiz_master_cache.json`, saved next to the script) | Every create/edit/delete is written here immediately. This is what makes the app usable offline and preserves data between launches. | Always on |
| **Firebase Realtime Database** (via `CloudStore`) | Syncs quizzes, drafts, and subjects between everyone using the same Firebase project, signed in anonymously. Runs in a background thread so it never blocks the UI. | Optional |

If Firebase isn't configured (or `pyrebase4` isn't installed, or there's no network connection), the app falls back to local-only mode automatically — no crashes, no blocking.

## Setting up cloud sync (optional)

1. Create a free project at [console.firebase.google.com](https://console.firebase.google.com)
2. **Build → Realtime Database → Create Database** (start in locked mode)
3. In the **Rules** tab, set and **Publish**:
   ```json
   { "rules": { ".read": "auth != null", ".write": "auth != null" } }
   ```
4. **Build → Authentication → Sign-in method → Anonymous → Enable**
5. **Project settings → General → Your apps → Add app → Web**, then copy the project's config into a new file called `firebase_config.py` (use `firebase_config.example.py` as the starting template):
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
   `firebase_config.py` is listed in `.gitignore` and is never committed — this is what makes it safe to keep `Quiz_Master.py` in a public repo. `Quiz_Master.py` imports from `firebase_config.py` if it exists, and falls back to local-only mode if it doesn't.
6. On successful connection, a **"☁ Synced with the cloud"** toast appears on launch.

The `apiKey` is a public project identifier, not a secret by itself — but combined with the anonymous-sign-in rules above, anyone with the full config can read and write the database. That is why it is kept out of the public repo rather than relied on being "safe" by itself.

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
- Navigation swaps `self.body.content` between screens; there is no router/URL, just method calls like `self.goto_dashboard()`.

## Building for mobile

```bash
flet build apk    # Android
flet build ipa    # iOS
```

Note: the local cache currently writes `quiz_master_cache.json` next to the script, which works for desktop but is not writable the same way inside a packaged mobile app. Before shipping a mobile build, that path should be swapped for a proper writable directory (e.g. via `ft.StoragePaths`).

## Troubleshooting

- **"Unknown control: SharedPreferences" / coroutine warnings** — the app does not use `ft.SharedPreferences`; local caching is done via a plain JSON file, which behaves consistently across Flet versions. If this error appears, confirm the installed version of `Quiz_Master.py` matches this repo.
- **`pip install` errors mentioning a package called `system-packages`** — caused by `--break system-packages` (space) instead of `--break-system-packages` (hyphen). On Windows this flag isn't needed at all.
- **Editor shows an unresolved import for `pyrebase`** — the editor's selected Python interpreter is likely different from the one `pyrebase4` was installed into. Check the interpreter setting in the editor.
- **No "☁ Synced with the cloud" toast** — confirm `firebase_config.py` exists and its `"YOUR_..."` placeholders have been replaced with real values, that the database rules were published, and that Anonymous sign-in is enabled.