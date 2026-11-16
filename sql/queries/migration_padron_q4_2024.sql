-- ==============================================================================
-- Script: migration_padron_q4_2024.sql
-- Descripción: CUITs faltantes del padrón encontrados al importar Q4 2024
-- Fecha: 2024-11-03
-- Uso: Ejecutar en producción antes de importar datos de Q4 2024
-- ==============================================================================

-- IMPORTANTE: Estos CUITs aparecen en los datos de importación de Q4 2024
-- pero no están presentes en el padrón de AFIP.
-- Se agregan temporalmente con razón social "Por determinar" hasta obtener
-- los datos oficiales.

BEGIN;

-- Insertar CUITs faltantes encontrados en Octubre 2024
INSERT INTO padron (cuit, razon_social) VALUES
('20391558796', 'Por determinar')
ON CONFLICT (cuit) DO NOTHING;

-- Insertar CUITs faltantes encontrados en Noviembre 2024
INSERT INTO padron (cuit, razon_social) VALUES
('20338230320', 'Por determinar'),
('20398375220', 'Por determinar'),
('27303126193', 'Por determinar'),
('30717604373', 'Por determinar'),
('23318247234', 'Por determinar'),
('20264749906', 'Por determinar')
ON CONFLICT (cuit) DO NOTHING;

-- Insertar CUITs faltantes encontrados en Diciembre 2024
INSERT INTO padron (cuit, razon_social) VALUES
('27422916771', 'Por determinar'),
('20632005475', 'Por determinar'),
('20221544820', 'Por determinar'),
('30717106462', 'Por determinar'),
('30717901459', 'Por determinar')
ON CONFLICT (cuit) DO NOTHING;

-- Verificar cuántos CUITs se insertaron
SELECT
    'CUITs agregados al padrón' AS descripcion,
    COUNT(*) AS cantidad
FROM padron
WHERE cuit IN (
    '20391558796', '20338230320', '20398375220', '27303126193',
    '30717604373', '23318247234', '20264749906', '27422916771',
    '20632005475', '20221544820', '30717106462', '30717901459'
);

COMMIT;

-- ==============================================================================
-- NOTAS PARA PRODUCCIÓN:
-- ==============================================================================
--
-- 1. Este script debe ejecutarse ANTES de importar los datos de Q4 2024
-- 2. Los CUITs agregados tienen razón social "Por determinar"
-- 3. Se recomienda:
--    - Consultar con AFIP para obtener los datos oficiales de estos CUITs
--    - Actualizar las razones sociales cuando se obtengan los datos correctos
--    - Verificar si estos CUITs existen en padrones más recientes
--
-- 4. Para actualizar las razones sociales después:
--    UPDATE padron
--    SET razon_social = 'Razón social correcta'
--    WHERE cuit = 'CUIT_ESPECIFICO';
--
-- 5. Total de CUITs agregados: 12
--    - Octubre 2024: 1 CUIT
--    - Noviembre 2024: 6 CUITs
--    - Diciembre 2024: 5 CUITs
--
-- ==============================================================================
