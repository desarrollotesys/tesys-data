-- =====================================================================
-- INSERTS DE DIVISAS ARGENTINA - AFIP
-- =====================================================================
-- Fuente: divisas.csv
-- Generado: 2025-10-11
-- Total registros: 44 divisas (limpiadas de duplicados)
-- =====================================================================

-- Verificar estructura de la tabla antes de insertar
-- \d Divisas;

-- Limpiar datos existentes (opcional)
-- DELETE FROM Divisas;

-- Insertar todas las divisas según estructura real de la tabla
-- Estructura: codigo VARCHAR(5), nombre VARCHAR(50)
-- Nota: Se eliminaron duplicados del CSV original (19/019, 21/021, 60/060)
INSERT INTO Divisas (codigo, nombre) VALUES

-- DIVISAS PRINCIPALES
('002', 'Dólar estadounidense libre'),
('DOL', 'Dólar estadounidense'),
('060', 'Euro'),
('019', 'Yen'),
('021', 'Libra esterlina'),
('PES', 'Peso'),

-- DIVISAS EUROPEAS
('003', 'Franco francés'),
('004', 'Lira italiana'),
('005', 'Peseta'),
('006', 'Marco alemán'),
('007', 'Florín holandés'),
('008', 'Franco belga'),
('009', 'Franco suizo'),
('013', 'Escudo portugués'),
('014', 'Corona danesa'),
('015', 'Corona noruega'),
('016', 'Corona sueca'),
('017', 'Chelín austriaco'),
('022', 'Marco finlandés'),
('024', 'Corona checa'),
('027', 'Dracma'),
('028', 'Florín'),
('040', 'Leu rumano'),
('050', 'Libra irlandesa'),
('056', 'Forint'),
('058', 'ECU'),

-- DIVISAS AMERICANAS
('010', 'Peso mexicano'),
('011', 'Peso uruguayo'),
('012', 'Real'),
('018', 'Dólar canadiense'),
('023', 'Bolívar'),
('029', 'Guaraní'),
('031', 'Peso boliviano'),
('032', 'Peso colombiano'),
('033', 'Peso chileno'),
('035', 'Sol peruano'),
('036', 'Sucre'),
('055', 'Quetzal'),

-- DIVISAS ASIÁTICAS Y PACÍFICO
('026', 'Dólar australiano'),
('051', 'Dólar de Hong Kong'),
('052', 'Dólar de Singapur'),
('054', 'Dólar de Taiwán'),
('057', 'Baht'),
('061', 'Yuan'),

-- DIVISAS AFRICANAS Y MEDIO ORIENTE
('025', 'Dinar'),
('030', 'Shekel'),
('034', 'Rand'),
('059', 'Dinar kuwaití'),

-- DIVISAS DEL CARIBE
('053', 'Dólar de Jamaica'),

-- CÓDIGO ESPECIAL
('999', 'Indeterminado');

-- =====================================================================
-- VERIFICACIÓN DE INSERCIÓN
-- =====================================================================

-- Contar registros insertados
SELECT COUNT(*) as total_divisas FROM Divisas;

-- Mostrar primeras 10 divisas
SELECT codigo, nombre FROM Divisas ORDER BY codigo LIMIT 10;

-- Mostrar divisas principales (más usadas en comercio exterior argentino)
SELECT codigo, nombre FROM Divisas 
WHERE codigo IN ('002', 'DOL', '060', '019', '021', '012', 'PES') 
ORDER BY 
    CASE codigo
        WHEN 'DOL' THEN 1
        WHEN '002' THEN 2  
        WHEN '060' THEN 3
        WHEN 'PES' THEN 4
        WHEN '012' THEN 5
        WHEN '019' THEN 6
        WHEN '021' THEN 7
        ELSE 99
    END;

-- Mostrar divisas por región geográfica
SELECT 
    CASE 
        WHEN codigo IN ('002', 'DOL', '010', '011', '012', '018', '023', '029', '031', '032', '033', '035', '036', '053', '055', 'PES') THEN 'AMERICAS'
        WHEN codigo IN ('003', '004', '005', '006', '007', '008', '009', '013', '014', '015', '016', '017', '021', '022', '024', '027', '028', '040', '050', '056', '058', '060') THEN 'EUROPA'
        WHEN codigo IN ('019', '026', '051', '052', '054', '057', '061') THEN 'ASIA_PACIFICO'
        WHEN codigo IN ('025', '030', '034', '059') THEN 'AFRICA_MEDIO_ORIENTE'
        ELSE 'OTROS'
    END as region,
    COUNT(*) as cantidad_divisas
