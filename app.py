import os
import json
import requests
import io
import random
import smtplib
import ssl
from email.message import EmailMessage
import cloudinary
import cloudinary.uploader
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "diamant_secret_key_os_cloud_123"

# 🐘 CONFIGURACIÓN DE POSTGRESQL EXTERNA (Supabase)
DATABASE_URL = os.environ.get("DATABASE_URL")

OPENROUTER_API_KEY = os.environ.get("DIAMANTKEY", "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")

# 🔒 CONTRASEÑA ADMINISTRADOR PARA MANDAR LA UPDATE DESDE LA WEB
ADMIN_PASSWORD_UPDATE = "diamant_admin_os_2026"

# 📧 CONFIGURACIÓN SMTP (Gmail App Password)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER", "diamant.company1936@gmail.com")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

# 🌟 CONFIGURACIÓN DE CLOUDINARY
cloudinary.config(
    cloud_name="dwoaq0vf6",
    api_key="784588949973579",
    api_secret="VFZ6V7ZOQlw7vCe_iI80qnD_1Iw",
    secure=True
)

# Diccionario en memoria para códigos 2FA temporales
codigos_2fa_temporales = {}


def conectar_db(usar_dict=False):
    """Helper seguro para conectar a Supabase PostgreSQL con SSL"""
    if not DATABASE_URL:
        raise ValueError("Error crítico: La variable de entorno DATABASE_URL no está configurada en Render.")
    url_final = DATABASE_URL
    if "sslmode=" not in url_final:
        separador = "&" if "?" in url_final else "?"
        url_final = f"{url_final}{separador}sslmode=require"
    if usar_dict:
        return psycopg2.connect(url_final, cursor_factory=DictCursor)
    return psycopg2.connect(url_final)


