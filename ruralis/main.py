from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import requests  # Para obtener el tipo de cambio

# Configuración de la API
app = FastAPI(
    title="Ruralis API",
    description="API para la gestión agronómica y financiera",
    version="1.0"
)

# Configuración de la base de datos
DATABASE_URL = "sqlite:///./ruralis.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos de la base de datos
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)

class Agroquimico(Base):
    __tablename__ = "agroquimicos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    cantidad = Column(Float)  # Cantidad en litros o kg
    unidad = Column(String)  # Litros, kg, etc.
    precio_unitario = Column(Float)  # Precio por litro o kg
    moneda = Column(String, default="ARS")  # Moneda: ARS o USD

class GastoAgroquimico(Base):
    __tablename__ = "gastos_agroquimicos"
    id = Column(Integer, primary_key=True, index=True)
    agroquimico_id = Column(Integer, index=True)
    cantidad_aplicada = Column(Float)
    costo_total_ars = Column(Float)  # Costo en ARS
    costo_total_usd = Column(Float)  # Costo en USD
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

# Modelo Pydantic para validar datos
class AgroquimicoCreate(BaseModel):
    nombre: str
    cantidad: float
    unidad: str
    precio_unitario: float
    moneda: str = "ARS"

class AplicarAgroquimicoRequest(BaseModel):
    dosis: float  # Dosis en litros o kg por hectárea
    hectareas: float  # Cantidad de hectáreas a tratar

# ✅ Obtener tipo de cambio actual (ARS a USD)
def obtener_tipo_cambio():
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/ARS")
        data = response.json()
        return data["rates"].get("USD", 0.001)  # Si falla, usar un valor bajo para evitar errores
    except:
        return 0.001  # Valor de respaldo si la API no funciona

# ✅ Endpoint para agregar agroquímicos
@app.post("/agroquimicos/")
def create_agroquimico(agroquimico: AgroquimicoCreate, db: Session = Depends(get_db)):
    db_agroquimico = Agroquimico(**agroquimico.dict())
    db.add(db_agroquimico)
    db.commit()
    db.refresh(db_agroquimico)
    return {"message": "Agroquímico agregado", "agroquimico": db_agroquimico}

# ✅ Endpoint para obtener agroquímicos
@app.get("/agroquimicos/")
def get_agroquimicos(db: Session = Depends(get_db)):
    return {"agroquimicos": db.query(Agroquimico).all()}

# ✅ Aplicar agroquímico con cálculo de costos en ARS y USD
@app.post("/agroquimicos/{agroquimico_id}/aplicar/")
def aplicar_agroquimico(agroquimico_id: int, request: AplicarAgroquimicoRequest, db: Session = Depends(get_db)):
    db_agroquimico = db.query(Agroquimico).filter(Agroquimico.id == agroquimico_id).first()
    if not db_agroquimico:
        return {"error": "Agroquímico no encontrado"}
    
    # 🚜 Calcular cantidad aplicada
    cantidad_aplicada = request.dosis * request.hectareas

    if db_agroquimico.cantidad < cantidad_aplicada:
        return {"error": "Stock insuficiente"}

    # 📉 Reducir stock
    db_agroquimico.cantidad -= cantidad_aplicada

    # 💰 Calcular costo en ARS
    costo_total_ars = db_agroquimico.precio_unitario * cantidad_aplicada

    # 💱 Convertir a USD si el agroquímico estaba en ARS
    tipo_cambio = obtener_tipo_cambio()
    if db_agroquimico.moneda == "ARS":
        costo_total_usd = costo_total_ars * tipo_cambio
    else:
        costo_total_usd = costo_total_ars  # Ya está en USD

    # 📝 Guardar el gasto
    nuevo_gasto = GastoAgroquimico(
        agroquimico_id=agroquimico_id,
        cantidad_aplicada=cantidad_aplicada,
        costo_total_ars=costo_total_ars,
        costo_total_usd=costo_total_usd,
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
            "costo_total_ars": nuevo_gasto.costo_total_ars,
            "costo_total_usd": nuevo_gasto.costo_total_usd,
            "fecha": nuevo_gasto.fecha
        }
    }

# ✅ Obtener historial de gastos
@app.get("/agroquimicos/gastos/")
def get_gastos(db: Session = Depends(get_db)):
    return {"gastos": db.query(GastoAgroquimico).all()}

# ✅ Obtener costo total de agroquímicos aplicados en ARS y USD
@app.get("/reportes/costo-total/")
def get_costo_total(db: Session = Depends(get_db)):
    total_ars = db.query(func.sum(GastoAgroquimico.costo_total_ars)).scalar() or 0
    total_usd = db.query(func.sum(GastoAgroquimico.costo_total_usd)).scalar() or 0
    return {"costo_total_ars": total_ars, "costo_total_usd": total_usd}
