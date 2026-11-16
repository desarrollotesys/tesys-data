-- =====================================================
-- CONSULTA: Reporte de Importación para Cliente
-- =====================================================
-- Genera reporte completo de importaciones con todos los campos
-- necesarios para análisis del cliente
--
-- REGLAS DE NEGOCIO:
-- r1: REGLA DE 3 SIMPLE (cálculos proporcionales)
-- r5: FLETE, SEGURO, CIF se calculan en función del monto por despacho (proporcional al FOB)
-- r9: CANTIDAD, KGNETOS y FOB X SUBITEM vienen de r9 SI EL DESPACHO TIENE SUBITEM O DEL R5 SI NO TIENE SUBITEM
--
-- Uso:
-- psql -U postgres -d comercio_exterior_argentina \
--   -v fecha_desde="'2025-01-01'" -v fecha_hasta="'2025-02-01'" -v limite=100 \
--   -f sql/queries/reporte_cliente_importacion.sql
--
-- Para exportar a CSV:
-- \copy (...query...) TO '/tmp/reporte_enero_2025.csv' WITH (FORMAT CSV, HEADER, DELIMITER ',', QUOTE '"', FORCE_QUOTE *)
-- =====================================================

-- Valores por defecto si no se pasan con -v (ver "Uso" arriba)
\if :{?fecha_desde} \else \set fecha_desde '\'2025-01-01\'' \endif
\if :{?fecha_hasta} \else \set fecha_hasta '\'2025-02-01\'' \endif
\if :{?limite} \else \set limite 100 \endif

