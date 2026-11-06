# FURNACE-7 Interlock Suite — Reference Documentation

## System Overview

FURNACE-7 is the zone-B safety interlock suite for the heat-treatment
furnace line, written in the ILG interlock dialect. It consists of two
programs: `main.ilg` (`GUARD-MAIN`) which runs the permissive, relief,
cooling and fan-cut interlocks of the furnace itself, and `aux.ilg`
(`ALARM-HANDLER`) which manages the standby-panel horn, escalation and
reset logic. The suite consumes field signals (pressure, temperature,
limit switches, motor speed) and commands actuator signals (relief valve,
cooling, fan cut, horn, vent permissive, annunciator).

## Program GUARD-MAIN (main.ilg)

The `GUARD-MAIN` procedure executes the interlock chain top to bottom in
one scan.

### Start permissive

The start permissive `START_PERM` is granted only in AUTO mode
(`MODE_KNOB = 2`) with the access door closed (`DOOR_CLOSED = 1`) and the
light curtain clear (`GUARD_SENSOR = 1`). In any other configuration the
permissive is withheld. Later in the scan, the cut-start interlock
revokes an already-granted `START_PERM` when `MOTOR_CUT` is on, so an
overspeed or curtain condition can never leave the drive startable.

### Overpressure relief

The relief valve signal `RELIEF` is commanded on when `PRESSURE` exceeds
180 kPa and off at or below 180 kPa.

### Flue cooling with hysteresis

The cooling signal `COOLING` turns on when `TEMPERATURE` exceeds 90
Celsius and off when it falls below 60 Celsius; inside the 60-90 band the
flue loop leaves the cooling state unchanged (hysteresis). In AUTO mode
an additional rule forces `COOLING` on once `TEMPERATURE` exceeds 85
Celsius.

### Trips and motor protection

The compressor is tripped (`TRIP COMPRESSOR`) when `PRESSURE` exceeds 200
kPa **or** `TEMPERATURE` exceeds 100 Celsius; within both limits no trip
is signalled. The fan drive cut `MOTOR_CUT` engages when the light curtain
is broken while `MOTOR_SPEED` exceeds 3000 rpm, and independently as a
hard overspeed cut above 3800 rpm.

### Door and rotor interlocks

`LOCK ROTOR UNTIL DOOR_CLOSED = 1` blocks rotor motion while the door is
open (`LOCK-FAIL:ROTOR` is emitted). `ASSERT DOOR_CLOSED = 1 ALARM 'door
open'` raises the door-open alarm whenever `DOOR_CLOSED` is 0.

### Horn, vent and annunciator

On night shift (`SHIFT_NIGHT = 1`) the horn `ALARM_HORN` annunciates
whenever the relief valve is open; on day shift the horn stays off. The
vent permissive `VENT_PERM` opens when the manual vent handle is open
(`VENT_OPEN = 1`) and `PRESSURE` exceeds 150 kPa. The annunciator
`ANNUNCIATE` lights whenever the horn or the vent permissive is active.

## Program ALARM-HANDLER (aux.ilg)

The standby-panel handler processes horn, escalation and reset requests.

### Horn handling

If the horn is active and horn silence is requested (`HORN_SILENCE = 1`)
the horn is cancelled; without a silence request the handler re-asserts
`ALARM_HORN` on.

### Escalation and furnace trip

`TRIP FURNACE` fires above the 220 kPa escalation limit. An escalation
request (`ESCALATION = 1`) calls the supervisor (`CALL_SUPERVISOR = ON`)
only on night shift.

### Reset chain

A reset request (`RESET_REQUEST = 1`) is permitted (`RESET_PERM = ON`)
only with the door closed and `PRESSURE` below 100 kPa; otherwise the
reset is inhibited and the `reset inhibited` alarm is emitted.

## Data Dictionary

| Signal | Direction | Meaning |
| --- | --- | --- |
| PRESSURE | input | furnace pressure, kPa |
| TEMPERATURE | input | flue gas temperature, Celsius |
| DOOR_CLOSED | input | access door limit switch (1 = closed) |
| GUARD_SENSOR | input | light curtain (1 = clear) |
| MOTOR_SPEED | input | exhaust fan motor, rpm |
| VENT_OPEN | input | manual vent handle (1 = open) |
| SHIFT_NIGHT | input | night-shift flag |
| MODE_KNOB | input | 0 = OFF, 1 = MANUAL, 2 = AUTO |
| START_PERM | output | drive start permissive |
| RELIEF | output | relief valve command |
| COOLING | output | flue cooling command |
| MOTOR_CUT | output | fan drive cut |
| ALARM_HORN | output/inout | horn annunciation |
| VENT_PERM | output | vent permissive |
| ANNUNCIATE | output | panel annunciator |
| CALL_SUPERVISOR | output | supervisor call (aux) |
| RESET_PERM | output | reset permissive (aux) |
