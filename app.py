import os
import sqlite3
from flask import Flask, jsonify, render_template, request, redirect, url_for, session

app = Flask(__name__)
# Llave secreta para manejar las sesiones/cuentas de desarrolladores
app.secret_key = "diamant_secret_key_os_cloud_123"

DB_PATH = 'diamant_cloud.db'

def inicializar_base_datos():
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    # Tabla de aplicaciones modificada para guardar el CÓDIGO FUENTE
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

# 🚀 MOTOR DE COMPILACIÓN Y PUBLICACIÓN EN LA NUBE
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

    # 🧠 Validador de errores básico en la nube antes de guardar
    if "class" not in codigo or "void" not in codigo:
        # Si el código no tiene estructura básica, tiramos una advertencia simulada
        return "<h3>⚠️ Error de compilación Cloud: Estructura de clase C# no válida. Revisa tus llaves.</h3><a href='/'>Volver al editor</a>"

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
