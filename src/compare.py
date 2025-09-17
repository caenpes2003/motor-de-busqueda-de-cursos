"""
Comparador de cursos - Calcula similitud entre cursos
Universidad Javeriana
"""

import json
import csv
import math
import re
import time
from typing import Dict, Set, List, Tuple
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Clase para almacenar métricas de rendimiento"""
    execution_time: float
    memory_usage_mb: float
    algorithm_name: str
    similarity_score: float
    course1_word_count: int
    course2_word_count: int
    shared_words: int
    vocabulary_overlap: float
    computational_complexity: str

    def print_metrics(self):
        """Imprime las métricas de rendimiento de forma legible"""
        print(f"\n{'='*50}")
        print(f"MÉTRICAS DE RENDIMIENTO - {self.algorithm_name.upper()}")
        print(f"{'='*50}")
        print(f"Similitud calculada:      {self.similarity_score:.4f}")
        print(f"Tiempo de ejecución:      {self.execution_time*1000:.2f} ms")
        print(f"Uso de memoria:           {self.memory_usage_mb:.2f} MB")
        print(f"Palabras curso 1:         {self.course1_word_count}")
        print(f"Palabras curso 2:         {self.course2_word_count}")
        print(f"Palabras compartidas:     {self.shared_words}")
        print(f"Solapamiento vocabulario: {self.vocabulary_overlap:.2%}")
        print(f"Complejidad computacional:{self.computational_complexity}")
        print(f"{'='*50}")


class CourseComparator:
    """Clase para comparar similitud entre cursos"""
    
    def __init__(self, courses_file: str, index_file: str, mapping_file: str = None):
        """
        Inicializa el comparador con los archivos generados por el crawler
        
        Args:
            courses_file: Archivo JSON con información de cursos
            index_file: Archivo CSV con índice palabra-curso
            mapping_file: Archivo JSON con mapeo de IDs (opcional)
        """
        self.courses = self.load_courses(courses_file)
        
        # Cargar mapeo de IDs si está disponible
        if mapping_file is None:
            mapping_file = index_file.replace('.csv', '_mapping.json')
        self.id_mapping = self.load_id_mapping(mapping_file)
        
        self.word_index = self.load_word_index(index_file)
        self.course_words = self.build_course_word_sets()
        self.vocabulary = set(self.word_index.keys())
        self.idf_scores = self.calculate_idf_scores()
     
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
            print(f"Error cargando mapeo de IDs: {e}")
            return {}
    
    def load_word_index(self, index_file: str) -> Dict[str, Set[str]]:
        """Carga el índice palabra-curso desde CSV"""
        word_index = defaultdict(set)
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter='|')
                for row in reader:
                    if len(row) == 2:
                        course_id, word = row
                        word_index[word].add(course_id)
        except Exception as e:
            print(f"Error cargando índice: {e}")
        
        return dict(word_index)
    
    def build_course_word_sets(self) -> Dict[str, Set[str]]:
        """Construye conjuntos de palabras para cada curso usando mapeo de IDs"""
        course_words = defaultdict(set)
        
        for word, formatted_course_ids in self.word_index.items():
            for formatted_id in formatted_course_ids:
                # Convertir ID formateado (Curso_0001) a ID original
                original_id = self.id_mapping.get(formatted_id, formatted_id)
                if original_id in self.courses:
                    course_words[original_id].add(word)
        
        return dict(course_words)

    def _get_memory_usage(self) -> float:
        """Calcula el uso actual de memoria en MB"""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Si psutil no está disponible, usar estimación básica
            return 0.0

    def _calculate_performance_metrics(self, course1: str, course2: str,
                                     similarity_score: float, execution_time: float,
                                     algorithm_name: str) -> PerformanceMetrics:
        """Calcula métricas de rendimiento para una comparación"""
        words1 = self.course_words.get(course1, set())
        words2 = self.course_words.get(course2, set())

        shared_words = len(words1.intersection(words2))
        total_unique_words = len(words1.union(words2))
        vocabulary_overlap = shared_words / total_unique_words if total_unique_words > 0 else 0.0

        # Determinar complejidad computacional
        complexity_map = {
            'jaccard': 'O(n + m)',
            'cosine': 'O(V)',  # V = tamaño del vocabulario
            'overlap': 'O(n + m)',
            'semantic': 'O(n + m + k)',  # k = número de patrones regex
            'combined': 'O(V + n + m + k)'
        }

        memory_usage = self._get_memory_usage()

        return PerformanceMetrics(
            execution_time=execution_time,
            memory_usage_mb=memory_usage,
            algorithm_name=algorithm_name,
            similarity_score=similarity_score,
            course1_word_count=len(words1),
            course2_word_count=len(words2),
            shared_words=shared_words,
            vocabulary_overlap=vocabulary_overlap,
            computational_complexity=complexity_map.get(algorithm_name, 'O(?)')
        )

    def calculate_idf_scores(self) -> Dict[str, float]:
        """Calcula scores IDF para cada palabra"""
        total_courses = len(self.courses)
        idf_scores = {}
        
        for word, course_ids in self.word_index.items():
            df = len(course_ids)  # document frequency
            idf = math.log(total_courses / df) if df > 0 else 0
            idf_scores[word] = idf
        
        return idf_scores
    
    def jaccard_similarity(self, course1: str, course2: str) -> float:
        """
        Calcula similitud de Jaccard entre dos cursos
        
        Args:
            course1: ID del primer curso
            course2: ID del segundo curso
            
        Returns:
            Similitud de Jaccard [0,1]
        """
        words1 = self.course_words.get(course1, set())
        words2 = self.course_words.get(course2, set())
        
        if not words1 and not words2:
            return 1.0  # Ambos vacíos
        if not words1 or not words2:
            return 0.0  # Uno vacío
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def cosine_similarity_tfidf(self, course1: str, course2: str) -> float:
        """
        Calcula similitud coseno usando vectores TF-IDF
        
        Args:
            course1: ID del primer curso
            course2: ID del segundo curso
            
        Returns:
            Similitud coseno [0,1]
        """
        words1 = self.course_words.get(course1, set())
        words2 = self.course_words.get(course2, set())
        
        if not words1 or not words2:
            return 0.0
        
        # Calcular vectores TF-IDF
        vector1 = self.get_tfidf_vector(course1, words1)
        vector2 = self.get_tfidf_vector(course2, words2)
        
        # Calcular similitud coseno
        dot_product = sum(vector1.get(word, 0) * vector2.get(word, 0) 
                         for word in self.vocabulary)
        
        norm1 = math.sqrt(sum(score ** 2 for score in vector1.values()))
        norm2 = math.sqrt(sum(score ** 2 for score in vector2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_tfidf_vector(self, course_id: str, words: Set[str]) -> Dict[str, float]:
        """Calcula vector TF-IDF para un curso"""
        _ = course_id  # Parámetro reservado para futuras expansiones
        vector = {}

        for word in words:
            tf = 1.0  # En nuestro caso, cada palabra aparece una vez por curso
            idf = self.idf_scores.get(word, 0)
            vector[word] = tf * idf

        return vector
    
    def overlap_coefficient(self, course1: str, course2: str) -> float:
        """
        Calcula coeficiente de solapamiento (overlap coefficient)
        
        Args:
            course1: ID del primer curso
            course2: ID del segundo curso
            
        Returns:
            Coeficiente de solapamiento [0,1]
        """
        words1 = self.course_words.get(course1, set())
        words2 = self.course_words.get(course2, set())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        min_size = min(len(words1), len(words2))
        
        return intersection / min_size if min_size > 0 else 0.0
    
    def semantic_similarity(self, course1: str, course2: str) -> float:
        """
        Calcula similitud semántica basada en coincidencias de palabras clave
        y contexto temático
        
        Args:
            course1: ID del primer curso
            course2: ID del segundo curso
            
        Returns:
            Similitud semántica [0,1]
        """
        # Obtener información completa de los cursos
        info1 = self.courses.get(course1, {})
        info2 = self.courses.get(course2, {})
        
        if not info1 or not info2:
            return 0.0
        
        # Extraer palabras de títulos y descripciones
        text1 = (info1.get('title', '') + ' ' + info1.get('description', '')).lower()
        text2 = (info2.get('title', '') + ' ' + info2.get('description', '')).lower()
        
        # Identificar palabras temáticas importantes
        keywords1 = self.extract_keywords(text1)
        keywords2 = self.extract_keywords(text2)
        
        # Calcular similitud ponderada
        keyword_similarity = self.calculate_keyword_similarity(keywords1, keywords2)
        word_similarity = self.jaccard_similarity(course1, course2)
        
        # Combinar métricas con pesos
        return 0.6 * keyword_similarity + 0.4 * word_similarity
    
    def extract_keywords(self, text: str) -> Set[str]:
        """Extrae palabras clave relevantes del texto"""
        # Palabras que indican área temática
        theme_patterns = [
            r'\b(programaci[oó]n|desarrollo|software|web|python|java|javascript)\b',
            r'\b(marketing|publicidad|ventas|digital|redes sociales)\b',
            r'\b(administraci[oó]n|gesti[oó]n|empresarial|negocios|finanzas)\b',
            r'\b(dise[ñn]o|gr[aá]fico|visual|creatividad|arte)\b',
            r'\b(salud|medicina|cl[ií]nica|terapia|bienestar)\b',
            r'\b(educaci[oó]n|pedagog[ií]a|ense[ñn]anza|aprendizaje)\b',
            r'\b(derecho|legal|jur[ií]dico|normatividad)\b',
            r'\b(fotograf[ií]a|imagen|audiovisual|multimedia)\b'
        ]
        
        keywords = set()
        for pattern in theme_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            keywords.update(matches)
        
        return keywords
    
    def calculate_keyword_similarity(self, keywords1: Set[str], keywords2: Set[str]) -> float:
        """Calcula similitud entre conjuntos de palabras clave"""
        if not keywords1 and not keywords2:
            return 1.0
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))
        
        return intersection / union if union > 0 else 0.0
    
    def compare(self, course1: str, course2: str, method: str = 'combined',
                show_metrics: bool = False) -> float:
        """
        Función principal de comparación entre dos cursos

        Args:
            course1: ID del primer curso
            course2: ID del segundo curso
            method: Método de similitud ('jaccard', 'cosine', 'overlap', 'semantic', 'combined')
            show_metrics: Si True, imprime las métricas de rendimiento

        Returns:
            Similitud entre cursos [0,1]
        """
        if course1 == course2:
            return 1.0

        if course1 not in self.courses or course2 not in self.courses:
            return 0.0

        # Medir tiempo de ejecución
        start_time = time.time()

        if method == 'jaccard':
            similarity = self.jaccard_similarity(course1, course2)
        elif method == 'cosine':
            similarity = self.cosine_similarity_tfidf(course1, course2)
        elif method == 'overlap':
            similarity = self.overlap_coefficient(course1, course2)
        elif method == 'semantic':
            similarity = self.semantic_similarity(course1, course2)
        elif method == 'combined':
            # Combinar múltiples métricas para mejor precisión
            jaccard = self.jaccard_similarity(course1, course2)
            cosine = self.cosine_similarity_tfidf(course1, course2)
            semantic = self.semantic_similarity(course1, course2)

            # Pesos ajustados empíricamente
            similarity = 0.3 * jaccard + 0.3 * cosine + 0.4 * semantic
        else:
            raise ValueError(f"Método desconocido: {method}")

        end_time = time.time()
        execution_time = end_time - start_time

        # Calcular y mostrar métricas si se solicita
        if show_metrics:
            metrics = self._calculate_performance_metrics(
                course1, course2, similarity, execution_time, method
            )
            metrics.print_metrics()

        return similarity
    
    def find_similar_courses(self, course_id: str, top_k: int = 5, method: str = 'combined') -> List[Tuple[str, float]]:
        """
        Encuentra los cursos más similares a uno dado
        
        Args:
            course_id: ID del curso de referencia
            top_k: Número de cursos similares a retornar
            method: Método de similitud a usar
            
        Returns:
            Lista de tuplas (course_id, similarity_score) ordenada por similitud
        """
        if course_id not in self.courses:
            return []
        
        similarities = []
        for other_course_id in self.courses:
            if other_course_id != course_id:
                similarity = self.compare(course_id, other_course_id, method)
                similarities.append((other_course_id, similarity))
        
        # Ordenar por similitud descendente
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]

    def compare_algorithms_performance(self, course1: str, course2: str) -> Dict[str, PerformanceMetrics]:
        """
        Compara el rendimiento de todos los algoritmos de similitud disponibles

        Args:
            course1: ID del primer curso
            course2: ID del segundo curso

        Returns:
            Diccionario con métricas de rendimiento para cada algoritmo
        """
        algorithms = ['jaccard', 'cosine', 'overlap', 'semantic', 'combined']
        performance_results = {}

        print(f"\n{'='*80}")
        print(f"COMPARACIÓN DE RENDIMIENTO ENTRE ALGORITMOS")
        print(f"Curso 1: {course1}")
        print(f"Curso 2: {course2}")
        print(f"{'='*80}")

        for algorithm in algorithms:
            start_time = time.time()
            similarity = self.compare(course1, course2, method=algorithm, show_metrics=False)
            end_time = time.time()
            execution_time = end_time - start_time

            metrics = self._calculate_performance_metrics(
                course1, course2, similarity, execution_time, algorithm
            )
            performance_results[algorithm] = metrics
            metrics.print_metrics()

        # Resumen comparativo
        print(f"\n{'='*80}")
        print(f"RESUMEN COMPARATIVO DE ALGORITMOS")
        print(f"{'='*80}")
        print(f"{'Algoritmo':<12} {'Similitud':<12} {'Tiempo(ms)':<12} {'Memoria(MB)':<12} {'Complejidad':<15}")
        print(f"{'-'*80}")

        for algorithm, metrics in performance_results.items():
            print(f"{algorithm:<12} {metrics.similarity_score:<12.4f} "
                  f"{metrics.execution_time*1000:<12.2f} {metrics.memory_usage_mb:<12.2f} "
                  f"{metrics.computational_complexity:<15}")

        return performance_results

    def get_course_info(self, course_id: str) -> Dict:
        """Obtiene información completa de un curso"""
        return self.courses.get(course_id, {})
    
    def list_all_courses(self) -> List[str]:
        """Retorna lista de todos los IDs de cursos disponibles"""
        return list(self.courses.keys())


def compare(course1: str, course2: str, courses_file: str = 'curso.json',
           index_file: str = 'curso.csv', method: str = 'combined',
           show_metrics: bool = False) -> float:
    """
    Función de comparación standalone requerida por el laboratorio

    Args:
        course1: ID del primer curso
        course2: ID del segundo curso
        courses_file: Archivo JSON con cursos
        index_file: Archivo CSV con índice
        method: Método de similitud
        show_metrics: Si True, muestra las métricas de rendimiento

    Returns:
        Similitud entre cursos [0,1]
    """
    comparator = CourseComparator(courses_file, index_file)
    return comparator.compare(course1, course2, method, show_metrics)


if __name__ == "__main__":
    # Ejemplo de uso
    import sys

    if len(sys.argv) < 3:
        print("Uso: python compare.py <course1> <course2> [courses_file] [index_file] [--metrics] [--compare-all]")
        print("\nEjemplos:")
        print("python compare.py propiedad-horizontal marketing-digital-avanzado")
        print("python compare.py propiedad-horizontal marketing-digital-avanzado --metrics")
        print("python compare.py propiedad-horizontal marketing-digital-avanzado --compare-all")
        print("\nOpciones:")
        print("  --metrics     Mostrar métricas de rendimiento detalladas")
        print("  --compare-all Comparar rendimiento de todos los algoritmos")
        sys.exit(1)

    course1 = sys.argv[1]
    course2 = sys.argv[2]

    # Procesamiento de argumentos
    show_metrics = '--metrics' in sys.argv
    compare_all = '--compare-all' in sys.argv

    # Archivos (excluyendo las flags)
    remaining_args = [arg for arg in sys.argv[3:] if not arg.startswith('--')]
    courses_file = remaining_args[0] if len(remaining_args) > 0 else 'curso.json'
    index_file = remaining_args[1] if len(remaining_args) > 1 else 'curso.csv'

    try:
        comparator = CourseComparator(courses_file, index_file)

        print(f"=== COMPARACIÓN DE CURSOS ===")
        print(f"Curso 1: {course1}")
        print(f"Curso 2: {course2}")

        # Mostrar información de los cursos
        info1 = comparator.get_course_info(course1)
        info2 = comparator.get_course_info(course2)

        if info1:
            print(f"\nTítulo 1: {info1.get('title', 'N/A')}")
        if info2:
            print(f"Título 2: {info2.get('title', 'N/A')}")

        if compare_all:
            # Comparar rendimiento de todos los algoritmos
            performance_results = comparator.compare_algorithms_performance(course1, course2)
        else:
            # Calcular similitudes con diferentes métodos
            methods = ['jaccard', 'cosine', 'semantic', 'combined']

            print(f"\n=== RESULTADOS DE SIMILITUD ===")
            for method in methods:
                similarity = comparator.compare(course1, course2, method, show_metrics)
                if not show_metrics:  # Solo mostrar el resultado si no se mostraron métricas detalladas
                    print(f"{method.capitalize():12}: {similarity:.4f}")

        # Encontrar cursos similares al primero
        print(f"\n=== CURSOS SIMILARES A '{course1}' ===")
        similar = comparator.find_similar_courses(course1, top_k=3)
        for i, (similar_id, score) in enumerate(similar, 1):
            similar_info = comparator.get_course_info(similar_id)
            title = similar_info.get('title', similar_id)
            print(f"{i}. {title} (similitud: {score:.4f})")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()