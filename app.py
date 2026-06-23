import os
import sqlite3
import json
import requests  # Necesario para llamar a la API de OpenRouter
import io        # Requerido para codificar los strings a bytes en memoria
import cloudinary
import cloudinary.uploader  # 🌟 El motor de Cloudinary
from flask import Flask, jsonify, render_template, request, redirect, url_for, session, send_from_directory, Response
from werkzeug.security import generate_password_hash, check_password_hash # Para encriptar contraseñas

app = Flask(__name__)
app.secret_key = "diamant_secret_key_os_cloud_123"

DB_PATH = 'diamant_cloud.db'
UPDATES_DIR = 'updates'  # Carpeta donde guardarás el archivo update.zip en el servidor

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

def inicializar_base_datos():
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aplicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            version TEXT NOT NULL,
            descripcion TEXT,
            categoria TEXT,
            codigo_fuente TEXT,
            autor TEXT,
            url_descarga TEXT,
            fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 💾 TABLA ACTUALIZADA: Agregamos correo_recuperacion para el Diamant Account
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            correo_recuperacion TEXT
        )
    ''')
    conexion.commit()
    conexion.close()

    # Asegura que exista la carpeta para tus archivos de actualización física
    if not os.path.exists(UPDATES_DIR):
        os.makedirs(UPDATES_DIR)
        # Inicializamos con tu versión de desarrollo actual real
        with open(os.path.join(UPDATES_DIR, 'version.txt'), 'w') as f:
            f.write("1.0.0 bf3")


# =====================================================================
# 🌐 SECCIÓN DEDICADA: ENDPOINTS PARA ACTUALIZACIONES OTA (DIAMANT OS)
# =====================================================================

@app.route('/version.txt', methods=['GET'])
def obtener_version_ota():
    """Devuelve la versión actual del OS en texto plano limpio para el C#"""
    try:
        ruta_version = os.path.join(UPDATES_DIR, 'version.txt')
        if os.path.exists(ruta_version):
            with open(ruta_version, 'r') as f:
                version = f.read().strip()
            return Response(version, mimetype='text/plain')
        return Response("1.0.0 bf3", mimetype='text/plain')
    except Exception as e:
        return Response(f"Error leyendo version: {str(e)}", status=500, mimetype='text/plain')


@app.route('/set_version', methods=['POST'])
def cambiar_version_ota():
    """Ruta útil para que cambies la versión en el servidor de forma remota"""
    nueva_version = request.form.get('version')
    if nueva_version:
        try:
            ruta_version = os.path.join(UPDATES_DIR, 'version.txt')
            with open(ruta_version, 'w') as f:
                f.write(nueva_version.strip())
            return jsonify({"status": "ok", "version_guardada": nueva_version}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Falta el parámetro 'version'"}), 400


@app.route('/update.zip', methods=['GET'])
def descargar_update_ota():
    """Descarga el paquete físico real .zip que procesará tu AjustesControl en C#"""
    try:
        return send_from_directory(UPDATES_DIR, 'update.zip', as_attachment=True)
    except Exception as e:
        return jsonify({"error": "El archivo de actualización no está disponible en el servidor."}), 404


# =====================================================================
# 📱 REQUERIMIENTO 1: ENDPOINT DE ACTUALIZACIÓN DE APPS INDIVIDUALES
# =====================================================================

@app.route('/appactualizacion', methods=['GET'])
def app_actualizacion():
    """
    Ruta para que Diamant Store consulte la última versión estable de una app del ecosistema.
    Ejemplo de llamada: /appactualizacion?app=bloc_notas
    """
    id_app = request.args.get('app')
    if not id_app:
        return Response("error|Falta el parametro app", status=400, mimetype='text/plain')
    
    # Repositorio de la versión oficial del Ecosistema de aplicaciones
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
    
    app_info = ecosistema_apps.get(id_app.lower().strip())
    if app_info:
        respuesta_plana = f"{app_info['version']}|{app_info['url']}"
        return Response(respuesta_plana, mimetype='text/plain')
    
    return Response("error|Aplicacion no registrada en el ecosistema Kernel", status=404, mimetype='text/plain')


# =====================================================================
# 🔐 REQUERIMIENTO 2: GESTIÓN CENTRALIZADA DIAMANT ACCOUNT EN LA NUBE
# =====================================================================

@app.route('/api/diamant_account/check', methods=['POST'])
def check_diamant_account():
    """
    Ruta que el C# llamará en segundo plano al escribir el usuario.
    Verifica si la identidad @diamantaccount.com existe.
    """
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    
    if not cuenta.endswith('@diamantaccount.com'):
        username_limpio = cuenta
    else:
        username_limpio = cuenta.replace('@diamantaccount.com', '')
        
    if not username_limpio:
        return jsonify({"status": "invalid", "message": "Nombre de cuenta vacío"}), 400

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('SELECT username FROM usuarios WHERE username = ?', (username_limpio,))
    resultado = cursor.fetchone()
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


@app.route('/api/diamant_account/auth', methods=['POST'])
def auth_diamant_account():
    """
    Inicia sesión de forma remota desde el sistema operativo C#.
    Maneja contraseñas seguras mediante hashes.
    """
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    password = datos.get('password', '')
    
    username_limpio = cuenta.replace('@diamantaccount.com', '') if '@diamantaccount.com' in cuenta else cuenta

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('SELECT password, correo_recuperacion FROM usuarios WHERE username = ?', (username_limpio,))
    resultado = cursor.fetchone()
    conexion.close()

    if resultado and check_password_hash(resultado[0], password):
        return jsonify({
            "auth": True,
            "username": username_limpio,
            "cuenta": f"{username_limpio}@diamantaccount.com",
            "correo_respaldo": resultado[1] or "No asignado"
        }), 200
        
    return jsonify({"auth": False, "message": "Credenciales incorrectas para Diamant Account"}), 401


@app.route('/api/diamant_account/register', methods=['POST'])
def registrar_diamant_account():
    """
    Crea dinámicamente un nuevo Diamant Account vinculándole un correo real de recuperación.
    """
    datos = request.json or {}
    cuenta = datos.get('cuenta', '').strip().lower()
    password = datos.get('password', '')
    correo_respaldo = datos.get('correo_respaldo', '').strip()

    username_limpio = cuenta.replace('@diamantaccount.com', '') if '@diamantaccount.com' in cuenta else cuenta

    if not username_limpio or not password:
        return jsonify({"status": "error", "message": "Campos obligatorios incompletos"}), 400

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    try:
        password_encriptada = generate_password_hash(password)
        cursor.execute('INSERT INTO usuarios (username, password, correo_recuperacion) VALUES (?, ?, ?)', 
                       (username_limpio, password_encriptada, correo_respaldo))
        conexion.commit()
        exito = True
    except sqlite3.IntegrityError:
        exito = False
    finally:
        conexion.close()

    if exito:
        return jsonify({
            "status": "created",
            "cuenta": f"{username_limpio}@diamantaccount.com",
            "message": "¡Cuenta del Kernel creada con éxito en la nube!"
        }), 201
        
    return jsonify({"status": "error", "message": "El identificador de cuenta ya se encuentra ocupado."}), 409


# =====================================================================
# 👥 NUEVO: PANEL VISUAL DE ADMINISTRACIÓN DE CUENTAS DEL KERNEL
# =====================================================================

@app.route('/panel_cuentas', methods=['GET'])
def panel_cuentas():
    """Muestra una interfaz web estilizada para ver los Diamant Accounts registrados"""
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('SELECT username, correo_recuperacion FROM usuarios ORDER BY username ASC')
    lista_usuarios = cursor.fetchall()
    conexion.close()
    
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


# =====================================================================


@app.route('/panel_update', methods=['GET'])
def panel_update():
    """Muestra una página web con diseño minimalista para subir la actualización desde el navegador"""
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
    """Recibe el formulario, guarda el archivo .zip y reescribe la nueva versión en la nube"""
    version = request.form.get('nueva_version')
    clave = request.form.get('admin_key')
    archivo = request.files.get('archivo_zip')

    if clave != ADMIN_PASSWORD_UPDATE:
        return '<script>alert("❌ Clave de desarrollador incorrecta."); window.history.back();</script>'

    if not version or not archivo or archivo.filename == '':
        return '<script>alert("❌ Faltan datos o el archivo zip no es válido."); window.history.back();</script>'

    try:
        ruta_zip = os.path.join(UPDATES_DIR, 'update.zip')
        archivo.save(ruta_zip)

        ruta_version = os.path.join(UPDATES_DIR, 'version.txt')
        with open(ruta_version, 'w') as f:
            f.write(version.strip())

        return f'''
        <script>
            alert("✨ ¡Diamant OS Actualizado en la Nube!\\n\\nNueva versión activa: {version}\\nEl archivo update.zip se guardó correctamente.");
            window.location.href = "/";
        </script>
        '''
    except Exception as e:
        return f'<script>alert("⚠️ Error crítico al almacenar los ficheros: {str(e)}"); window.history.back();</script>'


@app.route('/api/apps', methods=['GET'])
def obtener_apps():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT id, nombre, version, descripcion, categoria, autor, url_descarga, fecha_subida FROM aplicaciones ORDER BY fecha_subida DESC')
    apps = [dict(fila) for fila in cursor.fetchall()]
    conexion.close()
    return jsonify(apps)


@app.route('/api/apps/<int:app_id>/codigo', methods=['GET'])
def obtener_codigo_app(app_id):
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('SELECT codigo_fuente, url_descarga FROM aplicaciones WHERE id = ?', (app_id,))
    resultado = cursor.fetchone()
    conexion.close()
    if resultado:
        return jsonify({
            "codigo": resultado[0],
            "url_descarga": resultado[1]
        })
    return jsonify({"error": "App no encontrada"}), 404


@app.route('/', methods=['GET'])
def pagina_web():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM aplicaciones ORDER BY fecha_subida DESC')
    apps = cursor.fetchall()
    conexion.close()
    
    usuario_logueado = session.get('usuario')
    return render_template('tienda.html', aplicaciones=apps, usuario=usuario_logueado)


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    accion = request.form.get('accion')
    
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    if accion == "registro":
        try:
            password_encriptada = generate_password_hash(password)
            cursor.execute('INSERT INTO usuarios (username, password) VALUES (?, ?)', (username, password_encriptada))
            conexion.commit()
            session['usuario'] = username
        except sqlite3.IntegrityError:
            pass 
    else:
        cursor.execute('SELECT password FROM usuarios WHERE username = ?', (username,))
        resultado = cursor.fetchone()
        if resultado and check_password_hash(resultado[0], password):
            session['usuario'] = username
            
    conexion.close()
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
    Eres un compilador estricto de C# para Diamant OS. Tu única tarea es validar si el código tiene errores de sintaxis reales (como llaves sin cerrar, falta de puntos y coma, falta de la palabra 'class', variables no declaradas o bloques de bucles mal formados).
    
    NO intentes corregir el código. Si falta un solo punto y coma o una llave, debes marcarlo como inválido.

    Código C# a evaluar:
    {codigo}
    
    Responde OBLIGATORIAMENTE en este formato JSON puro, sin decoraciones de markdown ni texto extra:
    {{
        "valido": false,
        "error_mensaje": "Detalle del error aquí (línea y qué falta)"
    }}
    o si está 100% perfecto:
    {{
        "valido": true,
        "error_mensaje": ""
    }}
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
            print(f"Error de API OpenRouter: Código {respuesta.status_code}")
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
            print(f"--- ERROR CRÍTICO CLOUDINARY ---: {storage_err}")
            url_descarga_final = f"error: {str(storage_err)}"

        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()
        cursor.execute('''
            INSERT INTO aplicaciones (nombre, version, descripcion, categoria, codigo_fuente, autor, url_descarga)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, version, descripcion, categoria, codigo, autor, url_descarga_final))
        conexion.commit()
        conexion.close()
        return redirect(url_for('pagina_web'))

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
        
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('SELECT autor FROM aplicaciones WHERE id = ?', (app_id,))
    resultado = cursor.fetchone()
    
    if resultado and resultado[0] == session['usuario']:
        cursor.execute('DELETE FROM aplicaciones WHERE id = ?', (app_id,))
        conexion.commit()
        
    conexion.close()
    return redirect(url_for('pagina_web'))


if __name__ == '__main__':
    inicializar_base_datos()
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