SELECT
    -- Datos del importador
    p.razon_social AS "Importador (prob.)",
    d.cuit_importador AS "Cuit",

    -- Fecha
    TO_CHAR(d.fecha_oficializacion, 'mon-YY') AS "Mes/Año",
    TO_CHAR(d.fecha_oficializacion, 'DD/MM/YYYY') AS "Fecha oficialización",

    -- Despacho
    dest.tipo AS "tipoDestinación",
    d.despacho_id AS "Despacho",

    -- Producto
    i.posicion_sim AS "Posición SIM",
    n.descripcion AS "Descripción",
    -- NCM: código de 8 dígitos (primeros 10 caracteres del SIM incluyendo puntos)
    SUBSTRING(i.posicion_sim, 1, 10) AS "Descripción NCM",
    n.descripcion AS "Descripción SIM",

    -- Origen y destino
    ad.nombre AS "Aduana",
    po.nombre AS "Origen",
    pp.nombre AS "Pais de procedencia",

    -- Transporte
    d.medio AS "Medio",
    d.matricula AS "Transporte",
    d.condicion_venta AS "Cond. venta",

    -- Pesos (regla r9: de subitem si existe, sino de item)
    COALESCE(s.cantidad_unidades_subitem * i.kg_netos / i.cantidad_unidades, i.kg_netos) AS "Kg. netos",
    -- Kg. Brutos proporcional al FOB del subitem (igual que Flete y Seguro)
    CASE
        WHEN d.fob_monto > 0
        THEN ROUND((COALESCE(s.fob_dolar_subitem, i.fob_dolar) / d.fob_monto) * d.peso_bruto, 2)
        ELSE 0
    END AS "Kg. Brutos",

    -- Divisa
    di.nombre AS "Divisa",

    -- Flete proporcional al FOB del subitem (regla r5)
    CASE
        WHEN d.fob_monto > 0
        THEN ROUND((COALESCE(s.fob_dolar_subitem, i.fob_dolar) / d.fob_monto) * d.flete_monto, 2)
        ELSE 0
    END AS "Flete",

    -- Unidad declarada
    u.descripcion AS "Unidad declarada",

    -- Seguro proporcional al FOB del subitem (regla r5)
    CASE
        WHEN d.fob_monto > 0
        THEN ROUND((COALESCE(s.fob_dolar_subitem, i.fob_dolar) / d.fob_monto) * d.seguro_monto, 2)
        ELSE 0
    END AS "Seguro dólar",

    -- Estado mercadería
    e.descripcion AS "Estado de la mercadería",

    -- Item/Subitem (regla r9: datos vienen de r9 si tiene subitem, sino de r5)
    CASE
        WHEN s.subitem_id IS NOT NULL THEN i.item_id || ' - ' || s.subitem_id
        ELSE i.item_id || ' - 0000'
    END AS "Item - sub ítem",

    -- Cantidades (regla r9: de subitem si existe, sino de item)
    COALESCE(s.cantidad_unidades_subitem, i.cantidad_unidades) AS "Cantidad declarada x subitem",

    -- Precios unitarios y totales en divisa original
    CASE
        WHEN COALESCE(s.cantidad_unidades_subitem, i.cantidad_unidades) > 0
        THEN ROUND(COALESCE(s.fob_dolar_subitem, i.fob_dolar) / COALESCE(s.cantidad_unidades_subitem, i.cantidad_unidades), 2)
        ELSE 0
    END AS "Precio unitario en divisas",

    COALESCE(s.fob_dolar_subitem, i.fob_dolar) AS "Fob total en divisas",

    -- Precios en dólares (TODO: por ahora igual que divisas, falta conversión)
    CASE
        WHEN COALESCE(s.cantidad_unidades_subitem, i.cantidad_unidades) > 0
        THEN ROUND(COALESCE(s.fob_dolar_subitem, i.fob_dolar) / COALESCE(s.cantidad_unidades_subitem, i.cantidad_unidades), 2)
        ELSE 0
    END AS "Precio unitario en dólares",

    COALESCE(s.fob_dolar_subitem, i.fob_dolar) AS "Fob total en dólares",

    -- CIF (FOB + Seguro + Flete proporcionales) (regla r5)
    COALESCE(s.fob_dolar_subitem, i.fob_dolar) +
    CASE WHEN d.fob_monto > 0 THEN ROUND((COALESCE(s.fob_dolar_subitem, i.fob_dolar) / d.fob_monto) * d.seguro_monto, 2) ELSE 0 END +
    CASE WHEN d.fob_monto > 0 THEN ROUND((COALESCE(s.fob_dolar_subitem, i.fob_dolar) / d.fob_monto) * d.flete_monto, 2) ELSE 0 END AS "CIF",

    -- Sufijos de subitem (extraídos de JSONB)
    COALESCE(s.sufijos_completos->>'AA', 'SIN MARCA') AS "Marca",
    COALESCE(s.sufijos_completos->>'AB', 'SIN MODELO') AS "Modelo",
    COALESCE(s.sufijos_completos->>'AI', s.sufijos_completos->>'AH', 'SIN VERSION') AS "Versión",
    COALESCE(s.sufijos_completos->>'AC', 'SIN CODIGO') AS "Código",
    COALESCE(s.sufijos_completos->>'AJ', 'SIN PRESENTACION') AS "Presentación",
    COALESCE(s.sufijos_completos->>'AR', 'SIN VENCIMIENTO') AS "Vencimiento",

    -- Impuestos y obligaciones (TODO: se compartirán después)
    0 AS "Base imponible",
    0 AS "% Derechos",

    -- Derechos de importación (concepto 010, obligacion P)
    COALESCE((SELECT SUM(monto) FROM importacion_obligaciones ob
              WHERE ob.despacho_id = i.despacho_id
                AND ob.item_id = i.item_id
                AND ob.fecha_oficializacion = i.fecha_oficializacion
                AND ob.concepto = '010'
                AND ob.obligacion = 'P'), 0) AS "Derechos de importación",

    COALESCE((SELECT SUM(monto) FROM importacion_obligaciones ob
              WHERE ob.despacho_id = i.despacho_id
                AND ob.item_id = i.item_id
                AND ob.fecha_oficializacion = i.fecha_oficializacion
                AND ob.concepto = '010'
                AND ob.obligacion = 'D'), 0) AS "Derechos de importación en garantía",

    0 AS "ANTI-DUMPING", -- TODO
    0 AS "% Estadística",

    -- Tasa estadística (concepto 047)
    COALESCE((SELECT SUM(monto) FROM importacion_obligaciones ob
              WHERE ob.despacho_id = i.despacho_id
                AND ob.item_id = i.item_id
                AND ob.fecha_oficializacion = i.fecha_oficializacion
                AND ob.concepto = '047'), 0) AS "Tasa estadística",

    0 AS "% IVA",

    -- IVA (concepto 056, obligacion P)
    COALESCE((SELECT SUM(monto) FROM importacion_obligaciones ob
              WHERE ob.despacho_id = i.despacho_id
                AND ob.item_id = i.item_id
                AND ob.fecha_oficializacion = i.fecha_oficializacion
                AND ob.concepto = '056'
                AND ob.obligacion = 'P'), 0) AS "IVA",

    COALESCE((SELECT SUM(monto) FROM importacion_obligaciones ob
              WHERE ob.despacho_id = i.despacho_id
                AND ob.item_id = i.item_id
                AND ob.fecha_oficializacion = i.fecha_oficializacion
                AND ob.concepto = '056'
                AND ob.obligacion = 'D'), 0) AS "IVA en garantía",

    0 AS "% IVA adicional",
    0 AS "IVA adicional insc.",
    0 AS "% IIBB",
    0 AS "IIBB",
    0 AS "% Ganancias",
    0 AS "Impuesto a las ganancias",
    0 AS "Impuesto a las ganancias en garantía",
    0 AS "% Arancel SIM",
    0 AS "Arancel SIM",

    -- Otros (de subitems sufijo CA)
    -- Pendiente confirmar con Gaby: CA00 → BE vacío o leyenda "NUEVA SIN USO"?
    CASE WHEN s.sufijos_completos ? 'CA'
         THEN 'CA' || (s.sufijos_completos->>'CA')
         ELSE ''
    END AS "Código",
    (SELECT ns.descripcion
     FROM nomenclador_sufijos ns
     WHERE ns.tipo = 3
       AND ns.codigo_sufijo = 'CA' || (s.sufijos_completos->>'CA')
       AND ns.posicion IN (
             REGEXP_REPLACE(i.posicion_sim, '[A-Za-z]+$', ''),
             LEFT(i.posicion_sim, 2) || '.' || SUBSTRING(i.posicion_sim, 3, 2),
             LEFT(i.posicion_sim, 2)
           )
     ORDER BY length(ns.posicion) DESC
     LIMIT 1
    ) AS "Detalle"

