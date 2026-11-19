import re
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from pypdf import PdfReader

# ================== CONFIG ==================
CANVAS_URL = ""         
CANVAS_TOKEN = ""
GITHUB_TOKEN = ""
COURSE_ID = ""
ASSIGNMENT_ID = ""

PDF_LAB = "lab.pdf"              # instrucciones del lab 
REVISAR_CON_IA = False            # False = solo commits, clonado y reporte

OLLAMA_URL = "http://localhost:11434"
MODELO = "qwen2.5-coder:7b"
NUM_CTX = 32768                  # contexto del modelo 
MAX_CHARS = 60_000               # máximo de código por estudiante

ZONA = timezone(timedelta(hours=-6))   # Honduras
CARPETA = Path(f"tarea_{ASSIGNMENT_ID}")

EXTENSIONES = {".java", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".sql",
               ".c", ".cpp", ".h", ".cs", ".xml", ".properties", ".txt", ".md"}
IGNORAR_DIRS = {".git", "node_modules", "target", "build", "dist", "out", "bin",
                ".idea", ".vscode", "__pycache__", "venv", ".venv", ".gradle",
                "nbproject", ".settings"}
IGNORAR_ARCHIVOS = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                    "build.xml", "manifest.mf", ".classpath", ".project"}

SISTEMA = """Sos un asistente que ayuda a un instructor de programación a revisar laboratorios.
Te doy las INSTRUCCIONES DEL LAB y el CÓDIGO de un estudiante.
Respondé SIEMPRE en español y en Markdown, con estas secciones exactas:

## Resumen
2-3 líneas sobre el estado general de la entrega.

## Requisitos
Por cada requisito de las instrucciones, una línea así:
- [ESTADO] Requisito — archivo/método donde se ve — comentario corto
ESTADO es uno de: ✅ Cumple | ⚠️ Parcial | ❌ No cumple | ❔ Verificar ejecutando

## Errores encontrados
Errores de compilación, de lógica o casos que fallarían. Indicá archivo y número de línea.

## Calidad del código
2-4 puntos breves.

## Nota sugerida
Si las instrucciones traen rúbrica o puntaje, usala y desglosá. Si no, sugerí una nota sobre 100.

Reglas:
- No inventes código ni funcionalidad que no está en lo que te pasé.
- Si no podés confirmar algo solo leyendo, marcalo ❔.
- Sé directo y concreto."""

H_CANVAS = {"Authorization": f"Bearer {CANVAS_TOKEN}"}
H_GITHUB = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
REGEX_GH = re.compile(r'https?://github\.com/([\w.-]+)/([\w.-]+)')


# ================== CANVAS ==================
def canvas_get_all(url, params=None):
    datos = []
    while url:
        r = requests.get(url, headers=H_CANVAS, params=params)
        r.raise_for_status()
        datos.extend(r.json())
        url = r.links.get("next", {}).get("url")
        params = None
    return datos


def obtener_fecha_limite():
    url = f"{CANVAS_URL}/api/v1/courses/{COURSE_ID}/assignments/{ASSIGNMENT_ID}"
    r = requests.get(url, headers=H_CANVAS)
    if r.status_code == 200 and r.json().get("due_at"):
        return datetime.fromisoformat(r.json()["due_at"].replace("Z", "+00:00"))
    return None


def extraer_repo(sub):
    candidatos = []
    if sub.get("submission_type") == "online_url":
        candidatos.append((sub.get("url") or "", "URL Oficial"))
    elif sub.get("submission_type") == "online_text_entry":
        candidatos.append((sub.get("body") or "", "Texto Oficial"))
    for c in sub.get("submission_comments", []):
        candidatos.append((c.get("comment") or "", "Comentario (Penalizar)"))

    for texto, origen in candidatos:
        m = REGEX_GH.search(texto)
        if m:
            return m.group(1), re.sub(r'\.git$', '', m.group(2)), origen
    return None, None, None


# ================== GITHUB ==================
def obtener_commits(owner, repo):
    commits = []
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"per_page": 100}
    while url:
        r = requests.get(url, headers=H_GITHUB, params=params)
        if r.status_code != 200:   # 409 = repo vacío
            break
        for c in r.json():
            info = c["commit"]["author"]
            commits.append({
                "sha": c["sha"][:7],
                "autor": (c.get("author") or {}).get("login") or info["name"],
                "fecha": datetime.fromisoformat(info["date"].replace("Z", "+00:00")),
                "mensaje": c["commit"]["message"].splitlines()[0][:100],
            })
        url = r.links.get("next", {}).get("url")
        params = None
    return sorted(commits, key=lambda x: x["fecha"])


