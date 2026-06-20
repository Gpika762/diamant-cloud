import os
import sqlite3
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "diamant_secret_key_os"

DB_PATH = 'diamant_cloud.db'

def inicializar_base_datos():
    """Crea la base de datos real en internet si no existe"""
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aplicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            version TEXT NOT NULL,
            descripcion TEXT,
            url_descarga TEXT NOT NULL,
            categoria TEXT
        )
    ''')
    conexion.commit()
    conexion.close()

# =========================================================================
# 📡 ENDPOINT API PARA EL EMULADOR EN C#
# =========================================================================
@app.route('/api/apps', methods=['GET'])
def obtener_apps():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM aplicaciones')
    filas = cursor.fetchall() # Separamos la lectura en una línea normal
    apps = [dict(fila) for fila in filas]
    conexion.close()
    return jsonify(apps)

# =========================================================================
# 🌐 VISTA WEB PÚBLICA (GALAXY / PLAY STORE WEB STYLE)
# =========================================================================
@app.route('/', methods=['GET'])
def pagina_web():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM aplicaciones')
    apps = cursor.fetchall()
    conexion.close()
    return render_template('tienda.html', aplicaciones=apps)

# =========================================================================
# 📤 PANEL PARA SUBIR NUEVAS APPS DESDE LA WEB
# =========================================================================
@app.route('/subir', methods=['GET', 'POST'])
def subir_app():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        version = request.form.get('version')
        descripcion = request.form.get('descripcion')
        url_descarga = request.form.get('url_descarga')
        categoria = request.form.get('categoria')

        if nombre and version and url_descarga:
            conexion = sqlite3.connect(DB_PATH)
            cursor = conexion.cursor()
            cursor.execute('''
                INSERT INTO aplicaciones (nombre, version, descripcion, url_descarga, categoria)
                VALUES (?, ?, ?, ?, ?)
            ''', (nombre, version, descripcion, url_descarga, categoria))
            conexion.commit()
            conexion.close()
            return redirect(url_for('pagina_web'))
            
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Diamant Developer - Subir App</title>
        <style>
            body { font-family: sans-serif; background: #121317; color: white; padding: 40px; }
            .form-box { max-width: 500px; margin: 0 auto; background: #1c1e24; padding: 30px; border-radius: 20px; border: 1px solid #292d35; }
            input, select, textarea { width: 100%; padding: 10px; margin: 10px 0; background: #2e323d; border: none; color: white; border-radius: 8px; box-sizing: border-box; }
            button { background: #0a6ef2; color: white; padding: 12px; width: 100%; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="form-box">
            <h2>📤 Publicar App en Diamant Cloud</h2>
            <form method="POST">
                <input type="text" name="nombre" placeholder="Nombre de la App (ej: Rat Football League)" required>
                <input type="text" name="version" placeholder="Versión (ej: 4.1.0)" required>
                <select name="categoria">
                    <option value="Juegos">Juegos</option>
                    <option value="Sistema">Sistema</option>
                    <option value="Herramientas">Herramientas</option>
                </select>
                <textarea name="descripcion" placeholder="Descripción de lo que hace tu app..." rows="3"></textarea>
                <input type="url" name="url_descarga" placeholder="Link de descarga directa del .EXE" required>
                <button type="submit">🚀 Lanzar a la Tienda</button>
            </form>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    inicializar_base_datos()
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
