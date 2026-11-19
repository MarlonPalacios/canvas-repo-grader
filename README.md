# Canvas LMS GitHub Submission Cloner & Auditor

An automated Python tool designed for instructors and teaching assistants to fetch student submissions from Canvas LMS, audit repository status via the GitHub API, track every commit with its date and time, batch clone repositories locally, and optionally generate an AI-assisted review of each submission using a **local** model (Ollama).

> The AI review is a grading aid only. The final grade should always be decided by the instructor.

---

## Features

- **Automated Extraction:** Extracts repository links from Canvas official URL submissions, rich text entries, and submission comments.
- **Privacy Audit:** Detects public vs. private repositories to help enforce assignment policies.
- **Access Verification:** Flags missing collaborator invitations, 404 errors, broken links, and students who submitted without a GitHub link.
- **Detailed Commit History:** Lists every commit (hash, author, date/time and message) and flags commits made **after the Canvas due date** (⏰).
- **Smart Cloning:** Clones private repositories using your token (without leaving it saved in `.git/config`), and runs `git pull` instead of re-cloning if the repo already exists.
- **Full Pagination:** Handles any number of submissions and commits (no 100-item limit).
- **AI-Assisted Review (optional):** Reads the lab instructions from a PDF and compares them against each student's code using a local LLM. Generates a Markdown review per student with requirements checklist (✅ / ⚠️ / ❌ / ❔), bugs with file and line, code quality notes, and a suggested grade.
- **Privacy-Friendly AI:** The model runs on your own machine through Ollama — student code is never sent to an external service.
- **Detailed Audit Reports:** Prints a structured summary in the console and exports it to `Log_Tarea_<ASSIGNMENT_ID>.txt`.

---

## Prerequisites

- **Python 3.8+**
- **Git** installed and available in your system path
- **Canvas LMS API Access Token** (instructor or TA role in the course)
- **GitHub Personal Access Token** — **Classic** token with `repo` scope (fine-grained tokens cannot access other users' repos even as a collaborator)
- **Ollama** *(only if you use the AI review)* — recommended 16 GB RAM for the 7B model

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/MarlonPalacios/canvas-repo-grader
   cd canvas-repo-grader
   ```

2. Install dependencies:
   ```bash
   pip install requests pypdf
   ```

3. *(Optional, for AI review)* Install [Ollama](https://ollama.com/) and download a code model:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
   On machines with 8 GB of RAM, use `qwen2.5-coder:3b` instead.

---

## Configuration

Set your credentials and assignment details in the `CONFIG` section of the script:

```python
CANVAS_URL = "https://your-institution.instructure.com"   # no trailing slash
CANVAS_TOKEN = "your_canvas_api_token"
GITHUB_TOKEN = "your_github_token"
COURSE_ID = "your_course_id"
ASSIGNMENT_ID = "your_assignment_id"

PDF_LAB = "lab.pdf"          # lab instructions
REVISAR_CON_IA = True        # False = only commits, cloning and report
```

### Where to find each value

| Value | Where to get it |
|-------|-----------------|
| `CANVAS_URL` | Base address of your Canvas instance. |
| `COURSE_ID` / `ASSIGNMENT_ID` | From the assignment URL: `.../courses/12345/assignments/67890` |
| `CANVAS_TOKEN` | Canvas → Account → Settings → **+ New Access Token** |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → **Tokens (classic)** → `repo` scope |

### Optional settings

| Variable | Purpose |
|----------|---------|
| `MODELO` | Ollama model to use (default `qwen2.5-coder:7b`). |
| `NUM_CTX` | Model context size. Lower it to `16384` if your computer slows down. |
| `MAX_CHARS` | Max characters of code sent to the AI per student. |

> **Warning:** Never commit your actual API keys or personal access tokens to GitHub. Clear them before committing, or move them to environment variables (`os.getenv`) and add `.env` to `.gitignore`.

---

## Usage

1. Accept the students' collaborator invitations on GitHub (repos without an accepted invitation are reported as **NO ACCESS**).
2. Place the lab instructions PDF in the project folder as `lab.pdf` (must have selectable text, not a scan).
3. If using AI, make sure Ollama is running — open `http://localhost:11434` and you should see *Ollama is running*.
4. Run the script:
   ```bash
   python automatizadorALV.py
   ```

**Tip:** run it the first time with `REVISAR_CON_IA = False` to confirm Canvas and GitHub are working before waiting for the AI reviews.

---

## Output

```
tarea_67890/
├── John_Doe/                 ← cloned repository per student
├── Jane_Smith/
├── revisiones/
│   ├── John_Doe.md           ← AI review per student
│   └── Jane_Smith.md
└── Log_Tarea_67890.txt       ← audit report
```

Running it again updates the repositories with `git pull` and overwrites the reviews and report.

### Sample Report

```text
==================================================
REPORTE DE TAREA 67890 - 2026-11-18 20:00
Fecha límite: 2026-11-15 23:59
==================================================
Repositorios descargados: 28

REPOSITORIOS PÚBLICOS (Bajar puntos):
  - John Doe -> https://github.com/johndoe/project-1

ENTREGADOS POR COMENTARIO (Bajar puntos):
  - Jane Smith -> https://github.com/janesmith/project-1

SIN ACCESO (Sin invitación o enlace roto):
  - Mark Taylor -> https://github.com/marktaylor/project-1 (sin acceso / no existe)

ENTREGÓ PERO SIN LINK DE GITHUB:
  - Anna White

DETALLE DE COMMITS:
  John Doe — project-1 — 3 commits (1 después de la fecha límite)
    [a1b2c3d] 2026-11-14 18:20 | johndoe | Initial commit
    [d4e5f6a] 2026-11-15 21:05 | johndoe | Add menu and validations
    [b7c8d9e] 2026-11-16 09:12 | johndoe | Fix bug in calculator ⏰ TARDE
==================================================
```

### Sample AI Review (`revisiones/John_Doe.md`)

```markdown
# John Doe
Repo: https://github.com/johndoe/project-1
Commits: 3 (1 tarde)

## Resumen
Implements most of the requested features; input validation is incomplete.

## Requisitos
- [✅ Cumple] Main menu — Main.java/main — loops until option 0
- [⚠️ Parcial] Input validation — Main.java line 42 — negative numbers not handled
- [❌ No cumple] Average method — not found

## Nota sugerida
75/100
```

---

## Limitations

- The AI **reads** the code but does not run it; anything that requires execution is marked ❔.
- Small local models can make mistakes — use the review as a guide, not as the final grade.
- Scanned PDFs cannot be read.
- If a student changes their link to a different repository, delete their folder and run the script again.

---

## Security Notes

- Do not upload the `tarea_*` folders: they contain student code and names.
- Keep Ollama updated and do not expose it outside your machine (do not set `OLLAMA_HOST=0.0.0.0`).
- If a token was ever committed, revoke it and generate a new one — it stays in the Git history even after deletion.

Recommended `.gitignore`:

```gitignore
.env
tarea_*/
*.pdf
__pycache__/
```