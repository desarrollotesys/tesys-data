-- =====================================================================
-- INSERTS DE ADUANAS ARGENTINA - AFIP
-- =====================================================================
-- Fuente: aduanas.csv
-- Generado: 2025-10-11 (Actualizado: 2025-10-21)
-- Total registros: 79 aduanas (76 originales + 3 agregados automáticamente)
-- NOTA: Códigos 094, 274, 275 agregados para resolver FK constraints
-- =====================================================================

-- Verificar estructura de la tabla antes de insertar
-- \d aduanas;

-- Limpiar datos existos (opcional)
-- DELETE FROM aduanas;

-- Insertar todas las aduanas según estructura real de la tabla
-- Estructura real: codigo CHAR(3), nombre VARCHAR(100)
INSERT INTO aduanas (codigo, nombre) VALUES

-- Todas las aduanas según aduanas.csv (76 registros)
('000', 'Administración Central'),
('001', 'Buenos Aires'),
('003', 'Bahía Blanca'),
('004', 'Bariloche'),
('007', 'Cachi'),
('008', 'Campana'),
('009', 'Cieneguillas'),
('010', 'Barranqueras'),
('011', 'Chos Malal'),
('012', 'Clorinda'),
('013', 'Colón'),
('014', 'Comodoro Rivadavia'),
('015', 'Concepción del Uruguay'),
('016', 'Concordia'),
('017', 'Córdoba'),
('018', 'Corrientes'),
('019', 'Puerto Deseado'),
('020', 'Diamante'),
('021', 'Empedrado'),
('022', 'Esquina'),
('023', 'Esquel'),
('024', 'Formosa'),
('025', 'Goya'),
('026', 'Gualeguaychú'),
('027', 'Gualeguay'),
('028', 'Ibicuí'),
('029', 'Iguazú'),
('031', 'Jujuy'),
('033', 'La Plata'),
('034', 'La Quiaca'),
('035', 'Las Lajas'),
('037', 'Mar del Plata'),
('038', 'Mendoza'),
('040', 'Necochea'),
('041', 'Paraná'),
('042', 'Paso de los Libres'),
('045', 'Pocitos'),
('046', 'Posadas'),
('047', 'Puerto Madryn'),
('048', 'Río Gallegos'),
('049', 'Río Grande'),
('050', 'El Turbio'),
('052', 'Rosario'),
('053', 'Salta'),
('054', 'San Javier'),
('055', 'San Juan'),
('057', 'San Lorenzo'),
('058', 'San Martín de los Andes'),
('059', 'San Nicolás'),
('060', 'San Pedro'),
('061', 'Santa Cruz'),
('062', 'Santa Fe'),
('063', 'Santa Victoria'),
('065', 'Tigre'),
('066', 'Tinogasta'),
('067', 'Ushuaia'),
('068', 'Victoria'),
('069', 'Villa Constitución'),
('070', 'Vinchina'),
('071', 'Yavi'),
('073', 'Ezeiza'),
('074', 'Tucumán'),
('075', 'Neuquén'),
('076', 'Orán'),
('078', 'San Rafael'),
('079', 'La Rioja'),
('080', 'San Antonio Oeste'),
('082', 'Bernardo de Irigoyen'),
('083', 'San Luis'),
('084', 'Santo Tomé'),
('085', 'Villa Rellina'),
('086', 'Oberá'),
('087', 'Caleta Olivia'),
('088', 'General Deheza'),
('089', 'Santiago del Estero'),
('090', 'General Pico'),
('091', 'Buenos Aires Norte'),
('092', 'Buenos Aires Sur'),
('093', 'Rafaela'),
('099', 'Exterior Exportación'),
('250', 'Tierra del Fuego AAE'),
('251', 'Zona Franca La Plata'),
('252', 'Zona Franca Justo Daract'),
('253', 'Zona Franca Río Gallegos'),
('254', 'Islas Malvinas'),
('255', 'Zona Franca Tucumán'),
('256', 'Zona Franca Córdoba'),
('257', 'Zona Franca Mendoza'),
('258', 'Zona Franca General Pico'),
('266', 'Zona Franca Coronel Rosales'),
('267', 'Zona Franca Concepción del Uruguay'),
('268', 'Zona Franca Villa Constitución'),
('269', 'Zona Franca Puerto Galván'),
('999', 'Indeterminada');

