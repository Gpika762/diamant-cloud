import os
import json
import requests  # Necesario para llamar a la API de OpenRouter
import io        # Requerido para codificar los strings a bytes en memoria
import cloudinary
import cloudinary.uploader  # 🌟 El motor de Cloudinary
import psycopg2              # 🐘 Reemplazamos sqlite3 por PostgreSQL para persistencia real
from psycopg2.extras import DictCursor
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, send_from_directory, Response
from werkzeug.security import generate_password_hash, check_password_hash # Para encriptar contraseñas

app = Flask(__name__)
app.secret_key = "diamant_secret_key_os_cloud_123"

# 🐘 CONFIGURACIÓN DE POSTGRESQL EXTERNA (Neon.tech, Supabase, etc.)
# En producción, lee DATABASE_URL desde el entorno de Render de forma estricta.
DATABASE_URL = os.environ.get("DATABASE_URL")

OPENROUTER_API_KEY = os.environ.get("DIAMANTKEY", "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")

# 🔒 CONTRASENIA ADMINISTRADOR PARA MANDAR LA UPDATE DESDE LA WEB
ADMIN_PASSWORD_UPDATE = "diamant_admin_os_2026"

# 🌟 CONFIGURACIÓN DE CLOUDINARY
cloudinary.config( 
    cloud_name = "dwoaq0vf6", 
    api_key = "784588949973579", 
    api_secret = "VFZ6V7ZOQlw7vCe_iI80qnD_1Iw",
    secure = True
)

def conectar_db():
    """Helper seguro para conectar a la base de datos controlando la ausencia de credenciales"""
    if not DATABASE_URL:
        raise ValueError("Error crítico: La variable de entorno DATABASE_URL no está configurada en Render.")
    return psycopg2.connect(DATABASE_URL)

