# -*- coding: utf-8 -*-
"""
Motor de busqueda de cursos - Universidad Javeriana
Implementa busqueda por palabras clave con ranking y relevancia
"""

import json
import csv
import math
import re
import unicodedata
import html
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict, Counter
try:
    from .compare import CourseComparator
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from compare import CourseComparator


# =====================================================
# FUNCIONES DE UTILIDAD
# =====================================================

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
    'para', 'por', 'según', 'sin', 'sobre', 'tras', 'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',

    # Conjunciones y conectores
    'y', 'o', 'pero', 'si', 'no', 'que', 'quien', 'como', 'cuando', 'donde', 'cual', 'cuales',

    # Demostrativos
    'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella', 'aquellos', 'aquellas',

    # Metadatos técnicos sin valor semántico educativo
    'horas', 'fecha', 'inicio', 'precio', 'duracion', 'estudiante', 'estudiantes', 'profesional', 'profesionales',

    # Palabras muy comunes sin valor discriminativo
    'ser', 'estar', 'tener', 'hacer', 'dar', 'ver', 'poder', 'decir', 'vez', 'muy', 'mas', 'más', 'bien', 'todo', 'toda'
}


def is_stop_word(word: str) -> bool:
    """Verifica si una palabra es stop word"""
    return word.lower() in STOP_WORDS


