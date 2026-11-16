-- Inserts para tabla Unidades
-- Basado en unidades.csv - Catálogo oficial AFIP
-- Total: 42 unidades de medida (se omite columna 'sistema' del CSV)

INSERT INTO unidades (codigo, descripcion, activo) VALUES
-- Unidades básicas del sistema métrico
('1', 'Kilogramos', TRUE),
('2', 'Metros', TRUE),
('3', 'Metro Cuadrado', TRUE),
('4', 'Metro Cúbico', TRUE),
('5', 'Litros', TRUE),
('6', '1000 Kilowatt Hora', TRUE),
('7', 'Unidad', TRUE),
('8', 'Par', TRUE),
('9', 'Docena', TRUE),
('10', 'Quilate', TRUE),
('11', 'Millar', TRUE),
('14', 'Gramo', TRUE),
('15', 'Milímetro', TRUE),
('16', 'Milímetro Cúbico', TRUE),
('17', 'Kilómetro', TRUE),
('18', 'Hectolitro', TRUE),
('20', 'Centímetro', TRUE),
('25', 'Paquetes', TRUE),
('27', 'Centímetro Cúbico', TRUE),
('29', 'Tonelada', TRUE),
('30', 'Decímetro Cúbico', TRUE),
('31', 'Hectómetro Cúbico', TRUE),
('32', 'Kilómetro Cúbico', TRUE),

-- Unidades microscópicas
('33', 'Microgramo', TRUE),
('34', 'Nanogramo', TRUE),
('35', 'Picogramo', TRUE),
('41', 'Miligramo', TRUE),
('47', 'Mililitro', TRUE),

-- Unidades especiales (radioactividad, farmacéutica)
('48', 'Curie', TRUE),
('49', 'Milicurie', TRUE),
('50', 'Microcurie', TRUE),
('51', 'UI Actividad Hormonal', TRUE),
('52', 'Mega UI Actividad Hormonal', TRUE),
('53', 'Kilogramo Base', TRUE),
('54', 'Gruesa', TRUE),
('58', 'Kilogramo Base', TRUE),
('61', 'Kilogramo Bruto', TRUE),
('62', 'UI Actividad Antigénica', TRUE),
('63', 'Gramo', TRUE),

-- Unidades genéricas
('98', 'No Especifica', TRUE),
('99', 'Indefinido', TRUE);

-- Verificación del total de registros insertados
SELECT 'Total unidades insertadas: ' || COUNT(*) AS resultado FROM unidades;