# 📋 Guía de Instalación — Digest Tributario Chile
## Para usuarios sin experiencia técnica

---

## ¿Qué necesitas para que esto funcione?

| Qué | Para qué | Costo |
|-----|----------|-------|
| Una cuenta **GitHub** | Guardar el código y que se ejecute automáticamente | Gratis |
| Una clave **Anthropic (Claude AI)** | Para que la IA resuma los documentos | ~USD 5/mes según uso |
| Una cuenta **Gmail** con App Password | Para enviar los reportes por email | Gratis |

---

## PASO 1 — Crear cuenta en GitHub (5 minutos)

1. Ve a **https://github.com** en tu navegador
2. Haz clic en **"Sign up"** (esquina superior derecha)
3. Ingresa tu email, crea una contraseña y un nombre de usuario
4. Verifica tu email cuando te llegue el mensaje
5. Elige el plan **Free** (gratuito)

---

## PASO 2 — Subir el proyecto a GitHub (10 minutos)

1. Una vez con tu cuenta creada, haz clic en el botón verde **"New"** 
   (o ve a https://github.com/new)
2. En **"Repository name"** escribe: `digest-tributario`
3. Asegúrate de que esté marcado como **"Private"** (privado)
4. Haz clic en **"Create repository"**
5. En la página que aparece, busca la opción **"uploading an existing file"**
6. Descomprime el archivo `digest-tributario.zip` que descargaste
7. Arrastra TODOS los archivos de la carpeta descomprimida al navegador
8. Haz clic en **"Commit changes"** (botón verde)

---

## PASO 3 — Obtener clave API de Claude/Anthropic (5 minutos)

1. Ve a **https://console.anthropic.com**
2. Crea una cuenta con tu email
3. Una vez dentro, haz clic en **"API Keys"** en el menú izquierdo
4. Haz clic en **"Create Key"**
5. Copia la clave que aparece (empieza con `sk-ant-...`)
   ⚠️ **Guárdala en un lugar seguro, solo aparece una vez**
6. Agrega créditos: ve a "Billing" → "Add credits" → agrega USD $10
   (esto dura varios meses con el uso de este sistema)

---

## PASO 4 — Crear App Password en Gmail (5 minutos)

> ⚠️ Necesitas tener activada la **Verificación en 2 pasos** en tu cuenta Gmail

1. Ve a **https://myaccount.google.com/security**
2. Busca **"Verificación en 2 pasos"** y actívala si no lo está
3. Vuelve a la página de seguridad y busca **"Contraseñas de aplicaciones"**
   (si no aparece, busca en https://myaccount.google.com/apppasswords)
4. En **"Selecciona la aplicación"** elige **"Correo"**
5. En **"Selecciona el dispositivo"** elige **"Otro"** y escribe `digest-tributario`
6. Haz clic en **"Generar"**
7. Copia la contraseña de 16 caracteres que aparece (ej: `abcd efgh ijkl mnop`)
   ⚠️ **Guárdala, solo aparece una vez**

---

## PASO 5 — Configurar las claves secretas en GitHub (5 minutos)

1. Ve a tu repositorio en GitHub (`https://github.com/TU_USUARIO/digest-tributario`)
2. Haz clic en **"Settings"** (configuración, arriba a la derecha del repo)
3. En el menú izquierdo, busca **"Secrets and variables"** → **"Actions"**
4. Haz clic en **"New repository secret"** y agrega estos 4 secretos, uno por uno:

| Nombre (exacto) | Valor |
|----------------|-------|
| `ANTHROPIC_API_KEY` | La clave que copiaste en el Paso 3 |
| `GMAIL_USER` | Tu email Gmail (ej: tucuenta@gmail.com) |
| `GMAIL_APP_PASSWORD` | La contraseña de 16 chars del Paso 4 |
| `RECIPIENTS` | gerardo.montes@gandarillas.cl |

---

## PASO 6 — Editar los destinatarios en config.yaml

1. En tu repositorio GitHub, busca el archivo `config.yaml`
2. Haz clic en el ícono del lápiz (editar) 
3. Busca la sección `recipients:` y edita con los emails reales:
```yaml
recipients:
  - gerardo.montes@gandarillas.cl
  - otro.correo@dominio.cl
```
4. Haz clic en **"Commit changes"** para guardar

---

## PASO 7 — Hacer una prueba manual (2 minutos)

1. En tu repositorio, haz clic en **"Actions"** (menú superior)
2. En la lista izquierda, haz clic en **"Digest Tributario Chile"**
3. Haz clic en el botón **"Run workflow"** → **"Run workflow"**
4. Espera 2-3 minutos y revisa si llegó el email a gerardo.montes@gandarillas.cl
5. También puedes ver los logs haciendo clic en la ejecución que apareció

---

## ¿A qué hora se ejecuta automáticamente?

El sistema está configurado para ejecutarse todos los días a las **01:00 AM hora Chile**.
Si no hay novedades en las fuentes, no enviará email (para no saturar el correo).

---

## ¿Qué pasa si algo falla?

- GitHub te enviará un email de alerta si la ejecución falla
- Puedes ver los logs detallados en la pestaña **"Actions"** de tu repositorio
- Los logs se guardan por 14 días

---

## Contacto para soporte

Si tienes problemas en algún paso, comparte el mensaje de error 
y te ayudo a resolverlo.
