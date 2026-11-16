-- ============================================================================
-- INSERTS PARA TABLA DESTINACIONES - GENERADO AUTOMÁTICAMENTE
-- ============================================================================
-- Archivo generado: 2025-10-16 13:12:26
-- Total de registros: 219 (218 originales + 1 ICRS agregado)
-- Herramienta: Generador de Destinaciones PostgreSQL
-- NOTA: ICRS agregado automáticamente - REVISAR
-- ============================================================================

-- Configuración PostgreSQL
\set ON_ERROR_STOP on
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- Información previa
SELECT 'Iniciando inserción de destinaciones...' as mensaje;
SELECT COUNT(*) as registros_actuales FROM destinaciones;

-- Limpiar datos existentes (descomente si es necesario)
-- DELETE FROM destinaciones;

-- Iniciar transacción
BEGIN;

-- Configuraciones de rendimiento (compatibles con Docker)
SET synchronous_commit = off;

-- Inserción mediante comando COPY (más eficiente)
COPY destinaciones (codigo, tipo, regimen_arancelario, descripcion, aplicacion) FROM STDIN WITH (
    FORMAT text,
    DELIMITER E'\t',
    NULL '\N',
    ENCODING 'UTF8'
);
IC33	CONSUMO	RETEXTEST	RETORNO EXPORTACION TEMPORAL SIN TRANSFORMACION	\N
IC65	CONSUMO	\N	IMPORTACION CONSUMO DE GRANEL D. A. P. CON MANI REGISTR	\N
IC75	CONSUMO	\N	IMPORTACION A CONSUMO C/DOC TRANSPORTE DAP FORM7366 MANI-RG	\N
IC84	CONSUMO	\N	\N	\N
IC99	CONSUMO	\N	\N	\N
ICRF	CONSUMO	\N	\N	\N
IDA4	DEPOSITO	\N	\N	\N
IG24	CONSUMO	IMPCON	IMPORTACION A CONSUMO GRANDES OPERADORES	\N
IG25	CONSUMO	IMPCON	IMPORTACION A CONSUMO GRANDES OPERADORES	\N
IG31	CONSUMO	IMPCON	IMPORTACION A CONSUMO GRANDES OPERADORES	\N
IG34	CONSUMO	IMPCON	IMPORTACION A CONSUMO GRANDES OPERADORES	\N
IG35	CONSUMO	IMPCON	IMPORTACION A CONSUMO GRANDES OPERADORES	\N
IG36	CONSUMO	IMPCON	IMPORTACION A CONSUMO GRANDES OPERADORES	\N
IG81	CONSUMO	IMPCONTEMCT	IMPORTACION A CONSUMO P/GRANDES OPERADORES DE IMPORTACION TEMP. C/TRANSFORMACION	Importación a consumo de mercaderías previamente importadas temporalmente con transformación
IG82	CONSUMO	IMPCON	IMPORTACION A CONSUMO GRANDES OPERADORES	\N
IG83	CONSUMO	IMPCON	IMPORTACION A CONSUMO. P/GRANDES OPERADORES. DE IMPORTACION TEMPORAL S/TRANSFORMACION	\N
IS06	CONSUMO	IMPCON	FRANQUICIA DIPLOMATICA	franquicia diplomática para la nacionalización de vehículos que previamente fueron documentados como depósito de almacenamiento
IT18	TEMPORALES(AT)	IMPTEMST	\N	\N
IT65	TEMPORALES(AT)	IMPTEMST	\N	\N
TG03	TEMPORALES(AT)	IMPTEMST	\N	\N
TG13	TEMPORALES(AT)	IMPTEMST	\N	\N
TR51	TRANSITO	\N	\N	\N
TRB1	TRANSITO	\N	\N	\N
TRB2	TRANSITO	\N	\N	\N
TRB3	TRANSITO	\N	\N	\N
TRM4	TRANSITO	\N	\N	\N
TRM5	TRANSITO	\N	\N	\N
TRM6	TRANSITO	\N	\N	\N
BARA	RANCHO	EXPOCONS	RANCHO EXPORTACION DE COMBUSTIBLES A EMBARCACIONES DE BANDERA EXTRANJERA	Rancho para medios de transporte de bandera extranjera
CORI	DEPOSITO	IMPDEPALMACEN	DECLARACION DE CORRECCION DE INGRESO A DEPÓSITO	Declaración detallada de corrección de ingreso a depósito proveniente de traslado detallado
DIR1	TEMPORALES(AT)	IMPTEMST	DECLARACION DE IMPORTACION SUSPENSIVA EN EL RAF EN PLANTA S/DOC TRANSP	\N
DIR3	TEMPORALES(AT)	IMPTEMST	DECLARCION DE IMPORTACION SUSPENSIVA. RAF EN PLANTA S/DOC TRANSP VIA TERRESTRE	\N
DIR4	TEMPORALES(AT)	IMPTEMST	DECLARACION DE IMPORTACION SUSPENSIVA AL RAF EN PLANTA C/DOC DE TRANS	\N
DIR5	TEMPORALES(AT)	IMPTEMST	DECLARACION DE IMPORTACION SUSPENSIVA EN RAF AL ARRIBO C/DOC DE TRANS	\N
DIR6	TEMPORALES(AT)	IMPTEMST	DECLARACION DE IMPORTACION SUSPENSIVA RAF SOBRE DEP. ALMACENAMIENTO	\N
DIS1	CONSUMO	IMPCON	DESTINACION DE IMPORTACION SIMPLIFICADA SIN DOCUMENTO	Importación para consumo de acuerdo a lo normado para el régimen simplificado de Importación para mercaderías que arriben sin documento de transporte, por la vía postal o propios medios
DIS4	CONSUMO	IMPCON	DESTINACION DE IMPORTACION SIMPLIFICADA	Importación para consumo con documento de transporte de acuerdo a lo normado para el régimen simplificado de Importación
DIS5	CONSUMO	IMPCON	DESTINACION DE IMPORTACION SIMPLIFICADA DAP	Importación para consumo de acuerdo a lo normado para el régimen simplificado de Importación para mercaderías cuya destinación puede ser registrada con anterioridad al arribo del medio de transporte para su despacho directo a plaza
DJVE	DJVE	DJVE	DECLARACION JURADA DE VENTA LEY 21453	Declaración jurada de venta Ley 21453
DJVR	DJVE	DJVE	DECLARACIÓN JURADA DE VENTA AL EXTERIOR LEY 21453 -RESIDUALES	Declaración jurada de venta al exterior Ley 21453 Residuales
EC01	CONSUMO	EXPCON	EXPORTACION A CONSUMO	Exportación a consumo
EC02	CONSUMO	EXPCON	EXPORTACION A CONSUMO CON DIT SIN TRANSFORMACION	Exportación a consumo de mercaderías importadas temporalmente y exportadas sin transformación
EC03	CONSUMO	EXPCON	EXPORTACION A CONSUMO CON DIT CON TRANFORMACION	Exportación a consumo de mercaderías importadas temporalmente y exportadas con transformación
EC04	CONSUMO	EXPCON	EXPORT. A CONS. CON DIT INGRES. PARA TRANSFORMACION EGRESADO SIN TRANSFORMACION	Exportación a consumo de mercadería ingresada temporalmente para transformación pero exportada sin transformación
EC05	CONSUMO	EXPCONS	EXPORTACION A CONSUMO DE EXPORTACION TEMPORAL CON TRANSFORMACION	Exportación a consumo de mercadería exportada temporalmente con transformación
EC06	CONSUMO	EXPCONS	EXPORTACION A CONSUMO DE EXPORTACION TEMPORAL SIN TRANSFORMACION	Exportación a consumo de mercadería exportada temporalmente sin transformación
EC07	CONSUMO	EXPCONS	EXPORTACION A CONSUMO DE MERCADERIA EN CONSIGNACION	Exportación a consumo de mercadería exportada en consignación
EC08	CONSUMO	EXPCONS	EXPORTACION A CONSUMO DE MERCADERIA CON PRECIOS REVISABLES	Exportación a consumo de mercadería exportada con precios revisables
EC09	CONSUMO	EXPCONS	EXPORTACION A CONSUMO DE CONCENTRADO DE MINERALES	Exportación a consumo de concentrado de minerales
EC16	CONSUMO	EXPCON	EXPORTACION A CONSUMO RESIDUOS DE IMPORTACION TEMPORAL CON TRANSFORMACION	Exportación a consumo de residuos de mercaderías importadas temporalmente y transformadas
EC51	CONSUMO	VALORES	EXPORTACION DE VALORES	Declaración de egreso de valores(Billetes Monedas, etc.)del territorio aduanero
ECA1	CONSUMO	IMPCON	EGRESO A CONSUMO EN TNC MERCADERIA ORIGINARIA AAE EGRESO MISMO PRODUCTOR	Egreso a consumo hacia el Territorio Nacional Continental desde el Área Aduanera Especial de mercadería originaria del Área Aduanera Especial para consumo por el mismo productor
ECA2	CONSUMO	IMPCON	EGRESO AL TNC DE MERCADERIA ORIGINARIA AAE E IMPORTADOR CUIT DISTINTO PRODUCTOR	Egreso a consumo hacia el Territorio Nacional Continental desde el Área Aduanera Especial de mercadería originaria del Área Aduanera Especial para consumo por un importador de distinto CUIT del productor
ECA3	CONSUMO	IMPCON	EGRESO PARA CONSUMO EN TNC MERCADERIA DEL AAE NO ORIGINADA EN EL AREA	Egreso a consumo hacia el Territorio Nacional Continental desde el Área Aduanera Especial de mercadería no originaria del Área Aduanera Especial
ECA4	CONSUMO	IMPCON	REIMPORTACION AL TNC MERCADERIA EXPORTADA DESDE TNC AL AAE	Reimportación de mercadería al Territorio Nacional Continental de mercadería exportada desde el Territorio Nacional Continental al Área Aduanera Especial
ECE1	CONSUMO	EXPCON	EGRESO DEL AAE A CONSUMO EN EXTERIOR. CON TRANSPORTE TERRESTRE POR TNC	Exportación a consumo de mercadería desde el Área Aduanera Especial en tránsito por el Territorio nacional Continental
EG01	CONSUMO	EXPCON	EXPOTACION A CONSUMO GRAN OPERADOR	Exportación a consumo para Aduanas Domiciliarias
EG02	CONSUMO	EXPCON	EXPORTACION A CONSUMO CON DIT SIN TRANSFORMACION GRAN OPERADOR	Exportación a consumo de mercaderías importadas temporalmente y exportadas sin transformación por empresas contempladas en el régimen de Aduanas Domiciliarias
EG03	CONSUMO	EXPCON	EXPORTACION A CONSUMO CON DIT CON TRANSFORMACION GRAN OPERADOR	Exportación a consumo de mercaderías importadas temporalmente y exportadas con transformación por empresas contempladas en el régimen de Aduanas Domiciliarias
EG07	CONSUMO	EXPCONS	EXPORTACION A CONSUMO DE MERCADERIA EN CONSIGNACIÓN GRAN OPERADOR	Exportación a consumo de mercaderías en consignación por empresas contempladas en el régimen de Aduanas Domiciliarias
EGS1	SUSPENSIVA	EXPCON	EXPORTACION DE MERCADERIAS EN CONSIGNACION GRAN OPERADOR	Exportación de mercaderías en consignación por empresas contempladas en el régimen de Aduanas Domiciliarias
EGT1	TEMPORALES	EXPTEMCT	EXPORTACION TEMPORARIA CON TRANSFORMACION GRAN OPERADOR	Exportación temporal con transformación por empresas contempladas en el régimen de Aduanas Domiciliarias
EGT2	TEMPORALES	EXPTEMST	EXPORTACION TEMPORARIA SIN TRANSFORMACION GRAN OPERADOR	Exportación temporal sin transformación por empresas contempladas en el régimen de Aduanas Domiciliarias
ER01	RANCHO	EXPCON	EXPORTACION RANCHO COMBUSTIBLE DE BUQUE BANDERA EXTRANJERA	Exportación de rancho de combustible para buque de bandera extranjera
ER02	RANCHO	\N	Rancho para medios de transporte de bandera nacional	\N
ER03	RANCHO	\N	Rancho y aprovisionamiento de medios de transporte de bandera extranjera, excepto combustibles y lubricantes	\N
ER04	RANCHO	\N	Rancho y aprovisionamiento de medios de transporte de bandera nacional, excepto combustibles y lubricantes	\N
ER05	RANCHO	\N	Rancho y aprovisionamiento de medios de transporte de bandera extranjera, excepto combustibles y lubricantes	\N
ER06	RANCHO	\N	Rancho y aprovisionamiento de medios de transporte de bandera nacional, excepto combustibles y lubricantes	\N
ES01	EN CONSIGNACIÓN	EXPCON	EXPORTACION DE MERCADERIAS EN CONSIGNACION	Exportación de mercaderías en consignación
ES02	EN CONSIGNACIÓN	EXPCON	EXPORTACION DE MERCADERIAS CON PRECIOS REVISABLES	Exportación de mercaderías con precios revisables
ES03	EN CONSIGNACIÓN	EXPCON	EXPORTACION DE CONCENTRADO DE MINERALES	Exportación de concentrado de minerales
ET01	TEMPORALES	EXPTEMCT	EXPORTACION TEMPORARIA CON TRANSFORMACION	Exportación temporal con transformación
ET02	TEMPORALES	EXPTEMST	EXPORTACION TEMPORARIA SIN TRANSFORMACION	Exportación temporal sin transformación
ETA1	TEMPORALES	IMPTEMCT	EGRESO TEMPORALMENTE EN EL TNC DE MERCADERIA PROVENIENTE DEL AAE	Egreso temporal hacia el Territorio Nacional Continental de mercadería proveniente del Área Aduanera Especial
ETE1	TEMPORALES	EXPTEMCT	EGRESO TEMPORALMENTE DEL AAE AL EXTERIOR CON TRANSPORTE TERRESTRE POR TNC	Egreso temporal de mercadería con transformación, desde el Área Aduanera Especial al exterior, con Tránsito terrestre por el Territorio Nacional Continental
ETE2	TEMPORALES	EXPTEMST	EGRESO TEMPORAL CON TRANSPORTE TERRESTRE POR EL TNC SIN TRANSFORMACION	Egreso temporal de mercadería sin transformación, desde el Área Aduanera Especial al exterior, con Tránsito terrestre por el Territorio Nacional Continental
EXRS	CONSUMO	EXPCON	EXPORTACION REGIMEN SIMPLIFICADO DECRETO NRO. 855/97	Exportación a consumo según lo normado para el régimen simplificado de exportación
IC01	CONSUMO	IMPCON	IMPORTACION A CONSUMO SIN DOCUMENTO DE TRANSPORTE	Importación para consumo de mercaderías que arriben sin documento de transporte, por la vía postal o por propios medios
IC02	CONSUMO	IMPCON	IMPORTACION A CONSUMO MERCADERIA REGIMEN DE SOLICITUD PREVIA	Importación para consumo de mercaderías perecederas, sujetas al régimen de solicitud previa
IC03	CONSUMO	IMPCON	IMPORTACION CONSUMO DE MERCADERIA VIA TERRESTRE EN ENVIOS FRACCIONADOS	Importación para consumo de mercaderías arribadas en forma fraccionada y destinadas a partir del arribo de la primera fracción
IC04	CONSUMO	IMPCON	IMPORTACION A CONSUMO CON DOCUMENTO DE TRANSPORTE	Importación para consumo de mercaderías destinadas después del arribo del medio de transporte con documento de transporte, con ingreso a depósito
IC05	CONSUMO	IMPCON	IMPORTACION A CONSUMO CON DOCUMENTO DE TRANSPORTE DAP	Importación para consumo de mercaderías cuya destinación puede ser registrada con anterioridad al arribo del medio de transporte para su despacho directo a plaza
IC06	CONSUMO	IMPCON	IMPORTACION A CONSUMO SOBRE DEPÓSITO DE ALMACENAMIENTO	Importación para consumo de mercaderías previamente destinadas a depósito de almacenamiento
IC07	CONSUMO	IMPCON	IMPORTACION A CONSUMO REGIMEN AUTOMOTRIZ CON DOCUMENTO DAP	Importación para consumo de mercaderías comprendidas en el régimen automotor cuya destinación puede ser registrada con anterioridad al arribo del medio de transporte para su despacho directo a plaza
IC21	CONSUMO	RETEXTECT	RETORNO EXPORTACION TEMPORAL CON TRANSFORMACION SIN DOCUMENTO DE TRANSPORTE	Retorno de mercaderías exportadas temporariamente para ser objeto de transformación, que arriben sin documento de transporte, por vía postal o propios medios
IC24	CONSUMO	RETEXTECT	RETORNO EXPORTACION TEMPORAL CON TRANSFORMACION CON DOCUMENTO DE TRANSPORTE	Retorno de mercaderías exportadas temporariamente para ser objeto de transformación, cuya solicitud de destinación de importación se presente con posterioridad al arribo del medio transportador y con ingreso a depósito
IC25	CONSUMO	RETEXTECT	RETORNO EXPORTACION TEMPORAL CON TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP	Retorno de mercaderías exportadas temporariamente para ser objeto de transformación, cuya solicitud de destinación de importación pueda ser registrada con anterioridad al arribo del medio transportador para su despacho directo a plaza
IC26	CONSUMO	RETEXTECT	RETORNO EXPORTACION TEMPORAL CON TRANSFORMACION SOBRE DEPÓSITO DE ALMACENAMIENTO	Retorno de mercaderías exportadas temporariamente para ser objeto de transformación, previamente des tinadas a depósito de almacenamiento
IC31	CONSUMO	RETEXTEST	RETORNO EXPORTACION TEMPORAL SIN TRANSFORMACION SIN DOCUMENTO TRANSPORTE	Retorno de mercaderías en el mismo estado en que hubiesen sido exportadas temporariamente arribadas sin documento de transporte, por vía postal o propios medios
IC34	CONSUMO	RETEXTEST	RETORNO EXPORTACION TEMPORAL SIN TRANSFORMACION CON DOCUMENTO DE TRANSPORTE	Retorno de mercaderías en el mismo estado en que hubieren sido exportadas temporariamente sin transformación, cuya solicitud de destinación se presente con posterioridad al arribo del medio transportador y con ingreso a depósito
IC35	CONSUMO	RETEXTEST	RETORNO EXPORTACION TEMPORAL SIN TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP	Retorno de mercaderías en el mismo estado en que hubieren sido exportadas temporariamente sin transformación, cuya solicitud de destinación puede ser registrada con anterioridad al arribo del medio de transporte para su despacho directo a plaza
IC36	CONSUMO	RETEXTEST	RETORNO EXPORTACION TEMPORAL SOBRE DEPÓSITO DE ALMACENAMIENTO	Retorno de mercaderías en el mismo modo en que hubieren sido exportadas sin transformación, previamente, destinadas a depósito de almacenamiento
IC41	CONSUMO	RETEXTEST	RETORNO DE EXPORTACION EN CONSIGNACIÓN SIN DOCUMENTO DE TRANSPORTE	Retorno de mercaderías hubieren sido exportadas en consignación sin documento de transporte, por vía postal o propios medios
IC44	CONSUMO	RETEXTEST	RETORNO DE EXPORTACION EN CONSIGNACION CON DOCUMENTO DE TRANSPORTE	Retorno de mercaderías hubieren sido exportadas en consignación con documento de transporte con ingreso a depósito
IC45	CONSUMO	RETEXTEST	RETORNO DE EXPORTACION EN CONSIGNACION CON DOCUMENTO DE TRANSPORTE DAP	Retorno de mercaderías exportadas en consignación, cuya destinación puede ser registrada con anterioridad al arribo del medio transportador, para su despacho directo a plaza.
IC51	CONSUMO	VALORES	IMPORTACION DE VALORES	Declaración de ingreso de valores(Billetes, Monedas, etc.)
IC55	CONSUMO	VALORES	IMPORTACION DE VALORES DAP	Declaración de ingreso de valores(Billetes, Monedas, etc.)por el régimen de directo a plaza, que puede ser registrada con anterioridad al arribo del medio transportador
IC81	CONSUMO	IMPCONTEMCT	IMPORTACION A CONSUMO DE IMPORTACION TEMPORAL CON TRANSFORMACION	Importación a consumo de mercaderías previamente importadas temporalmente con transformación
IC82	CONSUMO	IMPCONTEMRESIDUO	IMPORTACION A CONSUMO DE RESIDUOS DE IMPORTACION TEMPORAL CON TRANSFORMACION	Importación a consumo de residuos de mercaderías previamente importadas temporalmente con transformación
IC83	CONSUMO	IMPCONTEMST	IMPORTACION A CONSUMO DE IMPORTACION TEMPORARIA SIN TRANSFORMACION	Importación a consumo de mercaderías previamente importadas temporalmente sin transformación
IDA2	DEPOSITO	IMPDEPALMACEN	IMPORTACION SUSPENSIVA DE DEPÓSITO DE ALMACENAMIENTO	Importación suspensiva de depósito de almacenamiento
IDTL	DEPOSITO	IMPDEPALMACEN	DECLARACION PARA EL FRACCIONAMIENTO DE LOS BULTOS DE UN DOCUMENTO DE TRANSPORTE	Declaración detallada que permite el fraccionamiento de un documento de transporte para hacer traslado detallado a más de un depósito
IG01	CONSUMO	IMPCON	IMPORTACION A CONSUMO P/GRANDES OPERADORES S/DOCUMENTO DE TRANSPORTE	Importación a consumo sin documento de transporte por empresas contempladas en el régimen de Aduanas Domiciliarias
IG03	CONSUMO	IMPCON	IMPORTACIÓN A CONSUMO VÍA TERRESTRE ENVÍOS FRACCIONADOS GRANDES OPERADORES	Importación para consumo de mercaderías arribadas en forma fraccionada y destinadas a partir del arribo de la primera fracción por empresas contempladas en el régimen de Aduanas Domiciliarias
IG04	CONSUMO	IMPCON	IMPORTACIÓN A CONSUMO CON DOCUMENTO DE TRANSPORTE GRANDES OPERADORES	Importación para consumo de mercaderías destinadas después del arribo del medio de transporte con ingreso a depósito realizada por empresas contempladas en el régimen de Aduanas Domiciliarias
IG05	CONSUMO	IMPCON	IMPORTACIÓN A CONSUMO CON DOCUMENTO DE TRANSPORTE DIRECTO A PLAZA GRANDES OPERADORES	Importación para consumo para el régimen de Aduanas Domiciliarias cuya destinación puede ser registrada con anterioridad al arribo del medio transportador
IG06	CONSUMO	IMPCON	IMPORTACIÓN A CONSUMO SOBRE COPIA DE DEPÓSITO DE ALMACENAMIENTO GRANDES OPERADORES	Importación para consumo de mercaderías previamente destinadas a depósito de almacenamiento por empresas contempladas en el régimen de Aduanas Domiciliarias
IG07	CONSUMO	IMPCON	IMPORTACIÓN A CONSUMO CON AUTORIZACIÓN PROVISORIA DE ENTREGA GRANDES OPERADORES	Importación a consumo de mercaderías comprendidas en el régimen automotor, por empresas contempladas en el régimen de Aduanas Domiciliarias
IT01	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORARIA SIN TRANSFORMACION SIN DOCUMENTO DE TRANSPORTE	Importación temporal sin transformación de mercaderías que arriben sin documento de transporte, por la vía postal o propios medios
IT03	TEMPORALES(AT)	IMPTEMST	IMPORT. TEMPORAL SIN TRANSFORMACION VIA TERRESTRE DE ENVIOS FRACCIONADOS	Importación temporal sin transformación de mercaderías arribadas en forma fraccionada y destinadas a partir del arribo de la primera fracción
IT04	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORARIA SIN TRANSFORMACION CON DOCUMENTO DE TRANSPORTE	Importación temporal sin transformación de mercaderías destinadas después del arribo del medio de transporte
IT05	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORARIA SIN TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP	Importación temporal sin transformación de mercaderías destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza
IT06	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORARIA SIN TRANSFORMACION SOBRE DEPÓSITO DE ALMACENAM. IENTO	Importación temporal sin transformación de mercaderías previamente destinadas a depósito de almacenamiento
IT07	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORAL REGIMEN AUTOMOTRIZ SIN TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP	Importación temporal sin transformación de mercaderías comprendidas en el régimen automotor destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza
IT11	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORARIA PARA TRANSFORMACION SIN DOCUMENTO DE TRANSPORTE	Importación temporal con transformación de mercaderías que arriben sin documento de transporte, por la vía postal o propios medios
IT13	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORAL CON TRANSFORMACION VIA TERRESTRE DE ENVIOS FRACCIONADOS	Importación temporal con transformación de mercaderías arribadas en forma fraccionada y destinadas a partir del arribo de la primera fracción
IT14	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORARIA PARA TRANSFORMACION CON DOCUMENTO DE TRANSPORTE	Importación temporal con transformación de mercaderías destinadas después del arribo del medio de transporte con ingreso a depósito
IT15	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORARIA PARA TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP	Importación temporal con transformación de mercaderías destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza
IT16	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORARIA CON TRANSFORMACION SOBRE DEPÓSITO DE ALMACENAMIENTO	Importación temporal con transformación de mercaderías previamente destinadas a depósito de almacenamiento
IT17	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORAL REGIMEN AUTOMOTRIZ SIN TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP	Importación temporal con transformación de mercaderías comprendidas en el régimen automotor destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza
LAPI	LAPI	IMPDEPALMACEN	LICENCIA AUTOMATICA PREVIA DE IMPORTACION	Licencia Automática previa de importación
RE01	CONSUMO	REEMBARCO	REEMBARCO SIN DOCUMENTO DE TRANSPORTE	Reembarco de mercadería sin documento de transporte, arribadas por vía postal o por propios medios
RE04	CONSUMO	REEMBARCO	REEMBARCO CON DOCUMENTO DE TRANSPORTE	Reembarco de mercadería ingresada a depósito
RE05	CONSUMO	REEMBARCO	REEMBARCO CON DOCUMENTO DE TRANSPORTE DAP	Reembarco de mercadería sin ingreso a depósito, bajo el régimen de directo a plaza
RE06	CONSUMO	REEMBARCO	REEMBARCO SOBRE DESTINACION SUSPENSIVA DE ALMACENAMIENTO	Reembarco de mercadería sobre una destinación suspensiva de almacenamiento
REM1	CONSUMO	REEMBARCO	Destinación Suspensiva de Removido	\N
REMO	CONSUMO	EXPCON	GUIA DE REMOVIDO	Guía de Removido
RZ06	DEPOSITO	IMPDEPALMACEN	REZAGO DE MERCADERIA DE DESTINACION SUSPENSIVA DE ALMACENAMIENTO	Destinación de Oficio para mercadería en situación de rezago, sobre una destinación suspensiva de almacenamiento
RZF1	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI1
RZF2	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI2
RZF3	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI3
RZF4	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI4
RZF5	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI5
RZF6	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI6
RZF7	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI7
RZF8	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS CON REENVASADO O REENVASADO USUARIO	Transferencia entre usuarios directos y/o indirectos con reenvasado, o reenvasado por parte del usuario dueño de la mercadería registrado sobre ZFI8
TB04	TRANSITO	TRASBORDO	TRASBORDO CON DOCUMENTO DE TRANSPORTE	Trasbordo de mercaderías con documento de transporte y con ingreso a depósito
TB05	TRANSITO	TRASBORDO	TRASBORDO CON DOCUMENTO DE TRANSPORTE DAP	Trasbordo con documento de transporte bajo el régimen de directo a plaza
TG01	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORAL SIN TRANSFORMACION SIN DOCUMENTO DE TRANSPORTE GRANDES OPERADORES	Importación temporal sin transformación de mercaderías que arriben sin documento de transporte, por la vía postal o propios medios por empresas contempladas en el régimen de Aduanas Domiciliarias
TG04	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORAL CON DOCUMENTO DE TRANSPORTE SIN TRANSFORMACION GRANDES OPERADORES	Importación temporal sin transformación de mercaderías destinadas después del arribo del medio de transporte por empresas contempladas en el régimen de Aduanas Domiciliarias
TG05	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORAL SIN TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP GRANDES OPERADORES	Importación temporal sin transformación de mercaderías destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza por empresas contempladas en el régimen de Aduanas Domiciliarias
TG06	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORAL SIN TRANSFORMACION SOBRE DEPÓSITO DE ALMACENAMIENTO GRANDES OPERADORES	Importación temporal sin transformación de mercaderías previamente destinadas a depósito de almacenamiento por empresas contempladas en el régimen de Aduanas Domiciliarias
TG07	TEMPORALES(AT)	IMPTEMST	IMPORTACION TEMPORAL SIN TRANSFORMACION DAP	Importación temporal sin transformación de mercaderías comprendidas en el régimen automotriz destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza por empresas contempladas en el régimen de Aduanas Domiciliarias
TG11	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORAL CON TRANSFORMACION SIN DOCUMENTO DE TRANSPORTE GRANDES OPERADORES	Importación temporal con transformación de mercaderías que arriben sin documento de transporte, por la vía postal o propios medios por empresas contempladas en el régimen de Aduanas Domiciliarias
TG14	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORAL PARA TRANSFORMACION CON DOCUMENTO DE TRANSPORTE GRANDES OPERADORES	Importación temporal con transformación de mercaderías destinadas después del arribo del medio de transporte por empresas contempladas en el régimen de Aduanas Domiciliarias
TG15	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORARIA PARA TRANSFORMACION CON DOCUMENTO DE TRANSPORTE DAP GRANDES OPERADORES	Importación temporal con transformación de mercaderías destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza por empresas contempladas en el régimen de Aduanas Domiciliarias
TG16	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORAL PARA TRANSFORMACION SOBRE DEPÓSITO DE ALMACENAMIENTO GRANDES OPERADORES	Importación temporal con transformación de mercaderías previamente destinadas a depósito de almacenamiento por empresas contempladas en el régimen de Aduanas Domiciliarias
TG17	TEMPORALES(AT)	IMPTEMCT	IMPORTACION TEMPORAL CON TRANSFORMACION GRANDES OPERADORES DAP	Importación temporal con transformación de mercaderías comprendidas en el régimen automotor destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza por empresas contempladas en el régimen de Aduanas Domiciliarias
TL04	TRANSITO	TRASLADO	TRASLADO DETALLADO CON DOCUMENTO DE TRANSPORTE	Traslado detallado de mercaderías destinadas después del arribo del medio de transporte
TL05	TRANSITO	TRASLADO	TRASLADO DETALLADO CON DOCUMENTO DE TRANSPORTE DAP	Traslado detallado de mercaderías con documento de transporte bajo el régimen de directo a plaza
TL06	TRANSITO	TRASLADO	TRASLADO DETALLADO CON DOCUMENTO DE TRANSPORTE A MAS DE UN DEPÓSITO FISCAL	Traslado detallado de mercaderías, a más de un depósito fiscal, destinadas después del arribo del medio de transporte
TR01	TRANSITO	TRAIMPST	TRANSITO DE IMPORTACION SIN DOCUMENTO DE TRANSPORTE	Transito detallado de mercaderías sin documento de transporte, por vía postal o por propios medios
TR04	TRANSITO	TRAIMPCT	TRANSITO DE IMPORTACION CON DOCUMENTO DE TRANSPORTE	Tránsito detallado con documento de transporte de mercaderías ingresadas a depósito y destinadas después del arribo del medio de transporte
TR05	TRANSITO	TRAIMPCT	TRANSITO DE IMPORTACION CON DOCUMENTO DE TRANSPORTE DAP	Tránsito detallado de mercaderías destinadas con anterioridad al arribo del medio de transporte para su despacho directo a plaza
TR06	TRANSITO	TRAIMPST	TRANSITO DE IMPORTACION SOBRE DEPÓSITO DE ALMACENAMIENTO	Tránsito detallado de mercaderías previamente destinadas a depósito de almacenamiento
TZF1	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI1
TZF2	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI2
TZF3	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI3
TZF4	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI4
TZF5	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI5
TZF6	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y/O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI6
TZF7	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI7
TZF8	DEPOSITO	IMPDEPALMACEN	TRANSFERENCIA ENTRE USUARIOS DIRECTOS Y / O INDIRECTOS	Transferencia entre usuarios directos y/o indirectos registrado sobre ZFI8
ZFE1	CONSUMO	IMPCON	EGRESO ZF PARA CONSUMO EN EL TERRITORIO	Egreso de zona franca para consumo en el territorio aduanero
ZFE2	CONSUMO	EXPCON	EGRESO POR AEROPUERTO PUERTO DE LA ZF EN EL MISMO ESTADO AL EXTERIOR	Egreso por aeropuerto puerto de la zona franca en el mismo estado al exterior
ZFE3	CONSUMO	IMPCON	EGRESO DE ZF DE UN PRODUCTO DE UN PROCESO PRODUCTIVO AL T. A	Egreso de zona franca de un producto de un proceso productivo al territorio aduanero
ZFE4	CONSUMO	EXPCON	EGRESO DE ZF DE UN PRODUCTO DE UN PROCESO PRODUCTIVO O REPARACION AL EXTERIOR	Egreso de zona franca de un producto de un proceso productivo o reparación al exterior
ZFE5	CONSUMO	IMPCON	EGRESO DE ZF DE UN RESIDUO DE UN PROCESO PRODUCTIVO CON VALOR COMERCIAL AL T. A	Egreso de zona franca de un residuo de un proceso productivo con valor comercial al territorio aduanero
ZFE6	CONSUMO	EXPCON	EGRESO DE ZF DE UN RESIDUO DE UN PROCESO PRODUCTIVO CON VALOR COMERCIAL AL EXTERIOR	Egreso de zona franca de un residuo de un proceso productivo con valor comercial al exterior
ZFER	CONSUMO	IMPCON	RETORNO AL T. A. DE ACUERDO AL ART. 566 DEL C. A	Retorno al territorio aduanero de acuerdo al art. 566 del Código Aduanero
ZFET	CONSUMO	IMPCON	RETORNO AL T. A. DE MERCADERIA EXPORTADA TEMPORALMENTE	Retorno al territorio aduanero de mercadería exportada temporalmente
ZFI1	ZF	IMPDEPALMACEN	INGRESO A ZF DE BIENES DE CAPITAL DE LIBRE CIRCULACION PARA RADICACION DEFINITIVA DE T. A	Ingreso a zona franca de bienes de capital de libre circulación para radicación definitiva, del territorio aduanero
ZFI2	ZF	IMPDEPALMACEN	INGRESO A ZF DE VITUALLAS Y MERCADERIAS DESTINADAS A CONSTRUCCION INSTALACIONES DEL EXTERIOR	Ingreso a zona franca de vituallas y mercaderías destinadas a construcción instalaciones del exterior
ZFI3	ZF	IMPDEPALMACEN	INGRESO A ZF DE BIENES DE CAPITAL PARA RADICACION DEFINITIVA DEL EXTERIOR	Ingreso a zona franca de bienes de capital para radicación definitiva, del exterior
ZFI4	ZF	IMPDEPALMACEN	\N	Ingreso a zona franca de mercadería de libre circulación para almacenamiento / comercialización y/o reparación, del territorio aduanero
ZFI5	ZF	IMPDEPALMACEN	INGRESO A ZF DE MERCADERIA PARA ALMACENAMIENTO / COMERCIALIZACION / REPARACION DEL EXT	Ingreso a zona franca de mercadería para almacenamiento y/o comercialización y/o reparación, del exterior
ZFI6	ZF	IMPDEPALMACEN	INGRESO A ZF DE INSUMOS DE LIBRE CIRCULACION EN FORMA TEMPORAL PARA UN PROCESO PRODUCTIVO DE T. A	Ingreso a zona franca de insumos de libre circulación en forma temporal para un proceso productivo, del territorio aduanero
ZFI7	ZF	IMPDEPALMACEN	INGRESO A ZF DE INSUMOS DE LIBRE CIRCULACION PARA UN PROCESO PRODUCTIVO DESDE T. A	Ingreso a zona franca de insumos de libre circulación para un proceso productivo, desde el territorio aduanero
ZFI8	ZF	IMPDEPALMACEN	INGRESO A ZF DE INSUMOS PARA PROCESOS PRODUCTIVOS DEL EXTERIOR	Ingreso a zona franca de insumos para procesos productivos, del exterior
ZFRE	CONSUMO	REEMBARCO	REEMBARCO POR AEROPUERTO / PUERTO DE LA ZF EN EL MISMO ESTADO	Reembarco por aeropuerto / puerto de la zona franca en el mismo estado
ZFTR	TRANSITO	TRAIMPST	EGRESO DE ZF EN TRANSITO AL EXTERIOR EN EL MISMO ESTADO DE INGRESO	Egreso de zona franca en transito al exterior en el mismo estado de ingreso
DIRR	CONSUMO	\N	Declaración de Ingreso al RAF	Importación a consumo de bienes transformados RAF
IC67	CONSUMO	\N	Importación a consumo de mercadería IMO D. A. P. con MANI registrado	MERCADERIA PELIGROSA
ICR1	CONSUMO	\N	Importación a consumo de bienes transformados	\N
ICR2	CONSUMO	\N	Importación a consumo de bienes no transformados RAF	\N
ICR3	CONSUMO	\N	Importación a consumo de mercaderías pendientes de cancelación RAF	- Este subrégimen cancelará las DIRR vencidas a nivel de ítem y unidades
ICR4	CONSUMO	\N	Importación de residuos de procesos productivos RAF	\N
ICRS	CONSUMO	\N	ICRS - Por determinar (agregado automáticamente)	-- TODO: Revisar descripción correcta del código ICRS según documentación AFIP
IG84	CONSUMO	IMPCONTEMRESIDUO	DECLARACIÓN DE PÉRDIDAS TANGIBLES P/ GRANDES OPERADORES	\N
IS14	CONSUMO	\N	Nacionalización de vehículos automóviles importados por el Régimen de Franquicias Diplomáticas	\N
IS21	CONSUMO	\N	Nacionalización de vehículos automóviles importados por el Régimen de Franquicias Diplomáticas	\N
IS31	CONSUMO	\N	Nacionalización de vehículos automóviles importados por el Régimen de Franquicias Diplomáticas	\N
PE01	CONSUMO	\N	Particular Exportación para consumo	\N
PE02	CONSUMO	\N	Particular Exportación para consumo de Exportación Temporal	\N
PER1	CONSUMO	\N	Particular Exportación de Importación Temporal	\N
PET1	CONSUMO	\N	Particular Exportación Temporal	\N
PI01	CONSUMO	\N	Particular Importación sin documento de transporte	\N
PI04	CONSUMO	\N	Particular Importación con documento de transporte	\N
PI05	CONSUMO	\N	Particular Importación con documento de transporte - D. A. P	\N
PI06	CONSUMO	\N	Particular Importación sobre depósito de almacenamiento	\N
PI83	CONSUMO	\N	Importación a consumo de Particular Importación temporal	\N
PIT1	AT	\N	Particular Importación Temporal sin documento de transporte	\N
PIT4	AT	\N	Particular Importación Temporal con documento de transporte	\N
PIT5	AT	\N	Particular Importación Temporal con documento de transporte - D. A. P	\N
PRI1	AT	\N	Particular Retorno de Salida Temporal sin documento de transporte	\N
PRI4	AT	\N	Particular Retorno de Salida Temporal con documento de transporte	\N
PRI5	AT	\N	Particular Retorno de Salida Temporal con documento de transporte - D. A. P	\N
PRI6	AT	\N	Particular Retorno de Salida Temporal sobre depósito de almacenamiento	\N
PZF1	CONSUMO	\N	Particular de Egreso de Zona Franca para consumo	\N
REBA	REEMBARCO	\N	Retorno de combustible documentado a través de una Declaración BARA	\N
REP1	REEMBARCO	\N	Reembarco Particular sin Documento de Transporte	\N
REP4	REEMBARCO	\N	Reembarco Particular con Documento de Transporte	\N
REP6	REEMBARCO	\N	Reembarco Particular sobre Destinación Suspensiva de Almacenamiento	\N
RR01	REEMBARCO	\N	Retorno al exterior de mercaderías no utilizadas por el RAF	- Retorno al exterior en el mismo estado que arribó
TLR1	TRANSITO	\N	Destinación suspensiva de removido	\N
TRP1	TRANSITO	\N	Tránsito de Particular Importación sin documento de transporte	\N
TRP4	TRANSITO	\N	Tránsito de Particular Importación con documento de transporte	\N
TRP5	TRANSITO	\N	Tránsito de Particular Importación con documento de transporte - D. A. P	\N
\.


-- Finalizar transacción
COMMIT;

-- Verificaciones finales
SELECT 'Inserción completada exitosamente' as mensaje;
SELECT COUNT(*) as total_destinaciones FROM destinaciones;

-- Estadísticas por tipo
SELECT 
    tipo,
    COUNT(*) as cantidad,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM destinaciones), 2) as porcentaje
FROM destinaciones 
GROUP BY tipo 
ORDER BY cantidad DESC;

-- Verificar códigos duplicados (no debería haber)
SELECT 
    codigo,
    COUNT(*) as duplicados
FROM destinaciones 
GROUP BY codigo 
HAVING COUNT(*) > 1;

-- ============================================================================
-- INSERCIÓN COMPLETADA - 2025-10-16 13:12:26
-- Total insertado: 219 destinaciones (218 originales + 1 ICRS agregado automáticamente)
-- NOTA: Se agregó ICRS temporalmente - REVISAR descripción correcta
-- ============================================================================
