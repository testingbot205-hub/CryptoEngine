"""
main.py — Точка входу SecureMsg
"""
import sys
import os

# Додаємо директорію програми до шляху для імпорту модулів
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_window import main

if __name__ == "__main__":
    main()

