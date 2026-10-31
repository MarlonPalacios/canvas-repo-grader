# Canvas LMS GitHub Submission Cloner & Auditor

An automated Python tool designed for instructors and teaching assistants to fetch student submissions from Canvas LMS, audit repository status via GitHub API, verify access permissions and visibility, track commit counts, and batch clone repositories locally.

---

## Features

- **Automated Extraction:** Extracts repository links from Canvas official URL submissions, rich text entries, and submission comments.
- **Privacy Audit:** Detects public vs. private repositories to help enforce assignment policies.
- **Access Verification:** Flags missing collaborator invitations, 404 errors, or broken links.
- **Fast Commit Count:** Uses GitHub API pagination headers to fetch the exact commit count without downloading git history first.
- **Batch Git Cloning:** Automatically clones all accessible student repositories locally.
- **Detailed Audit Reports:** Generates structured summary reports in console and exports a timestamped `Log.txt` file.

---

## Prerequisites

- **Python 3.8+**
- **Git** installed and available in your system path
- **Canvas LMS API Access Token** (generated in Canvas user settings)
- **GitHub Personal Access Token** (Classic token with `repo` scope to read private repos)

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/MarlonPalacios/canvas-repo-grader
   cd canvas-repo-grader
   ```

2. Install dependencies:
   ```bash
   pip install requests
   ```

---

## Configuration

Set your credentials and target assignment details inside the script or provide them as environment variables:

```python
CANVAS_URL = "https://your-institution.instructure.com"
CANVAS_TOKEN = "your_canvas_api_token"
GITHUB_TOKEN = "your_github_token"
COURSE_ID = "your_course_id"
ASSIGNMENT_ID = "your_assignment_id"
```

> **Warning:** Never commit your actual API keys or personal access tokens to GitHub. Consider using environment variables (`os.getenv`) and adding `.env` to `.gitignore`.

---

## Usage

Execute the script:

```bash
python automatizadorALV.py
```

### Sample Output Log

```text
==================================================
CANVAS ASSIGNMENT REPORT - GENERATED: 2026-10-30 20:00:00
==================================================
Total downloaded repositories: 28

 PUBLIC REPOSITORIES:
  - John Doe -> https://github.com/johndoe/project-1

SUBMITTED VIA COMMENTS:
  - Jane Smith -> https://github.com/janesmith/project-1

NO ACCESS (Missing invitation or broken link):
  - Mark Taylor -> https://github.com/marktaylor/project-1

COMMIT COUNTS:
  - John Doe: 14 commits (project-1)
  - Jane Smith: 9 commits (project-1)
==================================================
```

---
