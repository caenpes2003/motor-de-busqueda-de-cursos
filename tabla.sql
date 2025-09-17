-- =====================================================
-- LABORATORIO 2 - MOTOR DE BÚSQUEDA DE CURSOS
-- Universidad Javeriana - Recuperación de Información
-- =====================================================

-- Crear base de datos
CREATE DATABASE IF NOT EXISTS motor_busqueda_cursos
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE motor_busqueda_cursos;

-- =====================================================
-- TABLA PRINCIPAL: Salida del rastreador web
-- Contiene el índice completo generado por crawler.py
-- Formato de entrada: curso_id|palabra (separado por |)
-- =====================================================

DROP TABLE IF EXISTS indice_rastreador;

CREATE TABLE indice_rastreador (
    id INT AUTO_INCREMENT PRIMARY KEY,
    curso_id VARCHAR(255) NOT NULL COMMENT 'ID del curso (ej: propiedad-horizontal)',
    palabra VARCHAR(100) NOT NULL COMMENT 'Palabra indexada del curso',
    url VARCHAR(500) COMMENT 'URL completa del curso',
    titulo TEXT COMMENT 'Título completo del curso',
    descripcion TEXT COMMENT 'Descripción del curso',
    fecha_indexado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Índices optimizados para búsquedas por palabra (requerimiento principal)
    INDEX idx_palabra (palabra),
    INDEX idx_curso_id (curso_id),
    INDEX idx_palabra_curso (palabra, curso_id),
    INDEX idx_url (url),

    -- Evitar duplicados palabra-curso
    UNIQUE KEY unique_palabra_curso (curso_id, palabra)
) ENGINE=InnoDB
COMMENT='Tabla con la salida completa del rastreador - Requerimiento Lab 2';

-- =====================================================
-- TABLA AUXILIAR: Información completa de cursos
-- Para optimizar consultas que requieren datos del curso
-- =====================================================

DROP TABLE IF EXISTS cursos;

CREATE TABLE cursos (
    curso_id VARCHAR(255) PRIMARY KEY,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    url VARCHAR(500) NOT NULL,
    duracion VARCHAR(100),
    nivel VARCHAR(50),
    precio VARCHAR(100),
    fecha_inicio VARCHAR(100),
    fecha_rastreo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_titulo (titulo(100)),
    INDEX idx_url_curso (url)
) ENGINE=InnoDB
COMMENT='Información completa de cursos extraída por el rastreador';

-- =====================================================
-- PROCEDIMIENTO: Carga masiva desde archivo CSV
-- Automatiza la carga de la salida del rastreador
-- =====================================================

DELIMITER //

DROP PROCEDURE IF EXISTS CargarIndiceRastreador //

