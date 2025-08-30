# avalpaycenter_pro.py — Backend para Railway (Selenium opcional + 2captcha)
# Universidad del Norte – Proyecto Final

import os
import sys
import re
import time
import shutil
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import requests

# ------------------------------------------------------------------------------
# Logging (a stdout para que Railway lo capture)
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("avalpaycenter")

# ------------------------------------------------------------------------------
# App Flask
# ------------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
app.url_map.strict_slashes = False  # acepta /ruta y /ruta/

# ------------------------------------------------------------------------------
# Config y Selenium (import opcional)
# ------------------------------------------------------------------------------
ENABLE_SELENIUM = os.getenv("ENABLE_SELENIUM", "0") == "1"  # por defecto apagado
PAY_URL = (
    "https://www.avalpaycenter.com/wps/portal/portal-de-pagos/web/pagos-aval/"
    "resultado-busqueda/realizar-pago-facturadores?idConv=00000017&origen=buscar"
)

SELENIUM_IMPORT_OK = False
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_IMPORT_OK = True
except Exception as e:
    logger.info("Selenium no disponible (import falló o no instalado): %s", e)

automation_engine = None  # se creará bajo demanda

# ------------------------------------------------------------------------------
# Motor de automatización
# ------------------------------------------------------------------------------
class RailwayAvalPayCenterAutomation:
    """
    Motor preparado para Railway/Nixpacks.
    Requisitos para modo REAL:
      - ENABLE_SELENIUM=1
      - NIXPACKS_PKGS="chromium chromedriver"
      - (Opcional) 2CAPTCHA_API_KEY en Variables (o enviarla en el body)
    """

    def __init__(self):
        """Inicialización robusta de Chrome Headless en contenedor Railway."""
        if not SELENIUM_IMPORT_OK:
            raise RuntimeError("Selenium no está disponible en este entorno.")

        # Preferir binarios en PATH (Nixpacks suele dejarlos en /root/.nix-profile/bin o /nix/store/.../bin)
        env_chrome = os.getenv("CHROME_BIN")
        env_driver = os.getenv("CHROMEDRIVER_PATH")
        which_chrome = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        which_driver = shutil.which("chromedriver")

        def pick_existing(*cands):
            for p in cands:
                if p and os.path.exists(p):
                    return p
            return None

        fallback_chrome = "/usr/bin/chromium"
        fallback_driver = "/usr/bin/chromedriver"
        alt_driver      = "/usr/lib/chromium/chromedriver"

        CHROME_BIN        = pick_existing(env_chrome, which_chrome, fallback_chrome)
        CHROMEDRIVER_PATH = pick_existing(env_driver, which_driver, fallback_driver, alt_driver)

        # Entornos/dirs temporales seguros (evitan crash por permisos/locks)
        os.environ["HOME"] = "/tmp"
        os.environ["XDG_CACHE_HOME"] = "/tmp"
        os.environ["XDG_CONFIG_HOME"] = "/tmp"
        os.environ["XDG_RUNTIME_DIR"] = "/tmp"

        tmp_dir = "/tmp/chrome"
        os.makedirs(f"{tmp_dir}/user-data", exist_ok=True)
        os.makedirs(f"{tmp_dir}/data-path", exist_ok=True)
        os.makedirs(f"{tmp_dir}/cache-dir", exist_ok=True)

        chrome_options = Options()
        if CHROME_BIN:
            chrome_options.binary_location = CHROME_BIN

        # Flags probadas para contenedores (Chrome 130+)
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-zygote")
        chrome_options.add_argument("--window-size=1024,700")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument(f"--user-data-dir={tmp_dir}/user-data")
        chrome_options.add_argument(f"--data-path={tmp_dir}/data-path")
        chrome_options.add_argument(f"--disk-cache-dir={tmp_dir}/cache-dir")

        # Estabilidad extra (evita throttling de timers, etc.)
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-features=Translate,BackForwardCache,MediaRouter")
        chrome_options.add_argument("--ignore-certificate-errors")
        # Si persiste el crash, prueba a descomentar esta (no siempre es necesaria):
        # chrome_options.add_argument("--single-process")

        logger.info(f"[Selenium] CHROME_BIN={CHROME_BIN}")
        logger.info(f"[Selenium] CHROMEDRIVER_PATH={CHROMEDRIVER_PATH}")
        logger.info(f"[Selenium] which chromedriver={which_driver}, which chromium={which_chrome}")

        # Si tenemos ruta al driver la usamos; si no, que Selenium lo resuelva por PATH
        if CHROMEDRIVER_PATH:
            service = Service(CHROMEDRIVER_PATH)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            self.driver = webdriver.Chrome(options=chrome_options)

        self.wait = WebDriverWait(self.driver, 15)
        logger.info("✅ Chrome inicializado en Railway")

    # ---------- Utilidades/real ----------
    def _find_recaptcha_sitekey(self) -> Optional[str]:
        """Detecta la sitekey del reCAPTCHA en la página actual."""
        # 1) iframe de anchor: .../api2/anchor?ar=1&k=<SITEKEY>...
        try:
            iframe = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "iframe[src*='api2/anchor']")))
            src = iframe.get_attribute("src") or ""
            parsed = urlparse(src)
            sitekey = parse_qs(parsed.query).get("k", [None])[0]
            if sitekey:
                return sitekey
        except Exception:
            pass
        # 2) data-sitekey directo en DOM
        try:
            box = self.driver.find_element(By.CSS_SELECTOR, "[data-sitekey]")
            return box.get_attribute("data-sitekey")
        except Exception:
            return None

    def navigate_to_avalpaycenter_real(self, reference_number: str, api_key_2captcha: Optional[str] = None) -> Dict[str, Any]:
        """
        Abre la página de 'realizar-pago-facturadores', llena la referencia,
        intenta resolver reCAPTCHA (si aparece) y envía el formulario.
        Ajusta los selectores si el HTML cambia.
        """
        try:
            # 1) Ir directo a la página de pago de facturadores (idConv=00000017)
            self.driver.get(PAY_URL)

            # 2) Encontrar el input de referencia (probamos varios selectores comunes)
            used_field_sel = None
            field = None
            field_candidates = [
                "input[name*='referen' i]",
                "input[id*='referen' i]",
                "input[placeholder*='referen' i]",
                "input[name*='codigo' i]",
                "input[id*='codigo' i]",
                "input[type='text']",
            ]
            for sel in field_candidates:
                try:
                    field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                    field.clear()
                    field.send_keys(reference_number)
                    used_field_sel = sel
                    break
                except Exception:
                    continue

            if not field:
                return {
                    "success": False,
                    "error": "No se encontró el campo de referencia",
                    "selectors_tried": field_candidates,
                    "url": self.driver.current_url
                }

            # 3) Si hay reCAPTCHA, resolver antes de enviar (si recibimos API key)
            captcha_info = None
            if api_key_2captcha:
                try:
                    captcha_info = self.solve_recaptcha_real(api_key_2captcha)
                except Exception as e:
                    captcha_info = {"success": False, "error": str(e)}

            # 4) Click en el botón (Buscar / Continuar / Pagar)
            clicked = False

            # por CSS
            btn_css_candidates = [
                "button[type='submit']",
                "input[type='submit']",
                "button[name*='buscar' i]",
                "button[name*='continuar' i]",
            ]
            for sel in btn_css_candidates:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                    btn.click()
                    clicked = True
                    break
                except Exception:
                    pass

            # si no, por texto con XPATH
            if not clicked:
                xpath_candidates = [
                    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'buscar')]",
                    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continuar')]",
                    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'pagar')]",
                    "//input[@type='submit']",
                ]
                for xp in xpath_candidates:
                    try:
                        btn = self.driver.find_element(By.XPATH, xp)
                        btn.click()
                        clicked = True
                        break
                    except Exception:
                        pass

            # 5) Espera corta a que carguen resultados (ajustable)
            time.sleep(2.5)

            return {
                "success": True,
                "navigated_url": self.driver.current_url,
                "field_selector": used_field_sel,
                "clicked": clicked,
                "captcha": captcha_info
            }
        except Exception as e:
            logger.exception("navigate_to_avalpaycenter_real fallo")
            return {"success": False, "error": str(e), "url": self.driver.current_url}

    def extract_payment_info_real(self) -> Dict[str, Any]:
        """Ejemplo de extracción (ajusta selectores al HTML real)."""
        try:
            def txt(sel: str) -> Optional[str]:
                try:
                    return self.driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                except Exception:
                    return None

            # Ajusta estos selectores:
            name   = txt(".customer-name, #nombreCliente, [data-field='customer']")
            amt_t  = txt(".amount, .valor, #amount, [data-field='amount']")
            status = txt(".status, .estado, #estado, [data-field='status']") or "unknown"

            amount_due = None
            if amt_t:
                amt_norm = amt_t.replace("\xa0", " ").replace(".", "").replace(",", ".")
                m = re.search(r"(\d+(?:\.\d+)?)", amt_norm)
                if m:
                    try:
                        amount_due = float(m.group(1))
                    except Exception:
                        pass

            info = {
                "entity": "AvalPayCenter",
                "customer_name": name or "N/A",
                "amount_due": amount_due,
                "currency": "COP",
                "status": status,
            }
            return {"success": True, "payment_info": info}
        except Exception as e:
            logger.exception("Falló la extracción REAL")
            return {"success": False, "error": str(e)}

    def solve_recaptcha_real(self, api_key_2captcha: Optional[str]) -> Dict[str, Any]:
        """Resuelve reCAPTCHA v2 usando 2captcha (si hay captcha en la página)."""
        if not api_key_2captcha:
            return {"success": False, "error": "Falta 2captcha_api_key (o 2CAPTCHA_API_KEY)"}

        sitekey = self._find_recaptcha_sitekey()
        if not sitekey:
            return {"success": True, "message": "No se detectó reCAPTCHA en la página actual."}

        pageurl = self.driver.current_url
        try:
            # 1) Crear tarea
            payload = {
                "key": api_key_2captcha,
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": pageurl,
                "json": 1,
            }
            r = requests.post("https://2captcha.com/in.php", data=payload, timeout=30)
            j = r.json()
            if j.get("status") != 1:
                return {"success": False, "error": j.get("request", "2captcha in.php error")}
            captcha_id = j["request"]

            # 2) Polling 120s
            for _ in range(24):
                time.sleep(5)
                rr = requests.get(
                    "https://2captcha.com/res.php",
                    params={"key": api_key_2captcha, "action": "get", "id": captcha_id, "json": 1},
                    timeout=30,
                )
                jj = rr.json()
                if jj.get("status") == 1:
                    token = jj["request"]
                    # 3) Inyectar token
                    self.driver.execute_script("""
                        var el = document.getElementById('g-recaptcha-response');
                        if(!el){
                            el = document.createElement('textarea');
                            el.id = 'g-recaptcha-response';
                            el.name = 'g-recaptcha-response';
                            el.style.display = 'none';
                            document.body.appendChild(el);
                        }
                        el.value = arguments[0];
                    """, token)
                    return {"success": True, "message": "reCAPTCHA resuelto", "sitekey": sitekey}
                if jj.get("request") != "CAPCHA_NOT_READY":
                    return {"success": False, "error": jj.get("request")}
            return {"success": False, "error": "Timeout esperando 2captcha"}
        except Exception as e:
            logger.exception("Error resolviendo 2captcha")
            return {"success": False, "error": str(e)}

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass


