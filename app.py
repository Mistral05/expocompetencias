# importaciones necesarias
#pip install flask pymysql werkzeug pdfkit
#descargar wkhtmltopdf e instalarlo: https://wkhtmltopdf.org/downloads.html
import os
from flask import Flask, request, session, redirect, url_for, render_template, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pdfkit
import pymysql


# --- Configuración de Flask ---
app = Flask(__name__)
# Configuración de clave secreta (variable de entorno o fallback)
app.secret_key = os.environ.get(
    'SECRET_KEY', '3bcbdeba836860774336fba79ed55026248690cddb6c3b6fc18b01c8d0538a13')

# --- Configuración de Conexión a DB ---


def conectar():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        db="guia",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

# --- Rutas Básicas ---


@app.route("/")
def index():
    return render_template("index/index.html")


@app.route('/register')
def register():
    error_message = session.pop('error_register', None)
    return render_template('registro/register.html', error=error_message)


@app.route("/perfil")
def perfil():
    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))
    usuario_id = session['usuario_id']
    progreso_porcentaje = 0
    
    email = session.get('correo')
    emailsql_check = "SELECT correo FROM usuarios WHERE id_usuario = %s"
    with conectar().cursor() as cursor:
        cursor.execute(emailsql_check, (usuario_id,))
    resultado = cursor.fetchone()
    email = resultado['correo'] if resultado else ''
    
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            sql_check = "SELECT unidad_1_completa, unidad_2_completa, unidad_3_completa FROM progreso_unidad1 WHERE id_usuario = %s"
            cursor.execute(sql_check, (usuario_id,))
            resultado = cursor.fetchone()

            if resultado:
                # Convertimos None a 0 y sumamos
                unidades = [
                    resultado.get('unidad_1_completa', 0) or 0,
                    resultado.get('unidad_2_completa', 0) or 0,
                    resultado.get('unidad_3_completa', 0) or 0
                ]
                total_unidades_completadas = sum(unidades)
                # Calculamos porcentaje (3 unidades total)
                progreso_porcentaje = int(
                    round((total_unidades_completadas / 3) * 100))
                
    except Exception as e:
        print(f"Error cargando perfil: {e}")
    finally:
        conexion.close()
    return render_template("perfil/perfilUsuario.html",nombre_usuario=session['nombre'], email=email,progreso_unidad1=progreso_porcentaje)


@app.route("/olvidar_contraseña")
def olvidarcontraseña():
    return render_template("cont/contr.html")


@app.route("/creacion")
def creacion():
    return render_template("complements/creacion.html")


@app.route('/session')
def session_page():
    error_message = session.pop('error_login', None)
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login/session.html', error=error_message)

# --- Rutas de Autenticación ---