CREATE PROCEDURE CargarIndiceRastreador(
    IN archivo_csv VARCHAR(500)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- Limpiar tabla antes de carga
    TRUNCATE TABLE indice_rastreador;

    -- Cargar datos desde CSV formato: curso_id|palabra
    SET @sql = CONCAT('LOAD DATA LOCAL INFILE ''', archivo_csv, '''
        INTO TABLE indice_rastreador (curso_id, palabra)
        FIELDS TERMINATED BY ''|''
        LINES TERMINATED BY ''\\n''
        IGNORE 1 LINES');

    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;

    -- Actualizar URLs y títulos desde tabla de cursos (si existe)
    UPDATE indice_rastreador ir
    JOIN cursos c ON ir.curso_id = c.curso_id
    SET ir.url = c.url, ir.titulo = c.titulo, ir.descripcion = c.descripcion;

    COMMIT;

    -- Mostrar estadísticas de carga
    SELECT
        COUNT(*) as total_registros_cargados,
        COUNT(DISTINCT curso_id) as cursos_indexados,
        COUNT(DISTINCT palabra) as palabras_unicas
    FROM indice_rastreador;

END //

DELIMITER ;

-- =====================================================
-- DATOS DE MUESTRA PARA DEMOSTRACIÓN
-- Simula la salida típica del rastreador web
-- =====================================================

-- Insertar cursos de muestra
INSERT IGNORE INTO cursos (curso_id, titulo, url, descripcion) VALUES
('programacion-web-frontend', 'Programación Web Frontend Avanzada',
 'https://educacionvirtual.javeriana.edu.co/programacion-web-frontend',
 'Curso completo de desarrollo web frontend con HTML5, CSS3, JavaScript y React'),

('inteligencia-artificial-aplicada', 'Inteligencia Artificial Aplicada',
 'https://educacionvirtual.javeriana.edu.co/inteligencia-artificial-aplicada',
 'Fundamentos y aplicaciones de IA, machine learning y redes neuronales'),

('gestion-proyectos-agiles', 'Gestión de Proyectos con Metodologías Ágiles',
 'https://educacionvirtual.javeriana.edu.co/gestion-proyectos-agiles',
 'Scrum, Kanban y metodologías ágiles para gestión efectiva de proyectos'),

('marketing-digital-estrategico', 'Marketing Digital y Estrategias de Comunicación',
 'https://educacionvirtual.javeriana.edu.co/marketing-digital-estrategico',
 'SEO, SEM, redes sociales y análisis de métricas digitales'),

('diseno-experiencia-usuario', 'Diseño de Experiencia de Usuario (UX/UI)',
 'https://educacionvirtual.javeriana.edu.co/diseno-experiencia-usuario',
 'Prototipado, investigación de usuarios y diseño centrado en el usuario');

-- Insertar índice de palabras (simula salida del crawler)
INSERT IGNORE INTO indice_rastreador (curso_id, palabra) VALUES
-- Programación Web Frontend
('programacion-web-frontend', 'programacion'),
('programacion-web-frontend', 'web'),
('programacion-web-frontend', 'frontend'),
('programacion-web-frontend', 'html'),
('programacion-web-frontend', 'css'),
('programacion-web-frontend', 'javascript'),
('programacion-web-frontend', 'react'),
('programacion-web-frontend', 'desarrollo'),

-- Inteligencia Artificial
('inteligencia-artificial-aplicada', 'inteligencia'),
('inteligencia-artificial-aplicada', 'artificial'),
('inteligencia-artificial-aplicada', 'machine'),
('inteligencia-artificial-aplicada', 'learning'),
('inteligencia-artificial-aplicada', 'redes'),
('inteligencia-artificial-aplicada', 'neuronales'),
('inteligencia-artificial-aplicada', 'algoritmos'),

-- Gestión de Proyectos
('gestion-proyectos-agiles', 'gestion'),
('gestion-proyectos-agiles', 'proyectos'),
('gestion-proyectos-agiles', 'agiles'),
('gestion-proyectos-agiles', 'scrum'),
('gestion-proyectos-agiles', 'kanban'),
('gestion-proyectos-agiles', 'metodologias'),

-- Marketing Digital
('marketing-digital-estrategico', 'marketing'),
('marketing-digital-estrategico', 'digital'),
('marketing-digital-estrategico', 'seo'),
('marketing-digital-estrategico', 'sem'),
('marketing-digital-estrategico', 'redes'),
('marketing-digital-estrategico', 'sociales'),
('marketing-digital-estrategico', 'metricas'),

-- Diseño UX/UI
('diseno-experiencia-usuario', 'diseno'),
('diseno-experiencia-usuario', 'experiencia'),
('diseno-experiencia-usuario', 'usuario'),
('diseno-experiencia-usuario', 'prototipado'),
('diseno-experiencia-usuario', 'investigacion'),
('diseno-experiencia-usuario', 'centrado');

-- Actualizar URLs y títulos desde tabla de cursos
UPDATE indice_rastreador ir
JOIN cursos c ON ir.curso_id = c.curso_id
SET ir.url = c.url, ir.titulo = c.titulo, ir.descripcion = c.descripcion;

-- =====================================================
-- VERIFICACIÓN DE CARGA Y ESTADÍSTICAS
-- =====================================================

-- Mostrar estadísticas del índice cargado
SELECT
    'ESTADÍSTICAS DEL ÍNDICE RASTREADOR' as info,
    COUNT(*) as total_registros,
    COUNT(DISTINCT curso_id) as cursos_indexados,
    COUNT(DISTINCT palabra) as palabras_unicas,
    COUNT(DISTINCT url) as urls_unicas
FROM indice_rastreador;

-- Mostrar muestra de datos cargados
SELECT
    'MUESTRA DE DATOS INDEXADOS' as info,
    curso_id,
    titulo,
    palabra,
    url
FROM indice_rastreador
ORDER BY curso_id, palabra
LIMIT 10;