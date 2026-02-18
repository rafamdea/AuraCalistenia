# Aura Calistenia Web

Web con landing pública, panel admin y portal de alumnos.

## Variables de entorno (Render)

### Base de datos (Neon)
- `DATABASE_URL` = URL de conexión PostgreSQL de Neon.

### SMTP (correos de registro y recuperación)
- `AURA_SMTP_ENABLED` = `true`
- `AURA_SMTP_HOST` = `smtp.gmail.com`
- `AURA_SMTP_PORT` = `587` (recomendado con Gmail)
- `AURA_SMTP_USER` = tu correo Gmail completo
- `AURA_SMTP_PASS` = contraseña de aplicación de Gmail
- `AURA_SMTP_FROM` = nombre visible del remitente (ej: `Aura Calistenia`)
- `AURA_SMTP_ADMIN` = correo donde quieres recibir las notificaciones admin
- `AURA_SMTP_TLS` = `true`
- `AURA_SMTP_SSL` = `false`

Notas:
- Si usas puerto `465`, pon `AURA_SMTP_SSL=true`.
- Tras cambiar variables en Render, haz redeploy del servicio.

## Diagnóstico SMTP

En `Admin > Gestión de alumnos` aparece una tarjeta **Estado SMTP** con:
- estado actual (listo / incompleto / error / desactivado),
- host, puerto y seguridad,
- detalle técnico del último error de envío.

## Legal

Se añadió `legal.html` con:
- aviso legal,
- política de privacidad,
- política de cookies.

Revisa y personaliza esos textos con tus datos fiscales/legales reales antes de publicar en producción.
