import pandas as pd
import json
import os
import sys

# --- CONFIGURACIÓN ---
# Nombre exacto de tu archivo CSV de entrada
INPUT_FILE = 'bolsas_trabajo_uex_detallado.csv'
# Nombre del archivo que generaremos para la web
OUTPUT_FILE = 'bolsas_limpias.json'

def main():
    # 1. Comprobamos que el archivo existe
    if not os.path.exists(INPUT_FILE):
        print(f"❌ ERROR: No encuentro el archivo '{INPUT_FILE}' en esta carpeta.")
        print("👉 Asegúrate de copiar el CSV en la misma carpeta que este script.")
        return

    print(f"📂 Leyendo archivo: {INPUT_FILE}...")

    # 2. Leemos el CSV con Pandas
    # Probamos primero utf-8, si falla (común en Excel en español), probamos latin-1
    try:
        df = pd.read_csv(INPUT_FILE, encoding='utf-8')
    except UnicodeDecodeError:
        print("⚠️ El formato UTF-8 falló, intentando con Latin-1 (común en Windows)...")
        df = pd.read_csv(INPUT_FILE, encoding='latin-1')
    except Exception as e:
        print(f"❌ Error crítico leyendo el CSV: {e}")
        return

    # 3. Limpieza de datos (Lógica "Forward Fill")
    # Esto soluciona lo de "Bolsa actualizada..." asignándole el nombre de la bolsa anterior
    
    clean_data = []
    current_bolsa_name = "Desconocido"
    filas_corregidas = 0

    print("🔄 Procesando y limpiando filas...")

    print("🔄 Procesando y limpiando filas...")

    for index, row in df.iterrows():
        # Convertimos a texto y quitamos espacios
        raw_bolsa = str(row['bolsa']).strip()
        raw_lower = raw_bolsa.lower() # Convertimos a minúsculas para comparar mejor
        
        # --- LÓGICA DE FILTRADO MEJORADA ---
        es_titulo_nuevo = True
        
        # 1. Si pone "actualizada" o "ampliación", NO es titulo nuevo (se suma al anterior)
        if "actualizada" in raw_lower or "ampliación" in raw_lower:
            es_titulo_nuevo = False
            
        # 2. Si es una cabecera de ciudad/fecha (ej: Bolsa Cáceres...), NO es titulo nuevo
        # Esto hace que se ignoren esos textos y la gente se asigne al puesto de arriba.
        filtros_basura = [
            "bolsa cáceres", 
            "bolsa mérida", 
            "bolsa plasencia", 
            "bolsa badajoz", 
            "bolsa original"
        ]
        
        for filtro in filtros_basura:
            if filtro in raw_lower:
                es_titulo_nuevo = False
                break

        # --- ASIGNACIÓN ---
        if es_titulo_nuevo:
            # Es un puesto real, actualizamos el nombre actual
            current_bolsa_name = raw_bolsa
        else:
            # Es basura o continuación, contamos como corrección
            filas_corregidas += 1

        # Agregamos la fila limpia con el nombre del puesto CORRECTO (current_bolsa_name)
        clean_data.append({
            "bolsa": current_bolsa_name, 
            "puesto": str(row['puesto']),
            "nombre": str(row['nombre']),
            "situacion": str(row['situación'])
        })

    # 4. Estadísticas
    df_clean = pd.DataFrame(clean_data)
    total_bolsas = len(df_clean['bolsa'].unique())
    
    print(f"✅ Análisis completado:")
    print(f"   - Filas totales procesadas: {len(clean_data)}")
    print(f"   - Filas corregidas (nombres de bolsa arreglados): {filas_corregidas}")
    print(f"   - Bolsas únicas detectadas: {total_bolsas}")

    # 5. Guardar como JSON
    print(f"💾 Guardando {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)

    print(f"🚀 ¡LISTO! Ahora mueve '{OUTPUT_FILE}' a tu carpeta de la web.")

if __name__ == "__main__":
    main()