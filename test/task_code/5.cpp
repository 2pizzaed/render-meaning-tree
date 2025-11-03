#include <iostream>

int step(int n)
{
    cout << "[" << n << "]";
    return n % 2 == 0 ? n / 2 : n + 1;
}

int main()
{
    int x = 5;
    while (x > 0 && x < 10)
    {
        x = step(x);
        if (x == 3)
            x += 4;
        else if (x == 4)
            break;
    }
    cout << " end";
}
