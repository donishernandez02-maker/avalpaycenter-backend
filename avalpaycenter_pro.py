# avalpaycenter_pro.py
# Backend REAL para Railway (demo estable de endpoints)
# Universidad del Norte - Proyecto Final
# Automatización / Diagnóstico para AvalPayCenter (con Selenium opcional)

import os
import sys
import json
import time
import logging
import shutil
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify
from flask_cors import CORS

# -----------------------------------------------------------------------------
# Logging básico (stdout) – Railway capta stdout/stderr
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("avalpaycenter_pro")

# -----------------------------------------------------------------------------
# App Flask
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.url_map.strict_slashes = False
CORS(app)

# -----------------------------------------------------------------------------
# Flags / cache de motor Selenium (lazy init)
# -----------------------------------------------------------------------------
SELENIUM_IMPORT_OK = True
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
except Exception as e:
    SELENIUM_IMPORT_OK = False
    logger.warning("Selenium no disponible: %s", e)

# Cache global del "motor" (detalles y paths).  ¡Declarado al NIVEL MÓDULO!
automation_engine: Optional[Dict[str, Any]] = None

# Driver Selenium (solo si se necesita y si está habilitado)
DRIVER: Optional["webdriver.Chrome"] = None

# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def _exists(path: Optional[str]) -> bool:
    return bool(path) and os.path.exists(path)

def _which(cmd: str) -> Optional[str]:
    try:
        p = shutil.which(cmd)
        return p
    except Exception:
        return None

def _run_which(cmd: str) -> Optional[str]:
    # a veces which del shell da otra pista
    try:
        out = subprocess.check_output(["/usr/bin/env", "which", cmd], stderr=subprocess.STDOUT, timeout=1)
        return out.decode().strip()
    except Exception:
        return None

def _common_paths() -> Dict[str, str]:
    return {
        "chromedriver_1": "/usr/bin/chromedriver",
        "chromedriver_2": "/usr/lib/chromium/chromedriver",
        "chromedriver_3": "/root/.nix-profile/bin/chromedriver",
        "chromium_1": "/usr/bin/chromium",
        "chromium_2": "/usr/bin/chromium-browser",
        "chromium_3": "/root/.nix-profile/bin/chromium",
    }

def _detect_binaries() -> Dict[str, Any]:
    """
    Busca chrome/chromedriver en:
    - Variables de entorno opcionales (CHROME_BIN, CHROMEDRIVER_PATH)
    - shutil.which(...)
    - rutas comunes (Nixpacks: /root/.nix-profile/bin/*)
    """
    env_chrome = os.getenv("CHROME_BIN")
    env_driver = os.getenv("CHROMEDRIVER_PATH")

    which_chrome = _which("chromium") or _which("chromium-browser") or _which("google-chrome")
    which_driver = _which("chromedriver")

    run_which_chrome = _run_which("chromium") or _run_which("chromium-browser") or _run_which("google-chrome")
    run_which_driver = _run_which("chromedriver")

    commons = _common_paths()

    candidates_chrome = [
        env_chrome,
        which_chrome,
        run_which_chrome,
        commons["chromium_1"],
        commons["chromium_2"],
        commons["chromium_3"],
    ]
    candidates_driver = [
        env_driver,
        which_driver,
        run_which_driver,
        commons["chromedriver_1"],
        commons["chromedriver_2"],
        commons["chromedriver_3"],
    ]

    chrome_bin = next((p for p in candidates_chrome if _exists(p)), None)
    chromedriver_path = next((p for p in candidates_driver if _exists(p)), None)

    return {
        "env": {
            "CHROME_BIN": env_chrome,
            "CHROMEDRIVER_PATH": env_driver,
        },
        "which": {
            "chrome": which_chrome,
            "chromedriver": which_driver,
        },
        "which_shell": {
            "chrome": run_which_chrome,
            "chromedriver": run_which_driver,
        },
        "commons": commons,
        "resolved": {
            "chrome_bin": chrome_bin,
            "chromedriver_path": chromedriver_path,
        },
        "exists": {
            "chrome_bin": _exists(chrome_bin),
            "chromedriver_path": _exists(chromedriver_path),
        },
    }

