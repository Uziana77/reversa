       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYRPT.
      * Payslip line builder, chained after PAYROLL (job PAY-02).
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  GROSS-PAY       PIC 9(6)V9(2) VALUE 0.
       01  TAX-AMT         PIC 9(6)V9(2) VALUE 0.
       01  NET-PAY         PIC 9(6)V9(2) VALUE 0.
       01  SLIP-COUNT      PIC 9(3)     VALUE 0.
       01  REPORT-TOTAL    PIC 9(7)V9(2) VALUE 0.
       PROCEDURE DIVISION.
       BUILD-SLIP.
           IF GROSS-PAY > 0
               DISPLAY 'SLIP GROSS=' GROSS-PAY
               ADD 1 TO SLIP-COUNT
               ADD GROSS-PAY TO REPORT-TOTAL
           ELSE
               DISPLAY 'SLIP EMPTY'
           END-IF.
       TAX-LINE.
           IF TAX-AMT > 0
               DISPLAY 'TAX=' TAX-AMT
           END-IF.
       NET-LINE.
           IF NET-PAY > 0
               DISPLAY 'NET=' NET-PAY
           END-IF.
