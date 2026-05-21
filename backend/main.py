# Reemplaza las funciones que usan pandas con esto:

import sqlite3
from pathlib import Path
import requests
import csv
from io import StringIO

def init_database():
    """Inicializa SQLite y carga datos de NUFORC sin pandas"""
    DATA_DIR = Path("data")
    DATA_DIR.mkdir(exist_ok=True)
    DB_PATH = DATA_DIR / "ufo_sightings.db"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Crear tabla si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sightings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_time TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            shape TEXT,
            duration TEXT,
            duration_seconds INTEGER,
            comments TEXT,
            date_posted TEXT,
            latitude REAL,
            longitude REAL,
            image_link TEXT
        )
    """)
    
    # Verificar si ya hay datos
    cursor.execute("SELECT COUNT(*) FROM sightings")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    # Descargar y parsear CSV manualmente
    CSV_URL = "https://raw.githubusercontent.com/planetsig/ufo-reports/master/CSV-CLEANED/ufo_sightings.csv"
    try:
        response = requests.get(CSV_URL, timeout=30)
        response.raise_for_status()
        
        # Parsear CSV sin pandas
        lines = response.text.split('\n')
        reader = csv.DictReader(lines)
        
        count = 0
        for row in reader:
            try:
                cursor.execute("""
                    INSERT INTO sightings 
                    (date_time, city, state, country, shape, duration, duration_seconds, comments, date_posted, latitude, longitude, image_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('datetime'),
                    row.get('city'),
                    row.get('state'),
                    row.get('country'),
                    row.get('shape'),
                    row.get('duration'),
                    row.get('duration (seconds)'),
                    row.get('comments'),
                    row.get('date posted'),
                    row.get('latitude'),
                    row.get('longitude'),
                    row.get('image_link')
                ))
                count += 1
                if count % 1000 == 0:
                    conn.commit()  # Commit parcial para no saturar memoria
            except:
                continue  # Saltar filas con errores
        
        conn.commit()
        print(f"✅ {count} registros cargados")
        
    except Exception as e:
        print(f"⚠️ Error al cargar: {e}")
        # Insertar datos de fallback
        fallback = [
            ("2024-01-15 20:30:00", "Phoenix", "AZ", "us", "light", "2 minutes", 120, "Bright lights", "2024-01-16", 33.4484, -112.0740, ""),
            ("2024-02-20 22:15:00", "Mexico City", "CDMX", "mx", "triangle", "5 minutes", 300, "Triangular craft", "2024-02-21", 19.4326, -99.1332, ""),
            ("2024-03-10 03:45:00", "London", "", "gb", "sphere", "1 minute", 60, "Glowing sphere", "2024-03-10", 51.5074, -0.1278, "")
        ]
        for item in fallback:
            cursor.execute("""
                INSERT INTO sightings (date_time, city, state, country, shape, duration, duration_seconds, comments, date_posted, latitude, longitude, image_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, item)
        conn.commit()
    
    conn.close()

def get_sightings(limit=50, shape=None, country=None):
    """Consulta sin pandas"""
    conn = sqlite3.connect("data/ufo_sightings.db")
    conn.row_factory = sqlite3.Row  # Permite acceder por nombre de columna
    cursor = conn.cursor()
    
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
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Convertir a lista de diccionarios
    return [dict(row) for row in rows]

def get_stats():
    """Estadísticas sin pandas"""
    conn = sqlite3.connect("data/ufo_sightings.db")
    cursor = conn.cursor()
    
    # Total
    cursor.execute("SELECT COUNT(*) FROM sightings")
    total = cursor.fetchone()[0]
    
    # Top shapes
    cursor.execute("""
        SELECT shape, COUNT(*) as count 
        FROM sightings 
        WHERE shape IS NOT NULL 
        GROUP BY shape 
        ORDER BY count DESC LIMIT 10
    """)
    shapes = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Top countries
    cursor.execute("""
        SELECT country, COUNT(*) as count 
        FROM sightings 
        WHERE country IS NOT NULL 
        GROUP BY country 
        ORDER BY count DESC LIMIT 10
    """)
    countries = {row[0]: row[1] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        "total_records": total,
        "top_shapes": shapes,
        "top_countries": countries
    }