class CourseSearchEngine:
    """Motor de busqueda de cursos con ranking TF-IDF y filtros"""

    def __init__(self, courses_file: str, index_file: str, mapping_file: str = None):
        """
        Inicializa el motor de busqueda

        Args:
            courses_file: Archivo JSON con informacion de cursos
            index_file: Archivo CSV con indice palabra-curso
            mapping_file: Archivo JSON con mapeo de IDs (opcional)
        """
        self.courses = self.load_courses(courses_file)

        # Cargar mapeo de IDs si esta disponible
        if mapping_file is None:
            mapping_file = index_file.replace('.csv', '_mapping.json')
        self.id_mapping = self.load_id_mapping(mapping_file)

        self.word_index = self.load_word_index(index_file)
        self.vocabulary = set(self.word_index.keys())
        self.idf_scores = self.calculate_idf_scores()
        self.course_word_counts = self.build_course_word_counts()

        # Inicializar comparador para métricas de similitud
        try:
            self.comparator = CourseComparator(courses_file, index_file, mapping_file)
        except Exception as e:
            print(f"Advertencia: No se pudo inicializar comparador: {e}")
            self.comparator = None

    def load_courses(self, courses_file: str) -> Dict:
        """Carga el diccionario de cursos desde JSON"""
        try:
            with open(courses_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando cursos: {e}")
            return {}

    def load_id_mapping(self, mapping_file: str) -> Dict:
        """Carga el mapeo bidireccional de IDs"""
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                return mapping_data.get('formatted_to_original', {})
        except Exception as e:
            print(f"Advertencia: No se pudo cargar mapeo de IDs: {e}")
            return {}

    def load_word_index(self, index_file: str) -> Dict[str, Set[str]]:
        """Carga el indice palabra-curso desde CSV"""
        word_index = defaultdict(set)

        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter='|')
                for row in reader:
                    if len(row) == 2:
                        course_id, word = row
                        word_index[word].add(course_id)
        except Exception as e:
            print(f"Error cargando indice: {e}")

        return dict(word_index)

    def calculate_idf_scores(self) -> Dict[str, float]:
        """Calcula scores IDF para cada palabra"""
        total_courses = len(self.courses)
        idf_scores = {}

        for word, course_ids in self.word_index.items():
            df = len(course_ids)  # document frequency
            idf = math.log(total_courses / df) if df > 0 else 0
            idf_scores[word] = idf

        return idf_scores

    def build_course_word_counts(self) -> Dict[str, Dict[str, int]]:
        """Construye conteos de palabras por curso"""
        course_words = defaultdict(lambda: defaultdict(int))

        for word, formatted_course_ids in self.word_index.items():
            for formatted_id in formatted_course_ids:
                # Convertir ID formateado a original
                original_id = self.id_mapping.get(formatted_id, formatted_id)
                if original_id in self.courses:
                    course_words[original_id][word] += 1

        return dict(course_words)

    def preprocess_query(self, query: str) -> List[str]:
        """
        Preprocesa una consulta de busqueda

        Args:
            query: Consulta del usuario

        Returns:
            Lista de palabras limpias de la consulta
        """
        # Convertir a minusculas y extraer palabras
        words = re.findall(r'\b\w+\b', query.lower())

        # Limpiar y filtrar palabras
        clean_words = []
        for word in words:
            cleaned_word = clean_word(word)
            if cleaned_word and not is_stop_word(cleaned_word):
                clean_words.append(cleaned_word)

        return clean_words



    def normalize_scores(self, scores: List[float]) -> List[float]:
        """
        Normaliza una lista de scores al rango [0-1]

        Args:
            scores: Lista de scores a normalizar

        Returns:
            Lista de scores normalizados [0-1]
        """
        if not scores:
            return []

        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [1.0 if score > 0 else 0.0 for score in scores]

        return [(score - min_score) / (max_score - min_score) for score in scores]

    def calculate_relevance_score(self, course_id: str, query_words: List[str]) -> float:
        """
        Calcula score de relevancia simple:
        Cantidad de palabras de la consulta presentes en el curso / Total palabras consulta

        Args:
            course_id: ID del curso
            query_words: Palabras de la consulta

        Returns:
            Score de relevancia [0,1]
        """
        if not query_words or course_id not in self.courses:
            return 0.0

        # Obtener palabras del curso desde el comparador (si está disponible)
        if self.comparator and course_id in self.comparator.course_words:
            course_words = self.comparator.course_words[course_id]
        else:
            # Fallback a course_word_counts si no hay comparador
            course_words = set(self.course_word_counts.get(course_id, {}).keys())

        # Contar palabras de la consulta que están en el curso
        matches = sum(1 for word in query_words if word in course_words)

        # Relevancia = coincidencias / total palabras consulta
        return matches / len(query_words)

    def calculate_keyword_frequency(self, course_id: str, query_words: List[str]) -> int:
        """
        Calcula la frecuencia total de las palabras clave de la consulta en el curso

        Args:
            course_id: ID del curso
            query_words: Palabras de la consulta

        Returns:
            Frecuencia total de keywords en el curso
        """
        if not query_words or course_id not in self.courses:
            return 0

        # Obtener conteos de palabras del curso
        word_counts = self.course_word_counts.get(course_id, {})

        # Sumar frecuencias de cada palabra de la consulta
        total_frequency = sum(word_counts.get(word, 0) for word in query_words)

        return total_frequency

    def calculate_tf_idf_score(self, course_id: str, query_words: List[str]) -> float:
        """
        Calcula score TF-IDF entre consulta y curso

        Args:
            course_id: ID del curso
            query_words: Palabras de la consulta

        Returns:
            Score TF-IDF acumulado
        """
        if not query_words or course_id not in self.courses:
            return 0.0

        word_counts = self.course_word_counts.get(course_id, {})
        total_words_in_course = sum(word_counts.values()) or 1  # Evitar división por 0

        tfidf_score = 0.0
        for word in query_words:
            # TF (Term Frequency): frecuencia relativa en el curso
            tf = word_counts.get(word, 0) / total_words_in_course

            # IDF (Inverse Document Frequency): ya calculado
            idf = self.idf_scores.get(word, 0)

            # TF-IDF para esta palabra
            tfidf_score += tf * idf

        return tfidf_score

    def calculate_cosine_similarity(self, course_id: str, query_words: List[str]) -> float:
        """
        Calcula similitud coseno entre vector de consulta y vector de curso

        Args:
            course_id: ID del curso
            query_words: Palabras de la consulta

        Returns:
            Similitud coseno [0,1]
        """
        if not query_words or course_id not in self.courses:
            return 0.0

        # Vector de consulta: cada palabra tiene peso 1
        query_vector = Counter(query_words)

        # Vector de curso: usar TF-IDF como pesos
        course_word_counts = self.course_word_counts.get(course_id, {})
        total_words_in_course = sum(course_word_counts.values()) or 1

        # Crear vectores alineados para todas las palabras únicas
        all_words = set(query_words) | set(course_word_counts.keys())

        query_vec = []
        course_vec = []

        for word in all_words:
            # Query vector: frecuencia simple
            query_vec.append(query_vector.get(word, 0))

            # Course vector: TF-IDF
            tf = course_word_counts.get(word, 0) / total_words_in_course
            idf = self.idf_scores.get(word, 0)
            course_vec.append(tf * idf)

        # Calcular similitud coseno
        dot_product = sum(q * c for q, c in zip(query_vec, course_vec))

        query_magnitude = math.sqrt(sum(q * q for q in query_vec))
        course_magnitude = math.sqrt(sum(c * c for c in course_vec))

        if query_magnitude == 0 or course_magnitude == 0:
            return 0.0

        return dot_product / (query_magnitude * course_magnitude)



    def calculate_smart_ranking(self, course_id: str, query_words: List[str]) -> float:
        """
        Calcula ranking inteligente que prioriza cobertura de consulta

        Args:
            course_id: ID del curso
            query_words: Palabras de la consulta

        Returns:
            Score que prioriza coincidencias múltiples
        """
        if not query_words or course_id not in self.courses:
            return 0.0

        # Paso 1: Calcular cobertura de consulta (más importante)
        course_words = set(self.course_word_counts.get(course_id, {}).keys())
        matching_words = set(query_words) & course_words
        coverage = len(matching_words) / len(query_words)

        # Paso 2: Calcular cosine para desempate entre cursos con misma cobertura
        cosine_score = self.calculate_cosine_similarity(course_id, query_words)

        # Paso 3: Ranking híbrido - cobertura domina, cosine desempata
        # Multiplicar cobertura por 10 para que domine sobre cosine (0-1)
        hybrid_score = (coverage * 10.0) + cosine_score

        return hybrid_score

    def search(self, query: str, max_results: int = 10, method: str = 'cosine') -> List[Tuple[str, float, Dict]]:
        """
        Realiza busqueda de cursos

        Args:
            query: Consulta de busqueda
            max_results: Numero maximo de resultados
            method: Metodo de ranking ('cosine', 'relevance', 'tfidf')

        Returns:
            Lista de tuplas (course_id, score, course_info) ordenada por relevancia
        """
        if not query.strip():
            return []

        # Preprocesar consulta
        query_words = self.preprocess_query(query)
        if not query_words:
            return []

        print(f"Busqueda: '{query}'")
        print(f"Palabras procesadas: {query_words}")

        # Encontrar cursos candidatos
        candidate_courses = set()
        for word in query_words:
            if word in self.word_index:
                formatted_ids = self.word_index[word]
                for formatted_id in formatted_ids:
                    original_id = self.id_mapping.get(formatted_id, formatted_id)
                    if original_id in self.courses:
                        candidate_courses.add(original_id)

        print(f"Cursos candidatos: {len(candidate_courses)}")

        # Calcular scores
        results = []
        for course_id in candidate_courses:
            if method == 'cosine':
                score = self.calculate_cosine_similarity(course_id, query_words)
            elif method == 'relevance':
                score = self.calculate_relevance_score(course_id, query_words)
            elif method == 'tfidf':
                score = self.calculate_tf_idf_score(course_id, query_words)
            elif method == 'smart':
                score = self.calculate_smart_ranking(course_id, query_words)
            else:
                raise ValueError(f"Metodo desconocido: {method}. Disponibles: 'cosine', 'relevance', 'tfidf', 'smart'")

            if score > 0:
                course_info = self.courses[course_id]
                results.append((course_id, score, course_info))

        # Ordenar por score descendente
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:max_results]

    def search_by_category(self, query: str, category: str = None, max_results: int = 10) -> List[Tuple[str, float, Dict]]:
        """
        Busqueda con filtro por categoria/area tematica

        Args:
            query: Consulta de busqueda
            category: Categoria a filtrar (opcional)
            max_results: Numero maximo de resultados

        Returns:
            Lista de resultados filtrados por categoria
        """
        # Realizar busqueda normal
        results = self.search(query, max_results * 2, method='cosine')  # Buscar mas para compensar filtro

        if not category:
            return results[:max_results]

        # Filtrar por categoria
        filtered_results = []
        category_lower = category.lower()

        for course_id, score, course_info in results:
            title = course_info.get('title', '').lower()
            description = course_info.get('description', '').lower()

            # Verificar si la categoria aparece en titulo o descripcion
            if (category_lower in title or
                category_lower in description or
                any(cat_word in title + ' ' + description
                    for cat_word in category_lower.split())):
                filtered_results.append((course_id, score, course_info))

        return filtered_results[:max_results]

    def get_course_info(self, course_id: str) -> Dict:
        """Obtiene informacion completa de un curso"""
        return self.courses.get(course_id, {})

    def get_statistics(self) -> Dict:
        """Obtiene estadisticas del motor de busqueda"""
        return {
            'total_courses': len(self.courses),
            'vocabulary_size': len(self.vocabulary),
            'index_entries': sum(len(course_ids) for course_ids in self.word_index.values()),
            'avg_words_per_course': sum(len(words) for words in self.course_word_counts.values()) / len(self.courses) if self.courses else 0
        }

    def measure_performance(self, query: str, max_results: int = 10) -> Dict:
        """
        Mide métricas de rendimiento del sistema de búsqueda

        Args:
            query: Consulta de búsqueda
            max_results: Número máximo de resultados

        Returns:
            Diccionario con métricas de rendimiento
        """
        import time

        start_time = time.time()

        # Preprocesar consulta
        preprocessing_start = time.time()
        query_words = self.preprocess_query(query)
        preprocessing_time = time.time() - preprocessing_start

        if not query_words:
            return {
                'query': query,
                'preprocessing_time_ms': preprocessing_time * 1000,
                'search_time_ms': 0,
                'total_time_ms': preprocessing_time * 1000,
                'query_words': [],
                'candidate_courses': 0,
                'results_found': 0,
                'results_returned': 0,
                'coverage': 0.0,
                'precision_at_k': 0.0,
                'avg_relevance_score': 0.0
            }

        # Encontrar cursos candidatos
        candidate_start = time.time()
        candidate_courses = set()
        for word in query_words:
            if word in self.word_index:
                formatted_ids = self.word_index[word]
                for formatted_id in formatted_ids:
                    original_id = self.id_mapping.get(formatted_id, formatted_id)
                    if original_id in self.courses:
                        candidate_courses.add(original_id)
        candidate_time = time.time() - candidate_start

        # Calcular scores y generar resultados
        scoring_start = time.time()
        results = []
        for course_id in candidate_courses:
            score = self.calculate_cosine_similarity(course_id, query_words)
            if score > 0:
                course_info = self.courses[course_id]
                results.append((course_id, score, course_info))

        # Ordenar por score
        results.sort(key=lambda x: x[1], reverse=True)
        final_results = results[:max_results]
        scoring_time = time.time() - scoring_start

        total_time = time.time() - start_time

        # Calcular métricas de rendimiento
        results_with_score = len(results)
        results_returned = len(final_results)

        # Coverage: proporción de cursos que tienen al menos una palabra de la consulta
        coverage = len(candidate_courses) / len(self.courses) if self.courses else 0.0

        # Precision@K: proporción de resultados relevantes en top-K
        # Consideramos relevante si score > umbral mínimo (0.1)
        relevant_results = sum(1 for _, score, _ in final_results if score > 0.1)
        precision_at_k = relevant_results / len(final_results) if final_results else 0.0

        # Score promedio de relevancia
        avg_relevance = sum(score for _, score, _ in final_results) / len(final_results) if final_results else 0.0

        return {
            'query': query,
            'preprocessing_time_ms': preprocessing_time * 1000,
            'candidate_search_time_ms': candidate_time * 1000,
            'scoring_time_ms': scoring_time * 1000,
            'total_time_ms': total_time * 1000,
            'query_words': query_words,
            'candidate_courses': len(candidate_courses),
            'results_found': results_with_score,
            'results_returned': results_returned,
            'coverage': coverage,
            'precision_at_k': precision_at_k,
            'avg_relevance_score': avg_relevance,
            'relevance_threshold': 0.1
        }


