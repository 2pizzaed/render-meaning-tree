public class Main {
    public static void main(String[] args) {
        int i = 1, sum = 0;
        while (i < 6) {
            sum += i;
            if (sum % 2 == 0)
                i += 2;
            else
                i++;
            System.out.print(sum + " ");
        }
    }
}
