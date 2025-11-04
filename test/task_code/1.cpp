int main()
{
    int a = 4, b = 2, c = 6;
    if (a > b)
        if (c < a + b)
        std::cout << "X";
        else
            std::cout << "Y";
    else
        std::cout << "Z";
    std::cout << "W";
}
