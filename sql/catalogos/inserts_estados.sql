-- =====================================================================
-- INSERTS DE ESTADOS DE MERCADERÍA ARGENTINA - AFIP
-- =====================================================================
-- Fuente: estados.csv
-- Generado: 2025-10-11
-- Total registros: 6 estados (limpiados de duplicados)
-- =====================================================================

-- Verificar estructura de la tabla antes de insertar
-- \d Estados;

-- Limpiar datos existentes (opcional)
-- DELETE FROM Estados;

-- Insertar todos los estados según estructura real de la tabla
-- Estructura: codigo VARCHAR(5), descripcion VARCHAR(100)
-- Nota: Se consolidaron múltiples versiones del CSV original
INSERT INTO Estados (codigo, descripcion) VALUES

-- ESTADOS DE MERCADERÍA PARA COMERCIO EXTERIOR
('1', 'NUEVO SIN USO ARGENTINO'),
('2', 'NUEVO SIN USO IMPORTADO'),
('3', 'USADO ARGENTINO INCLUYE REACONDICIONADO'),
('4', 'USADO IMPORTADO INCLUYE REACONDICIONADO'),
('5', 'SIN USO ARGENTINO'),
('6', 'SIN USO IMPORTADO');

-- =====================================================================
-- VERIFICACIÓN DE INSERCIÓN
-- =====================================================================

-- Contar registros insertados
SELECT COUNT(*) as total_estados FROM Estados;

-- Mostrar todos los estados
SELECT codigo, descripcion FROM Estados ORDER BY codigo;

-- Mostrar estados por origen (argentino vs importado)
SELECT 
    CASE 
        WHEN descripcion ILIKE '%argentino%' THEN 'ORIGEN_ARGENTINO'
        WHEN descripcion ILIKE '%importado%' THEN 'ORIGEN_IMPORTADO'
        ELSE 'OTROS'
    END as origen,
    COUNT(*) as cantidad_estados,
    STRING_AGG(codigo || ': ' || descripcion, E'\n' ORDER BY codigo) as detalle
FROM Estados
GROUP BY 
    CASE 
        WHEN descripcion ILIKE '%argentino%' THEN 'ORIGEN_ARGENTINO'
        WHEN descripcion ILIKE '%importado%' THEN 'ORIGEN_IMPORTADO'
        ELSE 'OTROS'
    END
ORDER BY origen;

-- Mostrar estados por condición (nuevo vs usado vs sin uso)
SELECT 
    CASE 
        WHEN descripcion ILIKE '%nuevo%' THEN 'NUEVO'
        WHEN descripcion ILIKE '%usado%' THEN 'USADO'
        WHEN descripcion ILIKE '%sin uso%' THEN 'SIN_USO'
        ELSE 'OTROS'
    END as condicion,
    COUNT(*) as cantidad_estados,
    STRING_AGG(codigo || ': ' || descripcion, E'\n' ORDER BY codigo) as detalle
FROM Estados
GROUP BY 
    CASE 
        WHEN descripcion ILIKE '%nuevo%' THEN 'NUEVO'
        WHEN descripcion ILIKE '%usado%' THEN 'USADO'
        WHEN descripcion ILIKE '%sin uso%' THEN 'SIN_USO'
        ELSE 'OTROS'
    END
ORDER BY condicion;

-- Verificar que no hay duplicados
SELECT codigo, COUNT(*) FROM Estados GROUP BY codigo HAVING COUNT(*) > 1;

-- Comentarios finales
COMMENT ON TABLE Estados IS 'Estados de mercadería para comercio exterior Argentina - 6 registros consolidados. Fuente: estados.csv AFIP actualizado 2025-10-11';

-- =====================================================================
-- NOTAS DE IMPLEMENTACIÓN
-- =====================================================================

