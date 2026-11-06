# RPT Batch Reports — Reference Documentation

## System Overview

The RPT batch suite produces the quarterly sales report and the returns
reconciliation for the commercial department. It is written in the RPT
report-scripting dialect and processes record collections supplied by the
upstream extract job. Two scripts exist: `sales.rpt` (job RPT-114,
consolidated sales report) and `returns.rpt` (job RPT-208, returns
reconciliation).

## Script SALES-RPT (sales.rpt)

The script defines seven accumulators, scans the `RECORDS` collection
record by record, and prints a summary at the end.

### Accumulators

`TOTAL-AMT` accumulates the gross amount of every record via
`ACCUMULATE REC_AMOUNT`. `NET-TOTAL` accumulates the discounted amount,
`COMM-TOTAL` the commission. `HIGH-COUNT` counts the high-value records,
`REGION-NORTH` and `REGION-SOUTH` bucket the amounts by region, and
`TOP-AMT` tracks the running maximum record amount.

### Region bucketing

Records whose `REC_REGION` is `NORTH` accumulate into `REGION-NORTH`;
every other region falls into the `REGION-SOUTH` bucket through the else
branch.

### High-value detail

A record whose `REC_AMOUNT` exceeds 100 increments `HIGH-COUNT` and
prints a `HIGH` detail line with the rep name and the amount. Records at
or below 100 print no detail line.

### Quantity discount

Records with `REC_QTY` above 10 are netted at 90 percent of the amount
(`DISCOUNT = REC_AMOUNT * 0.9`); records with quantity 10 or less are
netted at full amount. The discounted value accumulates into `NET-TOTAL`.

### Commission

Rep `ANA` earns 5 percent of the discounted amount; every other rep earns
3 percent. Commission accumulates into `COMM-TOTAL`.

### Summary lines

The report ends with `TOTAL`, `NET`, `COMM`, `HIGH` and `TOP` summary
lines carrying the final accumulator values.

## Script RETURNS-RPT (returns.rpt)

### Reconciliation

`RETURN-TOTAL` accumulates all return amounts and `RETURN-COUNT` counts
the return records. Each refund is computed against `GROSS`: a return
whose amount exceeds `GROSS` is clamped to `GROSS`, increments
`FLAG-COUNT` and prints a `CLAMPED` line; a return at or below `GROSS` is
refunded in full. Refunds accumulate into `REFUND-TOTAL`. Empty
collections produce zero totals.

## Data Dictionary

| Field | Meaning |
| --- | --- |
| RECORDS | input collection of sales records (amount, qty, rep, region) |
| RETURNS | input collection of return records (amount) |
| GROSS | input gross amount used to clamp refunds |
| TOTAL-AMT | gross sales total |
| NET-TOTAL | discounted sales total |
| COMM-TOTAL | commission total |
| HIGH-COUNT | count of records above the 100 threshold |
| REGION-NORTH | amount bucket for NORTH region |
| REGION-SOUTH | amount bucket for all other regions |
| TOP-AMT | maximum record amount |
| DISCOUNT | per-record discounted amount |
| COMM | per-record commission |
| RETURN-TOTAL | total of return amounts |
| RETURN-COUNT | number of return records |
| REFUND-TOTAL | total of refunded (clamped) amounts |
| FLAG-COUNT | number of clamped refunds |
