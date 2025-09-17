"""
Rastreador web para el catálogo de cursos de la Universidad Javeriana
"""

import json
import csv
import re
import requests
import unicodedata
import html
import time
from collections import deque, defaultdict
from typing import Dict, Set, List, Optional
from urllib.parse import urljoin, urlparse
import bs4


# =====================================================
# FUNCIONES DE UTILIDAD
# =====================================================

def is_absolute_url(url: str) -> bool:
    """Verifica si una URL es absoluta"""
    return bool(urlparse(url).netloc)


def convert_if_relative_url(base_url: str, url: str) -> Optional[str]:
    """Convierte URL relativa a absoluta usando la URL base"""
    try:
        if is_absolute_url(url):
            return url
        else:
            return urljoin(base_url, url)
    except Exception:
        return None


def remove_fragment(url: str) -> str:
    """Elimina el fragmento (#) de una URL"""
    return url.split('#')[0]


def get_request(url: str) -> Optional[requests.Response]:
    """Realiza una petición HTTP GET a la URL especificada"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response
    except Exception as e:
        print(f"Error al obtener {url}: {e}")
        return None


def read_request(request: requests.Response) -> str:
    """Lee el contenido HTML de un objeto request"""
    try:
        return request.text
    except Exception as e:
        print(f"Warning: Some characters could not be decoded: {e}")
        return request.text


def get_request_url(request: requests.Response) -> str:
    """Obtiene la URL final de un request (después de redirecciones)"""
    return request.url


def is_url_ok_to_follow(url: str, domain: str) -> bool:
    """Verifica si una URL es válida para seguir según las reglas del crawler"""
    if not is_absolute_url(url):
        return False

    parsed = urlparse(url)

    # Verificar dominio
    if domain not in parsed.netloc:
        return False

    # Verificar que no contenga @ o mailto:
    if '@' in url or 'mailto:' in url.lower():
        return False

    # Verificar extensión del archivo
    path = parsed.path.lower()
    if path.endswith('/') or path == '':
        return True

    # Verificar que termine sin extensión o con .html
    if '.' not in path.split('/')[-1]:
        return True

    if path.endswith('.html') or path.endswith('.htm'):
        return True

    return False


def is_sequence_container(tag) -> bool:
    """Verifica si un tag es un contenedor de secuencia"""
    if not tag or not hasattr(tag, 'get'):
        return False

    # Obtener atributo class
    class_attr = tag.get('class', [])
    if isinstance(class_attr, list):
        class_str = ' '.join(class_attr)
    else:
        class_str = str(class_attr)

    # Verificar indicadores de secuencia
    sequence_indicators = ['item-programa', 'ais-Hits-item']
    return any(indicator in class_str for indicator in sequence_indicators)


def find_sequence(tag) -> List:
    """Encuentra subsecuencias asociadas a una etiqueta bs4 dada"""
    if not tag:
        return []

    sequence_courses = []

    # Navegar hacia arriba para encontrar el contenedor de secuencia
    current = tag
    sequence_container = None

    # Buscar hasta 5 niveles hacia arriba para encontrar el contenedor de secuencia
    for _ in range(5):
        if current and is_sequence_container(current):
            sequence_container = current
            break
        current = current.parent if current else None

    # Si no encontramos contenedor de secuencia, no es parte de una secuencia
    if not sequence_container:
        return []

    # Buscar todos los div class="card-body" dentro del contenedor de secuencia
    card_bodies = sequence_container.find_all('div', class_='card-body')

    # Filtrar para asegurar que realmente sean cursos válidos
    for card_body in card_bodies:
        # Verificar que tenga la estructura mínima de un curso
        title_tag = card_body.find('b', class_='card-title')
        link_tag = card_body.find('a', href=True)

        if title_tag and link_tag:
            sequence_courses.append(card_body)

    return sequence_courses


def extract_course_id(title: str) -> str:
    """Extrae el ID del curso del título"""
    # Decodificar entidades HTML primero
    course_id = html.unescape(title.lower())

    # Reemplazar espacios no separables (&#160;) con espacios normales
    course_id = course_id.replace('\u00a0', ' ')  # &nbsp; / &#160;

    # Normalizar caracteres acentuados
    course_id = unicodedata.normalize('NFD', course_id)
    course_id = ''.join(c for c in course_id if unicodedata.category(c) != 'Mn')

    # Reemplazar caracteres especiales con espacios y luego con guiones
    course_id = re.sub(r'[^a-zA-Z0-9\s]', ' ', course_id)
    course_id = re.sub(r'\s+', '-', course_id.strip())

    # Eliminar guiones al inicio y final
    course_id = course_id.strip('-')

    return course_id


def clean_word(word: str) -> Optional[str]:
    """Limpia una palabra según las reglas del indexador"""
    # Convertir a minúsculas
    word = word.lower()

    # Decodificar entidades HTML
    word = html.unescape(word)

    # Eliminar puntuación al final
    word = re.sub(r'[!.,:;?]+$', '', word)

    # Verificar longitud mínima
    if len(word) <= 1:
        return None

    # Normalizar acentos
    word = unicodedata.normalize('NFD', word)
    word = ''.join(c for c in word if unicodedata.category(c) != 'Mn')

    # Verificar que sea una palabra válida después de normalización
    if len(word) <= 1:
        return None

    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', word):
        return None

    return word


# Lista optimizada de stop words
STOP_WORDS = {
    # Preposiciones y artículos
    'a', 'al', 'ante', 'bajo', 'con', 'de', 'del', 'desde', 'durante', 'en', 'entre', 'hacia', 'hasta',
    'para', 'por', 'según', 'sin', 'sobre', 'tras', 'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'ha', 'cada', 'tanto', 'frente',

    # Conjunciones y conectores
    'y', 'o', 'pero', 'si', 'no', 'que', 'quien', 'como', 'cuando', 'donde', 'cual', 'cuales',

    # Demostrativos
    'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella', 'aquellos', 'aquellas', 'estara'

    # Pronombres y determinantes
    'me', 'te', 'se', 'nos', 'les', 'lo', 'le', 'su', 'sus', 'mi', 'mis', 'tu', 'tus', 'nuestro', 'nuestra', 'nuestros', 'nuestras',

    # Metadatos técnicos sin valor semántico educativo
    'horas', 'fecha', 'inicio', 'precio', 'duracion', 'duración', 'estudiante', 'estudiantes', 'profesional', 'profesionales',
    'curso', 'cursos', 'programa', 'programas', 'nivel', 'modalidad', 'virtual', 'presencial',

    # Palabras muy comunes sin valor discriminativo
    'ser', 'estar', 'tener', 'hacer', 'dar', 'ver', 'poder', 'decir', 'vez', 'muy', 'mas', 'más', 'bien', 'todo', 'toda',
    'todos', 'todas', 'esta', 'este', 'esta', 'hay', 'han', 'has', 'he', 'había', 'hemos', 'habían', 'son', 'somos',
    'era', 'eran', 'fue', 'fueron', 'será', 'serán', 'sea', 'sean', 'sido', 'siendo', 'dotar', 'busca', 'aplicar', 'utilizar', 'brindar', 'puede'

    # Palabras en inglés comunes que aparecen en contenido académico
    'the', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'for', 'with', 'by', 'from', 'all', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'can', 'must', 'shall', 'this', 'that', 'these', 'those', 'as', 'an', 'a',

    # Verbos auxiliares y muy comunes en español
    'ir', 'voy', 'va', 'van', 'vamos', 'iba', 'ibas', 'iban', 'fue', 'fuiste', 'fueron', 'irá', 'irán', 'vaya', 'vayan',
    'haga', 'hagan', 'haces', 'hacen', 'hacía', 'hacían', 'hizo', 'hicieron', 'hará', 'harán', 'haga', 'hagan'
}


def is_stop_word(word: str) -> bool:
    """Verifica si una palabra es stop word"""
    return word.lower() in STOP_WORDS


class CourseCrawler:
    """Rastreador de cursos del catálogo universitario"""

    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.course_index: Dict[str, Set[str]] = defaultdict(set)
        self.courses_found: Dict[str, Dict] = {}

        # Métricas de rendimiento
        self.metrics = {
            'start_time': None,
            'end_time': None,
            'pages_crawled': 0,
            'courses_found': 0,
            'descriptions_fetched': 0,
            'http_requests': 0,
            'failed_requests': 0,
            'total_words_indexed': 0,
            'processing_times': {
                'page_extraction': 0.0,
                'description_fetching': 0.0,
                'indexing': 0.0,
                'file_writing': 0.0
            }
        }
        
    def extract_links(self, soup: bs4.BeautifulSoup, base_url: str, domain: str) -> List[str]:
        """
        Extrae enlaces válidos de una página
        
        Args:
            soup: Objeto BeautifulSoup de la página
            base_url: URL base de la página actual
            domain: Dominio permitido
            
        Returns:
            Lista de URLs válidas para seguir
        """
        links = []
        
        # Buscar todos los enlaces <a>
        for link_tag in soup.find_all('a', href=True):
            href = link_tag['href']
            
            # Convertir URL relativa a absoluta
            absolute_url = convert_if_relative_url(base_url, href)
            if not absolute_url:
                continue
                
            # Remover fragmentos
            clean_url = remove_fragment(absolute_url)
            
            # Verificar si es válida para seguir
            if is_url_ok_to_follow(clean_url, domain):
                if clean_url not in self.visited_urls:
                    links.append(clean_url)
                    
        return links
    
    def extract_course_info(self, soup: bs4.BeautifulSoup, url: str) -> None:
        """
        Extrae información de cursos de una página, manejando secuencias

        Args:
            soup: Objeto BeautifulSoup de la página
            url: URL de la página actual
        """
        # Buscar bloques de cursos con class="card-body"
        course_blocks = soup.find_all('div', class_='card-body')
        processed_sequences = set()  # Para evitar procesar la misma secuencia múltiples veces

        for block in course_blocks:
            course_info = self.parse_course_block(block, url)
            if course_info:
                course_id = course_info['id']

                # Si no tenemos descripción, intentar obtenerla de la página individual
                if not course_info['description'] and course_info['url']:
                    description = self.fetch_course_description(course_info['url'])
                    if description:
                        course_info['description'] = description
                        self.metrics['descriptions_fetched'] += 1

                self.courses_found[course_id] = course_info

                # Verificar si este curso es parte de una secuencia
                sequence_courses = find_sequence(block)

                if sequence_courses and len(sequence_courses) > 1:
                    # Es parte de una secuencia - usar ID único basado en el primer curso
                    sequence_id = f"sequence_{sequence_courses[0].get('id', id(sequence_courses[0]))}"

                    if sequence_id not in processed_sequences:
                        processed_sequences.add(sequence_id)
                        self.process_course_sequence(sequence_courses, url, course_info)
                else:
                    # Curso individual
                    text_to_index = course_info['title'] + ' ' + course_info['description']
                    self.index_text(text_to_index, course_id)
    
    def process_course_sequence(self, sequence_courses: List, url: str, main_course_info: Dict) -> None:
        """
        Procesa una secuencia de cursos 
        
        Estrategia:
        - Mapear palabras del título principal y descripción a TODOS los cursos de la secuencia
        - Mapear palabras de descripciones individuales solo a sus respectivos cursos
        
        Args:
            sequence_courses: Lista de bloques div class="card-body" de la secuencia
            url: URL de la página
            main_course_info: Información del curso principal de la secuencia
        """
        # Obtener todas las IDs de cursos en la secuencia
        sequence_course_ids = []
        
        for course_block in sequence_courses:
            course_info = self.parse_course_block(course_block, url)
            if course_info:
                course_id = course_info['id']
                sequence_course_ids.append(course_id)
                
                # Asegurar que el curso esté en el diccionario
                if course_id not in self.courses_found:
                    self.courses_found[course_id] = course_info
        
        # Indexar título y descripción principal a TODOS los cursos de la secuencia
        main_text = main_course_info['title'] + ' ' + main_course_info['description']
        for course_id in sequence_course_ids:
            self.index_text(main_text, course_id)
        
        # Indexar descripciones individuales solo a sus respectivos cursos
        for course_block in sequence_courses:
            course_info = self.parse_course_block(course_block, url)
            if course_info:
                course_id = course_info['id']
                # Solo indexar la descripción específica de este curso
                individual_text = course_info['description']
                if individual_text and individual_text != main_course_info['description']:
                    self.index_text(individual_text, course_id)
    
    def parse_course_block(self, block: bs4.BeautifulSoup, base_url: str) -> Optional[Dict]:
        """
        Parsea un bloque de curso individual usando validación en 3 capas
        
        Args:
            block: Bloque div del curso
            base_url: URL base
            
        Returns:
            Diccionario con información del curso o None
        """
        try:
            # Capa 1: Validación estructural HTML (rápida)
            if not self.validate_html_structure(block):
                return None
            
            # Extraer información básica
            title_tag = block.find('b', class_='card-title')
            title = title_tag.get_text(strip=True)
            
            # Extraer URL del curso
            link_tag = block.find('a', href=True)
            course_url = ""
            if link_tag:
                href = link_tag['href']
                course_url = convert_if_relative_url(base_url, href) or ""
            
            # Extraer descripción con múltiples estrategias
            description_parts = []

            # Estrategia 1: Buscar párrafos con text-align:justify (descripciones reales)
            justified_paragraphs = block.find_all('p', style=lambda x: x and 'text-align:justify' in x)
            for p_tag in justified_paragraphs:
                text = p_tag.get_text(strip=True)
                if text and len(text) > 20:  # Solo descripciones sustantivas
                    description_parts.append(text)

            # Estrategia 2: Buscar párrafos sin class (a menudo contienen descripciones)
            if not description_parts:
                plain_paragraphs = block.find_all('p', class_=False, style=False)
                for p_tag in plain_paragraphs:
                    text = p_tag.get_text(strip=True)
                    # Filtrar metadatos y solo incluir texto descriptivo
                    if (text and len(text) > 20 and
                        not any(meta in text for meta in ['Duración:', 'Nivel:', 'Fecha:', 'Precio:', 'Modalidad:'])):
                        description_parts.append(text)

            # Estrategia 3: Buscar en párrafos con class pero excluyendo metadatos
            if not description_parts:
                for p_tag in block.find_all('p'):
                    text = p_tag.get_text(strip=True)
                    # Filtrar metadatos pero ser menos restrictivo
                    if (text and len(text) > 20 and
                        not any(meta in text for meta in ['Duración:', 'Nivel:', 'Fecha:', 'Precio:', 'Modalidad:', 'Horario:']) and
                        not p_tag.get('class', []) == ['card-text']):  # Evitar metadatos con class card-text
                        description_parts.append(text)

            # Estrategia 4: Buscar fuera del card-body si no encontramos descripción
            if not description_parts and block.parent:
                parent_container = block.parent
                external_paragraphs = parent_container.find_all('p', style=lambda x: x and 'text-align:justify' in x)
                for p_tag in external_paragraphs:
                    text = p_tag.get_text(strip=True)
                    if text and len(text) > 30:  # Descripciones más largas fuera del card-body
                        description_parts.append(text)

            description = ' '.join(description_parts)
            
            # Capas 2 y 3: Validación de contenido y filtros mínimos
            if not self.is_valid_course(title, description, course_url):
                return None
            
            # Generar ID del curso
            course_id = extract_course_id(title)
            
            return {
                'id': course_id,
                'title': title,
                'description': description,
                'url': course_url,
                'source_page': base_url
            }
            
        except Exception as e:
            print(f"Error parseando bloque de curso: {e}")
            return None
    
    def validate_html_structure(self, block: bs4.BeautifulSoup) -> bool:
        """
        Capa 1: Análisis estructural HTML (rápido, confiable)
        Verifica que el bloque tenga la estructura esperada de un curso
        
        Args:
            block: Bloque div del curso
            
        Returns:
            True si tiene estructura válida de curso
        """
        # Debe tener título con class="card-title"
        title_tag = block.find('b', class_='card-title')
        if not title_tag:
            return False
        
        # Debe tener al menos un enlace
        link_tag = block.find('a', href=True)
        if not link_tag:
            return False
        
        # Debe tener información de metadatos del curso (duración, nivel, etc.)
        meta_info = block.find_all('p', class_='card-text')
        if len(meta_info) < 2:  # Al menos duración y nivel
            return False
        
        return True
    
    def validate_content_heuristics(self, title: str, description: str, course_url: str) -> bool:
        """
        Capa 2: Heurísticas de contenido (flexible, adaptable)
        Verifica que el contenido sea de un curso real
        
        Args:
            title: Título del curso
            description: Descripción del curso
            course_url: URL del curso
            
        Returns:
            True si el contenido parece ser de un curso válido
        """
        # Verificar longitud mínima del título
        if not title or len(title.strip()) < 10:
            return False
        
        # Debe contener palabras indicativas de cursos educativos
        course_indicators = [
            'curso', 'programa', 'diplomado', 'especialización', 'certificado',
            'formación', 'capacitación', 'entrenamiento', 'educación'
        ]
        
        title_lower = title.lower()
        description_lower = description.lower() if description else ""
        
        # Buscar indicadores en título o descripción
        has_course_indicator = any(
            indicator in title_lower or indicator in description_lower 
            for indicator in course_indicators
        )
        
        # Si no tiene indicadores directos, verificar que al menos tenga contenido sustantivo
        if not has_course_indicator:
            # Debe tener al menos 2 palabras de más de 4 caracteres
            words = re.findall(r'\b\w+\b', title_lower)
            substantial_words = [w for w in words if len(w) > 4]
            if len(substantial_words) < 2:
                return False
        
        # Verificar que la URL sea específica de curso
        if course_url and course_url != "":
            # URLs que NO son cursos específicos
            invalid_url_patterns = [
                r'/buscar', r'/filtrar', r'/categoria', r'/tipo', 
                r'/nivel', r'/page', r'/admin', r'/login', r'/home'
            ]
            
            for pattern in invalid_url_patterns:
                if re.search(pattern, course_url.lower()):
                    return False
        
        return True
    
    def validate_minimal_filters(self, title: str) -> bool:
        """
        Capa 3: Filtros mínimos (solo casos extremadamente obvios)
        Rechaza solo elementos claramente NO cursos
        
        Args:
            title: Título del curso
            
        Returns:
            True si NO es un caso obvio de no-curso
        """
        if not title:
            return False
        
        title_clean = title.upper().strip()
        
        # Solo rechazar casos extremadamente obvios
        obvious_non_courses = {
            'TIPO', 'MODALIDAD', 'NIVEL', 'CATEGORIA', 'CATEGORÍA',
            'FILTRAR', 'BUSCAR', 'ORDENAR', 'VER', 'MOSTRAR'
        }
        
        # Rechazar si es exactamente una de estas palabras
        if title_clean in obvious_non_courses:
            return False
        
        # Rechazar títulos de una sola palabra muy corta
        words = title_clean.split()
        if len(words) == 1 and len(words[0]) <= 3:
            return False
        
        # Rechazar si es solo números
        if title_clean.isdigit():
            return False
        
        return True
    
    def is_valid_course(self, title: str, description: str, course_url: str) -> bool:
        """
        Método principal que combina las 3 capas de validación
        
        Args:
            title: Título del curso
            description: Descripción del curso
            course_url: URL del curso
            
        Returns:
            True si pasa todas las validaciones
        """
        # Aplicar filtros mínimos primero (más rápido)
        if not self.validate_minimal_filters(title):
            return False
        
        # Aplicar heurísticas de contenido
        if not self.validate_content_heuristics(title, description, course_url):
            return False
        
        return True

    def fetch_course_description(self, course_url: str) -> str:
        """
        Obtiene la descripción de un curso desde su página individual

        Args:
            course_url: URL de la página individual del curso

        Returns:
            Descripción del curso o cadena vacía si no se encuentra
        """
        try:
            # Usar print seguro para evitar errores de codificación
            try:
                print(f"    Obteniendo descripción de: {course_url}")
            except UnicodeEncodeError:
                print(f"    Obteniendo descripción de URL...")

            # Realizar petición a la página individual
            request = get_request(course_url)
            if not request:
                return ""

            # Parsear HTML
            html_content = read_request(request)
            soup = bs4.BeautifulSoup(html_content, 'html5lib')

            description_parts = []

            # Estrategia 1: Buscar párrafos con style="text-align:justify"
            justified_paragraphs = soup.find_all('p', style=lambda x: x and 'text-align:justify' in x)
            for p_tag in justified_paragraphs:
                text = p_tag.get_text(strip=True)
                if text and len(text) > 30:  # Solo párrafos sustantivos
                    description_parts.append(text)

            # Estrategia 2: Buscar en divs con contenido descriptivo
            if not description_parts:
                content_divs = soup.find_all('div', class_=['content', 'description', 'course-content'])
                for div in content_divs:
                    paragraphs = div.find_all('p')
                    for p_tag in paragraphs:
                        text = p_tag.get_text(strip=True)
                        if text and len(text) > 30:
                            description_parts.append(text)

            # Estrategia 3: Buscar párrafos largos sin filtros estrictos
            if not description_parts:
                all_paragraphs = soup.find_all('p')
                for p_tag in all_paragraphs:
                    text = p_tag.get_text(strip=True)
                    # Solo incluir párrafos largos que no sean obviamente metadatos
                    if (text and len(text) > 50 and
                        not any(meta in text for meta in ['Duración:', 'Precio:', 'Fecha:', 'Nivel:', 'Modalidad:', 'Copyright', '©'])):
                        description_parts.append(text)

            description = ' '.join(description_parts[:3])  # Limitar a 3 párrafos más relevantes

            # Aplicar la misma normalización que a los títulos
            if description:
                # Decodificar entidades HTML
                description = html.unescape(description)

                # Reemplazar espacios no separables
                description = description.replace('\u00a0', ' ')

                # Normalizar caracteres Unicode para evitar problemas de codificación
                description = unicodedata.normalize('NFD', description)
                description = ''.join(c for c in description if unicodedata.category(c) != 'Mn')

                # Limpiar caracteres problemáticos que causan errores de impresión
                description = re.sub(r'[^\w\s\.,;:!?()\-áéíóúñÁÉÍÓÚÑ]', ' ', description)
                description = re.sub(r'\s+', ' ', description.strip())

                print(f"    >> Descripción obtenida: {len(description)} caracteres")
            else:
                print(f"    >> No se encontró descripción")

            return description

        except Exception as e:
            try:
                print(f"    Error obteniendo descripción: {e}")
            except UnicodeEncodeError:
                print(f"    Error obteniendo descripción: [Error de codificación]")
            return ""

    def index_text(self, text: str, course_id: str) -> None:
        """
        Indexa el texto de un curso
        
        Args:
            text: Texto a indexar
            course_id: ID del curso
        """
        # Dividir en palabras
        words = re.findall(r'\b\w+\b', text.lower())
        
        for word in words:
            cleaned_word = clean_word(word)
            if cleaned_word and not is_stop_word(cleaned_word):
                self.course_index[cleaned_word].add(course_id)
    
    def crawl(self, start_url: str, domain: str, max_pages: int) -> None:
        """
        Ejecuta el rastreador web

        Args:
            start_url: URL de inicio
            domain: Dominio permitido
            max_pages: Número máximo de páginas a visitar
        """
        # Inicializar métricas
        self.metrics['start_time'] = time.time()

        # Cola FIFO para URLs por visitar
        url_queue = deque([start_url])
        pages_visited = 0

        print(f"Iniciando rastreo desde: {start_url}")
        print(f"Dominio: {domain}")
        print(f"Máximo páginas: {max_pages}")

        while url_queue and pages_visited < max_pages:
            current_url = url_queue.popleft()
            
            if current_url in self.visited_urls:
                continue
                
            print(f"Visitando ({pages_visited + 1}/{max_pages}): {current_url}")
            
            # Realizar petición
            self.metrics['http_requests'] += 1
            request = get_request(current_url)
            if not request:
                self.metrics['failed_requests'] += 1
                continue

            # Marcar como visitada
            actual_url = get_request_url(request)
            self.visited_urls.add(actual_url)
            pages_visited += 1
            self.metrics['pages_crawled'] += 1

            # Parsear HTML
            html_content = read_request(request)
            soup = bs4.BeautifulSoup(html_content, 'html5lib')

            # Extraer información de cursos (con medición de tiempo)
            extraction_start = time.time()
            courses_before = len(self.courses_found)
            self.extract_course_info(soup, actual_url)
            courses_after = len(self.courses_found)
            self.metrics['courses_found'] = courses_after
            self.metrics['processing_times']['page_extraction'] += time.time() - extraction_start

            # Extraer enlaces para continuar rastreando
            new_links = self.extract_links(soup, actual_url, domain)
            for link in new_links:
                if link not in self.visited_urls:
                    url_queue.append(link)
            
            print(f"  - Cursos encontrados en esta página: {len([c for c in self.courses_found.values() if c['source_page'] == actual_url])}")
            print(f"  - Nuevos enlaces encontrados: {len(new_links)}")
        
        print(f"\nRastreo completado:")
        print(f"  - Páginas visitadas: {pages_visited}")
        print(f"  - Cursos encontrados: {len(self.courses_found)}")
        print(f"  - Palabras indexadas: {len(self.course_index)}")

        # Finalizar métricas
        self.metrics['end_time'] = time.time()
        self.metrics['courses_found'] = len(self.courses_found)
        self.metrics['total_words_indexed'] = len(self.course_index)

        # Mostrar métricas de rendimiento
        self.print_performance_metrics()

    def print_performance_metrics(self) -> None:
        """Imprime métricas de rendimiento del crawler"""
        if not self.metrics['start_time'] or not self.metrics['end_time']:
            return

        total_time = self.metrics['end_time'] - self.metrics['start_time']

        print(f"\n{'='*80}")
        print("MÉTRICAS DE RENDIMIENTO DEL CRAWLER")
        print(f"{'='*80}")

        # Tiempos
        print(f"Tiempo total de crawling: {total_time:.2f} segundos")
        print(f"Tiempo promedio por página: {total_time/self.metrics['pages_crawled']:.2f} segundos")

        # Estadísticas generales
        print(f"Páginas crawleadas: {self.metrics['pages_crawled']}")
        print(f"Cursos encontrados: {self.metrics['courses_found']}")
        print(f"Descripciones obtenidas: {self.metrics['descriptions_fetched']}")
        print(f"Palabras indexadas: {self.metrics['total_words_indexed']}")

        # Estadísticas de red
        print(f"Peticiones HTTP realizadas: {self.metrics['http_requests']}")
        print(f"Peticiones fallidas: {self.metrics['failed_requests']}")
        if self.metrics['http_requests'] > 0:
            success_rate = (self.metrics['http_requests'] - self.metrics['failed_requests']) / self.metrics['http_requests']
            print(f"Tasa de éxito HTTP: {success_rate:.1%}")

        # Eficiencia
        if total_time > 0:
            pages_per_second = self.metrics['pages_crawled'] / total_time
            courses_per_second = self.metrics['courses_found'] / total_time
            print(f"Páginas por segundo: {pages_per_second:.2f}")
            print(f"Cursos por segundo: {courses_per_second:.2f}")

        # Tiempos de procesamiento detallados
        print(f"\nTiempos de procesamiento:")
        for process, time_spent in self.metrics['processing_times'].items():
            print(f"  {process.replace('_', ' ').title()}: {time_spent:.2f}s")

    def save_index_to_csv(self, output_file: str) -> None:
        """
        Guarda el índice en formato CSV
        Formato: curso_id|palabra (con IDs tipo Curso_0001)

        Args:
            output_file: Nombre del archivo de salida
        """
        file_start = time.time()
        print(f"Guardando índice en: {output_file}")

        # Crear mapeo de IDs a formato Curso_XXXX
        course_id_mapping = {}
        course_counter = 1

        for course_id in self.courses_found.keys():
            if course_id not in course_id_mapping:
                course_id_mapping[course_id] = f"Curso_{course_counter:04d}"
                course_counter += 1
        
        # Validar unicidad de pares curso/palabra 
        unique_pairs = set()
        duplicate_count = 0
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter='|')
            
            # Formato: curso_id|palabra 
            for word, course_ids in self.course_index.items():
                for course_id in sorted(course_ids):
                    if course_id in course_id_mapping:  # Solo IDs válidos
                        formatted_id = course_id_mapping[course_id]
                        pair = (formatted_id, word)
                        
                        # Verificar duplicados 
                        if pair not in unique_pairs:
                            unique_pairs.add(pair)
                            writer.writerow([formatted_id, word])
                        else:
                            duplicate_count += 1
        
        total_entries = len(unique_pairs)
        print(f"Índice guardado con {total_entries} entradas únicas")
        print(f"Mapeo de IDs creado para {len(course_id_mapping)} cursos")
        if duplicate_count > 0:
            print(f"Se evitaron {duplicate_count} duplicados curso/palabra")
        
        # Guardar mapeo de IDs para uso en búsqueda y comparación
        mapping_file = output_file.replace('.csv', '_mapping.json')
        with open(mapping_file, 'w', encoding='utf-8') as f:
            # Crear mapeo bidireccional
            bidirectional_mapping = {
                'original_to_formatted': course_id_mapping,
                'formatted_to_original': {v: k for k, v in course_id_mapping.items()}
            }
            json.dump(bidirectional_mapping, f, ensure_ascii=False, indent=2)
        print(f"Mapeo de IDs guardado en: {mapping_file}")

        # Actualizar métricas de tiempo de escritura
        self.metrics['processing_times']['file_writing'] += time.time() - file_start

    def save_courses_to_json(self, dictionary_file: str) -> None:
        """
        Guarda información de cursos en JSON

        Args:
            dictionary_file: Nombre del archivo JSON
        """
        file_start = time.time()
        print(f"Guardando diccionario de cursos en: {dictionary_file}")

        with open(dictionary_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(self.courses_found, jsonfile, ensure_ascii=False, indent=2)

        print(f"Diccionario guardado con {len(self.courses_found)} cursos")

        # Actualizar métricas de tiempo de escritura
        self.metrics['processing_times']['file_writing'] += time.time() - file_start


def go(n: int, dictionary: str, output: str) -> None:
    """
    Función principal del rastreador
    
    Args:
        n: Número de páginas para rastrear
        dictionary: Nombre del archivo JSON para el diccionario de cursos
        output: Nombre del archivo CSV de salida
    """
    # Configuración inicial
    start_url = "https://educacionvirtual.javeriana.edu.co/nuestros-programas-nuevo"
    domain = "educacionvirtual.javeriana.edu.co"
    
    # Crear e inicializar rastreador
    crawler = CourseCrawler()
    
    # Ejecutar rastreo
    crawler.crawl(start_url, domain, n)
    
    # Guardar resultados
    crawler.save_courses_to_json(dictionary)
    crawler.save_index_to_csv(output)


if __name__ == "__main__":
    import sys

    # Valores por defecto
    n = 10
    dictionary = "curso.json"
    output = "curso.csv"

    # Procesar argumentos de línea de comandos
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    if len(sys.argv) > 2:
        dictionary = sys.argv[2]
    if len(sys.argv) > 3:
        output = sys.argv[3]

    print("=== RASTREADOR WEB DE CURSOS - UNIVERSIDAD JAVERIANA ===")
    print(f"Configuracion inicial:")
    print(f"  - Paginas a rastrear: {n}")
    print(f"  - Archivo diccionario: {dictionary}")
    print(f"  - Archivo indice: {output}")

    # Preguntar confirmación si son muchas páginas
    if n > 20:
        try:
            confirm = input(f"\nVa a rastrear {n} paginas. Esto puede tomar varios minutos. ¿Continuar? (s/N): ").strip().lower()
            if confirm not in ['s', 'si', 'y', 'yes']:
                print("Operacion cancelada.")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\nOperacion cancelada.")
            sys.exit(0)

    # Preguntar número de páginas si no se especificó
    if len(sys.argv) == 1:
        try:
            user_input = input(f"\n¿Cuantas paginas desea rastrear? (por defecto {n}, recomendado 10-50): ").strip()
            if user_input:
                n = int(user_input)
                if n <= 0:
                    print("Numero de paginas debe ser mayor a 0. Usando valor por defecto.")
                    n = 10
                elif n > 100:
                    print("AVISO: Rastrear mas de 100 paginas puede tomar mucho tiempo.")
                    confirm = input("¿Esta seguro? (s/N): ").strip().lower()
                    if confirm not in ['s', 'si', 'y', 'yes']:
                        n = 10
                        print(f"Usando valor seguro: {n} paginas")
        except (ValueError, KeyboardInterrupt):
            print(f"Usando valor por defecto: {n} paginas")

    print(f"\nIniciando rastreo de {n} paginas...")
    print(f"Archivos de salida: {dictionary}, {output}")
    print("Presione Ctrl+C para interrumpir en cualquier momento\n")

    try:
        go(n, dictionary, output)
        print(f"\nRastreo completado exitosamente!")
        print(f"Resultados guardados en:")
        print(f"  - Diccionario: {dictionary}")
        print(f"  - Indice: {output}")
    except KeyboardInterrupt:
        print("\nRastreo interrumpido por el usuario.")
    except Exception as e:
        print(f"Error durante el rastreo: {e}")
        sys.exit(1)