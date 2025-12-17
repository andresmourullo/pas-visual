!pip install pdfplumber

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from urllib.parse import urljoin
from google.colab import files
import pdfplumber
from io import BytesIO

# --- CONFIGURACIÓN ---
URL_BASE = "https://servicio-recursos-humanos.unex.es/funciones/concursos_pas/bolsa_trabajo/personal_funcionario/index__html/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
NOMBRE_ARCHIVO_CSV = 'bolsas_trabajo_uex_detallado.csv'

# --- FASE 1: Scraping del HTML y Extracción de Enlaces (CON PAUSA INICIAL) ---

def obtener_enlaces_bolsas(url, headers):
    print("--- PAUSA DE CORTESÍA INICIAL ---")
    print("Esperando 10 segundos antes de la primera solicitud...")
    time.sleep(10) # Pausa larga al inicio
    print("--- FASE 1: Extracción de enlaces y títulos desde el HTML ---")
    time.sleep(random.uniform(3, 5)) # Pausa antes de la solicitud HTML
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"Error al solicitar el HTML: {e}")
        return []

    # [Resto de la lógica de extracción de enlaces de FASE 1, sin cambios]
    soup = BeautifulSoup(response.content, 'html.parser')
    article_tag = soup.find('article')
    if not article_tag:
        print("ERROR: No se encontró la etiqueta <article>.")
        return []

    lista_items = article_tag.find_all('li')
    enlaces_a_procesar = []

    for item in lista_items:
        texto_item = item.get_text(strip=True).replace('\xa0', ' ')
        
        if "Turno Discapacidad" in texto_item:
            continue
            
        enlaces = item.find_all('a', href=True)
        if not enlaces:
            continue
            
        mejor_enlace_info = None
        prioridad_encontrada = 99 
        
        patrones_busqueda = [
            ("Bolsa actualizada", 0),  
            ("Bolsa Badajoz", 1),      
            ("Bolsa Cáceres", 1),      
            ("Bolsa Mérida", 1),       
            ("Bolsa Plasencia", 1),    
        ]

        for texto_patron, prioridad in patrones_busqueda:
            for a_tag in enlaces:
                texto_enlace = a_tag.get_text(strip=True).replace('\xa0', ' ')
                
                if texto_patron in texto_enlace:
                    if prioridad < prioridad_encontrada:
                        mejor_enlace_info = {
                            'texto_enlace': texto_enlace,
                            'url': urljoin(URL_BASE, a_tag['href'])
                        }
                        prioridad_encontrada = prioridad
                        if prioridad == 0: break 
            if prioridad_encontrada == 0: break

        if mejor_enlace_info is None and enlaces:
            a_tag = enlaces[0]
            mejor_enlace_info = {
                'texto_enlace': a_tag.get_text(strip=True).replace('\xa0', ' '),
                'url': urljoin(URL_BASE, a_tag['href'])
            }
            prioridad_encontrada = 2 

        if mejor_enlace_info:
            bolsa_puesto = texto_item.split('(Res')[0].split('(Diligencia')[0].split('(Acuerdo')[0].strip() # Se agrega Acuerdos por si acaso
            
            enlaces_a_procesar.append({
                'bolsa_completa': texto_item,
                'bolsa': bolsa_puesto,
                'url_pdf': mejor_enlace_info['url']
            })
            
    return enlaces_a_procesar

# --- FASE 2: Extracción de Datos de las Tablas en los PDF (CON RETRY Y PAUSAS MÁS LARGAS) ---