def search(query: str, courses_file: str = 'curso.json',
          index_file: str = 'curso.csv', max_results: int = 10, method: str = 'smart') -> List[str]:
    """
    Funcion de busqueda standalone

    Args:
        query: Consulta de busqueda (keywords)
        courses_file: Archivo JSON con cursos
        index_file: Archivo CSV con indice
        max_results: Numero maximo de resultados

    Returns:
        Lista de URLs ordenadas por relevancia
    """
    engine = CourseSearchEngine(courses_file, index_file)
    results = engine.search(query, max_results, method=method)

    # Retornar URLs ordenadas por relevancia
    urls = []
    for course_id, score, course_info in results:
        url = course_info.get('url', '')
        if url:  # Solo incluir cursos con URL valida
            urls.append(url)

    return urls


def search_with_scores(query: str, courses_file: str = 'curso.json',
                      index_file: str = 'curso.csv', max_results: int = 10, method: str = 'smart') -> List[Tuple[str, float]]:
    """
    Funcion de busqueda que retorna IDs y scores (para compatibilidad)

    Args:
        query: Consulta de busqueda
        courses_file: Archivo JSON con cursos
        index_file: Archivo CSV con indice
        max_results: Numero maximo de resultados

    Returns:
        Lista de tuplas (course_id, cosine_similarity_score)
    """
    engine = CourseSearchEngine(courses_file, index_file)
    results = engine.search(query, max_results, method=method)

    # Retornar ID y score
    return [(course_id, score) for course_id, score, _ in results]