def inicializar_base_datos():
    """Crea las tablas y columnas necesarias en PostgreSQL al arrancar"""
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()

        # Tabla aplicaciones con soporte para página web externa
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aplicaciones (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                version TEXT NOT NULL,
                descripcion TEXT,
                categoria TEXT,
                codigo_fuente TEXT,
                autor TEXT,
                url_descarga TEXT,
                pagina_web TEXT,
                fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('ALTER TABLE aplicaciones ADD COLUMN IF NOT EXISTS pagina_web TEXT')

        # Tabla usuarios para Diamant Account
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                correo_recuperacion TEXT
            )
        ''')

        # Tabla control de actualizaciones OTA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ota_version (
                id INTEGER PRIMARY KEY,
                version TEXT NOT NULL,
                url_zip TEXT NOT NULL
            )
        ''')

        cursor.execute('SELECT COUNT(*) FROM ota_version')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO ota_version (id, version, url_zip)
                VALUES (1, '1.0.0 bf3', 'https://diamant-cloud.onrender.com/update.zip')
            ''')

        conexion.commit()
        cursor.close()
        conexion.close()
        print("🐘 Base de datos PostgreSQL (Supabase) inicializada con éxito.")
    except Exception as e:
        print(f"❌ Error grave al inicializar la base de datos: {e}")


if DATABASE_URL:
    inicializar_base_datos()


def enviar_correo_smtp(destinatario, codigo_token):
    """Envía el token de verificación de 6 dígitos mediante Gmail SMTP"""
    if not SMTP_PASS:
        print("⚠️ Advertencia: SMTP_PASS no está configurado.")
        return False
    try:
        msg = EmailMessage()
        msg.set_content(f"Hola,\n\nTu código de verificación de seguridad para Diamant Account (@diamantaccount.com) es:\n\n{codigo_token}\n\nEste código expira en 120 segundos.\n\nAtentamente,\nDiamant OS Kernel Security")
        msg['Subject'] = "🔒 Código de Verificación - Diamant Account"
        msg['From'] = SMTP_USER
        msg['To'] = destinatario

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"❌ Error enviando correo SMTP: {e}")
        return False


# =====================================================================
# 🤖 BICONECTOR CLOUD: DIAMANT ASSISTANT v1.0.0
# =====================================================================

@app.route('/api/v1/assistant', methods=['POST'])
def diamant_assistant_v1():
    datos = request.json or {}
    query = datos.get('query', '').strip()
    usuario = datos.get('user', '').strip()

    if not usuario:
        return jsonify({"Reply": "🔒 Acceso denegado. Inicia sesión en Diamant Account.", "ActionCode": "NONE"}), 401

    if not query:
        return jsonify({"Reply": "¿En qué te ayudo en duix?", "ActionCode": "NONE"}), 200

    prompt_sistema = """
    Eres Diamant Assistant v1.0.0, el asistente oficial integrado en duix y Diamant UI 1.0.
    Responde de forma cercana, útil y concisa en español.
    Devuelve SIEMPRE un JSON puro con esta estructura exacta:
    {
        "Reply": "Tu respuesta para el usuario",
        "ActionCode": "CODIGO_ACCION"
    }
    Códigos de acción permitidos para ActionCode:
    - "NONE" (si solo es conversación o pregunta)
    - "OPEN_CALC" (si pide abrir la calculadora)
    - "OPEN_NOTEPAD" (si pide abrir notas o bloc de notas)
    - "OPEN_SETTINGS" (si pide abrir ajustes o configuración)
    - "OPEN_STORE" (si pide abrir Diamant Shop / tienda)
    """

    try:
        respuesta = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": [
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": f"[Usuario: {usuario}] {query}"}
                ],
                "response_format": {"type": "json_object"}
            },
            timeout=15
        )

        if respuesta.status_code == 200:
            contenido = respuesta.json()['choices'][0]['message']['content'].strip()
            if "```" in contenido:
                contenido = contenido.split("```")[1].replace("json", "", 1).split("```")[0].strip()
            parsed = json.loads(contenido)
            return jsonify({
                "Reply": parsed.get("Reply", "Listo."),
                "ActionCode": parsed.get("ActionCode", "NONE")
            }), 200
    except Exception as e:
        print(f"Error en Biconector IA: {e}")

    q = query.lower()
    if "calculadora" in q:
        return jsonify({"Reply": "Abriendo la calculadora en duix.", "ActionCode": "OPEN_CALC"}), 200
    if "notas" in q or "bloc" in q:
        return jsonify({"Reply": "Abriendo el bloc de notas.", "ActionCode": "OPEN_NOTEPAD"}), 200
    if "ajustes" in q or "configuracion" in q:
        return jsonify({"Reply": "Abriendo Ajustes del sistema.", "ActionCode": "OPEN_SETTINGS"}), 200

    return jsonify({"Reply": "Biconector conectado, pero la IA está ocupada. Intenta de nuevo en un segundo.", "ActionCode": "NONE"}), 200


# =====================================================================
# 🌐 SECCIÓN DEDICADA: ENDPOINTS PARA ACTUALIZACIONES OTA (DIAMANT OS)
# =====================================================================

@app.route('/version.txt', methods=['GET'])
def obtener_version_ota():
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT version FROM ota_version WHERE id = 1')
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()
        version = resultado[0] if resultado else "1.0.0 bf3"
        return Response(version, mimetype='text/plain')
    except Exception as e:
        return Response(f"Error leyendo version desde DB: {str(e)}", status=500, mimetype='text/plain')


@app.route('/set_version', methods=['POST'])
def cambiar_version_ota():
    nueva_version = request.form.get('version')
    if nueva_version:
        try:
            conexion = conectar_db()
            cursor = conexion.cursor()
            cursor.execute('UPDATE ota_version SET version = %s WHERE id = 1', (nueva_version.strip(),))
            conexion.commit()
            cursor.close()
            conexion.close()
            return jsonify({"status": "ok", "version_guardada": nueva_version}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Falta el parámetro 'version'"}), 400


@app.route('/update.zip', methods=['GET'])
def descargar_update_ota():
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT url_zip FROM ota_version WHERE id = 1')
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()
        if resultado and resultado[0] != "[https://diamant-cloud.onrender.com/](https://diamant-cloud.onrender.com/)":
            return redirect(resultado[0])
        return jsonify({"error": "El archivo de actualización no está configurado."}), 404
    except Exception as e:
        return jsonify({"error": f"Error recuperando OTA: {str(e)}"}), 500


# =====================================================================
# 📱 ENDPOINT DE ACTUALIZACIÓN DE APPS INTEGRADO A BASE DE DATOS
# =====================================================================

@app.route('/appactualizacion', methods=['GET'])
def app_actualizacion():
    id_app = request.args.get('app')
    if not id_app:
        return Response("error|Falta el parametro app", status=400, mimetype='text/plain')

    nombre_limpio = id_app.strip().lower()
    nombre_con_guiones = nombre_limpio.replace(" ", "_")

    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('''
            SELECT version, url_descarga FROM aplicaciones
            WHERE LOWER(nombre) = %s OR LOWER(nombre) = %s
            ORDER BY fecha_subida DESC LIMIT 1
        ''', (nombre_limpio, nombre_con_guiones))
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()

        if resultado:
            version_db = resultado[0]
            url_db = resultado[1] if resultado[1] else "[https://diamant-cloud.onrender.com/](https://diamant-cloud.onrender.com/)"
            return Response(f"{version_db}|{url_db}", mimetype='text/plain')
    except Exception as db_err:
        print(f"Error consultando la app en PostgreSQL: {db_err}")

    ecosistema_apps = {
        "bloc_notas": {"version": "1.2.0", "url": "[https://diamant-cloud.onrender.com/downloads/bloc_notas.zip](https://diamant-cloud.onrender.com/downloads/bloc_notas.zip)"},
        "calculadora": {"version": "1.0.5", "url": "[https://diamant-cloud.onrender.com/downloads/calculadora.zip](https://diamant-cloud.onrender.com/downloads/calculadora.zip)"},
        "diamant_store": {"version": "2.0.1", "url": "[https://diamant-cloud.onrender.com/downloads/store.zip](https://diamant-cloud.onrender.com/downloads/store.zip)"}
    }
    app_info = ecosistema_apps.get(nombre_limpio) or ecosistema_apps.get(nombre_con_guiones)
    if app_info:
        return Response(f"{app_info['version']}|{app_info['url']}", mimetype='text/plain')

    return Response("error|Aplicacion no registrada", status=404, mimetype='text/plain')


# =====================================================================
# 🔐 GESTIÓN CENTRALIZADA DIAMANT ACCOUNT & 2FA EN LA NUBE
# =====================================================================

@app.route('/api/diamant_account/check', methods=['POST'])
def check_diamant_account():
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    username_limpio = cuenta.replace('@diamantaccount.com', '') if cuenta.endswith('@diamantaccount.com') else cuenta

    if not username_limpio:
        return jsonify({"status": "invalid", "message": "Nombre de cuenta vacío"}), 400

    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT username FROM usuarios WHERE username = %s', (username_limpio,))
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()

        if resultado:
            return jsonify({
                "status": "exists",
                "cuenta_completa": f"{username_limpio}@diamantaccount.com",
                "message": "La cuenta existe. Proceder al login."
            }), 200
        return jsonify({
            "status": "not_found",
            "cuenta_completa": f"{username_limpio}@diamantaccount.com",
            "message": "La cuenta no existe."
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fallo de conexión DB: {str(e)}"}), 500


@app.route('/api/diamant_account/auth', methods=['POST'])
def auth_diamant_account():
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    password = datos.get('password', '')
    username_limpio = cuenta.replace('@diamantaccount.com', '') if '@diamantaccount.com' in cuenta else cuenta

    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT password, correo_recuperacion FROM usuarios WHERE username = %s', (username_limpio,))
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()

        if resultado and check_password_hash(resultado[0], password):
            correo_respaldo = resultado[1]
            if correo_respaldo:
                codigo_6_digitos = str(random.randint(100000, 999999))
                codigos_2fa_temporales[username_limpio] = codigo_6_digitos
                enviar_correo_smtp(correo_respaldo, codigo_6_digitos)

            return jsonify({
                "auth": True,
                "requires_2fa": bool(correo_respaldo),
                "username": username_limpio,
                "cuenta": f"{username_limpio}@diamantaccount.com",
                "correo_respaldo": correo_respaldo or "No asignado"
            }), 200

        return jsonify({"auth": False, "message": "Credenciales incorrectas para Diamant Account"}), 401
    except Exception as e:
        return jsonify({"auth": False, "message": f"Fallo de conexión DB: {str(e)}"}), 500


@app.route('/api/diamant_account/verify_2fa', methods=['POST'])
def verify_2fa_diamant_account():
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    codigo_ingresado = datos.get('codigo', '').strip()
    username_limpio = cuenta.replace('@diamantaccount.com', '') if '@diamantaccount.com' in cuenta else cuenta

    codigo_real = codigos_2fa_temporales.get(username_limpio)
    if codigo_real and codigo_real == codigo_ingresado:
        del codigos_2fa_temporales[username_limpio]
        return jsonify({"verified": True, "message": "¡Verificación 2FA completada con éxito!"}), 200

    return jsonify({"verified": False, "message": "Código de verificación inválido o expirado."}), 400


@app.route('/api/diamant_account/register', methods=['POST'])
def registrar_diamant_account():
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    password = datos.get('password', '')
    correo_respaldo = datos.get('correo_respaldo', '').strip()
    username_limpio = cuenta.replace('@diamantaccount.com', '') if '@diamantaccount.com' in cuenta else cuenta

    if not username_limpio or not password:
        return jsonify({"status": "error", "message": "Campos obligatorios incompletos"}), 400

    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        password_encriptada = generate_password_hash(password)
        cursor.execute('INSERT INTO usuarios (username, password, correo_recuperacion) VALUES (%s, %s, %s)',
                       (username_limpio, password_encriptada, correo_respaldo))
        conexion.commit()
        cursor.close()
        conexion.close()
        return jsonify({
            "status": "created",
            "cuenta": f"{username_limpio}@diamantaccount.com",
            "message": "¡Cuenta del Kernel creada con éxito en la nube!"
        }), 201
    except psycopg2.IntegrityError:
        return jsonify({"status": "error", "message": "El identificador de cuenta ya se encuentra ocupado."}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fallo de conexión: {str(e)}"}), 500


# =====================================================================
# 👥 PANELES VISUALES Y GESTIÓN WEB DE USUARIOS Y OTA
# =====================================================================

@app.route('/panel_cuentas', methods=['GET'])
def panel_cuentas():
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT username, correo_recuperacion FROM usuarios ORDER BY username ASC')
        lista_usuarios = cursor.fetchall()
        cursor.close()
        conexion.close()
    except Exception as e:
        return f"<h3>Error al cargar panel: {str(e)}</h3>"

    filas_tabla = ""
    for user in lista_usuarios:
        correo_rec = user[1] if user[1] else '<span style="color: #ecc94b;">⚠️ Sin correo asignado</span>'
        filas_tabla += f"<tr><td>👤 {user[0]}@diamantaccount.com</td><td>📧 {correo_rec}</td></tr>"

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Diamant OS - Panel de Usuarios</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #121824; color: #f3f4f6; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .container {{ background: #1a2333; padding: 35px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 550px; border: 1px solid #2d3d5a; }}
            h2 {{ color: #3b82f6; margin-top: 0; text-align: center; font-size: 24px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 14px; border-bottom: 1px solid #2d3d5a; text-align: left; }}
            th {{ background: #233047; color: #9ca3af; }}
            .btn-volver {{ display: block; text-align: center; padding: 12px; margin-top: 25px; background: #3b82f6; color: white; text-decoration: none; font-weight: bold; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>👥 Diamant Accounts Activos <span style="background:#2563eb; padding:3px 8px; border-radius:20px; font-size:12px;">{len(lista_usuarios)}</span></h2>
            <table>
                <thead><tr><th>Identidad Kernel</th><th>Correo de Respaldo</th></tr></thead>
                <tbody>{filas_tabla if filas_tabla else '<tr><td colspan="2" style="text-align:center;">No hay cuentas aún.</td></tr>'}</tbody>
            </table>
            <a href="/" class="btn-volver">Volver a Diamant Store</a>
        </div>
    </body>
    </html>
    '''