@app.route('/register_submit', methods=['POST'])
def register_submit():
    # Obtener datos del formulario
    nombre = request.form.get('frmUsuario')
    correo = request.form.get('frmCuentaCorreo')
    contra = request.form.get('frmContraseña')
    semestre = request.form.get('frmSemestre')
    grupo = request.form.get('frmGrupo')
    turno = request.form.get('frmTurno')
    especialidad = request.form.get('frmEspecialidad')

    # Validación básica
    if not all([nombre, correo, contra]):
        session['error_register'] = "Faltan datos obligatorios (Nombre, Correo o Contraseña)."
        return redirect(url_for('register'))

    contraseña_hasheada = generate_password_hash(contra)

    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            # Verificar si el correo ya existe
            sql_check = "SELECT id_usuario FROM usuarios WHERE correo = %s"
            cursor.execute(sql_check, (correo,))
            if cursor.fetchone():
                session['error_register'] = "El correo ya está registrado."
                return redirect(url_for('register'))

            # Insertar nuevo usuario
            sql_insert = """
                INSERT INTO usuarios (nombre, correo, contra, semestre, grupo, turno, especialidad) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql_insert, (nombre, correo,
                           contraseña_hasheada, semestre, grupo, turno, especialidad))
        conexion.commit()
        session['success_register'] = "Registro exitoso. Inicia sesión."
        return redirect(url_for('session_page'))
    except pymysql.MySQLError as e:
        print(f"Error DB en registro: {e}")
        session['error_register'] = "Error interno al registrar."
        return redirect(url_for('register'))
    finally:
        conexion.close()


@app.route('/login', methods=['POST'])
def login():
    correo = request.form.get('frmCuentaCorreo')
    contra_plana = request.form.get('frmContraseña')

    if not correo or not contra_plana:
        session['error_login'] = "Faltan datos de acceso."
        return redirect(url_for('session_page'))

    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            sql = "SELECT id_usuario, nombre, contra FROM usuarios WHERE correo = %s"
            cursor.execute(sql, (correo,))
            usuario = cursor.fetchone()

        if usuario and check_password_hash(usuario['contra'], contra_plana):
            session['usuario_id'] = usuario['id_usuario']
            session['nombre'] = usuario['nombre']
            return redirect(url_for('dashboard'))
        else:
            session['error_login'] = "Credenciales incorrectas"
            return redirect(url_for('session_page'))
    except pymysql.MySQLError as e:
        print(f"Error DB en login: {e}")
        session['error_login'] = "Error en servidor"
        return redirect(url_for('session_page'))
    finally:
        conexion.close()

# --- DASHBOARD ---


@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))
    usuario_id = session['usuario_id']
    progreso_porcentaje = 0
    diploma_generado = False
    
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            # Seleccionamos las columnas de progreso
            sql_check = "SELECT unidad_1_completa, unidad_2_completa, unidad_3_completa FROM progreso_unidad1 WHERE id_usuario = %s"
            cursor.execute(sql_check, (usuario_id,))
            resultado = cursor.fetchone()

            if resultado:
                # Convertimos None a 0 y sumamos
                unidades = [
                    resultado.get('unidad_1_completa', 0) or 0,
                    resultado.get('unidad_2_completa', 0) or 0,
                    resultado.get('unidad_3_completa', 0) or 0
                ]
                total_unidades_completadas = sum(unidades)
                # Calculamos porcentaje (3 unidades total)
                progreso_porcentaje = int(
                    round((total_unidades_completadas / 3) * 100))
                diploma_generado = (progreso_porcentaje == 100)
    except Exception as e:
        print(f"Error cargando dashboard: {e}")
    finally:
        conexion.close()

    return render_template('curso/dashboard.html', nombre_usuario=session['nombre'], progreso_global=progreso_porcentaje, diploma_disponible=diploma_generado)

# --- RUTAS DE LOS MÓDULOS ---

# Módulo 1


@app.route("/modulouno")
def modulouno():
    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))
    return render_module_page(session['usuario_id'], 'unidad_1_completa', "modulos/moduloone.html")

# Módulo 2


@app.route("/modulodos")
def modulodos():
    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))
    return render_module_page(session['usuario_id'], 'unidad_2_completa', "modulos/modulotwo.html")

# Módulo 3


@app.route("/modulotres")
def modulotres():
    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))
    return render_module_page(session['usuario_id'], 'unidad_3_completa', "modulos/modulothree.html")


@app.route("/examenalgebra")
def examenalgebra():

    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))
    return render_module_page(session['usuario_id'], 'unidad_3_completa', "examenes/examenalgebra.html")

# Helper para renderizar módulos y verificar si ya están completados


def render_module_page(user_id, col_name, template_name):
    progreso = "0%"
    conexion = conectar()
    try:
        with conexion.cursor() as cursor:
            sql = f"SELECT {col_name} FROM progreso_unidad WHERE id_usuario = %s"
            cursor.execute(sql, (user_id,))
            res = cursor.fetchone()
            if res and res.get(col_name) == 1:
                progreso = "100%"
    except Exception as e:
        print(f"Error renderizando modulo: {e}")
    finally:
        conexion.close()
    return render_template(template_name, progreso=progreso)

# --- GUARDAR PROGRESO (Dinámico para las 3 unidades) ---


@app.route('/lesson_submit', methods=['POST'])
def lesson_submit():
    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))

    usuario_id = session['usuario_id']
    unidad_completa = request.form.get('module_completed')
    unit_id = request.form.get('unit_id')  # Recibimos '1', '2' o '3'

    # Validación estricta para evitar inyección SQL en nombre de columna
    if unidad_completa == "true" and unit_id in ['1', '2', '3']:
        columna = f"unidad_{unit_id}_completa"  # ej: unidad_2_completa

        conexion = conectar()
        try:
            with conexion.cursor() as cursor:
                # 1. Verificar si ya existe registro de progreso para el usuario
                cursor.execute(
                    "SELECT id_progreso, unidad_1_completa, unidad_2_completa, unidad_3_completa FROM progreso_unidad WHERE id_usuario = %s", (usuario_id,))
                row = cursor.fetchone()

                if row:
                    # Si existe, actualizamos la columna específica
                    # Y TAMBIÉN recalculamos el progreso total numérico para mantener la base de datos limpia

                    # Obtenemos valores actuales y actualizamos el actual en memoria
                    u1 = 1 if (row['unidad_1_completa']
                               or unit_id == '1') else 0
                    u2 = 1 if (row['unidad_2_completa']
                               or unit_id == '2') else 0
                    u3 = 1 if (row['unidad_3_completa']
                               or unit_id == '3') else 0

                    nuevo_total = int(round(((u1 + u2 + u3) / 3) * 100))

                    sql_update = f"UPDATE progreso_unidad SET {columna} = 1, progreso_total = %s WHERE id_usuario = %s"
                    cursor.execute(sql_update, (nuevo_total, usuario_id))
                else:
                    # Crear registro inicial dinámicamente si es la primera vez
                    val_1 = 1 if unit_id == '1' else 0
                    val_2 = 1 if unit_id == '2' else 0
                    val_3 = 1 if unit_id == '3' else 0

                    # El progreso total inicial es 33 (1 de 3)
                    sql_insert = """
                        INSERT INTO progreso_unidad (id_usuario, unidad_1_completa, unidad_2_completa, unidad_3_completa, progreso_total)
                        VALUES (%s, %s, %s, %s, 33)
                    """
                    cursor.execute(
                        sql_insert, (usuario_id, val_1, val_2, val_3))

            conexion.commit()
            session['mensaje_exito'] = f"¡Unidad {unit_id} Completada!"
        except Exception as e:
            print(f"Error DB guardando lección: {e}")
        finally:
            conexion.close()

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('session_page'))

@app.route('/generate_pdf')
def generate_pdf():
    if 'usuario_id' not in session:
        return redirect(url_for('session_page'))

    # Datos dinámicos del usuario
    nombre = session.get('nombre', 'Usuario')
    curso = "Curso de Python Avanzado"

    # Renderizar HTML con Jinja2
    rendered = render_template('diploma/diploma.html', nombre=nombre, curso=curso, fecha="10 de Diciembre de 2024")

    # Configuración de wkhtmltopdf en Windows
    config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")

    # Convertir HTML a PDF (False = generar en memoria)
    pdf = pdfkit.from_string(rendered, False, configuration=config)

    # Crear respuesta HTTP con PDF
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename={nombre}_diploma.pdf'
    return response

if __name__ == '__main__':
    # 'debug=True' ayuda en desarrollo para ver errores en pantalla
    app.run("0.0.0.0", 5000, debug=True)
