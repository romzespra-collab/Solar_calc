"""solar_calc.pyw  v1.3.0
Запуск двойным щелчком (pythonw, без консоли). Вся программа — в solar_calc.py и modules/.

Журнал:
v1.3.0: стал запускатором — программа разбита на модули.
v1.2.1 и раньше: вся программа была в этом файле.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solar_calc import main   # noqa: E402

if __name__ == "__main__":
    main()