@app.route('/panel_update', methods=['GET'])
def panel_update():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Diamant OS - Panel de Actualizaciones OTA</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #f4f5f7; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); width: 400px; }
            h2 { color: #4285F4; text-align: center; }
            input, button { width: 100%; padding: 12px; margin: 8px 0 18px 0; border-radius: 8px; border: 1px solid #ccc; box-sizing: border-box; }
            button { background: #4285F4; color: white; font-weight: bold; cursor: pointer; border: none; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🚀 Lanzar Update de Diamant OS</h2>
            <form action="/subir_update" method="POST" enctype="multipart/form-data">
                <label>Nueva Versión (ej: 1.0.0 bf4):</label>
                <input type="text" name="nueva_version" placeholder="1.0.0 bf4" required>
                <label>Archivo de Actualización (update.zip):</label>
                <input type="file" name="archivo_zip" accept=".zip" required>
                <label>Clave de Desarrollador:</label>
                <input type="password" name="admin_key" placeholder="Contraseña de admin" required>
                <button type="submit">Publicar Actualización OTA</button>
            </form>
        </div>
    </body>
    </html>
    '''


@app.route('/subir_update', methods=['POST'])
def subir_update():
    version = request.form.get('nueva_version')
    clave = request.form.get('admin_key')
    archivo = request.files.get('archivo_zip')

    if clave != ADMIN_PASSWORD_UPDATE:
        return '<script>alert("❌ Clave de desarrollador incorrecta."); window.history.back();</script>'

    if not version or not archivo or archivo.filename == '':
        return '<script>alert("❌ Faltan datos o el archivo zip no es válido."); window.history.back();</script>'

    try:
        contenido_zip = archivo.read()
        archivo_simulado = io.BytesIO(contenido_zip)

        resultado_cloudinary = cloudinary.uploader.upload(
            archivo_simulado,
            folder="diamant_os_updates",
            resource_type="raw",
            public_id="update.zip",
            overwrite=True
        )
        url_zip_persistente = resultado_cloudinary['secure_url']

        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('''
            UPDATE ota_version
            SET version = %s, url_zip = %s
            WHERE id = 1
        ''', (version.strip(), url_zip_persistente))
        conexion.commit()
        cursor.close()
        conexion.close()

        return f'''
        <script>
            alert("✨ ¡Diamant OS Actualizado!\\n\\nNueva versión: {version}");
            window.location.href = "/";
        </script>
        '''
    except Exception as e:
        return f'<script>alert("⚠️ Error crítico: {str(e)}"); window.history.back();</script>'


# =====================================================================
# 🛒 DIAMANT SHOP: TIENDA, DETALLE DE APP Y GESTIÓN WEB
# =====================================================================

@app.route('/', methods=['GET'])
def pagina_web():
    try:
        conexion = conectar_db(usar_dict=True)
        cursor = conexion.cursor()
        cursor.execute('SELECT * FROM aplicaciones ORDER BY fecha_subida DESC')
        apps = cursor.fetchall()
        cursor.close()
        conexion.close()
    except Exception as e:
        apps = []
        print(f"Error cargando apps en página principal: {e}")

    usuario_logueado = session.get('usuario')
    return render_template('tienda.html', aplicaciones=apps, usuario=usuario_logueado)


@app.route('/app/<int:app_id>', methods=['GET'])
def detalle_app_web(app_id):
    try:
        conexion = conectar_db(usar_dict=True)
        cursor = conexion.cursor()
        cursor.execute('SELECT * FROM aplicaciones WHERE id = %s', (app_id,))
        app_data = cursor.fetchone()
        cursor.close()
        conexion.close()
    except Exception as e:
        return f"<h3>Error cargando aplicación: {str(e)}</h3>", 500

    if not app_data:
        return "<h3>Aplicación no encontrada en Diamant Shop.</h3>", 404

    descripcion = app_data['descripcion'] or "Sin descripción proporcionada."
    pagina_web_url = app_data['pagina_web'] or ""
    boton_web = f'<a href="{pagina_web_url}" target="_blank" class="btn btn-web">🌐 Visitar Página Oficial</a>' if pagina_web_url else ''

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{app_data['nombre']} - Diamant Shop</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }}
            .card {{ background: #1e293b; border-radius: 20px; padding: 35px; max-width: 680px; width: 100%; border: 1px solid #334155; box-shadow: 0 15px 35px rgba(0,0,0,0.4); }}
            .badge {{ background: #2563eb; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
            h1 {{ margin: 12px 0 6px 0; font-size: 28px; color: #38bdf8; }}
            .meta {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
            .desc-box {{ background: #0f172a; padding: 20px; border-radius: 14px; line-height: 1.6; color: #e2e8f0; border: 1px solid #1e293b; white-space: pre-wrap; }}
            .actions {{ display: flex; gap: 12px; margin-top: 28px; flex-wrap: wrap; }}
            .btn {{ padding: 12px 20px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 14px; }}
            .btn-dl {{ background: #10b981; color: white; }}
            .btn-web {{ background: #3b82f6; color: white; }}
            .btn-back {{ background: #334155; color: #cbd5e1; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">{app_data['categoria'] or 'General'}</span>
            <h1>{app_data['nombre']} <span style="font-size:16px; color:#94a3b8;">v{app_data['version']}</span></h1>
            <div class="meta">Desarrollado por <strong>@{app_data['autor']}</strong> • Publicado en Diamant Shop</div>
            <h3>📝 Acerca de esta aplicación</h3>
            <div class="desc-box">{descripcion}</div>
            <div class="actions">
                <a href="{app_data['url_descarga']}" class="btn btn-dl">⬇️ Descargar Código (.cs)</a>
                {boton_web}
                <a href="/" class="btn btn-back">← Volver a la Tienda</a>
            </div>
        </div>
    </body>
    </html>
    '''


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    accion = request.form.get('accion')

    if not username or not password:
        return '<script>alert("Campos vacíos."); window.history.back();</script>'

    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        if accion == "registro":
            try:
                password_encriptada = generate_password_hash(password)
                cursor.execute('INSERT INTO usuarios (username, password) VALUES (%s, %s)', (username, password_encriptada))
                conexion.commit()
                session['usuario'] = username
            except psycopg2.IntegrityError:
                cursor.close()
                conexion.close()
                return '<script>alert("El nombre de usuario ya existe."); window.history.back();</script>'
        else:
            cursor.execute('SELECT password FROM usuarios WHERE username = %s', (username,))
            resultado = cursor.fetchone()
            if resultado and check_password_hash(resultado[0], password):
                session['usuario'] = username
            else:
                cursor.close()
                conexion.close()
                return '<script>alert("Usuario o contraseña incorrectos."); window.history.back();</script>'
        cursor.close()
        conexion.close()
    except Exception as e:
        return f'<script>alert("Error del servidor en DB: {str(e)}"); window.history.back();</script>'

    return redirect(url_for('pagina_web'))


@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('pagina_web'))


@app.route('/subir', methods=['POST'])
def subir_app():
    if 'usuario' not in session:
        return redirect(url_for('pagina_web'))

    nombre = request.form.get('nombre')
    version = request.form.get('version')
    descripcion = request.form.get('descripcion', '').strip()
    categoria = request.form.get('categoria')
    pagina_web_app = request.form.get('pagina_web', '').strip()
    codigo = request.form.get('codigo_fuente')
    autor = session['usuario']

    if pagina_web_app and not pagina_web_app.startswith(('http://', 'https://')):
        pagina_web_app = 'https://' + pagina_web_app

    prompt_ia = f"""
    Eres un compilador estricto de C# para Diamant OS. Tu única tarea es validar si el código tiene errores de sintaxis reales.
    Responde OBLIGATORIAMENTE en este formato JSON puro:
    {{
        "valido": false,
        "error_mensaje": "Detalle del error"
    }} o {{
        "valido": true,
        "error_mensaje": ""
    }}
    Código C# a evaluar:
    {codigo}
    """

    pasa_la_ia = False
    try:
        url_api = "[https://openrouter.ai/api/v1/chat/completions](https://openrouter.ai/api/v1/chat/completions)"
        encabezados = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        cuerpo_peticion = {
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": prompt_ia}],
            "response_format": {"type": "json_object"}
        }

        respuesta = requests.post(url_api, headers=encabezados, json=cuerpo_peticion, timeout=12)
        if respuesta.status_code == 200:
            datos_ia = respuesta.json()
            contenido_respuesta = datos_ia['choices'][0]['message']['content'].strip()
            if "```" in contenido_respuesta:
                contenido_respuesta = contenido_respuesta.split("```")[1]
                if contenido_respuesta.startswith("json"):
                    contenido_respuesta = contenido_respuesta[4:]
                contenido_respuesta = contenido_respuesta.split("```")[0].strip()

            resultado_revision = json.loads(contenido_respuesta)
            if resultado_revision.get("valido") == False:
                error_formateado = resultado_revision.get("error_mensaje", "Error de sintaxis.").replace('"', '\\"').replace('\n', '\\n')
                return f'''
                <script>
                    alert("⚠️ Diamant OS Cloud Reviewer - Error:\\n\\n{error_formateado}");
                    window.history.back();
                </script>
                '''
            else:
                pasa_la_ia = True
        else:
            pasa_la_ia = True
    except Exception as e:
        pasa_la_ia = True

    if pasa_la_ia and nombre and version and codigo:
        url_descarga_final = ""
        try:
            nombre_archivo_cs = f"{nombre.lower().replace(' ', '_')}.cs"
            archivo_simulado = io.BytesIO(codigo.encode('utf-8'))
            resultado = cloudinary.uploader.upload(
                archivo_simulado,
                folder="diamant_store_uploads",
                resource_type="raw",
                public_id=nombre_archivo_cs,
                overwrite=True
            )
            url_descarga_final = resultado['secure_url']
        except Exception as storage_err:
            url_descarga_final = f"error: {str(storage_err)}"

        try:
            conexion = conectar_db()
            cursor = conexion.cursor()
            cursor.execute('''
                INSERT INTO aplicaciones (nombre, version, descripcion, categoria, codigo_fuente, autor, url_descarga, pagina_web)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (nombre, version, descripcion, categoria, codigo, autor, url_descarga_final, pagina_web_app))
            conexion.commit()
            cursor.close()
            conexion.close()
            return redirect(url_for('pagina_web'))
        except Exception as e:
            return f"<h3>Error al guardar la app: {str(e)}</h3>"

    return '<script>alert("❌ Error: Campos obligatorios vacíos."); window.history.back();</script>'


@app.route('/eliminar/<int:app_id>')
def eliminar_app(app_id):
    if 'usuario' not in session:
        return redirect(url_for('pagina_web'))
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT autor FROM aplicaciones WHERE id = %s', (app_id,))
        resultado = cursor.fetchone()
        if resultado and resultado[0] == session['usuario']:
            cursor.execute('DELETE FROM aplicaciones WHERE id = %s', (app_id,))
            conexion.commit()
        cursor.close()
        conexion.close()
    except Exception as e:
        print(f"Error al eliminar la app: {e}")
    return redirect(url_for('pagina_web'))


@app.route('/api/apps', methods=['GET'])
def obtener_apps():
    try:
        conexion = conectar_db(usar_dict=True)
        cursor = conexion.cursor()
        cursor.execute('SELECT id, nombre, version, descripcion, categoria, autor, url_descarga, pagina_web, fecha_subida FROM aplicaciones ORDER BY fecha_subida DESC')
        apps = [dict(fila) for fila in cursor.fetchall()]
        cursor.close()
        conexion.close()
        return jsonify(apps)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/apps/<int:app_id>', methods=['GET'])
def obtener_detalle_app_api(app_id):
    try:
        conexion = conectar_db(usar_dict=True)
        cursor = conexion.cursor()
        cursor.execute('SELECT id, nombre, version, descripcion, categoria, autor, url_descarga, pagina_web, fecha_subida FROM aplicaciones WHERE id = %s', (app_id,))
        fila = cursor.fetchone()
        cursor.close()
        conexion.close()
        if fila:
            return jsonify(dict(fila))
        return jsonify({"error": "App no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/apps/<int:app_id>/codigo', methods=['GET'])
def obtener_codigo_app(app_id):
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT codigo_fuente, url_descarga FROM aplicaciones WHERE id = %s', (app_id,))
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()
        if resultado:
            return jsonify({
                "codigo": resultado[0],
                "url_descarga": resultado[1]
            })
        return jsonify({"error": "App no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    inicializar_base_datos()
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
