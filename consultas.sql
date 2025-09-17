-- =====================================================
-- LABORATORIO 2 - CONSULTAS PARA IDENTIFICAR URLs POR PALABRA
-- Universidad Javeriana - Recuperación de Información
-- =====================================================

USE motor_busqueda_cursos;

-- =====================================================
-- REQUERIMIENTO: Consultas para identificar en cuál URL se encuentra una palabra dada
-- =====================================================

-- CONSULTA PRINCIPAL 1: Encontrar URLs de cursos que contengan una palabra específica
-- Cumple el requerimiento del laboratorio: "identificar en cuál URL se encuentra una palabra dada"

SELECT DISTINCT
    ir.url AS url_curso,
    ir.titulo AS titulo_curso,
    ir.curso_id AS identificador_curso,
    ir.palabra AS palabra_encontrada
FROM indice_rastreador ir
WHERE ir.palabra = 'programacion'  -- CAMBIAR 'programacion' por la palabra buscada
ORDER BY ir.titulo;

-- EJEMPLO DE USO:
-- Para buscar "javascript": cambiar 'programacion' por 'javascript'
-- Para buscar "gestion": cambiar 'programacion' por 'gestion'

-- =====================================================
-- CONSULTAS ADICIONALES PARA BÚSQUEDA AVANZADA POR PALABRA
-- =====================================================

-- CONSULTA 2: Búsqueda con ranking por relevancia
-- Útil para ordenar resultados por orden de relevancia (cuántas veces aparece la palabra)
SELECT
    ir.url AS url_curso,
    ir.titulo AS titulo_curso,
    ir.curso_id AS identificador_curso,
    COUNT(*) AS relevancia_score
FROM indice_rastreador ir
WHERE ir.palabra = 'digital'  -- CAMBIAR por palabra buscada
GROUP BY ir.url, ir.titulo, ir.curso_id
ORDER BY relevancia_score DESC, ir.titulo;

-- CONSULTA 3: Búsqueda múltiple (intersección de palabras)
-- Encuentra URLs que contengan TODAS las palabras especificadas
SELECT
    ir.url AS url_curso,
    ir.titulo AS titulo_curso,
    ir.curso_id AS identificador_curso,
    GROUP_CONCAT(DISTINCT ir.palabra ORDER BY ir.palabra) AS palabras_coincidentes,
    COUNT(DISTINCT ir.palabra) AS num_coincidencias
FROM indice_rastreador ir
WHERE ir.palabra IN ('web', 'programacion', 'javascript')  -- CAMBIAR por palabras buscadas
GROUP BY ir.url, ir.titulo, ir.curso_id
HAVING COUNT(DISTINCT ir.palabra) = 3  -- Debe contener TODAS las 3 palabras
ORDER BY ir.titulo;

-- CONSULTA 4: Búsqueda múltiple (unión de palabras)
-- Encuentra URLs que contengan AL MENOS UNA de las palabras especificadas
SELECT
    ir.url AS url_curso,
    ir.titulo AS titulo_curso,
    ir.curso_id AS identificador_curso,
    GROUP_CONCAT(DISTINCT ir.palabra ORDER BY ir.palabra) AS palabras_encontradas,
    COUNT(DISTINCT ir.palabra) AS num_coincidencias
FROM indice_rastreador ir
WHERE ir.palabra IN ('inteligencia', 'artificial', 'machine', 'learning')  -- CAMBIAR por palabras buscadas
GROUP BY ir.url, ir.titulo, ir.curso_id
HAVING COUNT(DISTINCT ir.palabra) >= 1  -- Al menos 1 de las palabras
ORDER BY num_coincidencias DESC, ir.titulo;

-- CONSULTA 5: Búsqueda aproximada por prefijo
-- Encuentra palabras que empiecen con cierto texto (útil para autocompletado)
SELECT DISTINCT
    ir.url AS url_curso,
    ir.titulo AS titulo_curso,
    ir.palabra AS palabra_encontrada
FROM indice_rastreador ir
WHERE ir.palabra LIKE 'program%'  -- CAMBIAR 'program' por prefijo buscado
ORDER BY ir.palabra, ir.titulo;

-- =====================================================
-- EJEMPLOS PRÁCTICOS PARA DEMOSTRACIÓN
-- Casos de uso reales con los datos de muestra cargados
-- =====================================================

-- EJEMPLO 1: ¿En qué URLs se encuentra la palabra "programacion"?
-- Respuesta directa al requerimiento del laboratorio
SELECT DISTINCT
    ir.url AS url_encontrada,
    ir.titulo AS curso_encontrado
FROM indice_rastreador ir
WHERE ir.palabra = 'programacion'
ORDER BY ir.titulo;

-- EJEMPLO 2: ¿En qué URLs se encuentra la palabra "inteligencia"?
SELECT DISTINCT
    ir.url AS url_encontrada,
    ir.titulo AS curso_encontrado
FROM indice_rastreador ir
WHERE ir.palabra = 'inteligencia'
ORDER BY ir.titulo;

-- EJEMPLO 3: ¿En qué URLs se encuentran las palabras relacionadas con "diseño"?
SELECT DISTINCT
    ir.url AS url_encontrada,
    ir.titulo AS curso_encontrado,
    ir.palabra AS palabra_relacionada
FROM indice_rastreador ir
WHERE ir.palabra IN ('diseno', 'experiencia', 'usuario', 'prototipado')
ORDER BY ir.titulo, ir.palabra;

