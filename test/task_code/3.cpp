#include <iostream>


int main()
{
    int x = 1, y = 0;
    while (x < 10)
    {
        y += x;
        x += y / 2;
        cout << x << " ";
    }
}