def get_engine() -> Optional[RailwayAvalPayCenterAutomation]:
    """
    Crea el motor SOLO cuando lo piden y si Selenium está habilitado por env.
    Si el driver murió, lo recrea automáticamente para el siguiente request.
    """
    global automation_engine
    if not ENABLE_SELENIUM or not SELENIUM_IMPORT_OK:
        return None

    # Si ya existe, confirma que sigue vivo
    if automation_engine:
        try:
            _ = automation_engine.driver.window_handles  # acceso "inocuo"
        except Exception:
            try:
                automation_engine.close()
            except Exception:
                pass
            automation_engine = None

    if not automation_engine:
        automation_engine = RailwayAvalPayCenterAutomation()
    return automation_engine

# ------------------------------------------------------------------------------
# Helpers demo
# ------------------------------------------------------------------------------
def demo_result(reference: str) -> Dict[str, Any]:
    """Respuesta de demostración coherente cuando no hay Selenium."""
    return {
        "success": True,
        "reference": reference,
        "extracted": {
            "success": True,
            "payment_info": {
                "entity": "AvalPayCenter (demo)",
                "customer_name": "Usuario Demo",
                "amount_due": 0,
                "currency": "COP",
                "status": "desconocido",
            }
        },
        "note": "Modo demo (Selenium deshabilitado o no instalado)"
    }

