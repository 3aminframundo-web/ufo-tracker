# backend/main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import pandas as pd
import sqlite3
from pathlib import Path
import os
import requests

# ══════════════════════════════════════
# ⚙️ CONFIGURACIÓN
# ══════════════════════════════════════
app = FastAPI(
    title="🛸 UFO Tracker API",
    description="API para avistamientos OVNI usando datos abiertos de NUFORC",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None
)

# CORS - Permite conexiones desde Netlify, localhost y cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas de datos
DB_PATH = "data/ufo_sightings.db"
DATA_DIR = Path("data")
CSV_URL = "https://raw.githubusercontent.com/planetsig/ufo-reports/master/CSV-CLEANED/ufo_sightings.csv"

# ══════════════════════════════════════
# 📦 MODELOS PYDANTIC
# ══════════════════════════════════════
class Sighting(BaseModel):
    id: Optional[Any] = None
    date_time: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    shape: Optional[str] = None
    duration: Optional[str] = None
    duration_seconds: Optional[int] = None
    comments: Optional[str] = None
    date_posted: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_link: Optional[str] = None

    class Config:
        from_attributes = True

class SightingResponse(BaseModel):
    success: bool
    count: int
    data: List[Sighting]
    message: Optional[str] = None

class StatsResponse(BaseModel):
    total_records: int
    top_shapes: dict
    top_countries: dict

# ══════════════════════════════════════
# 🗄️ BASE DE DATOS
# ══════════════════════════════════════
def init_database():
    """Inicializa SQLite y carga datos de NUFORC si está vacío"""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar si la tabla ya tiene datos
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sightings'")
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM sightings")
        count = cursor.fetchone()[0]
        if count > 0:
            conn.close()
            print(f"✅ DB ya tiene {count} registros")
            return
    
    print("📥 Cargando dataset NUFORC...")
    
    try:
        # Intentar descargar desde GitHub
        df = pd.read_csv(CSV_URL, low_memory=False, on_bad_lines='skip')
        print(f"✅ Descargados {len(df)} registros desde NUFORC")
    except Exception as e:
        print(f"⚠️ Error al descargar: {e}")
        # Dataset mínimo de fallback para pruebas
        df = pd.DataFrame([{
            "datetime": "2024-01-15 20:30:00",
            "city": "Phoenix",
            "state": "AZ",
            "country": "us",
            "shape": "light",
            "duration (seconds)": 120,
            "duration": "2 minutes",
            "comments": "Bright orange lights moving silently in formation",
            "date posted": "2024-01-16",
            "latitude": 33.4484,
            "longitude": -112.0740,
            "image_link": ""
        }, {
            "datetime": "2024-02-20 22:15:00",
            "city": "Mexico City",
            "state": "CDMX",
            "country": "mx",
            "shape": "triangle",
            "duration (seconds)": 300,
            "duration": "5 minutes",
            "comments": "Triangular craft with three lights at corners",
            "date posted": "2024-02-21",
            "latitude": 19.4326,
            "longitude": -99.1332,
            "image_link": ""
        }, {
            "datetime": "2024-03-10 03:45:00",
            "city": "London",
            "state": "",
            "country": "gb",
            "shape": "sphere",
            "duration (seconds)": 60,
            "duration": "1 minute",
            "comments": "Glowing sphere hovering then accelerating rapidly",
            "date posted": "2024-03-10",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "image_link": ""
        }])
        print(f"✅ Usando dataset de fallback con {len(df)} registros")
    
    # Normalizar nombres de columnas
    df = df.rename(columns={
        "datetime": "date_time",
        "duration (seconds)": "duration_seconds",
        "comments": "description"
    })
    
    # Asegurar que las columnas necesarias existan
    required_cols = ["date_time", "city", "country", "shape", "latitude", "longitude"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    
    # Guardar en SQLite
    df.to_sql("sightings", conn, if_exists="replace", index=False, method="multi")
    conn.close()
    print(f"✅ {len(df)} registros guardados en {DB_PATH}")

def get_sightings(limit: int = 50, shape: str = None, country: str = None):
    """Consulta filtrada a la base de datos"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT * FROM sightings 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params = []
    
    if shape and shape.strip():
        query += " AND LOWER(shape) LIKE LOWER(?)"
        params.append(f"%{shape}%")
    
    if country and country.strip():
        query += " AND LOWER(country) = LOWER(?)"
        params.append(country)
    
    query += " ORDER BY date_time DESC LIMIT ?"
    params.append(limit)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Reemplazar NaN con None para JSON
    return df.where(pd.notnull(df), None).to_dict(orient="records")

def get_stats():
    """Estadísticas generales del dataset"""
    conn = sqlite3.connect(DB_PATH)
    
    # Total de registros
    total = pd.read_sql_query("SELECT COUNT(*) as count FROM sightings", conn)["count"][0]
    
    # Formas más reportadas
    shapes = pd.read_sql_query(
        "SELECT shape, COUNT(*) as count FROM sightings WHERE shape IS NOT NULL GROUP BY shape ORDER BY count DESC LIMIT 10",
        conn
    )
    
    # Países más reportados
    countries = pd.read_sql_query(
        "SELECT country, COUNT(*) as count FROM sightings WHERE country IS NOT NULL GROUP BY country ORDER BY count DESC LIMIT 10",
        conn
    )
    
    conn.close()
    
    return {
        "total_records": int(total),
        "top_shapes": dict(zip(shapes["shape"], shapes["count"])),
        "top_countries": dict(zip(countries["country"], countries["count"]))
    }

# ══════════════════════════════════════
# 🚀 ENDPOINTS
# ══════════════════════════════════════
@app.on_event("startup")
def startup_event():
    """Inicializa la DB al arrancar la app"""
    init_database()

@app.get("/", tags=["Root"])
def root():
    """Endpoint raíz con información de la API"""
    return {
        "message": "🛸 UFO Tracker API - Datos de NUFORC",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "GET /api/sightings": "Obtener avistamientos con filtros",
            "GET /api/stats": "Obtener estadísticas generales"
        },
        "data_source": "https://www.nuforc.org"
    }

@app.get("/api/sightings", response_model=SightingResponse, tags=["Sightings"])
def list_sightings(
    limit: int = Query(50, ge=1, le=500, description="Máximo de resultados (1-500)"),
    shape: Optional[str] = Query(None, description="Filtrar por forma: light, triangle, disk, etc."),
    country: Optional[str] = Query(None, description="Código de país: us, mx, gb, etc.")
):
    """
    Obtiene avistamientos OVNI con filtros opcionales.
    
    - **limit**: Número de resultados (máx 500)
    - **shape**: Filtrar por forma del objeto
    - **country**: Filtrar por código de país (ISO 2 letras)
    """
    try:
        data = get_sightings(limit=limit, shape=shape, country=country)
        return SightingResponse(
            success=True,
            count=len(data),
            data=data,
            message=f"Mostrando {len(data)} avistamientos"
        )
    except Exception as e:
        print(f"❌ Error en /api/sightings: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/api/stats", response_model=StatsResponse, tags=["Stats"])
def get_statistics():
    """Obtiene estadísticas generales del dataset"""
    try:
        return get_stats()
    except Exception as e:
        print(f"❌ Error en /api/stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/health", tags=["Health"])
def health_check():
    """Endpoint para verificar que la API está funcionando"""
    return {"status": "healthy", "timestamp": pd.Timestamp.now().isoformat()}

# ══════════════════════════════════════
# 🏁 ENTRY POINT
# ══════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Iniciando UFO Tracker API en puerto {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)