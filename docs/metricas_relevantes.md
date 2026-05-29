# Métricas relevantes para mapas dinámicos de Chile

Este documento reúne métricas potenciales para extender el proyecto **Mapas Dinámicos Chile**.

La lógica recomendada es mantener una base única en formato largo:

```text
codigo_comuna | anio | id_metrica | valor | unidad | fuente
```

Cada nueva métrica debe incorporarse al pipeline con:

```text
fuente documentada
descarga reproducible
limpieza
validación
actualización de base final
visualización en la app
```

---

## 1. Inseguridad y delitos

Prioridad alta para el proyecto, especialmente para análisis territorial en la Región Metropolitana.

| id_metrica sugerido | Nombre | Unidad sugerida | Comentario |
|---|---|---|---|
| `homicidios` | Homicidios | casos | Casos absolutos por comuna y año. |
| `tasa_homicidios_100k_hab` | Tasa de homicidios | casos por 100.000 habitantes | Métrica prioritaria. Requiere población como denominador. |
| `robos_con_violencia` | Robos con violencia | casos | Útil para comparar comunas urbanas. |
| `tasa_robos_con_violencia_100k_hab` | Tasa de robos con violencia | casos por 100.000 habitantes | Mejor que casos absolutos para comparación territorial. |
| `delitos_mayor_connotacion_social` | Delitos de mayor connotación social | casos | Indicador amplio de criminalidad. |
| `tasa_dmcs_100k_hab` | Tasa de delitos de mayor connotación social | casos por 100.000 habitantes | Permite comparación comunal ajustada por población. |
| `violencia_intrafamiliar` | Violencia intrafamiliar | casos | Indicador relevante de seguridad y vulnerabilidad social. |
| `incivilidades` | Incivilidades | casos | Útil para percepción de deterioro urbano. |
| `denuncias_total` | Denuncias totales | casos | Indicador agregado. Requiere interpretar cambios en denuncia. |
| `detenciones_total` | Detenciones totales | casos | Complementa denuncias, pero no mide directamente ocurrencia delictual. |

### Fuentes potenciales

- CEAD / Subsecretaría de Prevención del Delito.
- Ministerio del Interior y Seguridad Pública.
- Fiscalía.
- Carabineros.
- INE, cuando existan estadísticas policiales o judiciales disponibles.

### Notas metodológicas

- Preferir tasas por 100.000 habitantes para comparar comunas.
- Mantener también los casos absolutos.
- Documentar si los datos corresponden a denuncias, detenciones, víctimas, causas o hechos policiales.
- Evitar mezclar definiciones de distintas fuentes sin trazabilidad.

---

## 2. Vulnerabilidad social

Métricas útiles para cruzar con inseguridad, salud, urbanismo y oportunidades territoriales.

| id_metrica sugerido | Nombre | Unidad sugerida | Comentario |
|---|---|---|---|
| `pobreza_por_ingresos` | Pobreza por ingresos | porcentaje | Puede no estar disponible anualmente a nivel comunal. |
| `pobreza_multidimensional` | Pobreza multidimensional | porcentaje | Muy útil para desigualdad territorial. |
| `ingreso_promedio_hogar` | Ingreso promedio del hogar | pesos | Requiere revisar comparabilidad temporal. |
| `hacinamiento` | Hacinamiento | porcentaje | Relevante para vulnerabilidad habitacional. |
| `escolaridad_promedio` | Escolaridad promedio | años | Indicador estructural de capital humano. |
| `personas_mayores_porcentaje` | Personas mayores | porcentaje | Puede derivarse de población por edad. |
| `poblacion_migrante_porcentaje` | Población migrante | porcentaje | Relevante para dinámicas urbanas recientes. |

### Fuentes potenciales

- Encuesta CASEN.
- Observatorio Social, Ministerio de Desarrollo Social y Familia.
- Censo / INE.
- Estimaciones comunales oficiales cuando existan.

### Notas metodológicas

- CASEN no necesariamente es anual.
- Algunas métricas pueden ser estimadas o modeladas a nivel comunal.
- Documentar año, metodología y nivel de precisión.

---

## 3. Salud y mortalidad

Permiten mapear desigualdades territoriales en condiciones sanitarias.

| id_metrica sugerido | Nombre | Unidad sugerida | Comentario |
|---|---|---|---|
| `mortalidad_general` | Mortalidad general | defunciones | Casos absolutos. |
| `tasa_mortalidad_100k_hab` | Tasa de mortalidad general | defunciones por 100.000 habitantes | Requiere población como denominador. |
| `mortalidad_cancer` | Mortalidad por cáncer | defunciones | Puede agregarse por comuna y año. |
| `mortalidad_cardiovascular` | Mortalidad cardiovascular | defunciones | Indicador sanitario relevante. |
| `nacimientos` | Nacimientos | casos | Base para natalidad. |
| `tasa_natalidad` | Tasa de natalidad | nacimientos por 1.000 habitantes | Métrica demográfica clásica. |
| `esperanza_vida_aproximada` | Esperanza de vida aproximada | años | Puede requerir metodología adicional. |

### Fuentes potenciales

- DEIS / MINSAL.
- INE, estadísticas vitales.
- MINSAL, tableros e indicadores sanitarios.

### Notas metodológicas

- Distinguir entre conteos absolutos y tasas.
- Para comunas pequeñas, las tasas pueden ser inestables.
- Evaluar uso de promedios móviles para eventos poco frecuentes.

---

## 4. Desarrollo urbano y vivienda

