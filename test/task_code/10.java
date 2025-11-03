public class Main {
    public static void main(String[] args) {
        int s = 0;
        for (int i = 1; i <= 4; i++) {
            if (i % 3 == 0) {
                s += i * 2;
            } else {
                s += i;
                if (s > 5)
                    break;
            }
            System.out.print(s + " ");
        }
    }
}