FROM Divisas 
WHERE codigo != '999'
GROUP BY 
    CASE 
        WHEN codigo IN ('002', 'DOL', '010', '011', '012', '018', '023', '029', '031', '032', '033', '035', '036', '053', '055', 'PES') THEN 'AMERICAS'
        WHEN codigo IN ('003', '004', '005', '006', '007', '008', '009', '013', '014', '015', '016', '017', '021', '022', '024', '027', '028', '040', '050', '056', '058', '060') THEN 'EUROPA'
        WHEN codigo IN ('019', '026', '051', '052', '054', '057', '061') THEN 'ASIA_PACIFICO'
        WHEN codigo IN ('025', '030', '034', '059') THEN 'AFRICA_MEDIO_ORIENTE'
        ELSE 'OTROS'
    END
ORDER BY cantidad_divisas DESC;

-- Verificar que no hay duplicados
SELECT codigo, COUNT(*) FROM Divisas GROUP BY codigo HAVING COUNT(*) > 1;

-- Mostrar divisas con códigos numéricos vs alfabéticos
SELECT 
    CASE 
        WHEN codigo ~ '^[0-9]+$' THEN 'NUMERICO'
        WHEN codigo ~ '^[A-Z]+$' THEN 'ALFABETICO'
        ELSE 'MIXTO'
    END as tipo_codigo,
    COUNT(*) as cantidad
FROM Divisas
GROUP BY 
    CASE 
        WHEN codigo ~ '^[0-9]+$' THEN 'NUMERICO'
        WHEN codigo ~ '^[A-Z]+$' THEN 'ALFABETICO'
        ELSE 'MIXTO'
    END
ORDER BY cantidad DESC;

-- Comentarios finales
COMMENT ON TABLE Divisas IS 'Divisas para comercio exterior Argentina - 44 registros total. Fuente: divisas.csv AFIP actualizado 2025-10-11';

-- =====================================================================
-- NOTAS DE IMPLEMENTACIÓN
-- =====================================================================

/*
DIVISAS PRINCIPALES EN COMERCIO EXTERIOR ARGENTINO:

MÁS USADAS:
- DOL / 002: Dólar estadounidense (principal divisa)
- 060: Euro (segunda en importancia)  
- PES: Peso argentino
- 012: Real brasileño (socio comercial principal)
- 019: Yen japonés
- 021: Libra esterlina

CÓDIGOS ESPECIALES:
- 002 vs DOL: Ambos representan USD (diferentes sistemas)
- PES: Peso argentino (código local)
- 999: Indeterminado (para casos especiales)

REGIONES REPRESENTADAS:
- AMERICAS: 16 divisas (incluye USD, Real, Peso, etc.)
- EUROPA: 22 divisas (Euro, Franco, Marco, etc.)
- ASIA_PACIFICO: 7 divisas (Yen, Yuan, Dólar australiano, etc.)
- AFRICA_MEDIO_ORIENTE: 4 divisas (Dinar, Shekel, Rand, etc.)

DIVISAS HISTÓRICAS:
Incluye monedas pre-Euro como:
- Franco francés, Lira italiana, Peseta, Marco alemán
- Estas se mantienen para datos históricos

USO EN COMERCIO EXTERIOR:
-- Buscar operaciones en USD
SELECT * FROM importacion_despachos WHERE fob_divisa IN ('DOL', '002');

-- Estadísticas por divisa
SELECT d.nombre, COUNT(*) as operaciones, SUM(i.fob_monto) as monto_total
FROM importacion_despachos i
JOIN Divisas d ON i.fob_divisa = d.codigo  
GROUP BY d.codigo, d.nombre
ORDER BY operaciones DESC;

-- Conversión de códigos (si es necesario)
UPDATE importacion_despachos 
SET fob_divisa = '002' 
WHERE fob_divisa = 'DOL';

VALIDACIONES RECOMENDADAS:
-- Verificar divisas válidas en despachos
SELECT DISTINCT fob_divisa 
FROM importacion_despachos 
WHERE fob_divisa NOT IN (SELECT codigo FROM Divisas);

-- Limpiar divisas nulas o vacías  
UPDATE importacion_despachos 
SET fob_divisa = '999' 
WHERE fob_divisa IS NULL OR fob_divisa = '';

COMPATIBILIDAD:
✅ Compatible con tabla Divisas (codigo VARCHAR(5), nombre VARCHAR(50))
✅ Limpiado de duplicados del CSV original
✅ Incluye divisas históricas y actuales
✅ Códigos tanto numéricos (002, 019) como alfabéticos (DOL, PES)
✅ Total: 44 divisas organizadas por región
*/