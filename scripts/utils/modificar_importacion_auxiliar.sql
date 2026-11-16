-- Script para modificar tabla importacion_auxiliar
-- Quita las FK de cuit_despachante y cuit_transportista hacia padron
-- Razon: El padron puede no estar actualizado con todos los CUITs

-- 1. Verificar constrains existentes
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'importacion_auxiliar'::regclass;

-- 2. Eliminar FK de cuit_despachante (si existe)
ALTER TABLE importacion_auxiliar
DROP CONSTRAINT IF EXISTS importacion_auxiliar_cuit_despachante_fkey;

-- 3. Eliminar FK de cuit_transportista (si existe)
ALTER TABLE importacion_auxiliar
DROP CONSTRAINT IF EXISTS importacion_auxiliar_cuit_transportista_fkey;

-- 4. Agregar comentarios explicativos
COMMENT ON COLUMN importacion_auxiliar.cuit_despachante IS
'CUIT del despachante de aduana - No tiene FK porque el padron puede no estar actualizado';

COMMENT ON COLUMN importacion_auxiliar.cuit_transportista IS
'CUIT del transportista o codigo de transporte - No tiene FK porque puede contener otros identificadores';

-- 5. Verificar cambios
SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'importacion_auxiliar'::regclass;
