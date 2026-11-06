// BL-419 invoice line calculator for the service desk. Money amounts
// are whole cents. Rush handling doubles the shipping charge.

public class Invoice {
    public int lineAmount;  // cents on this line
    public int taxRate;     // percent, whole number
    public int exempt;      // 1 = tax exempt
    public int rush;        // 1 = rush handling

    public int taxAmount;
    public int shipping;
    public int lineTotal;

    public void compute() {
        taxAmount = 0;
        if (exempt == 0) {
            taxAmount = lineAmount * taxRate / 100;
        }
        shipping = 900;
        if (rush == 1) {
            shipping = 1800;
        }
        lineTotal = lineAmount + taxAmount + shipping;
    }
}
