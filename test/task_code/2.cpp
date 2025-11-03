#include <iostream>

int main()
{
    for (int i = 1; i <= 3; i++)
    {
        for (int j = i; j <= 3; j++)
        {
            if (i + j == 4)
                cout << "(" << i << "," << j << ") ";
        }
    }
}