# ------------------------------------------------------------------------------
# Rutas
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def root():
    return redirect("/api/health", code=302)

@app.route("/api/health", methods=["GET"])
@app.route("/api/health/", methods=["GET"])
def health_check():
    return jsonify({
        "success": True,
        "status": "healthy",
        "service": "AvalPayCenter Automation API",
        "version": "3.6.0",
        "selenium_import_ok": SELENIUM_IMPORT_OK,
        "enable_selenium": ENABLE_SELENIUM,
        "available_endpoints": [
            "GET /api/health - Estado del sistema",
            "POST /api/search-reference - Búsqueda REAL en AvalPayCenter",
            "POST /api/solve-captcha - Resolver reCAPTCHA REAL",
            "POST /api/complete-automation - Automatización COMPLETA",
            "GET /api/session-info - Estado de la sesión",
            "GET /api/test-avalpaycenter - Probar conexión",
            "GET /api/_routes - (debug) rutas cargadas",
            "GET /api/_engine - (debug) inicializar/ver estado del motor"
        ]
    }), 200

@app.route("/api/search-reference", methods=["POST"])
@app.route("/api/search-reference/", methods=["POST"])
def search_reference():
    try:
        data = request.get_json(force=True, silent=True) or {}
        ref = data.get("reference_number")
        if not ref:
            return jsonify({"success": False, "error": "Falta 'reference_number'"}), 400

        engine = get_engine()
        if not engine:
            return jsonify(demo_result(ref)), 200

        nav = engine.navigate_to_avalpaycenter_real(ref, os.getenv("2CAPTCHA_API_KEY"))
        if not nav.get("success"):
            return jsonify({"success": False, "error": "No se pudo navegar", "details": nav}), 500

        extracted = engine.extract_payment_info_real()
        return jsonify({"success": True, "reference": ref, "extracted": extracted}), 200

    except Exception as e:
        logger.exception("Error en /api/search-reference")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/solve-captcha", methods=["POST"])
