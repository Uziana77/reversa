# Subscription Billing Engine (BL-402 / BL-419) — Reference Documentation

## System Overview

Two legacy Java services handle the money side of the platform.
`Billing.java` (job BL-402) is the weeknight subscription batch;
`Invoice.java` (job BL-419) prices service-desk invoice lines. All
amounts are whole cents and percentages use integer math per finance
memo 3, so totals are reproducible run to run.

## Billing.java

### Base and seat amounts

`baseAmount` is `months * monthlyRate`; `seatAmount` is `months * seats *
seatPrice`. `grossAmount` is their sum, computed before any discount.

### Discounts

Coupon 1 (SPRING10) takes 10 percent of the gross amount; coupon 2
(SUMMER15) takes 15 percent; any other coupon code gives no discount.

### Late fee

An invoice paid late incurs a flat 500 late fee plus 100 per late day.
An invoice paid on time incurs no fee.

### Total and status

`totalDue` is `grossAmount - discount + lateFee - credit`. The status is
`CLEAR` by default, `LATE` when the invoice is more than 30 days late,
and `VOID` when the total due drops to zero or below (a fully credited
invoice).

## Invoice.java

### Tax

A taxable line charges `lineAmount * taxRate / 100`; a tax-exempt line
carries no tax.

### Shipping

Standard handling ships at a flat 900 cents, rush handling at 1800.

### Line total

`lineTotal` is `lineAmount + taxAmount + shipping`.

## Data Dictionary

| Field | Meaning |
| --- | --- |
| months | subscription months billed |
| monthlyRate | cents per month |
| seats | licensed seats |
| seatPrice | cents per seat per month |
| coupon | 1 = SPRING10, 2 = SUMMER15, else none |
| lateDays | invoice days late |
| credit | account credit applied, cents |
| baseAmount | months x monthlyRate |
| seatAmount | months x seats x seatPrice |
| grossAmount | base + seat before discounts |
| discount | coupon discount |
| lateFee | flat 500 + 100 per late day |
| totalDue | gross - discount + lateFee - credit |
| status | CLEAR / LATE / VOID |
| lineAmount | invoice line amount, cents |
| taxRate | tax percentage, whole number |
| exempt | 1 = tax exempt |
| rush | 1 = rush handling |
| taxAmount | line tax |
| shipping | handling and shipping fee |
| lineTotal | line amount + tax + shipping |
