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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conexion.commit()
    conexion.close()

    # Asegura que exista la carpeta para tus archivos de actualización física
    if not os.path.exists(UPDATES_DIR):
        os.makedirs(UPDATES_DIR)
        # Inicializamos con tu versión de desarrollo actual
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
            # 🔐 Encriptar contraseña antes de guardarla
            password_encriptada = generate_password_hash(password)
            cursor.execute('INSERT INTO usuarios (username, password) VALUES (?, ?)', (username, password_encriptada))
            conexion.commit()
            session['usuario'] = username
        except sqlite3.IntegrityError:
            pass 
    else:
        cursor.execute('SELECT password FROM usuarios WHERE username = ?', (username,))
        resultado = cursor.fetchone()
        # 🔐 Verificar hash seguro de la contraseña
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
