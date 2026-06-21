import os
import sqlite3
import json
import requests  # Necesario para llamar a la API de OpenRouter
from flask import Flask, jsonify, render_template, request, redirect, url_for, session

app = Flask(__name__)
# Llave secreta para manejar las sesiones/cuentas de desarrolladores
app.secret_key = "diamant_secret_key_os_cloud_123"

DB_PATH = 'diamant_cloud.db'
OPENROUTER_API_KEY = "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"

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
            autor TEXT
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

# 🌐 API para el celular (Diamant Store C#)
@app.route('/api/apps', methods=['GET'])
def obtener_apps():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT id, nombre, version, descripcion, categoria FROM aplicaciones')
    apps = [dict(fila) for fila in cursor.fetchall()]
    conexion.close()
    return jsonify(apps)

# Endpoint para que el celular lea el código de una app específica si lo necesita
@app.route('/api/apps/<int:app_id>/codigo', methods=['GET'])
def obtener_codigo_app(app_id):
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('SELECT codigo_fuente FROM aplicaciones WHERE id = ?', (app_id,))
    resultado = cursor.fetchone()
    conexion.close()
    if resultado:
        return jsonify({"codigo": resultado[0]})
    return jsonify({"error": "App no encontrada"}), 404

# 🛍️ Página Web Principal (Tienda + Login + Editor)
@app.route('/', methods=['GET'])
def pagina_web():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM aplicaciones')
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

# 🚀 MOTOR DE COMPILACIÓN E IA CODE REVIEWER EN LA NUBE
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

    # 🤖 PROMPT DE INGENIERÍA: Forzamos a la IA a responder estrictamente en formato JSON
    prompt_ia = f"""
    Actúa como el compilador y revisor de código experto para el ecosistema Diamant OS.
    Analiza el siguiente código fuente escrito en C# para verificar si tiene errores de sintaxis (llaves mal cerradas, falta de puntos y coma, errores de herencia, nombres de variables inválidos).
    
    Código a revisar:
    {codigo}
    
    Debes responder ÚNICAMENTE con un formato JSON estricto sin bloques de código markdown adicionas, respetando la siguiente estructura:
    {{
        "valido": true o false,
        "error_mensaje": "Aquí detallas de forma amigable los errores encontrados línea por línea si es false, de lo contrario déjalo vacío."
    }}
    """

    # 🧠 Envío del código al cerebro de la IA (OpenRouter)
    try:
        url_api = "https://openrouter.ai/api/v1/chat/completions"
        encabezados = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        cuerpo_peticion = {
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": prompt_ia}]
        }
        
        respuesta = requests.post(url_api, headers=encabezados, json=cuerpo_peticion, timeout=10)
        
        if respuesta.status_code == 200:
            datos_ia = respuesta.json()
            contenido_respuesta = datos_ia['choices'][0]['message']['content'].strip()
            
            # Limpiar posibles bloques de formato que a veces añade la IA por error
            if contenido_respuesta.startswith("```json"):
                contenido_respuesta = contenido_respuesta.split("```json")[1].split("```")[0].strip()
            elif contenido_respuesta.startswith("```"):
                contenido_respuesta = contenido_respuesta.split("```")[1].split("```")[0].strip()
                
            resultado_revision = json.loads(contenido_respuesta)
            
            # Si la IA determina que el código está roto, devolvemos al editor sin borrar nada
            if not resultado_revision.get("valido", True):
                error_formateado = resultado_revision.get("error_mensaje", "Error desconocido de sintaxis.").replace('"', '\\"').replace('\n', '\\n')
                return f'''
                <script>
                    alert("⚠️ Diamant OS Cloud Reviewer - Error de Compilación:\\n\\n{error_formateado}");
                    window.history.back(); // Regresa manteniendo los datos en el formulario web
                </script>
                '''
        else:
            print(f"Error de API OpenRouter: Código {respuesta.status_code}")
            
    except Exception as e:
        print(f"Excepción en la validación por IA: {e}")
        # En caso de caída de internet o error de respuesta, se aplica un rollback preventivo amigable
        return '''
        <script>
            alert("⚡ Diamant Cloud Link: El revisor IA no respondió a tiempo. Tu código está intacto, intenta compilar nuevamente.");
            window.history.back();
        </script>
        '''

    # Si pasa la revisión de la IA exitosamente, se guarda en la base de datos
    if nombre and version and codigo:
        conexion = sqlite3.connect(DB_PATH)
        cursor = conexion.cursor()
        cursor.execute('''
            INSERT INTO aplicaciones (nombre, version, descripcion, categoria, codigo_fuente, autor)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nombre, version, descripcion, categoria, codigo, autor))
        conexion.commit()
        conexion.close()
        
    return redirect(url_for('pagina_web'))

# 🗑️ ELIMINAR APP (Seguridad: Solo el autor puede borrarla)
@app.route('/eliminar/<int:app_id>')
def eliminar_app(app_id):
    if 'usuario' not in session:
        return redirect(url_for('pagina_web'))
        
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    # Verificamos que pertenezca al usuario activo
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