FROM importacion_items i
INNER JOIN importacion_despachos d ON i.despacho_id = d.despacho_id AND i.fecha_oficializacion = d.fecha_oficializacion
LEFT JOIN importacion_subitems s ON i.despacho_id = s.despacho_id AND i.item_id = s.item_id AND i.fecha_oficializacion = s.fecha_oficializacion
LEFT JOIN padron p ON d.cuit_importador = p.cuit
LEFT JOIN nomenclador n ON i.posicion_sim = n.posicion_sim
LEFT JOIN destinaciones dest ON d.tipo_destinacion = dest.codigo
LEFT JOIN aduanas ad ON d.codigo_aduana = ad.codigo
LEFT JOIN paises po ON i.codigo_origen = po.codigo
LEFT JOIN paises pp ON i.codigo_procedencia = pp.codigo
LEFT JOIN divisas di ON d.fob_divisa = di.codigo
LEFT JOIN unidades u ON i.codigo_unidad = u.codigo
LEFT JOIN estados e ON i.estado_mercaderia = e.codigo

WHERE d.fecha_oficializacion >= :fecha_desde
  AND d.fecha_oficializacion < :fecha_hasta
  -- Repetir el filtro de fecha sobre items para que el planner pode las
  -- particiones de importacion_items (si no, escanea todas las particiones)
  AND i.fecha_oficializacion >= :fecha_desde
  AND i.fecha_oficializacion < :fecha_hasta
  -- Filtro de ejemplo por posición específica (comentar para ver todo)
  -- AND i.posicion_sim = '8450.11.00.390W'

ORDER BY d.fecha_oficializacion, d.despacho_id, i.item_id, s.subitem_id NULLS FIRST

LIMIT :limite; -- Pasar -v limite=ALL (o quitar este LIMIT) para exportar todo
