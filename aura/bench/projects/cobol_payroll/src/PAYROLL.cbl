       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
      * PAYCYCLE-WEEKLY payroll engine for the lamination plant.
      * Run under scheduler job PAY-01 every Friday 22:00.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  HOURS-WORKED    PIC 9(3)     VALUE 0.
       01  PAY-RATE        PIC 9(4)     VALUE 0.
       01  SHIFT-CODE      PIC 9(1)     VALUE 0.
       01  GRADE           PIC 9(1)     VALUE 0.
       01  YEARS-OF-SERVICE PIC 9(2)    VALUE 0.
       01  ABSENT-DAYS     PIC 9(2)     VALUE 0.
       01  BASE-PAY        PIC 9(6)V9(2) VALUE 0.
       01  OT-PAY          PIC 9(6)V9(2) VALUE 0.
       01  SHIFT-PREMIUM   PIC 9(6)V9(2) VALUE 0.
       01  BONUS-AMT       PIC 9(6)V9(2) VALUE 0.
       01  GROSS-PAY       PIC 9(6)V9(2) VALUE 0.
       01  TAX-AMT         PIC 9(6)V9(2) VALUE 0.
       01  PENALTY         PIC 9(6)V9(2) VALUE 0.
       01  NET-PAY         PIC 9(6)V9(2) VALUE 0.
       01  PAY-STATUS      PIC X(1)     VALUE 'Z'.
       PROCEDURE DIVISION.
       CALC-BASE.
           IF HOURS-WORKED > 40
               COMPUTE BASE-PAY = 40 * PAY-RATE
               COMPUTE OT-PAY = (HOURS-WORKED - 40) * PAY-RATE * 2
           ELSE
               COMPUTE BASE-PAY = HOURS-WORKED * PAY-RATE
               COMPUTE OT-PAY = 0
           END-IF.
       CALC-SHIFT.
           IF SHIFT-CODE = 2
               COMPUTE SHIFT-PREMIUM = BASE-PAY * 0.10
           ELSE
               COMPUTE SHIFT-PREMIUM = 0
           END-IF.
       CALC-SENIORITY.
           IF YEARS-OF-SERVICE >= 10
               COMPUTE BONUS-AMT = BASE-PAY * 0.05
           ELSE
               COMPUTE BONUS-AMT = 0
           END-IF.
       CALC-GRADE.
           EVALUATE GRADE
               WHEN 1
                   ADD 0 TO BONUS-AMT
               WHEN 2
                   ADD 100 TO BONUS-AMT
               WHEN 3
                   ADD 250 TO BONUS-AMT
               WHEN OTHER
                   ADD 50 TO BONUS-AMT
           END-EVALUATE.
       CALC-GROSS.
           COMPUTE GROSS-PAY = BASE-PAY + OT-PAY + SHIFT-PREMIUM + BONUS-AMT.
       CALC-TAX.
           EVALUATE GROSS-PAY
               WHEN 0 THRU 1000
                   COMPUTE TAX-AMT = GROSS-PAY * 0.05
               WHEN 1001 THRU 3000
                   COMPUTE TAX-AMT = GROSS-PAY * 0.10
               WHEN OTHER
                   COMPUTE TAX-AMT = GROSS-PAY * 0.15
           END-EVALUATE.
       CALC-PENALTY.
           IF ABSENT-DAYS > 0
               COMPUTE PENALTY = ABSENT-DAYS * 20
           ELSE
               COMPUTE PENALTY = 0
           END-IF.
       CALC-NET.
           COMPUTE NET-PAY = GROSS-PAY - TAX-AMT - PENALTY.
       SET-STATUS.
           IF NET-PAY > 0
               MOVE 'P' TO PAY-STATUS
           ELSE
               MOVE 'Z' TO PAY-STATUS
           END-IF.
