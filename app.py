from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'mi_clave_secreta_para_rabobank_2024'

# --- CONFIGURACIÓN DE BASE DE DATOS ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://alejandro:123456789@192.168.1.21/BANCORIA'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- MODELOS ---
class Usuario(db.Model):
    __tablename__ = 'usuario'
    dni = db.Column(db.String(15), primary_key=True)
    nombre = db.Column(db.String(30))
    apellido = db.Column(db.String(30))
    email = db.Column(db.String(70), unique=True)
    fecha_nac = db.Column(db.Date)
    direccion = db.Column(db.String(50))
    provincia = db.Column(db.String(40))
    pais = db.Column(db.String(20))
    ciudad = db.Column(db.String(40))
    codigo_postal = db.Column(db.String(50))
    contrasena = db.Column(db.String(190))
    telefono = db.Column(db.Integer, unique=True)

class Cuenta(db.Model):
    __tablename__ = 'cuenta'
    id_cuenta = db.Column(db.Integer, primary_key=True, autoincrement=True)
    saldo = db.Column(db.Float, default=0.0)
    iban = db.Column(db.String(50), unique=True)
    dni = db.Column(db.String(15), db.ForeignKey('usuario.dni'))


class Prestamo(db.Model):
    __tablename__ = 'prestamos'
    id_prestamo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    estado = db.Column(db.String(20), default='Pendiente')
    concepto = db.Column(db.String(50))
    cantidad = db.Column(db.Float)
    cantidad_pagar = db.Column(db.Float)
    interes = db.Column(db.Float)
    mensualidad = db.Column(db.Float)
    plazo = db.Column(db.Date)
    fecha_creacion = db.Column(db.Date, default=datetime.now().date)
    id_cuenta = db.Column(db.Integer, db.ForeignKey('cuenta.id_cuenta'))

class Movimiento(db.Model):
    __tablename__ = 'movimiento'
    id_movimiento = db.Column(db.Integer, primary_key=True, autoincrement=True)
    concepto = db.Column(db.String(30))
    cantidad = db.Column(db.Float)
    fecha = db.Column(db.Date, default=datetime.now().date)
    hora = db.Column(db.Time, default=datetime.now().time)
    id_cuenta = db.Column(db.Integer, db.ForeignKey('cuenta.id_cuenta'))
    
    
class Chat(db.Model):
    __tablename__ = 'chat'
    id_chat = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asunto = db.Column(db.String(20))
    mensaje = db.Column(db.String(120))
    nombre_destinatario = db.Column(db.String(20))
    dni = db.Column(db.String(15), db.ForeignKey('usuario.dni'))
    
    
# --- FUNCIONES DE APOYO ---
def generar_iban_unico(nombre):
    nombre_min = nombre.lower()[:4].ljust(4, 'z')
    iban_bin = "".join([bin(ord(c))[2:] for c in nombre_min])
    return iban_bin

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/')
def login_page():
    """Muestra el formulario de login"""
    return render_template('login.html')

@app.route('/registro')
def registro_page():
    """Muestra el formulario de registro"""
    return render_template('registro.html')

@app.route('/index')
def dashboard():
    if 'dni' not in session:
        return redirect(url_for('login_page'))
    
    user = Usuario.query.get(session['dni'])
    cuenta = Cuenta.query.filter_by(dni=user.dni).first()
    
    # Traemos los últimos 4 movimientos para la tabla del index
    movs = Movimiento.query.filter_by(id_cuenta=cuenta.id_cuenta).order_by(Movimiento.fecha.desc(), Movimiento.hora.desc()).limit(4).all()
    
    return render_template('index.html', usuario=user, cuenta=cuenta, ultimos_movimientos=movs)

# --- LÓGICA DE PROCESAMIENTO ---

@app.route('/auth_login', methods=['POST'])
def auth_login():
    dni = request.form.get('dni')
    contrasena = request.form.get('contrasena')
    
    user = Usuario.query.filter_by(dni=dni).first()
    
    # IMPORTANTE: Como en tu captura se ve que la contraseña está encriptada ($2b$12...), 
    # usamos bcrypt.check_password_hash
    if user and bcrypt.check_password_hash(user.contrasena, contrasena):
        session['dni'] = user.dni
        return redirect(url_for('dashboard'))
    else:
        flash("Acceso denegado, revisa tus datos", "danger")
        return redirect(url_for('login_page'))

@app.route('/auth_registro', methods=['POST'])
def auth_registro():
    dni = request.form.get('dni')
    email = request.form.get('email')
    password = request.form.get('contrasena')
    
    if Usuario.query.filter((Usuario.dni == dni) | (Usuario.email == email)).first():
        flash("El DNI o el Email ya están registrados", "danger")
        return redirect(url_for('registro_page'))

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    nuevo_usuario = Usuario(
        dni=dni,
        nombre=request.form.get('nombre'),
        apellido=request.form.get('apellido'),
        email=email,
        contrasena=hashed_password,
        pais=request.form.get('pais'),
        telefono=request.form.get('telefono')
    )

    try:
        db.session.add(nuevo_usuario)
        db.session.flush()
        
        nueva_cuenta = Cuenta(
            saldo=0.0,
            iban=generar_iban_unico(nuevo_usuario.nombre),
            dni=nuevo_usuario.dni
        )
        db.session.add(nueva_cuenta)
        db.session.commit()
        
        flash("¡Registro completado!", "success")
        return redirect(url_for('login_page'))
    except Exception as e:
        db.session.rollback()
        return f"Error: {str(e)}"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/cajero')