def clonar_o_actualizar(owner, repo, destino):
    url_auth = f"https://{GITHUB_TOKEN}@github.com/{owner}/{repo}.git"
    if destino.exists():
        res = subprocess.run(["git", "-C", str(destino), "pull", url_auth],
                             capture_output=True, text=True)
    else:
        res = subprocess.run(["git", "clone", url_auth, str(destino)],
                             capture_output=True, text=True)
        if res.returncode == 0:   # no dejar el token guardado en .git/config
            subprocess.run(["git", "-C", str(destino), "remote", "set-url", "origin",
                            f"https://github.com/{owner}/{repo}.git"])
    return res.returncode == 0


# ================== OLLAMA ==================
def ollama_disponible():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        modelos = [m["name"] for m in r.json().get("models", [])]
        if MODELO not in modelos:
            print(f"El modelo {MODELO} no está descargado. Corré: ollama pull {MODELO}")
            return False
        return True
    except requests.RequestException:
        print("Ollama no está corriendo. Abrí la app de Ollama o corré: ollama serve")
        return False


def leer_pdf(ruta):
    lector = PdfReader(ruta)
    texto = "\n".join((p.extract_text() or "") for p in lector.pages).strip()
    if not texto:
        print("El PDF no tiene texto seleccionable (¿es escaneado?). No se puede leer.")
    return texto


def leer_codigo(carpeta):
    PRIORIDAD = {".java": 0, ".py": 0, ".js": 0, ".jsx": 0, ".ts": 0, ".tsx": 0,
                 ".c": 0, ".cpp": 0, ".h": 0, ".cs": 0, ".sql": 1, ".html": 1, ".css": 1}

    arbol, archivos = [], []
    for ruta in sorted(carpeta.rglob("*")):
        rel = ruta.relative_to(carpeta)
        if any(p in IGNORAR_DIRS for p in rel.parts) or not ruta.is_file():
            continue
        arbol.append(rel.as_posix())
        if ruta.suffix.lower() in EXTENSIONES and ruta.name not in IGNORAR_ARCHIVOS:
            archivos.append(ruta)

    archivos.sort(key=lambda r: (PRIORIDAD.get(r.suffix.lower(), 2), r.as_posix()))

    partes, total, incluidos = [], 0, 0
    for ruta in archivos:
        try:
            texto = ruta.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = ruta.relative_to(carpeta).as_posix()
        numerado = "\n".join(f"{i:4}| {l}" for i, l in enumerate(texto.splitlines(), 1))
        bloque = f"\n===== {rel} =====\n{numerado}\n"
        if total + len(bloque) > MAX_CHARS:
            partes.append(f"\n[... {len(archivos) - incluidos} archivo(s) omitidos por tamaño ...]\n")
            break
        partes.append(bloque)
        total += len(bloque)
        incluidos += 1

    print(f"     Enviando {incluidos} archivo(s) de código a la IA")
    return "ESTRUCTURA DEL REPO:\n" + "\n".join(arbol) + "\n\nCÓDIGO:\n" + "".join(partes)


def revisar_con_ollama(instrucciones, estudiante, codigo):
    payload = {
        "model": MODELO,
        "stream": False,
        "options": {"num_ctx": NUM_CTX, "temperature": 0.2},
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content":
                f"INSTRUCCIONES DEL LAB:\n{instrucciones}\n\n"
                f"ESTUDIANTE: {estudiante}\n\n{codigo}"},
        ],
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=1800)
    r.raise_for_status()
    return r.json()["message"]["content"]


# ================== UTILIDADES ==================
def formatear_commits(commits, limite):
    lineas = []
    for c in commits:
        tarde = " ⏰ TARDE" if limite and c["fecha"] > limite else ""
        hora = c["fecha"].astimezone(ZONA).strftime("%Y-%m-%d %H:%M")
        lineas.append(f"    [{c['sha']}] {hora} | {c['autor']} | {c['mensaje']}{tarde}")
    return "\n".join(lineas) if lineas else "    (sin commits)"


def nombre_seguro(texto):
    return re.sub(r'[^\w\-]+', '_', texto).strip('_')


