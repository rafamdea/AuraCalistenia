# AuraCalistenia Web

Web con landing pública, panel admin y portal de alumnos.

## Variables de entorno (Render)

### Base de datos (Neon)
- `DATABASE_URL` = URL de conexión PostgreSQL de Neon.
- `AURA_REQUIRE_DB` = `true` para modo estricto (si Neon falla o falta, la app no guarda en JSON local).

### Media/CDN (opcional)
- `AURA_MEDIA_BASE_URL` = base pública para servir vídeos externos manteniendo las rutas actuales.
- Ejemplo: si subes `FOTOS/back-lever.mp4` a `https://cdn.tudominio.com/FOTOS/back-lever.mp4`, define `AURA_MEDIA_BASE_URL=https://cdn.tudominio.com`.
- Afecta a los vídeos públicos configurados con rutas relativas como `FOTOS/...` o `progresion-pino/...`.

### SMTP (correos de registro y recuperación)
- Mínimas (Gmail):
  - `AURA_SMTP_USER` = tu correo Gmail completo
  - `AURA_SMTP_PASS` = contraseña de aplicación de Gmail
- Recomendadas:
  - `AURA_SMTP_HOST` = `smtp.gmail.com`
  - `AURA_SMTP_PORT` = `587`
  - `AURA_SMTP_TLS` = `true`
  - `AURA_SMTP_SSL` = `false`
  - `AURA_SMTP_FROM` = nombre visible del remitente (ej: `AuraCalistenia`)
  - `AURA_SMTP_ADMIN` = correo para notificaciones admin
  - `AURA_SMTP_ENABLED` = `true` (si no la defines, se activa automáticamente si hay host+user+pass)

Compatibilidad:
- También acepta aliases: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_TLS`, `SMTP_SSL`, `SMTP_ENABLED`.
- También detecta variantes comunes como `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_*`, `EMAIL_*`, `GMAIL_APP_PASSWORD` y keys en minúsculas.

Notas:
- Si usas puerto `465`, pon `AURA_SMTP_SSL=true`.
- Tras cambiar variables en Render, haz redeploy del servicio.
- En producción, activa `AURA_REQUIRE_DB=true` para evitar perder cambios por fallback local temporal.

## Diagnóstico SMTP

En `Admin > Gestión de alumnos` aparece una tarjeta **Estado SMTP** con:
- estado actual (listo / incompleto / error / desactivado),
- host, puerto y seguridad,
- detalle técnico del último error de envío.
- botón `Probar SMTP` para enviar un email de prueba.

## Legal

Se añadió `legal.html` con:
- aviso legal,
- política de privacidad,
- política de cookies.

Revisa y personaliza esos textos con tus datos fiscales/legales reales antes de publicar en producción.

## Renovación de septiembre de 2026

La portada usa `landing.css` y `landing.js`, independientes del código del portal.
Presenta el entrenamiento personalizado de pago; precio y condiciones se acuerdan
con el entrenador. Conserva el formulario `/apply` y el acceso `/portal`.
Las referencias exactas a la antigua promoción se actualizan al leer el contenido,
también si está guardado en Neon. Los textos personalizados se mantienen.
Los eventos antiguos dejan de mostrarse en la portada; siguen disponibles en administración.

Las imágenes optimizadas y las miniaturas están en `assets/`. Los vídeos se cargan
al pulsar, y las respuestas de vídeo soportan rangos de bytes. El HTML se comprime
si el navegador admite gzip. Las consultas reutilizan una conexión PostgreSQL por
petición; se cierra al terminar y no se comparte entre usuarios. El acceso anónimo
al portal no lee los alumnos. Las solicitudes se guardan antes de enviar el correo
en segundo plano; los fallos SMTP se consultan en administración.

Comprobaciones locales: `python3 -m unittest discover -s tests -v`.
Arranque: `python3 app.py` (puerto 8000 por defecto). Al desplegar, incluir `assets/`,
`landing.css`, `landing.js` y las plantillas actualizadas junto con `app.py` y los
archivos existentes. No reemplazar los datos de alumnos.

Las pruebas locales no miden el arranque en frío del alojamiento ni la latencia
real entre Render y Neon; esas mediciones requieren comprobar el despliegue.
