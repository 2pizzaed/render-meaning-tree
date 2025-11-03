#include <iostream>


int g(int n);

int f(int n)
{
    cout << "f ";
    if (n > 1)
        g(n - 1);
    return n + 1;
}

int g(int n)
{
    cout << "g ";
    if (n > 0)
        f(n - 1);
    return n * 2;
}

int main()
{
    int res = f(2);
    cout << res;
}