@app.route("/api/solve-captcha/", methods=["POST"])
def solve_captcha():
    try:
        data = request.get_json(force=True, silent=True) or {}
        api_key = data.get("2captcha_api_key") or os.getenv("2CAPTCHA_API_KEY")
        engine = get_engine()
        if not engine:
            return jsonify({"success": True, "message": "Modo demo: no se requiere reCAPTCHA"}), 200
        result = engine.solve_recaptcha_real(api_key)
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Error en /api/solve-captcha")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/complete-automation", methods=["POST"])
@app.route("/api/complete-automation/", methods=["POST"])
def complete_automation():
    try:
        data = request.get_json(force=True, silent=True) or {}
        ref = data.get("reference_number")
        api_key = data.get("2captcha_api_key") or os.getenv("2CAPTCHA_API_KEY")
        if not ref:
            return jsonify({"success": False, "error": "Falta 'reference_number'"}), 400

        engine = get_engine()
        if not engine:
            return jsonify({
                "success": True,
                "reference": ref,
                "captcha": None,
                "extracted": demo_result(ref)["extracted"],
                "note": "Modo demo sin Selenium"
            }), 200

        steps = []

        # 1) Navegar + llenar + (si hay) resolver captcha + submit
        nav = engine.navigate_to_avalpaycenter_real(ref, api_key)
        steps.append({"step": 1, "name": "navigation", "result": nav})
        if not nav.get("success"):
            return jsonify({"success": False, "steps": steps, "error": "Navegación falló"}), 500

        # 2) Extraer información del resultado
        extracted = engine.extract_payment_info_real()
        steps.append({"step": 2, "name": "extraction", "result": extracted})

        # 3) Resultado de captcha (si navigate ya lo resolvió, úsalo; si no, intenta ahora)
        captcha = nav.get("captcha")
        if not isinstance(captcha, dict):
            captcha = engine.solve_recaptcha_real(api_key)
        steps.append({"step": 3, "name": "captcha", "result": captcha})

        ok = nav.get("success") and extracted.get("success") and captcha.get("success", True)
        return jsonify({
            "success": bool(ok),
            "reference": ref,
            "steps": steps,
            "extracted": extracted,
            "captcha": captcha
        }), 200

    except Exception as e:
        logger.exception("Error en /api/complete-automation")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/session-info", methods=["GET"])