def inicializar_base_datos():
    """Crea las tablas en PostgreSQL si no existen utilizando sintaxis compatible"""
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        
        # Tabla aplicaciones modificada a sintaxis PostgreSQL (SERIAL en vez de AUTOINCREMENT)
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
                fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla usuarios para Diamant Account
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                correo_recuperacion TEXT
            )
        ''')
        
        # 📝 TABLA EXTRA: Para guardar la versión del OS y la URL del zip de forma persistente
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ota_version (
                id INTEGER PRIMARY KEY,
                version TEXT NOT NULL,
                url_zip TEXT NOT NULL
            )
        ''')
        
        # Insertar versión por defecto si la tabla de control OTA está vacía
        cursor.execute('SELECT COUNT(*) FROM ota_version')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO ota_version (id, version, url_zip) 
                VALUES (1, '1.0.0 bf3', 'https://diamant-cloud.onrender.com/')
            ''')

        conexion.commit()
        cursor.close()
        conexion.close()
        print("🐘 Base de datos PostgreSQL inicializada con éxito.")
    except Exception as e:
        print(f"❌ Error grave al inicializar la base de datos: {e}")


# =====================================================================
# 🌐 SECCIÓN DEDICADA: ENDPOINTS PARA ACTUALIZACIONES OTA (DIAMANT OS)
# =====================================================================

@app.route('/version.txt', methods=['GET'])
def obtener_version_ota():
    """Devuelve la versión actual del OS directo desde PostgreSQL (Persistente)"""
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
    """Ruta útil para cambiar rápidamente la versión en la base de datos externa"""
    nueva_version = request.form.get('version')
    if nueva_version:
        try:
            conexion = conectar_db()
            cursor = conexion.cursor()
            # 🔧 CORREGIDO: Se cambió '?' por '%s' para compatibilidad estricta con psycopg2
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
    """Redirecciona al binario update.zip real alojado permanentemente en Cloudinary"""
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT url_zip FROM ota_version WHERE id = 1')
        resultado = cursor.fetchone()
        cursor.close()
        conexion.close()
        
        if resultado and resultado[0] != "https://diamant-cloud.onrender.com/":
            # Redireccionamos el cliente C# directamente a la descarga segura de Cloudinary
            return redirect(resultado[0])
            
        return jsonify({"error": "El archivo de actualización no está configurado en el almacenamiento externo."}), 404
    except Exception as e:
        return jsonify({"error": f"Error recuperando OTA de almacenamiento: {str(e)}"}), 500


# =====================================================================
# 📱 REQUERIMIENTO 1: ENDPOINT DE ACTUALIZACIÓN DE APPS INTEGRADO A BASE DE DATOS
# =====================================================================

@app.route('/appactualizacion', methods=['GET'])
def app_actualizacion():
    """
    Ruta optimizada para C#. Consulta la base de datos PostgreSQL externa.
    """
    id_app = request.args.get('app')
    if not id_app:
        return Response("error|Falta el parametro app", status=400, mimetype='text/plain')
    
    nombre_limpio = id_app.strip().lower()
    nombre_con_guiones = nombre_limpio.replace(" ", "_")

    # 1. Intentar buscar en PostgreSQL externa
    try:
        conexion = conectar_db()
        cursor = conexion.cursor()
        
        # Buscamos ignorando mayúsculas/minúsculas empleando la función LOWER nativa
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
            url_db = resultado[1] if resultado[1] else "https://diamant-cloud.onrender.com/"
            return Response(f"{version_db}|{url_db}", mimetype='text/plain')

    except Exception as db_err:
        print(f"Error consultando la app en PostgreSQL: {db_err}")

    # 2. Diccionario de Respaldo (Ecosistema base estático)
    ecosistema_apps = {
        "bloc_notas": {
            "version": "1.2.0",
            "url": "https://diamant-cloud.onrender.com/downloads/bloc_notas.zip"
        },
        "calculadora": {
            "version": "1.0.5",
            "url": "https://diamant-cloud.onrender.com/downloads/calculadora.zip"
        },
        "diamant_store": {
            "version": "2.0.1",
            "url": "https://diamant-cloud.onrender.com/downloads/store.zip"
        }
    }
    
    app_info = ecosistema_apps.get(nombre_limpio) or ecosistema_apps.get(nombre_con_guiones)
    
    if app_info:
        respuesta_plana = f"{app_info['version']}|{app_info['url']}"
        return Response(respuesta_plana, mimetype='text/plain')
    
    return Response("error|Aplicacion no registrada en el ecosistema Kernel ni en la Nube", status=404, mimetype='text/plain')


# =====================================================================
# 🔐 REQUERIMIENTO 2: GESTIÓN CENTRALIZADA DIAMANT ACCOUNT EN LA NUBE
# =====================================================================

@app.route('/api/diamant_account/check', methods=['POST'])
def check_diamant_account():
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    
    if not cuenta.endswith('@diamantaccount.com'):
        username_limpio = cuenta
    else:
        username_limpio = cuenta.replace('@diamantaccount.com', '')
        
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
        else:
            return jsonify({
                "status": "not_found", 
                "cuenta_completa": f"{username_limpio}@diamantaccount.com",
                "message": "La cuenta no existe. El telefono puede ofrecer registrarla."
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
            return jsonify({
                "auth": True,
                "username": username_limpio,
                "cuenta": f"{username_limpio}@diamantaccount.com",
                "correo_respaldo": resultado[1] or "No asignado"
            }), 200
            
        return jsonify({"auth": False, "message": "Credenciales incorrectas para Diamant Account"}), 401
    except Exception as e:
        return jsonify({"auth": False, "message": f"Fallo de conexión DB: {str(e)}"}), 500


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
# 👥 PANEL VISUAL DE ADMINISTRACIÓN DE CUENTAS DEL KERNEL
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
        filas_tabla += f"""
        <tr>
            <td>👤 {user[0]}@diamantaccount.com</td>
            <td>📧 {correo_rec}</td>
        </tr>
        """
        
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Diamant OS - Panel de Usuarios</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #121824; color: #f3f4f6; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .container {{ background: #1a2333; padding: 35px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); width: 550px; border: 1px solid #2d3d5a; }}
            h2 {{ color: #3b82f6; margin-top: 0; text-align: center; font-size: 24px; letter-spacing: 0.5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; text-align: left; }}
            th, td {{ padding: 14px; border-bottom: 1px solid #2d3d5a; font-size: 14px; }}
            th {{ background: #233047; color: #9ca3af; font-weight: 600; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px; }}
            tr:hover {{ background: #222e44; }}
            .btn-volver {{ display: inline-block; width: 100%; text-align: center; padding: 12px; margin-top: 25px; background: #3b82f6; color: white; text-decoration: none; font-weight: bold; border-radius: 8px; font-size: 14px; box-sizing: border-box; transition: background 0.2s; }}
            .btn-volver:hover {{ background: #2563eb; }}
            .count-badge {{ background: #2563eb; color: white; padding: 3px 8px; border-radius: 20px; font-size: 12px; margin-left: 8px; vertical-align: middle; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>👥 Diamant Accounts Activos <span class="count-badge">{len(lista_usuarios)}</span></h2>
            <table>
                <thead>
                    <tr>
                        <th>Identidad Kernel</th>
                        <th>Correo de Respaldo</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_tabla if filas_tabla else '<tr><td colspan="2" style="text-align:center; color:#6b7280;">No hay cuentas vinculadas en la nube aún.</td></tr>'}
                </tbody>
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
            h2 { color: #4285F4; margin-top: 0; text-align: center; }
            label { font-weight: 600; color: #333; font-size: 14px; }
            input, button { width: 100%; padding: 12px; margin: 8px 0 18px 0; border-radius: 8px; border: 1px solid #ccc; box-sizing: border-box; font-size: 14px; }
            button { background: #4285F4; color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 5px; transition: background 0.2s; }
            button:hover { background: #2b72e2; }
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
    """Sube el binario update.zip de forma segura a Cloudinary y registra la metadata en Postgres"""
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
        # 🔧 CORREGIDO: Sintaxis %s adaptada correctamente para PostgreSQL
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
            alert("✨ ¡Diamant OS Actualizado Eternamente!\\n\\nNueva versión activa: {version}\\nEl paquete OTA se distribuyó en Cloudinary de forma persistente.");
            window.location.href = "/";
        </script>
        '''
    except Exception as e:
        return f'<script>alert("⚠️ Error crítico al almacenar los ficheros OTA: {str(e)}"); window.history.back();</script>'