Muy relevante para Santiago y expansión metropolitana.

| id_metrica sugerido | Nombre | Unidad sugerida | Comentario |
|---|---|---|---|
| `permisos_edificacion` | Permisos de edificación | permisos | Indicador de actividad inmobiliaria. |
| `superficie_aprobada_m2` | Superficie aprobada | m² | Permite ver intensidad de construcción. |
| `viviendas_nuevas` | Viviendas nuevas aprobadas | viviendas | Útil para crecimiento urbano. |
| `densidad_poblacional` | Densidad poblacional | habitantes por km² | Puede derivarse de población y superficie comunal. |
| `areas_verdes_m2_por_habitante` | Áreas verdes por habitante | m² por habitante | Indicador urbano y ambiental. |
| `distancia_a_transporte_publico` | Distancia a transporte público | metros | Puede requerir análisis geoespacial. |
| `equipamiento_comunal` | Equipamiento comunal | conteo o índice | Requiere definir tipologías. |

### Fuentes potenciales

- INE, permisos de edificación.
- MINVU.
- Observatorio Urbano.
- IDE Chile.
- Datos municipales abiertos.
- OpenStreetMap, si se documenta como fuente complementaria.

### Notas metodológicas

- Algunas métricas son comunales anuales; otras requieren análisis espacial.
- La densidad poblacional puede construirse desde datos ya existentes.
- Las áreas verdes requieren definir qué se considera área verde.

---

## 5. Movilidad y transporte

Capa relevante para análisis metropolitano y accesibilidad urbana.

| id_metrica sugerido | Nombre | Unidad sugerida | Comentario |
|---|---|---|---|
| `estaciones_metro_por_comuna` | Estaciones de Metro por comuna | estaciones | Indicador simple de cobertura. |
| `paraderos_red_por_comuna` | Paraderos RED por comuna | paraderos | Útil para accesibilidad. |
| `accesibilidad_transporte_publico` | Accesibilidad a transporte público | índice | Requiere metodología propia. |
| `tiempo_promedio_viaje` | Tiempo promedio de viaje | minutos | Puede venir de encuestas o modelos. |
| `vehiculos_por_habitante` | Vehículos por habitante | vehículos por habitante | Puede derivarse de permisos de circulación y población. |
| `permisos_circulacion` | Permisos de circulación | permisos | Indicador disponible en varias fuentes municipales/INE. |

### Fuentes potenciales

- Ministerio de Transportes y Telecomunicaciones.
- Directorio de Transporte Público Metropolitano.
- Metro de Santiago.
- SECTRA.
- INE, permisos de circulación.
- Datos municipales.

### Notas metodológicas

- Algunas métricas son infraestructura fija, no necesariamente anuales.
- Para series temporales, priorizar permisos de circulación y cambios de infraestructura por año.
- Accesibilidad puede requerir análisis espacial adicional.

---

## 6. Economía local y actividad productiva

Métricas para comparar dinamismo económico comunal.

| id_metrica sugerido | Nombre | Unidad sugerida | Comentario |
|---|---|---|---|
| `empresas_activas` | Empresas activas | empresas | Puede obtenerse por comuna y rubro. |
| `trabajadores_dependientes` | Trabajadores dependientes | trabajadores | Indicador laboral territorial. |
| `ventas_empresas` | Ventas de empresas | pesos o UF | Requiere revisar disponibilidad y anonimización. |
| `patentes_comerciales` | Patentes comerciales | patentes | Puede depender de datos municipales. |
| `desempleo_estimado` | Desempleo estimado | porcentaje | Puede no existir anual a nivel comunal. |
| `informalidad_laboral` | Informalidad laboral | porcentaje | Normalmente difícil a nivel comunal anual. |

### Fuentes potenciales

- Servicio de Impuestos Internos.
- INE.
- Municipios.
- Ministerio de Economía.
- DataChile u otras fuentes trazables.

### Notas metodológicas

- Algunas fuentes económicas pueden tener restricciones de acceso.
- Revisar comparabilidad temporal.
- Documentar si los datos son por domicilio tributario, establecimiento o actividad económica.

---

## Orden recomendado de implementación

1. `tasa_homicidios_100k_hab`
2. `delitos_mayor_connotacion_social`
3. `pobreza_multidimensional`
4. `densidad_poblacional`
5. `permisos_edificacion`
6. `areas_verdes_m2_por_habitante`
7. `tasa_mortalidad_100k_hab`
8. `empresas_activas`

---

## Métrica prioritaria siguiente

La siguiente métrica recomendada para implementar es:

```text
tasa_homicidios_100k_hab
```

Motivo:

- Está alineada con el interés del proyecto en inseguridad.
- Permite comparación entre comunas de distinto tamaño.
- Obliga a integrar correctamente conteos absolutos y población.
- Es una métrica fácil de explicar en la app.

Debe calcularse como:

```text
tasa_homicidios_100k_hab = homicidios / poblacion_total * 100000
```

---

## Reglas generales para nuevas métricas

1. No inventar valores.
2. No copiar datos manualmente en archivos finales.
3. Priorizar fuentes oficiales o trazables.
4. Registrar siempre fuente, URL, fecha de descarga y limitaciones.
5. Mantener formato largo.
6. Usar `codigo_comuna` como llave principal.
7. Validar duplicados, años faltantes y comunas faltantes.
8. Mantener casos absolutos y tasas cuando corresponda.
9. Documentar si la métrica es observada, estimada, proyectada o derivada.
10. Asegurar que la app pueda leer la nueva métrica desde el selector.