@app.route("/api/session-info/", methods=["GET"])
def session_info():
    engine = get_engine()
    return jsonify({
        "success": True,
        "selenium_import_ok": SELENIUM_IMPORT_OK,
        "enable_selenium": ENABLE_SELENIUM,
        "driver": "activo" if (engine and getattr(engine, "driver", None)) else "no inicializado"
    }), 200

@app.route("/api/test-avalpaycenter", methods=["GET"])
@app.route("/api/test-avalpaycenter/", methods=["GET"])
def test_avalpaycenter():
    try:
        r = requests.get("https://www.avalpaycenter.com/", timeout=10)
        return jsonify({
            "success": True,
            "avalpaycenter_status": r.status_code,
            "avalpaycenter_accessible": r.status_code == 200
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 200

# -------------------------- Endpoints de debug -------------------------------
@app.route('/api/_routes', methods=['GET'])
@app.route('/api/_routes/', methods=['GET'])
def list_routes():
    """Lista las rutas realmente cargadas por esta release."""
    rules = []
    for r in app.url_map.iter_rules():
        methods = sorted([m for m in r.methods if m not in ('HEAD', 'OPTIONS')])
        rules.append({"rule": str(r), "endpoint": r.endpoint, "methods": methods})
    return jsonify({"success": True, "count": len(rules), "routes": rules}), 200

@app.route('/api/_engine', methods=['GET'])
@app.route('/api/_engine/', methods=['GET'])
def force_init_engine():
    """Intenta inicializar el motor y reporta diagnóstico de rutas."""
    info = {
        "ENABLE_SELENIUM": ENABLE_SELENIUM,
        "SELENIUM_IMPORT_OK": SELENIUM_IMPORT_OK,
        "env": {
            "CHROME_BIN": os.getenv("CHROME_BIN"),
            "CHROMEDRIVER_PATH": os.getenv("CHROMEDRIVER_PATH"),
        },
        "which": {
            "chromium": shutil.which("chromium"),
            "chromium-browser": shutil.which("chromium-browser"),
            "google-chrome": shutil.which("google-chrome"),
            "chromedriver": shutil.which("chromedriver"),
        },
        "exists": {
            "/usr/bin/chromium": os.path.exists("/usr/bin/chromium"),
            "/usr/bin/chromedriver": os.path.exists("/usr/bin/chromedriver"),
            "/usr/lib/chromium/chromedriver": os.path.exists("/usr/lib/chromium/chromedriver"),
        }
    }
    try:
        eng = get_engine()
        if eng and getattr(eng, "driver", None):
            info["engine"] = "activo"
            return jsonify({"success": True, "debug": info}), 200
        info["engine"] = "no inicializado"
        return jsonify({"success": False, "debug": info}), 200
    except Exception as e:
        info["engine"] = "error"
        info["error"] = str(e)
        return jsonify({"success": False, "debug": info}), 200

# ------------------------------------------------------------------------------
# Handler 404 (muestra endpoints)
# ------------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_e):
    return jsonify({
        "success": False,
        "error": "Endpoint no encontrado",
        "available_endpoints": [
            "GET /api/health - Estado del sistema",
            "POST /api/search-reference - Búsqueda REAL en AvalPayCenter",
            "POST /api/solve-captcha - Resolver reCAPTCHA REAL",
            "POST /api/complete-automation - Automatización COMPLETA",
            "GET /api/session-info - Estado de la sesión",
            "GET /api/test-avalpaycenter - Probar conexión",
            "GET /api/_routes - (debug) rutas cargadas",
            "GET /api/_engine - (debug) inicializar/ver estado del motor"
        ]
    }), 404

# ------------------------------------------------------------------------------
# Bootstrap local (en Railway usa Gunicorn con Procfile)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    host = "0.0.0.0"
    logger.info("🚀 Iniciando API en http://%s:%s (selenium_import_ok=%s, enable=%s)",
                host, port, SELENIUM_IMPORT_OK, ENABLE_SELENIUM)
    app.run(host=host, port=port)
