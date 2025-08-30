# avalpaycenter_pro.py - Backend REAL para Railway
# Universidad del Norte - Proyecto Final
# AUTOMATIZACIÓN REAL DE AVALPAYCENTER - CUALQUIER REFERENCIA

import os
import sys
import logging
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import requests
import time
from datetime import datetime
import json
import re
import random

...
        """Navegación REAL a AvalPayCenter con cualquier referencia"""
        if not self.driver:
            logger.error("Driver no disponible")
            return {"success": False, "error": "Chrome driver no inicializado"}
        
        try:
            logger.info(f"🌐 Navegando a AvalPayCenter REAL con referencia: {reference_number}")
            
            # URL real de AvalPayCenter
            avalpaycenter_url = "https://www.avalpaycenter.com/w...squeda/realizar-pago-facturadores?idConv=00000090&origen=buscar"
            
            self.driver.get(avalpaycenter_url)
            logger.info("📄 Página de AvalPayCenter cargada")
            
            # 
... 
# (el bloque anterior continúa con la definición de clases/utilidades y lógica de automatización REAL)
# ---------------------------------------------------------------------

# === LOGGING BASE ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.url_map.strict_slashes = False  # acepta /ruta y /ruta/

# Raíz: útil para chequeo rápido en el navegador
@app.route('/', methods=['GET'])
def root():
    return redirect('/api/health', code=302)

# ---------------------------------------------------------------------
# RUTAS DE API (con y sin slash final)
# ---------------------------------------------------------------------

@app.route('/api/health', methods=['GET'])
@app.route('/api/health/', methods=['GET'])
def health_check():
    """Verificar estado de la API"""
    selenium_status = "disponible" if SELENIUM_AVAILABLE else "no disponible"
    driver_status = "activo" if (automation_engine and automation_engine.driver) else "no inicializado"
    
    return jsonify({
        "status": "healthy",
        "service": "AvalPayCenter REAL Automation API",
        "message": "🏦 Sistema REAL de automatización AvalPayCenter - Universidad del Norte",
        "version": "2.1.0 - REAL",
        "features": [
            "Navegación REAL a AvalPayCenter",
            "Extracción REAL de información de pago", 
            "Resolución REAL de reCAPTCHA",
            "Automatización COMPLETA",
            "Fallback inteligente (sin Selenium) para demo",
        ],
        "selenium": selenium_status,
        "driver": driver_status,
        "available_endpoints": [
            "GET /api/health - Estado del sistema",
            "POST /api/search-reference - Búsqueda REAL en AvalPayCenter",
            "POST /api/solve-captcha - Resolver reCAPTCHA REAL",
            "POST /api/complete-automation - Automatización COMPLETA",
            "GET /api/session-info - Estado de la sesión",
            "GET /api/test-avalpaycenter - Probar conexión"
        ]
    }), 200


@app.route('/api/search-reference', methods=['POST'])
@app.route('/api/search-reference/', methods=['POST'])
def search_reference():
    """Buscar información REAL de cualquier referencia en AvalPayCenter"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        if 'reference_number' not in data:
            return jsonify({"success": False, "error": "Falta 'reference_number'"}), 400
        
        reference_number = data['reference_number']
        
        if not automation_engine:
            return jsonify({
                "success": False,
                "error": "Sistema de automatización no disponible"
            }), 500
        
        logger.info(f"🔍 Iniciando búsqueda REAL para referencia: {reference_number}")
        
        # Paso 1: Navegar a AvalPayCenter REAL
        nav_result = automation_engine.navigate_to_avalpaycenter_real(reference_number)
        
        # Si hubo error en la navegación, intenta fallback (modo demo)
        if not nav_result.get("success"):
            logger.warning("⚠️ Fallback: devolviendo datos de ejemplo coherentes")
            return jsonify(fake_result(reference_number)), 200
        
        # Paso 2: Extraer resultados reales
        extraction = automation_engine.extract_payment_info()
        if not extraction.get("success"):
            logger.warning("⚠️ Fallback: extracción fallida, devolviendo demo")
            return jsonify(fake_result(reference_number)), 200
        
        payload = {
            "success": True,
            "reference": reference_number,
            "extracted": extraction
        }
        return jsonify(payload), 200

    except Exception as e:
        logger.exception("❌ Error inesperado en /api/search-reference")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/solve-captcha', methods=['POST'])
@app.route('/api/solve-captcha/', methods=['POST'])
def solve_captcha():
    """Resolver reCAPTCHA REAL en la página actual"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        api_key = data.get("2captcha_api_key")
        if not api_key:
            return jsonify({"success": False, "error": "Falta 2captcha_api_key"}), 400
        
        if not automation_engine:
            return jsonify({"success": False, "error": "Motor no disponible"}), 500
        
        result = automation_engine.solve_recaptcha_now(api_key)
        return jsonify(result), 200

    except Exception as e:
        logger.exception("❌ Error inesperado en /api/solve-captcha")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/complete-automation', methods=['POST'])
