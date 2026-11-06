// BL-402 subscription billing engine. Weeknight batch job. All money
// amounts are whole cents; percentages use integer math per finance
// memo 3 so totals are reproducible.

public class Billing {
    public int months;       // subscription months billed
    public int monthlyRate;  // cents per month
    public int seats;        // licensed seats
    public int seatPrice;    // cents per seat per month
    public int coupon;       // 1 = SPRING10, 2 = SUMMER15, else none
    public int lateDays;     // invoice days late
    public int credit;       // account credit applied, cents

    public int baseAmount;
    public int seatAmount;
    public int grossAmount;
    public int discount;
    public int lateFee;
    public int totalDue;
    public String status;    // CLEAR / LATE / VOID

    public void compute() {
        baseAmount = months * monthlyRate;
        seatAmount = months * seats * seatPrice;
        grossAmount = baseAmount + seatAmount;
        discount = 0;
        if (coupon == 1) {
            discount = grossAmount * 10 / 100;
        } else if (coupon == 2) {
            discount = grossAmount * 15 / 100;
        }
        lateFee = 0;
        if (lateDays > 0) {
            lateFee = 500 + lateDays * 100;
        }
        totalDue = grossAmount - discount + lateFee - credit;
        status = "CLEAR";
        if (lateDays > 30) {
            status = "LATE";
        }
        if (totalDue <= 0) {
            status = "VOID";
        }
    }
}