def extraer_datos_pdf(url_pdf, bolsa_info, headers):
    
    bolsa_nombre = bolsa_info['bolsa']
    print(f"\n[DEBUG] Procesando: {bolsa_nombre[:60]}...")
    print(f"[DEBUG] URL PDF: {url_pdf}")
    datos_personal = []
    max_retries = 3
    
    pausa = random.uniform(5, 10)
    print(f"[DEBUG] Esperando {pausa:.2f} segundos antes de descargar el PDF...")
    time.sleep(pausa) 

    for attempt in range(max_retries):
        try:
            response = requests.get(url_pdf, headers=headers)
            response.raise_for_status()
            print(f"[DEBUG] Descarga del PDF exitosa (Intento {attempt + 1}).")
            
            with pdfplumber.open(BytesIO(response.content)) as pdf:
                
                for i, page in enumerate(pdf.pages):
                    tablas = page.extract_tables()
                    
                    for j, tabla in enumerate(tablas):
                        if not tabla or len(tabla) < 2: continue
                            
                        # Tomamos la primera fila como cabecera (que puede ser incompleta)
                        header = [h.strip() if h else '' for h in tabla[0]]
                        
                        idx_nombre, idx_situacion = -1, -1
                        
                        # Función de limpieza robusta: mayúsculas, remoción de acentos y caracteres especiales comunes
                        def limpiar_y_mayus(texto):
                            if not texto: return ""
                            texto = texto.upper().strip()
                            # Reemplazos de acentos y Ñ para SITUACIÓN/SITUACION y ORDEN/ÓRDEN
                            texto = texto.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
                            texto = texto.replace('Ñ', 'N')
                            # Eliminamos espacios y algunos caracteres de puntuación para una coincidencia más estricta
                            texto = texto.replace(' ', '').replace('.', '').replace(',', '').replace(':', '')
                            return texto

                        # Generar una lista de cabeceras limpias
                        cabeceras_limpias = [limpiar_y_mayus(h) for h in header]

                        try:
                            # --- BÚSQUEDA DEL ÍNDICE DE NOMBRE ---
                            
                            # Buscamos 'NOMBRE' o 'APELLIDOS' en la cabecera limpia (contempla todas las variaciones)
                            idx_nombre_candidatos = []
                            for idx, h_limpia in enumerate(cabeceras_limpias):
                                
                                # Si encontramos 'NOMBRE' o 'APELLIDOS' en la cadena limpia
                                if 'NOMBRE' in h_limpia or 'APELLIDOS' in h_limpia:
                                    # Usamos la cabecera original en mayúsculas para verificar si es 'COMPLETO' o 'Y'
                                    h_original_mayus = header[idx].upper() 
                                    
                                    # Prioridad 1: Si es "NOMBRE COMPLETO" o "APELLIDOS Y NOMBRE" (más específico)
                                    if 'COMPLETO' in h_original_mayus or ('APELLIDOS' in h_limpia and 'NOMBRE' in h_limpia):
                                        idx_nombre = idx
                                        break
                                    # Guardar como candidato de prioridad 2 (ej. solo "NOMBRE" o solo "APELLIDOS")
                                    idx_nombre_candidatos.append(idx)
                                
                            # Si no se encontró la prioridad 1, tomamos el primer candidato simple
                            if idx_nombre == -1 and idx_nombre_candidatos:
                                idx_nombre = idx_nombre_candidatos[0]
                                
                            # Si todavía no hay índice de nombre, se levanta error para pasar al siguiente bucle
                            if idx_nombre == -1:
                                raise StopIteration("No se encontró columna de Nombre.")
                                
                            # --- BÚSQUEDA DEL ÍNDICE DE SITUACIÓN ---
                            
                            # Buscar SITUACION (sin acento) en las cabeceras limpias
                            idx_situacion = next(idx for idx, h_limpia in enumerate(cabeceras_limpias) if 'SITUACION' in h_limpia)
                            
                            # Log de la cabecera real
                            if j == 0 and i == 0:
                                print(f"[DEBUG] Cabecera de la primera tabla encontrada: {header}")
                                print(f"[DEBUG] Cabeceras limpias (muestra): {cabeceras_limpias[:5]}")
                                print(f"[DEBUG] Índices de columnas encontrados: Nombre={idx_nombre}, Situación={idx_situacion}")
                                
                        except StopIteration:
                            print(f"[DEBUG] No se encontraron las columnas clave ('NOMBRE'/'APELLIDOS' o 'SITUACIÓN') en esta tabla.")
                            continue
                            
                        # Procesar las filas de datos
                        filas_extraidas_tabla = 0
                        for fila in tabla[1:]:
                            
                            if len(fila) > max(idx_nombre, idx_situacion):
                                
                                nombre_limpio = fila[idx_nombre].strip() if fila[idx_nombre] else ''
                                situacion_limpia = fila[idx_situacion].strip() if fila[idx_situacion] else ''
                                
                                # Si la situación está vacía, a veces está en las columnas siguientes debido a la doble cabecera.
                                # Por simplicidad, tomamos la situación que ya está en la columna SITUACIÓN (índice idx_situacion).
                                
                                if nombre_limpio:  # Solo agregar si hay un nombre válido
                                    
                                    # Log de la primera fila extraída para verificar el formato
                                    if filas_extraidas_tabla == 0:
                                        print(f"[DEBUG] Primera fila de datos: Nombre='{nombre_limpio}', Situación='{situacion_limpia}'")
                                        
                                    datos_personal.append({
                                        'bolsa': bolsa_nombre,
                                        'puesto': bolsa_nombre, 
                                        'nombre': nombre_limpio,
                                        'situación': situacion_limpia
                                    })
                                    filas_extraidas_tabla += 1
                        
                        print(f"[DEBUG] Tabla {j+1} procesada, {filas_extraidas_tabla} registros añadidos.")
            
            # Si la extracción es exitosa, salimos del bucle de reintentos
            break 
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                print(f"[ERROR 429] Demasiadas peticiones. Esperando 60 segundos antes de reintentar ({attempt + 1}/{max_retries}).")
                time.sleep(60)
            else:
                print(f"[ERROR HTTP] No se pudo descargar el PDF {url_pdf}: {e}")
                break
        except Exception as e:
            print(f"[ERROR GENERAL] Excepción al procesar el PDF {url_pdf}: {e}")
            break
            
    print(f"[DEBUG] Total de personas extraídas de este PDF: {len(datos_personal)}")
    return datos_personal

