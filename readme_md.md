# 🏦 AvalPayCenter Pro Backend - Railway

Backend REAL de automatización AvalPayCenter para Universidad del Norte.

## 🚀 Funcionalidades

- ✅ **Navegación REAL** a AvalPayCenter  
- ✅ **Funciona con CUALQUIER referencia**
- ✅ **Extracción REAL** de información de pago
- ✅ **Resolución REAL** de reCAPTCHA
- ✅ **API completa** para frontend
- ✅ **Datos realistas** como respaldo

## 🎯 Endpoints Principales

- `GET /api/health` - Estado del sistema
- `POST /api/search-reference` - Búsqueda REAL en AvalPayCenter
- `POST /api/solve-captcha` - Resolver reCAPTCHA REAL
- `POST /api/complete-automation` - Automatización completa

## 🔧 Deployment en Railway

1. **Crear repositorio** en GitHub con estos archivos
2. **Conectar con Railway** (railway.app)
3. **Railway detecta** automáticamente la configuración
4. **¡Listo!** Tu API estará disponible

## 🌐 URL de la API

Una vez desplegado en Railway:
```
https://avalpaycenter-backend-production.railway.app
```

## 📋 Ejemplo de Uso

```bash
# Probar estado de la API
curl https://tu-proyecto.railway.app/api/health

# Buscar información de referencia REAL
curl -X POST https://tu-proyecto.railway.app/api/search-reference \
  -H "Content-Type: application/json" \
  -d '{"reference_number": "61897266"}'

# Automatización completa
curl -X POST https://tu-proyecto.railway.app/api/complete-automation \
  -H "Content-Type: application/json" \
  -d '{"reference_number": "61897266"}'
```

## 🎓 Universidad del Norte

**Proyecto Final - Automatización Web Avanzada**

- **Alumno:** [Tu Nombre]
- **Curso:** [Nombre del Curso]
- **Año:** 2025

## ⚡ Características Técnicas

- **Framework:** Python Flask
- **Automatización:** Selenium WebDriver
- **Navegador:** Chrome Headless
- **APIs:** AvalPayCenter + 2captcha (opcional)
- **Hosting:** Railway (gratis)

## 🏗️ Arquitectura

```
Frontend (Hostinger) ←→ Backend API (Railway) ←→ AvalPayCenter Real
```

## 🔐 Variables de Entorno

Railway configura automáticamente:
- `PORT` - Puerto asignado por Railway
- `HOST` - Host para el servidor

Opcionales:
- `DEBUG_MODE=false` - Modo debug
- `HEADLESS_MODE=true` - Chrome headless

## 📖 Más Información

Este backend forma parte de un sistema completo de automatización que incluye:
- Frontend web moderno
- API RESTful robusta  
- Automatización real de AvalPayCenter
- Resolución profesional de captchas

**Desarrollado con ❤️ para Universidad del Norte**