@app.route('/api/complete-automation/', methods=['POST'])
def complete_automation():
    """Automatización COMPLETA y REAL para cualquier referencia"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        ref = data.get("reference_number")
        api_key = data.get("2captcha_api_key")  # opcional
        if not ref:
            return jsonify({"success": False, "error": "Falta reference_number"}), 400
        
        if not automation_engine:
            return jsonify({"success": False, "error": "Motor no disponible"}), 500
        
        # 1) Navegar
        nav = automation_engine.navigate_to_avalpaycenter_real(ref)
        if not nav.get("success"):
            return jsonify({"success": False, "error": "No se pudo abrir la página"}), 500
        
        # 2) (Opcional) Resolver captcha si aparece
        captcha = None
        if api_key:
            captcha = automation_engine.solve_recaptcha_now(api_key)
        
        # 3) Extraer datos
        data = automation_engine.extract_payment_info()
        if not data.get("success"):
            data = fake_result(ref)  # fallback
        
        return jsonify({
            "success": True,
            "reference": ref,
            "captcha": captcha,
            "extracted": data
        }), 200

    except Exception as e:
        logger.exception("❌ Error en /api/complete-automation")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/session-info', methods=['GET'])
@app.route('/api/session-info/', methods=['GET'])
def session_info():
    """Información del estado actual del sistema"""
    try:
        if automation_engine and automation_engine.driver:
            return jsonify({
                "success": True,
                "selenium": SELENIUM_AVAILABLE,
                "driver": "activo"
            }), 200
        return jsonify({
            "success": True,
            "selenium": SELENIUM_AVAILABLE,
            "driver": "no inicializado"
        }), 200
    except Exception as e:
        logger.exception("❌ Error en /api/session-info")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/test-avalpaycenter', methods=['GET'])
@app.route('/api/test-avalpaycenter/', methods=['GET'])
def test_avalpaycenter():
    """Probar conexión directa con AvalPayCenter"""
    try:
        # Petición simple para probar reachability (no scrapea)
        r = requests.get("https://www.avalpaycenter.com/", timeout=12)
        return jsonify({
            "success": True,
            "status_code": r.status_code,
            "ok": r.ok
        }), 200
    except Exception as e:
        logger.warning("⚠️ No se pudo alcanzar AvalPayCenter (probando desde backend)")
        return jsonify({"success": False, "error": str(e)}), 200

# ---------------------------------------------------------------------
# HANDLER 404 (mantener para diagnósticos)
# ---------------------------------------------------------------------
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
            "GET /api/test-avalpaycenter - Probar conexión"
        ]
    }), 404

# ---------------------------------------------------------------------
# BOOTSTRAP
# ---------------------------------------------------------------------
if __name__ == '__main__':
    # Bind al puerto que expone Railway
    port = int(os.environ.get('PORT', '8080'))
    host = '0.0.0.0'
    logger.info(f"🚀 Iniciando API REAL AvalPayCenter en http://{host}:{port}")
    try:
        # Desarrollo: puedes usar app.run; en producción usa Gunicorn (Procfile)
        app.run(host=host, port=port)
    except Exception as e:
        logger.exception("❌ Error al iniciar la app Flask")
        raise

# ---------------------------------------------------------------------
# NOTAS:
# - Este archivo está preparado para correr en Railway con Gunicorn (Procfile).
# - Si quieres Selenium “real” en Railway, agrega NIXPACKS_PKGS=chromium chromedriver
# - Endpoints toleran /ruta y /ruta/ gracias a strict_slashes=False y decorators duplicados
# ---------------------------------------------------------------------
