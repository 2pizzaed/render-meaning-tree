public class Main {
    static int f(int x) {
        System.out.print("f" + x + " ");
        return x % 2 == 0 ? x / 2 : x + 2;
    }

    static int g(int x) {
        System.out.print("g" + x + " ");
        return f(x - 1) + 1;
    }

    public static void main(String[] args) {
        int res = g(3);
        System.out.print(res);
    }
}
