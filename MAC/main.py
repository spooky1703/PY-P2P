import sys
import os

def main():
    try:
        import flet as ft
        import app_gui
        print("Iniciando interfaz gráfica...")
        ft.app(target=app_gui.main)
    except ImportError as e:
        print("[-] Error: No se encontró la librería 'flet'.")
        print("Por favor instálala ejecutando: pip install flet")
        input("Presiona Enter para salir...")

if __name__ == "__main__":
    main()