@app.route('/api/apps', methods=['GET'])
def obtener_apps():
    try:
        conexion = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
        cursor = conexion.cursor()
        cursor.execute('SELECT id, nombre, version, descripcion, categoria, autor, url_descarga, fecha_subida FROM aplicaciones ORDER BY fecha_subida DESC')
        apps = [dict(fila) for fila in cursor.fetchall()]
        cursor.close()
        conexion.close()
        return jsonify(apps)
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


@app.route('/', methods=['GET'])
def pagina_web():
    try:
        conexion = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
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


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    accion = request.form.get('accion')
    
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
                pass 
        else:
            cursor.execute('SELECT password FROM usuarios WHERE username = %s', (username,))
            resultado = cursor.fetchone()
            if resultado and check_password_hash(resultado[0], password):
                session['usuario'] = username
                
        cursor.close()
        conexion.close()
    except Exception as e:
        print(f"Fallo de login en DB: {e}")
        
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
    descripcion = request.form.get('descripcion')
    categoria = request.form.get('categoria')
    codigo = request.form.get('codigo_fuente')
    autor = session['usuario']

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
        url_api = "https://openrouter.ai/api/v1/chat/completions"
        encabezados = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        cuerpo_peticion = {
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": prompt_ia}],
            "response_format": { "type": "json_object" }
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
                    alert("⚠️ Diamant OS Cloud Reviewer - Error de Compilación:\\n\\n{error_formateado}");
                    window.history.back();
                </script>
                '''
            else:
                pasa_la_ia = True
        else:
            pasa_la_ia = True  
            
    except Exception as e:
        print(f"Excepción en la validación por IA: {e}")
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
                INSERT INTO aplicaciones (nombre, version, descripcion, categoria, codigo_fuente, autor, url_descarga)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (nombre, version, descripcion, categoria, codigo, autor, url_descarga_final))
            conexion.commit()
            cursor.close()
            conexion.close()
            return redirect(url_for('pagina_web'))
        except Exception as e:
            return f"<h3>Error al guardar la app en base de datos: {str(e)}</h3>"

    return '''
    <script>
        alert("❌ Error: Los campos Nombre, Versión o Código no pueden estar vacíos.");
        window.history.back();
    </script>
    '''


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


if __name__ == '__main__':
    inicializar_base_datos()
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