-- EJEMPLO 4: Búsqueda múltiple - Cursos que contienen tanto "redes" como "sociales"
SELECT
    ir.url AS url_encontrada,
    ir.titulo AS curso_encontrado,
    GROUP_CONCAT(DISTINCT ir.palabra ORDER BY ir.palabra) AS palabras_coincidentes
FROM indice_rastreador ir
WHERE ir.palabra IN ('redes', 'sociales')
GROUP BY ir.url, ir.titulo, ir.curso_id
HAVING COUNT(DISTINCT ir.palabra) = 2  -- Ambas palabras deben estar presentes
ORDER BY ir.titulo;

-- EJEMPLO 5: Búsqueda aproximada - Palabras que empiecen con "gest"
SELECT DISTINCT
    ir.url AS url_encontrada,
    ir.titulo AS curso_encontrado,
    ir.palabra AS palabra_encontrada
FROM indice_rastreador ir
WHERE ir.palabra LIKE 'gest%'
ORDER BY ir.palabra, ir.titulo;

-- =====================================================
-- CONSULTAS DE VERIFICACIÓN Y ESTADÍSTICAS
-- =====================================================

-- VERIFICACIÓN 1: Comprobar que la tabla contiene datos
SELECT
    'Verificación de contenido de la tabla' AS tipo_consulta,
    COUNT(*) AS total_registros,
    COUNT(DISTINCT curso_id) AS cursos_diferentes,
    COUNT(DISTINCT palabra) AS palabras_unicas,
    COUNT(DISTINCT url) AS urls_diferentes
FROM indice_rastreador;

-- VERIFICACIÓN 2: Mostrar todas las palabras indexadas para un curso específico
SELECT
    ir.curso_id,
    ir.titulo,
    ir.url,
    GROUP_CONCAT(ir.palabra ORDER BY ir.palabra SEPARATOR ', ') AS vocabulario_indexado
FROM indice_rastreador ir
WHERE ir.curso_id = 'programacion-web-frontend'
GROUP BY ir.curso_id, ir.titulo, ir.url;

-- VERIFICACIÓN 3: Estadísticas - Palabras más frecuentes (aparecen en más cursos)
SELECT
    palabra,
    COUNT(DISTINCT curso_id) AS num_cursos_contienen_palabra,
    COUNT(*) AS total_apariciones,
    ROUND(COUNT(DISTINCT curso_id) * 100.0 / (SELECT COUNT(DISTINCT curso_id) FROM indice_rastreador), 2) AS porcentaje_cobertura
FROM indice_rastreador
GROUP BY palabra
ORDER BY num_cursos_contienen_palabra DESC, palabra
LIMIT 15;

-- VERIFICACIÓN 4: Cursos con más palabras indexadas
SELECT
    ir.curso_id,
    ir.titulo,
    ir.url,
    COUNT(DISTINCT ir.palabra) AS num_palabras_indexadas
FROM indice_rastreador ir
GROUP BY ir.curso_id, ir.titulo, ir.url
ORDER BY num_palabras_indexadas DESC, ir.titulo;

-- =====================================================
-- CONSULTAS PARAMETRIZADAS PARA INTEGRACIÓN CON APLICACIONES
-- =====================================================

-- TEMPLATE 1: Consulta parametrizada para buscar una palabra específica
-- Usar con prepared statements: SET @palabra_buscar = 'valor';
SET @palabra_buscar = 'javascript';
SELECT DISTINCT
    ir.url AS url_resultado,
    ir.titulo AS titulo_resultado,
    ir.curso_id AS id_resultado
FROM indice_rastreador ir
WHERE ir.palabra = @palabra_buscar
ORDER BY ir.titulo;

-- TEMPLATE 2: Consulta parametrizada para búsqueda múltiple
-- Para uso programático con múltiples palabras
PREPARE consulta_multiple FROM '
    SELECT
        ir.url AS url_resultado,
        ir.titulo AS titulo_resultado,
        COUNT(DISTINCT ir.palabra) AS coincidencias
    FROM indice_rastreador ir
    WHERE ir.palabra IN (?)
    GROUP BY ir.url, ir.titulo, ir.curso_id
    ORDER BY coincidencias DESC, ir.titulo
';

-- =====================================================
-- CONSULTA FINAL: Demostración completa del requerimiento
-- "Archivo SQL con consultas para identificar en cuál URL se encuentra una palabra dada"
-- =====================================================

-- Esta consulta cumple exactamente el requerimiento del laboratorio:
-- Dado una palabra, identifica en qué URL(s) se encuentra

SELECT
    '*** CUMPLIMIENTO DEL REQUERIMIENTO DEL LABORATORIO ***' AS info,
    'Consulta para identificar en cuál URL se encuentra una palabra dada' AS descripcion;

SELECT
    ir.palabra AS palabra_buscada,
    ir.url AS url_donde_se_encuentra,
    ir.titulo AS titulo_del_curso,
    ir.curso_id AS identificador_del_curso
FROM indice_rastreador ir
WHERE ir.palabra = 'web'  -- CAMBIAR POR CUALQUIER PALABRA BUSCADA
ORDER BY ir.url, ir.titulo;

-- Para buscar cualquier otra palabra, simplemente cambiar 'web' por la palabra deseada
-- Ejemplos: 'programacion', 'inteligencia', 'marketing', 'gestion', etc.