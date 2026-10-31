import requests
import subprocess
import re
import os
from datetime import datetime

# --- configs ---

CANVAS_URL = ""
CANVAS_TOKEN = ""
GITHUB_TOKEN = "" # change url, id and tokens 
COURSE_ID = ""
ASSIGNMENT_ID = ""


# --- code ---
headers_canvas = {"Authorization": f"Bearer {CANVAS_TOKEN}"}
headers_github = {"Authorization": f"token {GITHUB_TOKEN}","Accept": "application/vnd.github.v3+json"}

url_canvas = f"{CANVAS_URL}/api/v1/courses/{COURSE_ID}/assignments/{ASSIGNMENT_ID}/submissions"


params_canvas = {"per_page": 100,"include[]": ["submission_comments", "user"]}

def obtener_cantidad_commits(owner, repo):
    url_commits = f"https://api.github.com/repos/{owner}/{repo}/commits"
    res = requests.get(url_commits, headers=headers_github, params={"per_page": 1})
    if res.status_code == 200:
        if 'last' in res.links:
            match = re.search(r'page=(\d+)', res.links['last']['url'])
            return int(match.group(1)) if match else 1
        else:
            return len(res.json()) 
    return "Desconocido"

print("Conectando a Canvas para obtener los enlaces...")
response = requests.get(url_canvas, headers=headers_canvas, params=params_canvas)

if response.status_code == 200:
    submissions = response.json()
    repos_clonados = 0
    lista_publicos = []
    lista_comentarios = []
    lista_sin_acceso = []
    log_commits = []
    for sub in submissions:
        git_url = None
        origen_enlace = None
        estudiante = sub.get('user', {}).get('name', f"ID: {sub.get('user_id')}")
        if sub.get('submission_type') == 'online_url':
            git_url = sub.get('url')
            origen_enlace = "URL Oficial"
        elif sub.get('submission_type') == 'online_text_entry':
            match = re.search(r'(https://github\.com/[^\s<"\'&]+)', sub.get('body', ''))
            if match:
                git_url = match.group(1)
                origen_enlace = "Texto Oficial"
        if not git_url and 'submission_comments' in sub:
            for comentario in sub['submission_comments']:
                match = re.search(r'(https://github\.com/[^\s<"\'&]+)', comentario.get('comment', ''))
                if match:
                    git_url = match.group(1)
                    origen_enlace = "Comentario (Penalizar)"
                    lista_comentarios.append(f"{estudiante} -> {git_url}")
                    break 
        if git_url and "github.com" in git_url:
            match_repo = re.search(r'github\.com/([^/]+)/([^/]+)', git_url)
            if match_repo:
                owner = match_repo.group(1)
                repo_name = match_repo.group(2).replace('.git', '')
                api_repo_url = f"https://api.github.com/repos/{owner}/{repo_name}"
                github_res = requests.get(api_repo_url, headers=headers_github)
                if github_res.status_code == 200:
                    datos_repo = github_res.json()
                    es_privado = datos_repo.get('private')
                    if not es_privado:
                        lista_publicos.append(f"{estudiante} -> {git_url}")
                        print(f"\n[PÚBLICO] {estudiante}")
                    else:
                        print(f"\n[Privado] {estudiante}")
                    commits = obtener_cantidad_commits(owner, repo_name)
                    log_commits.append(f"{estudiante}: {commits} commits ({repo_name})")
                    repos_clonados += 1
                    subprocess.run(["git", "clone", git_url])
                elif github_res.status_code == 404:
                    print(f"\n[SIN ACCESO] {estudiante} -> {git_url}")
                    lista_sin_acceso.append(f"{estudiante} -> {git_url}")

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reporte = f"""==================================================
REPORTE DE TAREA CANVAS - GENERADO: {fecha_actual}
==================================================
Total de repositorios descargados: {repos_clonados}

REPOSITORIOS PÚBLICOS (Bajar puntos):
{chr(10).join(['  - ' + r for r in lista_publicos]) if lista_publicos else '  Ninguno'}

ENTREGADOS POR COMENTARIO (Bajar puntos):
{chr(10).join(['  - ' + r for r in lista_comentarios]) if lista_comentarios else '  Ninguno'}

SIN ACCESO (Olvido de invitación o enlace roto):
{chr(10).join(['  - ' + r for r in lista_sin_acceso]) if lista_sin_acceso else '  Ninguno'}

CANTIDAD DE COMMITS (Al momento de ejecución):
{chr(10).join(['  - ' + r for r in log_commits]) if log_commits else '  Sin datos'}
==================================================
"""
    print("\n" + reporte)
    nombre_archivo = f"Log_Tarea_{ASSIGNMENT_ID}.txt"
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(reporte)
    print(f"El reporte se ha guardado en: {nombre_archivo}")
else:
    print(f"Error al conectar con Canvas: {response.status_code}")
