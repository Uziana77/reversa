# Weekly Payroll Engine (PAYROLL / PAYRPT) — Reference Documentation

## System Overview

The payroll suite runs every Friday evening under scheduler jobs PAY-01
and PAY-02. `PAYROLL.cbl` (program `PAYROLL`) computes one employee's
weekly payslip values from hours, rate and service data. `PAYRPT.cbl`
(program `PAYRPT`) formats the payslip lines and accumulates the batch
report total. Both programs exchange values through a working-storage
interface rather than files.

## Program PAYROLL

The `PROCEDURE DIVISION` runs the calculation paragraphs in order.

### CALC-BASE

`BASE-PAY` equals `HOURS-WORKED * PAY-RATE` while hours stay at or below
40. Above 40 hours the base is capped at `40 * PAY-RATE` and the excess
hours are paid as double-time overtime: `OT-PAY = (HOURS-WORKED - 40) *
PAY-RATE * 2`.

### CALC-SHIFT

Night shift (`SHIFT-CODE = 2`) earns a shift premium of 10 percent of
`BASE-PAY`; day shift earns none (`SHIFT-PREMIUM = 0`).

### CALC-SENIORITY and CALC-GRADE

Ten or more years of service (`YEARS-OF-SERVICE >= 10`) earn a seniority
bonus of 5 percent of `BASE-PAY`. On top of that, the `GRADE` selector
adds a flat bonus through an `EVALUATE`: grade 1 adds nothing, grade 2
adds 100, grade 3 adds 250, and any other grade falls back to 50.

### CALC-GROSS

`GROSS-PAY` is the sum of `BASE-PAY`, `OT-PAY`, `SHIFT-PREMIUM` and
`BONUS-AMT`.

### CALC-TAX

Tax is computed by bracket over `GROSS-PAY` with an `EVALUATE` range:
gross up to 1000 is taxed at 5 percent, 1001 to 3000 at 10 percent, and
anything above 3000 at 15 percent.

### CALC-PENALTY and CALC-NET

Each absent day penalises the payslip by 20 (`PENALTY = ABSENT-DAYS *
20`). `NET-PAY` is `GROSS-PAY - TAX-AMT - PENALTY`.

### SET-STATUS

`PAY-STATUS` becomes `P` when `NET-PAY` is positive and `Z` otherwise.

## Program PAYRPT

### BUILD-SLIP

A positive `GROSS-PAY` prints a `SLIP GROSS=` line, increments
`SLIP-COUNT` and adds the gross to `REPORT-TOTAL`; a zero gross prints
`SLIP EMPTY` and counts no slip.

### TAX-LINE and NET-LINE

The `TAX=` line prints only when `TAX-AMT` is positive, and the `NET=`
line only when `NET-PAY` is positive.

## Data Dictionary

| Field | Meaning |
| --- | --- |
| HOURS-WORKED | weekly hours for the employee |
| PAY-RATE | hourly pay rate |
| SHIFT-CODE | 2 = night shift, otherwise day |
| GRADE | grade selector (1/2/3, other = fallback) |
| YEARS-OF-SERVICE | completed years of service |
| ABSENT-DAYS | unpaid absent days |
| BASE-PAY | capped or straight-time base pay |
| OT-PAY | double-time overtime pay |
| SHIFT-PREMIUM | night-shift premium |
| BONUS-AMT | seniority + grade bonus |
| GROSS-PAY | total gross pay |
| TAX-AMT | bracketed income tax |
| PENALTY | absence penalty |
| NET-PAY | take-home pay |
| PAY-STATUS | P (positive) or Z (zero) |
| SLIP-COUNT | payslips built in this run |
| REPORT-TOTAL | batch gross total |
