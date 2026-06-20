import os
import sqlite3
from flask import Flask, jsonify, render_template, request, send_from_directory

app = Flask(__name__)

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
    
    # Insertar datos de prueba iniciales solo si la tabla está vacía
    cursor.execute('SELECT COUNT(*) FROM aplicaciones')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO aplicaciones (nombre, version, descripcion, url_descarga, categoria)
            VALUES ('Rat Football League', '4.1.0', 'El juego oficial de fútbol de ratas de pana.', 'https://raw.githubusercontent.com/datasets/master/README.md', 'Juegos')
        ''')
        cursor.execute('''
            INSERT INTO aplicaciones (nombre, version, descripcion, url_descarga, categoria)
            VALUES ('Bro OS Mod', '1.0.0', 'Kernel modular de pruebas internas.', 'https://raw.githubusercontent.com/datasets/master/README.md', 'Sistema')
        ''')
        conexion.commit()
    conexion.close()

# =========================================================================
# 📡 APIS PARA TU DIAMANT STORE EN C#
# =========================================================================
@app.route('/api/apps', methods=['GET'])
def obtener_apps():
    """C# llamará aquí para obtener la lista real desde internet"""
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM aplicaciones')
    filas = cursor.fetchall()
    
    apps = [dict(fila) for fila in filas]
    conexion.close()
    return jsonify(apps)

# =========================================================================
# 🌐 VISTA WEB PÚBLICA (PÁGINA WEB REAL)
# =========================================================================
@app.route('/', methods=['GET'])
def pagina_web():
    """Cualquiera que entre desde Chrome en su celular verá tu página"""
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM aplicaciones')
    apps = cursor.fetchall()
    conexion.close()
    return render_template('tienda.html', aplicaciones=apps)

if __name__ == '__main__':
    inicializar_base_datos()
    # Usar el puerto que nos asigne internet de forma dinámica
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
