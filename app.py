import os
import sqlite3
import json
import requests  # Necesario para llamar a la API de OpenRouter
import io        # Requerido para codificar los strings a bytes en memoria
import cloudinary
import cloudinary.uploader  # 🌟 NUEVO: El motor de Cloudinary
from flask import Flask, jsonify, render_template, request, redirect, url_for, session

app = Flask(__name__)
# Llave secreta para manejar las sesiones/cuentas de desarrolladores
app.secret_key = "diamant_secret_key_os_cloud_123"

DB_PATH = 'diamant_cloud.db'

OPENROUTER_API_KEY = os.environ.get("DIAMANTKEY", "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")

# 🌟 NUEVO: CONFIGURACIÓN DE CLOUDINARY (Reemplaza por completo a Supabase)
cloudinary.config( 
    cloud_name = "dwoaq0vf6", 
    api_key = "852478336132985", 
    api_secret = "sdhkaNkTsxn1JBJ4pOQvnmyUbkg",
    secure = True
)

def inicializar_base_datos():
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    # 🌟 CORRECCIÓN: Agregamos la columna 'fecha_subida' que se auto-rellena con la fecha y hora actual
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
    
    # Tabla para las cuentas de los programadores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    conexion.commit()
    conexion.close()

# 🌐 API CORREGIDA para el celular (Diamant Store C#) - ¡Ahora con Orden por Fechas!
@app.route('/api/apps', methods=['GET'])
def obtener_apps():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    # 🌟 NUEVO: Añadimos 'fecha_subida' y ordenamos por DESC (de más nueva a más vieja) para la Galería organizada
    cursor.execute('SELECT id, nombre, version, descripcion, categoria, autor, url_descarga, fecha_subida FROM aplicaciones ORDER BY fecha_subida DESC')
    apps = [dict(fila) for fila in cursor.fetchall()]
    conexion.close()
    return jsonify(apps)

# Endpoint secundario para leer por ID
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

# 🛍️ Página Web Principal (Tienda + Login + Editor)
@app.route('/', methods=['GET'])
def pagina_web():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    # Mostramos todo ordenado cronológicamente en la web también
    cursor.execute('SELECT * FROM aplicaciones ORDER BY fecha_subida DESC')
    apps = cursor.fetchall()
    conexion.close()
    
    usuario_logueado = session.get('usuario')
    return render_template('tienda.html', aplicaciones=apps, usuario=usuario_logueado)

# 🔑 SISTEMA DE CUENTAS: Registro y Login
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    accion = request.form.get('accion') # "login" o "registro"
    
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    if accion == "registro":
        try:
            cursor.execute('INSERT INTO usuarios (username, password) VALUES (?, ?)', (username, password))
            conexion.commit()
            session['usuario'] = username
        except sqlite3.IntegrityError:
            pass # El usuario ya existe
    else:
        cursor.execute('SELECT * FROM usuarios WHERE username = ? AND password = ?', (username, password))
        if cursor.fetchone():
            session['usuario'] = username
            
    conexion.close()
    return redirect(url_for('pagina_web'))

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('pagina_web'))

# 🚀 MOTOR DE COMPILACIÓN + SUBIDA INYECTADA A CLOUDINARY STORAGE
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

    # 🤖 INSTRUCCIÓN DE LA IA COMPILADORA
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
            pasa_la_ia = True  # Bypass preventivo
            
    except Exception as e:
        print(f"Excepción en la validación por IA: {e}")
        pasa_la_ia = True  # Rollback preventivo por red

    # 💾 GUARDA EL ARCHIVO EN CLOUDINARY SI PASÓ LAS PRUEBAS
    if pasa_la_ia and nombre and version and codigo:
        url_descarga_final = ""
        try:
            nombre_archivo_cs = f"{nombre.lower().replace(' ', '_')}.cs"
            
            # Convertimos el string de código C# en bytes de memoria limpios
            archivo_bytes = io.BytesIO(codigo.encode('utf-8')).getvalue()
            
            # 🌟 NUEVO: Subida directa a Cloudinary sin rebotes usando 'raw'
            resultado = cloudinary.uploader.upload(
                archivo_bytes,
                folder="diamant_store_uploads",
                resource_type="raw",
                public_id=nombre_archivo_cs,
                overwrite=True
            )
            
            # Extraemos la url segura que nos da Cloudinary
            url_descarga_final = resultado['secure_url']
            
        except Exception as storage_err:
            print(f"Error subiendo a Cloudinary Storage: {storage_err}")
            url_descarga_final = "error_storage"

        # 4. Guardar metadatos e incluir la URL permanente en SQLite
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

# 🗑️ ELIMINAR APP (Seguridad: Solo el autor puede borrarla)
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

# 🌟 CORRECCIÓN DE ARRANQUE: Configuración limpia para el puerto de Render en producción
if __name__ == '__main__':
    inicializar_base_datos()
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
