# Guía del Desafío Mantenimiento Predictivo de Aeronaves

## Para qué es este documento

Este documento te da el contexto necesario para resolver el ejercicio **sin necesidad de conocimiento previo de la industria aeronáutica**. Léelo antes de abrir el notebook (\~5 minutos de lectura).

---

## El problema de negocio (en simple)

Una aerolínea tiene aviones. Cada avión tiene piezas mecánicas (bombas, válvulas, filtros). Cuando una pieza **falla sin aviso**, el avión queda en tierra — esto se llama un evento **AOG** (Aircraft on Ground) y es extremadamente costoso: cancelaciones, reubicación de pasajeros, pérdida de slots aeroportuarios.

**El objetivo**: predecir qué piezas van a fallar **antes** de que fallen, para repararlas de forma preventiva durante ventanas de mantenimiento programado.

Esto es análogo a:

- Predecir qué máquina en una fábrica va a detenerse  
- Predecir qué disco duro en un data center va a morir  
- Predecir qué sensor IoT va a dejar de reportar

---

## Glosario: términos clave traducidos

| Término aeronáutico | Qué significa realmente |
| :---- | :---- |
| **Ciclo de vuelo** (`flight_cycle`) | Un vuelo completo (despegue → aterrizaje). Es la unidad de "uso" de una pieza. |
| **Aeronave** (`aircraft_id`) | Un avión específico de la flota |
| **Componente** (`component_id`) | Una pieza mecánica instalada en un avión |
| **Tipo de componente** (`component_type`) | Categoría funcional de la pieza |
| **Lectura de sensor** | Medición automática del estado de una pieza en cada ciclo |
| **Mantenimiento programado** (`scheduled`) | Revisión de rutina planificada con anticipación |
| **Mantenimiento no programado** (`unscheduled`) | Reparación de emergencia por falla inesperada |
| **AOG** (Aircraft on Ground) | Avión fuera de servicio por falla → pérdida masiva |
| **Horas de vuelo** (`total_flight_hours`) | Uso acumulado de la aeronave a lo largo de su vida |

&nbsp;

---

## Los datos: qué son y cómo se relacionan

Tienes 4 tablas. Piensa en ellas como un sistema de monitoreo:

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│ fleet_info  │────►│  components  │────►│ sensor_readings  │
│ 20 aviones  │     │  50 piezas   │     │ 5,000 lecturas   │
└─────────────┘     └──────┬───────┘     └──────────────────┘
                           │
                           ▼
                    ┌──────────────────┐
                    │maintenance_events│
                    │ 198 registros    │
                    └──────────────────┘
```

&nbsp;

### `fleet_info` — Los aviones (= los servidores)

20 aviones con su modelo, año de fabricación, base operacional y horas totales de vuelo. Piensa en esto como el inventario de hardware.

### `components` — Las piezas (= el hardware instalado)

50 componentes distribuidos entre los aviones. Cada uno tiene un tipo (bomba hidráulica, válvula, filtro, etc.) y una fecha de instalación.

### `sensor_readings` — Las métricas de monitoreo

Cada pieza tiene sensores que miden **temperatura**, **vibración** y **presión** en cada ciclo de vuelo. Son 100 ciclos por componente \= 5,000 filas.

Los 3 sensores son:

| Sensor | Qué mide | Unidad | Por qué importa |
| :---- | :---- | :---- | :---- |
| `temperature_celsius` | Calor generado por la pieza | °C | Temperatura anormalmente alta \= fricción excesiva o desgaste |
| `vibration_mm_s` | Vibración mecánica | mm/s | Vibración creciente \= desalineamiento, desgaste de rodamientos |
| `pressure_psi` | Presión de fluidos | PSI | Presión anormal \= fugas, obstrucciones, sellos desgastados |

&nbsp;

> **Nota**: Cada tipo de componente opera en rangos muy distintos. Una bomba hidráulica trabaja a \~3,000 PSI; un rodamiento a \~25 PSI. Esto es normal.&nbsp;

### `maintenance_events` — Los incidentes y revisiones

Registro de cada vez que se intervino una pieza, con dos tipos:

- **Scheduled** (187 eventos): Revisiones de rutina — inspección, limpieza, lubricación, ajuste  
- **Unscheduled** (11 eventos): Fallas reales — reemplazo o reparación mayor. **Estos son los eventos que queremos predecir.**

---

## Lo que vas a construir

### Variable objetivo (target)

`will_fail_within_30_cycles` \= **¿Esta pieza va a tener una falla no programada dentro de los próximos 30 ciclos de vuelo?**

- `1` \= Sí, va a fallar pronto → hay que intervenir preventivamente  
- `0` \= No, está operando normalmente

### El patrón de degradación

Cuando una pieza se acerca a la falla, sus sensores muestran una tendencia:

- Temperatura sube gradualmente  
- Vibración aumenta  
- Presión se desvía de su rango normal

Este deterioro progresivo es lo que permite predecir la falla **antes** de que ocurra.

```
Estado normal          Degradación          Falla
   ───────────      ╱─────────────╲      ──╳──
   Sensores          Sensores                │
   estables          se desvían          Evento
                                        unscheduled
   ◄──── 70 ciclos ────►◄── 30 ciclos ──►
```

&nbsp;

---

<!--## Trampas deliberadas en los datos

Este ejercicio tiene problemas de calidad de datos **intencionales** que esperamos que identifiques. No los detallamos aquí — descubrirlos es parte de la evaluación.

Pistas:
- No toda la información en los datos estaría disponible en el momento de hacer una predicción
- Los datos no siempre están limpios ni completos-->