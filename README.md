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