# ================== MAIN ==================
def main():
    CARPETA.mkdir(exist_ok=True)
    (CARPETA / "revisiones").mkdir(exist_ok=True)

    instrucciones = ""
    if REVISAR_CON_IA:
        if not Path(PDF_LAB).exists():
            print(f"No encontré {PDF_LAB}. Ponelo en esta carpeta o desactivá REVISAR_CON_IA.")
            return
        if not ollama_disponible():
            return
        instrucciones = leer_pdf(PDF_LAB)
        if not instrucciones:
            return

    print("Conectando a Canvas...")
    limite = obtener_fecha_limite()
    url = f"{CANVAS_URL}/api/v1/courses/{COURSE_ID}/assignments/{ASSIGNMENT_ID}/submissions"
    subs = canvas_get_all(url, {"per_page": 100, "include[]": ["submission_comments", "user"]})

    publicos, por_comentario, sin_acceso, sin_link, detalle = [], [], [], [], []
    descargados = 0

    for sub in subs:
        estudiante = sub.get("user", {}).get("name", f"ID: {sub.get('user_id')}")
        owner, repo, origen = extraer_repo(sub)

        if not owner:
            if sub.get("workflow_state") != "unsubmitted":
                sin_link.append(estudiante)
            continue

        git_url = f"https://github.com/{owner}/{repo}"
        if origen.startswith("Comentario"):
            por_comentario.append(f"{estudiante} -> {git_url}")

        r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=H_GITHUB)
        if r.status_code != 200:
            motivo = "sin acceso / no existe" if r.status_code == 404 else f"error {r.status_code}"
            print(f"[SIN ACCESO] {estudiante} ({motivo})")
            sin_acceso.append(f"{estudiante} -> {git_url} ({motivo})")
            continue

        if not r.json().get("private"):
            publicos.append(f"{estudiante} -> {git_url}")

        commits = obtener_commits(owner, repo)
        tardes = sum(1 for c in commits if limite and c["fecha"] > limite)
        detalle.append(f"  {estudiante} — {repo} — {len(commits)} commits"
                       + (f" ({tardes} después de la fecha límite)" if tardes else "")
                       + "\n" + formatear_commits(commits, limite))

        destino = CARPETA / nombre_seguro(estudiante)
        if not clonar_o_actualizar(owner, repo, destino):
            print(f"[ERROR CLONANDO] {estudiante}")
            continue
        descargados += 1
        print(f"[OK] {estudiante}: {len(commits)} commits")

        if REVISAR_CON_IA:
            print("     Revisando con Ollama (puede tardar unos minutos)...")
            inicio = time.time()
            try:
                revision = revisar_con_ollama(instrucciones, estudiante, leer_codigo(destino))
                archivo = CARPETA / "revisiones" / f"{nombre_seguro(estudiante)}.md"
                archivo.write_text(
                    f"# {estudiante}\nRepo: {git_url}\nCommits: {len(commits)}"
                    + (f" ({tardes} tarde)" if tardes else "") + f"\n\n{revision}",
                    encoding="utf-8")
                print(f"     Listo en {time.time() - inicio:.0f}s")
            except requests.RequestException as e:
                print(f"     Error en la revisión: {e}")

    lista = lambda xs: "\n".join(f"  - {x}" for x in xs) if xs else "  Ninguno"
    lim_txt = limite.astimezone(ZONA).strftime("%Y-%m-%d %H:%M") if limite else "sin fecha límite"
    reporte = f"""==================================================
REPORTE DE TAREA {ASSIGNMENT_ID} - {datetime.now(ZONA).strftime("%Y-%m-%d %H:%M")}
Fecha límite: {lim_txt}
==================================================
Repositorios descargados: {descargados}

REPOSITORIOS PÚBLICOS (Bajar puntos):
{lista(publicos)}

ENTREGADOS POR COMENTARIO (Bajar puntos):
{lista(por_comentario)}

SIN ACCESO (Sin invitación o enlace roto):
{lista(sin_acceso)}

ENTREGÓ PERO SIN LINK DE GITHUB:
{lista(sin_link)}

DETALLE DE COMMITS:
{chr(10).join(detalle) if detalle else '  Sin datos'}
==================================================
"""
    print("\n" + reporte)
    (CARPETA / f"Log_Tarea_{ASSIGNMENT_ID}.txt").write_text(reporte, encoding="utf-8")
    print(f"Reporte en {CARPETA}/Log_Tarea_{ASSIGNMENT_ID}.txt")
    if REVISAR_CON_IA:
        print(f"Revisiones en {CARPETA}/revisiones/")


if __name__ == "__main__":
    main()