def search_detailed(query: str, courses_file: str = 'curso.json',
                   index_file: str = 'curso.csv', max_results: int = 10):
    """
    Función de búsqueda detallada que muestra tabla comparativa de métodos

    Args:
        query: Consulta de búsqueda
        courses_file: Archivo JSON con cursos
        index_file: Archivo CSV con índice
        max_results: Número máximo de resultados

    Returns:
        Número de resultados encontrados con score > 0
    """
    engine = CourseSearchEngine(courses_file, index_file)

    # Preprocesar consulta
    query_words = engine.preprocess_query(query)
    if not query_words:
        print("No se pudieron procesar las palabras de la consulta.")
        return 0

    # Encontrar cursos candidatos (misma lógica que method search)
    candidate_courses = set()
    for word in query_words:
        if word in engine.word_index:
            formatted_ids = engine.word_index[word]
            for formatted_id in formatted_ids:
                original_id = engine.id_mapping.get(formatted_id, formatted_id)
                if original_id in engine.courses:
                    candidate_courses.add(original_id)

    if not candidate_courses:
        print("No se encontraron cursos candidatos.")
        return 0

    # Calcular score de similitud coseno
    results = []
    for course_id in candidate_courses:
        cosine_score = engine.calculate_cosine_similarity(course_id, query_words)

        # Solo incluir cursos con score > 0
        if cosine_score > 0:
            course_info = engine.courses.get(course_id, {})

            # Calcular frecuencia de keywords para mostrar en tabla
            keyword_frequency = engine.calculate_keyword_frequency(course_id, query_words)

            results.append((course_id, cosine_score, keyword_frequency, course_info))

    if not results:
        print("No se encontraron resultados.")
        return 0

    # Ordenar por similitud coseno (ya no necesita desempate, coseno es más granular)
    # Formato: (course_id, cosine_score, keyword_frequency, course_info)
    results.sort(key=lambda x: -x[1])  # -cosine_score
    sort_method = "similitud coseno (vectores TF-IDF normalizados)"

    results = results[:max_results]

    # Mostrar resultados en tabla
    print(f"\n{'='*135}")
    print(f"RESULTADOS DE BÚSQUEDA: '{query}'")
    print(f"Palabras procesadas: {query_words}")
    print(f"Ordenado por: {sort_method}")
    print(f"{'='*135}")
    

    print(f"{'#':<3} {'CURSO':<65} {'COSINE':<10} {'KEYWORDS':<10} {'URL':<42}")
    print(f"{'-'*135}")

    for i, (course_id, cosine_score, keyword_frequency, course_info) in enumerate(results, 1):
        title = course_info.get('title', course_id)
        # Truncar título si es muy largo pero mantener legibilidad
        if len(title) > 65:
            title = title[:62] + "..."

        url = course_info.get('url', 'N/A')
        # Truncar URL si es muy larga
        if len(url) > 42:
            url = url[:39] + "..."

        print(f"{i:<3} {title:<65} {cosine_score:<10.3f} {keyword_frequency:<10} {url:<42}")

    print(f"{'-'*135}")
    print(f"Total: {len(results)} cursos encontrados")
    print("COSINE = Similitud coseno entre vectores de consulta y curso (TF-IDF)")
    print("KEYWORDS = Cantidad de palabras clave presentes en el curso")

    # Mostrar métricas de rendimiento
    print(f"\n{'='*80}")
    print("MÉTRICAS DE RENDIMIENTO")
    print(f"{'='*80}")

    performance = engine.measure_performance(query, max_results)

    print(f"Tiempo de preprocesamiento: {performance['preprocessing_time_ms']:.2f} ms")
    print(f"Tiempo de búsqueda candidatos: {performance['candidate_search_time_ms']:.2f} ms")
    print(f"Tiempo de scoring: {performance['scoring_time_ms']:.2f} ms")
    print(f"Tiempo total: {performance['total_time_ms']:.2f} ms")
    print(f"Cursos candidatos: {performance['candidate_courses']}")
    print(f"Cobertura: {performance['coverage']:.1%} del corpus")
    print(f"Precisión@{max_results}: {performance['precision_at_k']:.1%}")
    print(f"Score promedio: {performance['avg_relevance_score']:.3f}")

    return len(results)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python search.py <consulta> [archivo_cursos] [archivo_indice] [max_resultados]")
        print("\nEjemplos:")
        print("python search.py 'programacion python'")
        print("python search.py 'gestion proyectos' curso.json curso.csv 5")
        sys.exit(1)

    query = sys.argv[1]
    courses_file = sys.argv[2] if len(sys.argv) > 2 else 'curso.json'
    index_file = sys.argv[3] if len(sys.argv) > 3 else 'curso.csv'
    max_results = int(sys.argv[4]) if len(sys.argv) > 4 else 10

    try:
        # Crear motor de busqueda para estadisticas
        engine = CourseSearchEngine(courses_file, index_file)

        print(f"=== MOTOR DE BUSQUEDA DE CURSOS ===")
        print(f"Consulta: '{query}'")

        # Mostrar estadisticas del indice
        stats = engine.get_statistics()
        print(f"\nEstadisticas del indice:")
        print(f"  - Cursos indexados: {stats['total_courses']}")
        print(f"  - Vocabulario: {stats['vocabulary_size']} palabras")
        print(f"  - Entradas en indice: {stats['index_entries']}")

        # Preguntar cantidad de resultados si no se especificó
        if len(sys.argv) < 5:
            try:
                user_input = input(f"\n¿Cuántos resultados desea ver? (max {stats['total_courses']}, por defecto {max_results}): ").strip()
                if user_input:
                    max_results = int(user_input)
                    if max_results > stats['total_courses']:
                        print(f"AVISO: Solo hay {stats['total_courses']} cursos disponibles. Mostrando {stats['total_courses']} resultados.")
                        max_results = stats['total_courses']
            except (ValueError, KeyboardInterrupt, EOFError):
                print(f"Usando valor por defecto: {max_results}")

        # Usar la función de búsqueda detallada unificada
        print(f"\nBuscando '{query}' con límite de {max_results} resultados...")

        results_count = search_detailed(query, courses_file, index_file, max_results)

        if results_count == 0:
            print("\nNo se encontraron cursos que coincidan con su búsqueda.")
            print("Sugerencias:")
            print("  - Intente con palabras más generales")
            print("  - Verifique la ortografía")
            print("  - Use sinónimos o términos relacionados")
        elif results_count < max_results:
            print(f"\nSe encontraron {results_count} cursos con score > 0 (solicitó {max_results})")
            print("Para más resultados, intente términos más generales.")

        # Mostrar también las URLs puras 
        print(f"\n{'='*60}")
        print("LISTADO DE URLs:")
        print(f"{'='*60}")

        urls = search(query, courses_file, index_file, max_results)
        if urls:
            for i, url in enumerate(urls, 1):
                print(f"{i}. {url}")
        else:
            print("No se encontraron URLs.")

    except Exception as e:
        print(f"Error durante la búsqueda: {e}")
        import traceback
        traceback.print_exc()