def cajero():
    if 'dni' not in session:
        return redirect(url_for('login_page'))
    
    user = Usuario.query.get(session['dni'])
    cuenta = Cuenta.query.filter_by(dni=user.dni).first()
    return render_template('cajeroAutomatico.html', cuenta=cuenta, usuario=user)

@app.route('/ingresar', methods=['POST'])
def ingresar():
    dni = session.get('dni')
    cantidad = float(request.form.get('cantidad'))
    asunto = request.form.get('asunto')
    
    cuenta = Cuenta.query.filter_by(dni=dni).first()
    
    # 1. Actualizar saldo
    cuenta.saldo += cantidad
    
    # 2. Registrar movimiento
    nuevo_mov = Movimiento(
        concepto=asunto,
        cantidad=cantidad,
        id_cuenta=cuenta.id_cuenta
    )
    
    db.session.add(nuevo_mov)
    db.session.commit()
    flash(f"Has ingresado {cantidad}€ correctamente", "success")
    return redirect(url_for('cajero'))

@app.route('/retirar', methods=['POST'])
def retirar():
    dni = session.get('dni')
    cantidad = float(request.form.get('cantidadRetiro'))
    asunto = request.form.get('asuntoRetiro')
    
    cuenta = Cuenta.query.filter_by(dni=dni).first()
    
    if cantidad > cuenta.saldo:
        flash("No puedes sacar más dinero del que tienes, deja de ser pobre", "danger")
    else:
        cuenta.saldo -= cantidad
        nuevo_mov = Movimiento(
            concepto=asunto,
            cantidad=-cantidad, # Lo guardamos negativo para indicar salida
            id_cuenta=cuenta.id_cuenta
        )
        db.session.add(nuevo_mov)
        db.session.commit()
        flash(f"Has retirado {cantidad}€", "success")
        
    return redirect(url_for('cajero'))

@app.route('/movimientos')
def movimientos():
    if 'dni' not in session:
        return redirect(url_for('login_page'))
        
    cuenta = Cuenta.query.filter_by(dni=session['dni']).first()
    # Obtenemos los movimientos ordenados por fecha y hora más reciente
    lista_movs = Movimiento.query.filter_by(id_cuenta=cuenta.id_cuenta).order_by(Movimiento.fecha.desc(), Movimiento.hora.desc()).all()
    
    return render_template('mostrarMov.html', movimientos=lista_movs)


@app.route('/chat')
def chat_page():
    if 'dni' not in session:
        return redirect(url_for('login_page'))
    
    # Obtenemos los mensajes enviados por este usuario
    mensajes = Chat.query.filter_by(dni=session['dni']).all()
    return render_template('chat.html', mensajes=mensajes)

@app.route('/enviar_mensaje', methods=['POST'])
def enviar_mensaje():
    if 'dni' not in session:
        return redirect(url_for('login_page'))
    
    nuevo_msj = Chat(
        asunto=request.form.get('asunto') or "Soporte", # Valor por defecto si no hay asunto
        mensaje=request.form.get('mensaje'),
        nombre_destinatario="Admin", # Como no hay admin, lo marcamos así
        dni=session['dni']
    )
    
    db.session.add(nuevo_msj)
    db.session.commit()
    return redirect(url_for('chat_page'))

@app.route('/prestamos')
def prestamos_page():
    if 'dni' not in session:
        return redirect(url_for('login_page'))
    
    cuenta = Cuenta.query.filter_by(dni=session['dni']).first()
    mis_prestamos = Prestamo.query.filter_by(id_cuenta=cuenta.id_cuenta).all()
    return render_template('prestamos.html', cuenta=cuenta, prestamos=mis_prestamos)

@app.route('/solicitar_prestamo', methods=['POST'])
def solicitar_prestamo():
    if 'dni' not in session:
        return redirect(url_for('login_page'))
    
    cuenta = Cuenta.query.filter_by(dni=session['dni']).first()
    
    cantidad = float(request.form.get('cantidad'))
    concepto = request.form.get('concepto')
    meses = int(request.form.get('plazo_meses')) # Recibimos meses para calcular
    
    # Lógica de ejemplo: 5% de interés fijo
    interes_valor = 5.0 
    total_a_pagar = cantidad * (1 + (interes_valor / 100))
    cuota_mensual = total_a_pagar / meses
    
    # Calcular fecha de fin (plazo) aproximada
    from datetime import timedelta
    fecha_plazo = datetime.now() + timedelta(days=meses*30)

    nuevo_prestamo = Prestamo(
        estado='Estudio',
        concepto=concepto,
        cantidad=cantidad,
        cantidad_pagar=total_a_pagar,
        interes=interes_valor,
        mensualidad=cuota_mensual,
        plazo=fecha_plazo.date(),
        id_cuenta=cuenta.id_cuenta
    )
    
    db.session.add(nuevo_prestamo)
    db.session.commit()
    
    flash("Solicitud de préstamo enviada correctamente. En revisión.", "success")
    return redirect(url_for('prestamos_page'))

if __name__ == '__main__':
    app.run(debug=True)