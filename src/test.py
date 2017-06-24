def f(a, b, c, m, n):
    f = -(a * m + c) / b
    g = f - a / b
    print(min(f, g) <= n <= max(f, g))
