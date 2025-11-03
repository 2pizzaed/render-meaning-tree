#include <iostream>

int main()
{
    int a = 4, b = 2, c = 6;
    if (a > b)
        if (c < a + b)
            cout << "X";
        else
            cout << "Y";
    else
        cout << "Z";
    cout << "W";
}