# --- EJECUCIÓN PRINCIPAL ---

if __name__ == "__main__":
    
    lista_enlaces = obtener_enlaces_bolsas(URL_BASE, HEADERS)
    
    if not lista_enlaces:
        print("\n❌ No se pudieron obtener enlaces válidos para procesar.")
    else:
        print(f"\n--- FASE 2: Procesando {len(lista_enlaces)} archivos PDF ---")
        
        datos_finales = []
        
        # Procesamiento de PDFs
        for enlace in lista_enlaces:
            datos_personal_pdf = extraer_datos_pdf(enlace['url_pdf'], enlace, HEADERS)
            datos_finales.extend(datos_personal_pdf)
            
        print("\n" + "="*50)
        print(f"✅ Procesamiento completado. Se han extraído un total de {len(datos_finales)} registros.")
        print("="*50)
        
        if datos_finales:
            # Guardar y descargar el CSV
            df = pd.DataFrame(datos_finales)
            df = df[['bolsa', 'puesto', 'nombre', 'situación']]
            df.to_csv(NOMBRE_ARCHIVO_CSV, index=False, encoding='utf-8-sig') 
            
            print(f"💾 El archivo **{NOMBRE_ARCHIVO_CSV}** ha sido generado.")
            
            # Descarga Directa para Móvil
            print("\n--- PASO FINAL: Iniciando la descarga directa ---")
            files.download(NOMBRE_ARCHIVO_CSV)
            print("--- ¡DESCARGA INICIADA! (Revisa las notificaciones del navegador) ---")
            
        else:
            print("❌ No se pudo extraer ningún dato de las tablas PDF. Revisa los logs de DEBUG.")