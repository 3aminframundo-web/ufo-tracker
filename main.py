# backend/main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import sqlite3
from pathlib import Path
import requests
import csv
from io import StringIO
import os

# ══════════════════════════════════════
# ⚙️ CONFIGURACIÓN
# ══════════════════════════════════════
app = FastAPI(
    title="🛸 UFO Tracker API",
    description="API ligera para avistamientos OVNI",
    version="1.0.0",
    docs_url="/docs"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "data/ufo_sightings.db"
DATA_DIR = Path("data")
CSV_URL = "https://raw.githubusercontent.com/planetsig/ufo-reports/master/CSV-CLEANED/ufo_sightings.csv"

# ══════════════════════════════════════
# 📦 MODELOS
# ══════════════════════════════════════
class Sighting(BaseModel):
    id: Optional[Any] = None
    date_time: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    shape: Optional[str] = None
    duration: Optional[str] = None
    comments: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True

class SightingResponse(BaseModel):
    success: bool
    count: int
    data: List[Sighting]

class StatsResponse(BaseModel):
    total_records: int
    top_shapes: dict
    top_countries: dict

# ══════════════════════════════════════
# 🗄️ BASE DE DATOS (SIN PANDAS)
# ══════════════════════════════════════
def init_database():
    """Inicializa SQLite sin pandas"""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crear tabla
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sightings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_time TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            shape TEXT,
            duration TEXT,
            comments TEXT,
            latitude REAL,
            longitude REAL
        )
    """)
    
    # Verificar si ya hay datos
    cursor.execute("SELECT COUNT(*) FROM sightings")
    if cursor.fetchone()[0] > 0:
        conn.close()
        print("✅ DB ya tiene datos")
        return
    
    print("📥 Cargando datos de NUFORC...")
    
    try:
        # Descargar CSV
        response = requests.get(CSV_URL, timeout=60)
        response.raise_for_status()
        
        # Parsear sin pandas
        lines = response.text.split('\n')
        reader = csv.DictReader(lines)
        
        count = 0
        for row in reader:
            try:
                lat = row.get('latitude')
                lon = row.get('longitude')
                # Solo guardar si tiene coordenadas
                if lat and lon and lat.strip() and lon.strip():
                    cursor.execute("""
                        INSERT INTO sightings 
                        (date_time, city, state, country, shape, duration, comments, latitude, longitude)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('datetime'),
                        row.get('city'),
                        row.get('state'),
                        row.get('country'),
                        row.get('shape'),
                        row.get('duration'),
                        row.get('comments'),
                        float(lat) if lat else None,
                        float(lon) if lon else None
                    ))
                    count += 1
                    if count % 500 == 0:
                        conn.commit()
                        print(f"  → {count} registros...")
            except (ValueError, KeyError):
                continue
        
        conn.commit()
        print(f"✅ {count} registros cargados")
        
    except Exception as e:
        print(f"⚠️ Error: {e}")
        # Datos de fallback
        fallback = [
            ("2024-01-15 20:30", "Phoenix", "AZ", "us", "light", "2 min", "Bright lights", 33.4484, -112.0740),
            ("2024-02-20 22:15", "Mexico City", "CDMX", "mx", "triangle", "5 min", "Triangular craft", 19.4326, -99.1332),
            ("2024-03-10 03:45", "London", "", "gb", "sphere", "1 min", "Glowing sphere", 51.5074, -0.1278),
        ]
        for item in fallback:
            cursor.execute("""
                INSERT INTO sightings (date_time, city, state, country, shape, duration, comments, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, item)
        conn.commit()
    
    conn.close()

def get_sightings(limit: int = 50, shape: str = None, country: str = None):
    """Consulta sin pandas"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM sightings WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    params = []
    
    if shape and shape.strip():
        query += " AND LOWER(shape) LIKE LOWER(?)"
        params.append(f"%{shape}%")
    if country and country.strip():
        query += " AND LOWER(country) = LOWER(?)"
        params.append(country)
    
    query += " ORDER BY date_time DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_stats():
    """Estadísticas sin pandas"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM sightings")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT shape, COUNT(*) as c FROM sightings WHERE shape IS NOT NULL GROUP BY shape ORDER BY c DESC LIMIT 10")
    shapes = {r[0]: r[1] for r in cursor.fetchall()}
    
    cursor.execute("SELECT country, COUNT(*) as c FROM sightings WHERE country IS NOT NULL GROUP BY country ORDER BY c DESC LIMIT 10")
    countries = {r[0]: r[1] for r in cursor.fetchall()}
    
    conn.close()
    return {"total_records": total, "top_shapes": shapes, "top_countries": countries}

# ══════════════════════════════════════
# 🚀 ENDPOINTS
# ══════════════════════════════════════
@app.on_event("startup")
def startup():
    init_database()

@app.get("/")
def root():
    return {"message": "🛸 UFO Tracker API", "docs": "/docs"}

@app.get("/api/sightings", response_model=SightingResponse)
def list_sightings(
    limit: int = Query(50, ge=1, le=500),
    shape: Optional[str] = Query(None),
    country: Optional[str] = Query(None)
):
    try:
        data = get_sightings(limit=limit, shape=shape, country=country)
        return SightingResponse(success=True, count=len(data), data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", response_model=StatsResponse)
def stats():
    try:
        return get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))