# -----------------------------------------------------------------------------
# Motor (detalles de selenium/chrome). ¡Usa global declarado al inicio!
# -----------------------------------------------------------------------------
def get_engine(force: bool = False) -> Dict[str, Any]:
    """
    Devuelve detalles del 'motor' (paths, flags, etc.).  Lazy-init y cacheado.
    IMPORTANTE: el 'global automation_engine' debe ir antes de usar/asignar.
    """
    global automation_engine  # <- PRIMERA línea dentro de la función

    if automation_engine is not None and not force:
        return automation_engine

    enable_selenium = env_bool("ENABLE_SELENIUM", default=False)
    detected = _detect_binaries()

    engine = {
        "service": "AvalPayCenter Automation API",
        "version": "1.0.0",
        "enable_selenium": enable_selenium,
        "selenium_import_ok": SELENIUM_IMPORT_OK,
        "detected": detected,
        "ready": bool(SELENIUM_IMPORT_OK and enable_selenium and detected["exists"]["chrome_bin"] and detected["exists"]["chromedriver_path"]),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    automation_engine = engine
    return engine

# -----------------------------------------------------------------------------
# Selenium driver (solo si hace falta)
# -----------------------------------------------------------------------------
def _build_chrome_options() -> "Options":
    opts = Options()
    # modo moderno y estable para contenedores
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-software-rasterizer")
    # idioma/UA opcional
    opts.add_argument("--lang=es-ES")
    return opts

def get_driver(reuse: bool = True) -> Optional["webdriver.Chrome"]:
    global DRIVER

    eng = get_engine()
    if not eng["enable_selenium"] or not eng["selenium_import_ok"]:
        logger.info("Selenium deshabilitado o no disponible.")
        return None

    if reuse and DRIVER is not None:
        return DRIVER

    chrome_bin = eng["detected"]["resolved"]["chrome_bin"]
    chromedriver_path = eng["detected"]["resolved"]["chromedriver_path"]
    if not (chrome_bin and chromedriver_path):
        logger.warning("No se encontraron binarios de chrome/chromedriver.")
        return None

    try:
        opts = _build_chrome_options()
        opts.binary_location = chrome_bin

        service = Service(chromedriver_path)
        DRIVER = webdriver.Chrome(service=service, options=opts)
        logger.info("Driver Selenium inicializado (pid=%s)", getattr(DRIVER.service.process, "pid", "?"))
        return DRIVER
    except Exception as e:
        logger.error("Fallo iniciando Selenium: %s", e, exc_info=True)
        DRIVER = None
        return None

# -----------------------------------------------------------------------------
# Helpers de respuesta
# -----------------------------------------------------------------------------
def ok(data: Dict[str, Any], code: int = 200):
    data.setdefault("success", True)
    return jsonify(data), code

def fail(message: str, code: int = 500, extra: Optional[Dict[str, Any]] = None):
    payload = {"success": False, "error": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), code

def _available_endpoints() -> list:
    # lista human-readable
    return [
        "GET /api/health - Estado del sistema",
        "POST /api/search-reference - Búsqueda REAL en AvalPayCenter (demo)",
        "POST /api/solve-captcha - Resolver reCAPTCHA (demo)",
        "POST /api/complete-automation - Automatización COMPLETA (demo)",
        "GET /api/session-info - Estado de la sesión",
        "GET /api/test-avalpaycenter - Probar conexión",
        "GET /api/_routes - (debug) rutas cargadas",
        "GET /api/_engine - (debug) inicializar/ver estado del motor",
    ]

# -----------------------------------------------------------------------------
# Rutas
# -----------------------------------------------------------------------------
@app.get("/api/health")
def api_health():
    eng = get_engine(force=False)
    return ok({
        "service": eng["service"],
        "status": "healthy",
        "enable_selenium": eng["enable_selenium"],
        "selenium_import_ok": eng["selenium_import_ok"],
        "available_endpoints": _available_endpoints(),
    })

@app.get("/api/_routes")
def api_routes():
    routes = []
    for r in app.url_map.iter_rules():
        routes.append({
            "rule": str(r),
            "endpoint": r.endpoint,
            "methods": sorted(list(r.methods)),
        })
    return ok({"routes": routes})

@app.get("/api/_engine")
def api_engine():
    eng = get_engine(force=False)
    # incluir algunas banderas útiles
    debug = {
        "ENABLE_SELENIUM": env_bool("ENABLE_SELENIUM", False),
        "SELENIUM_IMPORT_OK": SELENIUM_IMPORT_OK,
        "engine_status": "activo" if eng["ready"] else "no inicializado",
        "env": eng["detected"]["env"],
        "which": eng["detected"]["which"],
        "which_shell": eng["detected"]["which_shell"],
        "commons": eng["detected"]["commons"],
        "resolved": eng["detected"]["resolved"],
        "exists": eng["detected"]["exists"],
    }
    return ok({"debug": debug})

@app.get("/api/session-info")
def api_session_info():
    eng = get_engine()
    driver_state = "iniciado" if DRIVER else "no inicializado"
    return ok({
        "driver": driver_state,
        "enable_selenium": eng["enable_selenium"],
        "selenium_import_ok": eng["selenium_import_ok"],
    })

@app.get("/api/test-avalpaycenter")
def api_test():
    # endpoint de latido simple
    return ok({"message": "Conectado a AvalPayCenter Backend (demo)."})

# -----------------------------------------------------------------------------
# Endpoints de negocio (demos estables)
# -----------------------------------------------------------------------------
@app.post("/api/search-reference")
def api_search_reference():
    """
    Demo estable que devuelve un payload de extracción.
    Body esperado: { "reference_number": "61897266" }
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        ref = str(payload.get("reference_number", "")).strip()

        if not ref:
            return fail("reference_number es requerido", 400)

        # En demo devolvemos estructura conocida
        extracted = {
            "payment_info": {
                "amount_due": None,
                "currency": "COP",
                "customer_name": "N/A",
                "entity": "AvalPayCenter",
                "status": "unknown",
            },
            "success": True,
        }

        return ok({"reference": ref, "extracted": extracted})
    except Exception as e:
        logger.exception("Fallo search-reference: %s", e)
        return fail(str(e), 500)

@app.post("/api/solve-captcha")
def api_solve_captcha():
    """
    Demo: simula resolución. Si se envía 2captcha_api_key devolvemos mensaje de OK.
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        key = payload.get("2captcha_api_key") or os.getenv("2CAPTCHA_API_KEY")

        if not key:
            # no hacemos requests reales a 2captcha en este demo
            msg = "No se detectó reCAPTCHA en la página actual."
        else:
            msg = "reCAPTCHA resuelto (demo)."

        return ok({"captcha": {"success": True, "message": msg}})
    except Exception as e:
        logger.exception("Fallo solve-captcha: %s", e)
        return fail(str(e), 500)

@app.post("/api/complete-automation")
def api_complete_automation():
    """
    Demo completo. Si ENABLE_SELENIUM=1 e instalados binarios, inicializa driver en headless.
    Body: { "reference_number": "...", "2captcha_api_key": "..." }
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        ref = str(payload.get("reference_number", "")).strip()
        if not ref:
            return fail("reference_number es requerido", 400)

        # (opcional) “resolver” captcha en demo
        key = payload.get("2captcha_api_key") or os.getenv("2CAPTCHA_API_KEY")
        captcha_msg = "No se detectó reCAPTCHA en la página actual."
        if key:
            captcha_msg = "reCAPTCHA resuelto (demo)."

        # Inicializar Selenium solo si procede (no imprescindible en demo)
        eng = get_engine()
        driver_used = False
        if eng["enable_selenium"] and eng["selenium_import_ok"]:
            drv = get_driver(reuse=True)
            if drv:
                driver_used = True
                # Aquí iría la navegación real (omitada en demo)
                # drv.get("https://www.avalpaycenter.com/...") etc.
                pass

        extracted = {
            "payment_info": {
                "amount_due": None,
                "currency": "COP",
                "customer_name": "N/A",
                "entity": "AvalPayCenter",
                "status": "unknown",
            },
            "success": True,
        }

        return ok({
            "captcha": {"success": True, "message": captcha_msg},
            "extracted": extracted,
            "reference": ref,
            "driver_used": driver_used,
        })
    except Exception as e:
        logger.exception("Fallo complete-automation: %s", e)
        return fail(str(e), 500)

# -----------------------------------------------------------------------------
# Arranque local (Railway usa Gunicorn vía Procfile)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Para pruebas locales / diagnóstico en Railway si usas startCommand
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info("🚀 Iniciando API en http://%s:%d ...", host, port)
    app.run(host=host, port=port)
