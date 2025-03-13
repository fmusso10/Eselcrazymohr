from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

# Configuración de la API
app = FastAPI(
    title="Ruralis API",
    description="API para la gestión agronómica y financiera",
    version="1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuración de la base de datos
DATABASE_URL = "sqlite:///./ruralis.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de Usuario
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)

# Modelo de Agroquímicos
class Agroquimico(Base):
    __tablename__ = "agroquimicos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    cantidad = Column(Float)  # Permite manejar cantidades con decimales
    unidad = Column(String)  # Litros, kg, etc.
    precio_unitario = Column(Float)

# Modelo de GastoAgroquimico
class GastoAgroquimico(Base):
    __tablename__ = "gastos_agroquimicos"
    id = Column(Integer, primary_key=True, index=True)
    agroquimico_id = Column(Integer, index=True)
    cantidad_aplicada = Column(Float)
    costo_total = Column(Float)
    fecha = Column(String)

# Crear la base de datos
Base.metadata.create_all(bind=engine)

# Dependencia para obtener la sesión de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Modelo para crear un usuario
class UserCreate(BaseModel):
    name: str
    email: str

# ✅ Endpoint para crear un usuario
@app.post("/users/")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(name=user.name, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "Usuario creado", "user": db_user}

# ✅ Endpoint para obtener todos los usuarios
@app.get("/users/")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {"users": users}

# ✅ Endpoint para eliminar usuario
@app.delete("/users/{user_id}/")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return {"error": "Usuario no encontrado"}
    
    db.delete(db_user)
    db.commit()
    
    return {"message": "Usuario eliminado"}

# Modelo para agregar un agroquímico
class AgroquimicoCreate(BaseModel):
    nombre: str
    cantidad: float
    unidad: str
    precio_unitario: float

# ✅ Endpoint para agregar un agroquímico
@app.post("/agroquimicos/")
def create_agroquimico(agroquimico: AgroquimicoCreate, db: Session = Depends(get_db)):
    db_agroquimico = Agroquimico(**agroquimico.dict())
    db.add(db_agroquimico)
    db.commit()
    db.refresh(db_agroquimico)
    return {"message": "Agroquímico agregado", "agroquimico": db_agroquimico}

# ✅ Endpoint para obtener todos los agroquímicos
@app.get("/agroquimicos/")
def get_agroquimicos(db: Session = Depends(get_db)):
    return {"agroquimicos": db.query(Agroquimico).all()}

# ✅ Endpoint para eliminar un agroquímico
@app.delete("/agroquimicos/{agroquimico_id}/")
def delete_agroquimico(agroquimico_id: int, db: Session = Depends(get_db)):
    db_agroquimico = db.query(Agroquimico).filter(Agroquimico.id == agroquimico_id).first()
    if not db_agroquimico:
        return {"error": "Agroquímico no encontrado"}
    
    db.delete(db_agroquimico)
    db.commit()
    
    return {"message": "Agroquímico eliminado"}

# Modelo para la aplicación de agroquímicos
class AplicarAgroquimicoRequest(BaseModel):
    dosis_por_ha: float
    hectareas: float

# ✅ Endpoint para aplicar agroquímicos y calcular el gasto
@app.post("/agroquimicos/{agroquimico_id}/aplicar/")
def aplicar_agroquimico(
    agroquimico_id: int,
    request: AplicarAgroquimicoRequest,  # Se usa el modelo para recibir datos en JSON
    db: Session = Depends(get_db)
):
    db_agroquimico = db.query(Agroquimico).filter(Agroquimico.id == agroquimico_id).first()
    if not db_agroquimico:
        return {"error": "Agroquímico no encontrado"}
    
    # 🚜 Calcular cantidad necesaria
    cantidad_necesaria = request.dosis_por_ha * request.hectareas  

    if db_agroquimico.cantidad < cantidad_necesaria:
        return {"error": "Stock insuficiente"}

    # 📉 Reducir stock
    db_agroquimico.cantidad -= cantidad_necesaria

    # 💰 Calcular costo
    costo_total = db_agroquimico.precio_unitario * (cantidad_necesaria / 1000)

    # 📝 Guardar gasto
    nuevo_gasto = GastoAgroquimico(
        agroquimico_id=agroquimico_id,
        cantidad_aplicada=cantidad_necesaria,
        costo_total=costo_total,
        fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    db.add(nuevo_gasto)
    db.commit()
    db.refresh(db_agroquimico)
    db.refresh(nuevo_gasto)

    return {
        "message": "Aplicación registrada",
        "agroquimico": {
            "id": db_agroquimico.id,
            "nombre": db_agroquimico.nombre,
            "stock_restante": db_agroquimico.cantidad
        },
        "gasto": {
            "id": nuevo_gasto.id,
            "cantidad_aplicada": nuevo_gasto.cantidad_aplicada,
            "costo_total": nuevo_gasto.costo_total,
            "fecha": nuevo_gasto.fecha
        }
    }

# ✅ Endpoint para ver el historial de gastos
@app.get("/agroquimicos/gastos/")
def get_gastos(db: Session = Depends(get_db)):
    return {"gastos": db.query(GastoAgroquimico).all()}