/*
ESTADOS DE MERCADERÍA EN COMERCIO EXTERIOR:

Los estados de mercadería son clasificaciones obligatorias que determinan:
- El origen de la mercadería (Argentina vs Importada)
- La condición de uso (Nuevo, Usado, Sin Uso)
- Tratamiento arancelario diferenciado
- Requisitos de verificación

CÓDIGOS Y SIGNIFICADOS:

MERCADERÍA NUEVA:
- 1: NUEVO SIN USO ARGENTINO
  * Mercadería fabricada en Argentina, nueva, sin usar
  * Primera comercialización
  * Régimen arancelario preferencial para producto nacional

- 2: NUEVO SIN USO IMPORTADO  
  * Mercadería importada, nueva, sin usar
  * Primera comercialización en Argentina
  * Sujeta a aranceles de importación completos

MERCADERÍA USADA (incluye reacondicionada):
- 3: USADO ARGENTINO INCLUYE REACONDICIONADO
  * Mercadería de origen argentino previamente usada
  * Incluye productos reacondicionados/refabricados en Argentina
  * Puede tener tratamiento arancelario especial

- 4: USADO IMPORTADO INCLUYE REACONDICIONADO
  * Mercadería importada previamente usada
  * Incluye productos reacondicionados en el exterior
  * Aranceles específicos para usados importados

MERCADERÍA SIN USO:
- 5: SIN USO ARGENTINO
  * Mercadería argentina que nunca fue puesta en uso
  * Diferente a "nuevo" (puede ser stock, exhibición, etc.)

- 6: SIN USO IMPORTADO
  * Mercadería importada que nunca fue puesta en uso
  * Stock, exhibición, demostraciones, etc.

IMPACTO EN COMERCIO EXTERIOR:

IMPORTACIÓN:
- Estados 2, 4, 6: Mercadería que ingresa del exterior
- Determina aranceles aplicables
- Requisitos de verificación de estado
- Controles de calidad específicos

EXPORTACIÓN:  
- Estados 1, 3, 5: Mercadería que egresa de Argentina
- Certificaciones de origen requeridas
- Valor agregado nacional para incentivos

CASOS DE USO FRECUENTES:

AUTOMOTRIZ:
- Vehículos nuevos: Estado 1 (argentinos) o 2 (importados)
- Vehículos usados: Estado 3 (argentinos) o 4 (importados)
- Autopartes: Según origen y condición

MAQUINARIA:
- Industrial nueva: Estados 1 o 2
- Maquinaria reacondicionada: Estados 3 o 4
- Equipos de demostración: Estados 5 o 6

ELECTRÓNICOS:
- Productos nuevos: Estados 1 o 2  
- Refurbished: Estados 3 o 4
- Stock de exhibición: Estados 5 o 6

CONSULTAS ÚTILES:

-- Estadísticas de importación por estado
SELECT e.descripcion, COUNT(*) as cantidad_items, 
       AVG(i.fob_dolar) as fob_promedio
FROM importacion_items ii
JOIN Estados e ON ii.estado_mercaderia = e.codigo
GROUP BY e.codigo, e.descripcion
ORDER BY cantidad_items DESC;

-- Productos argentinos vs importados en exportación
SELECT 
    CASE WHEN e.codigo IN ('1','3','5') THEN 'ORIGEN_ARGENTINO' 
         ELSE 'ORIGEN_IMPORTADO' END as origen,
    COUNT(*) as total_exportaciones,
    SUM(ei.monto_fob_dolar) as monto_total_usd
FROM exportacion_items ei
JOIN Estados e ON ei.estado_mercaderia = e.codigo  
GROUP BY CASE WHEN e.codigo IN ('1','3','5') THEN 'ORIGEN_ARGENTINO' 
              ELSE 'ORIGEN_IMPORTADO' END;

-- Validar estados válidos en items
SELECT DISTINCT estado_mercaderia 
FROM importacion_items 
WHERE estado_mercaderia NOT IN (SELECT codigo FROM Estados);

VALIDACIONES RECOMENDADAS:

-- Limpiar estados nulos
UPDATE importacion_items 
SET estado_mercaderia = '2'  -- Default: nuevo importado
WHERE estado_mercaderia IS NULL;

-- Validar consistencia origen vs destinación
SELECT COUNT(*) as inconsistencias
FROM importacion_items ii
JOIN Estados e ON ii.estado_mercaderia = e.codigo
WHERE ii.estado_mercaderia IN ('1','3','5')  -- Origen argentino en importación (raro)

COMPATIBILIDAD:
✅ Compatible con tabla Estados (codigo VARCHAR(5), descripcion VARCHAR(100))
✅ Consolidado de múltiples versiones del CSV
✅ Descripciones estandarizadas y claras
✅ Total: 6 estados oficiales AFIP
✅ Obligatorio en todas las operaciones de comercio exterior
*/