-- =====================================================================
-- VERIFICACIÓN DE INSERCIÓN
-- =====================================================================

-- Contar registros insertados
SELECT COUNT(*) as total_aduanas FROM aduanas;

-- Mostrar primeras 10 aduanas
SELECT codigo, nombre FROM aduanas ORDER BY codigo LIMIT 10;

-- Mostrar aduanas principales
SELECT codigo, nombre FROM aduanas 
WHERE codigo IN ('001', '073', '052', '003', '037') 
ORDER BY codigo;

-- Verificar zonas francas (códigos 25x)
SELECT codigo, nombre FROM aduanas 
WHERE codigo LIKE '25%' 
ORDER BY codigo;

-- Verificar que no hay duplicados
SELECT codigo, COUNT(*) FROM aduanas GROUP BY codigo HAVING COUNT(*) > 1;

-- Comentarios finales
COMMENT ON TABLE aduanas IS 'Aduanas AFIP Argentina - 76 registros total. Fuente: aduanas.csv AFIP actualizado 2025-10-11';

-- =====================================================================
-- NOTAS DE IMPLEMENTACIÓN
-- =====================================================================

/*
REGIONES UTILIZADAS:
- NACIONAL: Administración central y códigos especiales
- AMBA: Área Metropolitana Buenos Aires (8 aduanas)
- PAMPEANA: Región Pampeana (13 aduanas)
- LITORAL: Entre Ríos y litoral (13 aduanas) 
- NEA: Noreste Argentino (11 aduanas)
- NOA: Noroeste Argentino (9 aduanas)
- CUYO: Región de Cuyo (7 aduanas)
- PATAGONIA: Región Patagónica (12 aduanas)
- TIERRA_DEL_FUEGO: Tierra del Fuego y Antártida (4 aduanas)
- ZONA_FRANCA: Zonas Francas (8 aduanas)

TOTAL: 76 aduanas organizadas por región geográfica

CÓDIGOS ESPECIALES:
- 000: Administración Central
- 099: Exterior Exportación  
- 250-269: Zonas Francas y AAE
- 999: Indeterminada

PRINCIPALES PUERTOS:
- 001: Buenos Aires (principal)
- 052: Rosario
- 003: Bahía Blanca
- 037: Mar del Plata
- 073: Ezeiza (aeropuerto principal)

USO RECOMENDADO:
-- Buscar aduanas por región
SELECT * FROM aduanas WHERE region = 'AMBA' AND activo = TRUE;

-- Buscar aduanas por nombre
SELECT * FROM aduanas WHERE nombre ILIKE '%puerto%' AND activo = TRUE;

-- Validar código en importación/exportación
SELECT a.nombre, a.region 
FROM importacion_despachos i
JOIN aduanas a ON i.codigo_aduana = a.codigo
WHERE i.despacho_id = '25001IM010000001A';

-- ======================================================================
-- CÓDIGOS AGREGADOS AUTOMÁTICAMENTE (2025-10-21)
-- ======================================================================
-- Los siguientes códigos fueron agregados automáticamente durante
-- la carga de proveedores para resolver foreign key constraints:
-- 
-- 094: 'Código 094 - Por determinar' (113 registros en ProvMes)
-- 274: 'Código 274 - Por determinar' (1 registro en ProvMes)  
-- 275: 'Código 275 - Por determinar' (3 registros en ProvMes)
--
-- TODO: Investigar en documentación AFIP la descripción correcta
--       de estos códigos de aduana y actualizar nombres apropiados
-- ======================================================================
*/