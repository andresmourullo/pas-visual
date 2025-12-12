# 1. INSTALAMOS BEAUTIFULSOUP (Para leer el HTML como un humano)
!pip install requests python-dateutil beautifulsoup4

import csv
import requests
from datetime import datetime
from dateutil import parser
import time
import sys
import os
from bs4 import BeautifulSoup
from google.colab import files

# --- CONFIGURACIÓN ---
INPUT_FILE = 'PAS.csv'
OUTPUT_FILE = 'pas_final_webscraper.csv'

# Cabeceras para parecer un navegador normal
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 2. SUBIDA DE ARCHIVO ---
print("⬆️ Sube tu archivo PAS.csv:")
uploaded = files.upload()

if uploaded:
    nombre_subido = list(uploaded.keys())[0]
    if nombre_subido != INPUT_FILE:
        os.rename(nombre_subido, INPUT_FILE)

# --- 3. FUNCIONES DE SCRAPING ---

def clean_date(date_str):
    """Limpia el texto de la fecha (quita cosas como (xsd:date) o saltos de linea)"""
    if not date_str: return None
    # Quedarse solo con la primera parte antes de cualquier salto de línea o paréntesis
    cleaned = date_str.split('\n')[0].split('(')[0].strip()
    return cleaned

def calcular_dias(inicio_str, fin_str):
    try:
        if not inicio_str: return 0
        inicio = parser.parse(clean_date(inicio_str)).replace(tzinfo=None)
        
        if fin_str and clean_date(fin_str) != "":
            fin = parser.parse(clean_date(fin_str)).replace(tzinfo=None)
        else:
            fin = datetime.now()
            
        return (fin - inicio).days
    except:
        return 0

def obtener_fechas_intervalo(url_intervalo):
    """Entra en la web del intervalo (memberDuring) y busca hasBeginning/hasEnd"""
    try:
        # A veces el enlace viene con nodeID:// que hay que corregir
        if "nodeID://" in url_intervalo and "http" not in url_intervalo:
             # Si es un enlace relativo raro, intentamos construirlo (esto depende de la web)
             # Pero en tu HTML parece que son absolutos o relativos al dominio.
             pass 
        
        resp = requests.get(url_intervalo, headers=HEADERS, timeout=10)
        if resp.status_code != 200: return None, None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Buscamos en los DIVs con IDs específicos (basado en tu HTML)
        # hasBeginning
        start = None
        div_start = soup.find('div', id='hasBeginning')
        if not div_start: 
            # A veces el ID tiene prefijo, buscamos flexible
            div_start = soup.find('div', id=lambda x: x and 'hasBeginning' in x)
        
        if div_start:
            # El valor suele estar en un <ul><li>VALOR</li></ul>
            li = div_start.find('li')
            if li: start = li.get_text(strip=True)

        # hasEnd
        end = None
        div_end = soup.find('div', id='hasEnd')
        if not div_end:
            div_end = soup.find('div', id=lambda x: x and 'hasEnd' in x)
            
        if div_end:
            li = div_end.find('li')
            if li: end = li.get_text(strip=True)
            
        return start, end

    except Exception as e:
        return None, None

def procesar_persona(uri, nombre):
    if not uri or "http" not in uri: return "N/A", 0
    
    print(f"\n🔍 Analizando: {nombre}")
    
    try:
        # 1. Descargar página de la persona
        response = requests.get(uri, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 2. Buscar el contenedor de Membresías
        # En tu HTML: <div class="values" id="hasMembership">
        div_membership = soup.find('div', id='hasMembership')
        
        # Si no lo encuentra por ID exacto, busca algo que termine en hasMembership
        if not div_membership:
             div_membership = soup.find('div', id=lambda x: x and x.endswith('hasMembership'))
        
        if not div_membership:
            print("    ⚠️ No se encontró la sección 'hasMembership' en el HTML.")
            return "Sin datos web", 0

        # 3. Buscar enlaces a 'memberDuring'
        # Estructura: <li> <a ...>org:memberDuring</a> <a href="URL_DESTINO">...</a> </li>
        # Buscamos todos los enlaces que contengan "memberDuring" en su texto o href
        # Y cogemos el SIGUIENTE enlace, que es el del valor.
        
        enlaces_intervalos = []
        
        # Buscamos las etiquetas <a> que actúan como "etiqueta" (predicate)
        predicates = div_membership.find_all('a')
        for pred in predicates:
            if 'memberDuring' in pred.get_text() or 'memberDuring' in pred.get('href', ''):
                # El enlace al intervalo es el siguiente hermano en el DOM
                target_link = pred.find_next_sibling('a')
                if target_link:
                    url = target_link.get('href')
                    # Asegurar URL absoluta
                    if url.startswith('/'):
                        url = "https://opendata.unex.es" + url
                    enlaces_intervalos.append(url)

        print(f"    -> Encontrados {len(enlaces_intervalos)} puestos. Calculando fechas...")

        total_dias = 0
        
        # 4. Entrar en cada intervalo y sumar
        for url_int in enlaces_intervalos:
            start, end = obtener_fechas_intervalo(url_int)
            if start:
                dias = calcular_dias(start, end)
                total_dias += dias
                # print(f"       + Puesto ({dias} días): {start} a {end or 'Actualidad'}")

        anios = total_dias // 365
        resto_dias = total_dias % 365
        texto = f"{anios} años y {resto_dias} días"
        
        print(f"    ✅ Resultado: {texto}")
        return texto, total_dias

    except Exception as e:
        print(f"    ❌ Error: {e}")
        return "Error", 0

# --- 4. EJECUCIÓN PRUEBA (3 PERSONAS) ---
def main():
    if not os.path.exists(INPUT_FILE): return

    filas_procesadas = []
    
    with open(INPUT_FILE, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames + ['antiguedad_texto', 'antiguedad_dias']
        
        # MODO PRUEBA: SOLO 3
        filas = list(reader)[:3]
        
        print(f"\n🚀 Iniciando Web Scraping para {len(filas)} personas...")
        
        for row in filas:
            nombre = row.get('foaf_name', 'Desconocido')
            uri = row.get('uri', '')
            texto, dias = procesar_persona(uri, nombre)
            
            row['antiguedad_texto'] = texto
            row['antiguedad_dias'] = dias
            filas_procesadas.append(row)

    print("\n💾 Guardando archivo...")
    with open(OUTPUT_FILE, mode='w', encoding='utf-8', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filas_procesadas)

    files.download(OUTPUT_FILE)

if __name__ == "__main__":
    main()