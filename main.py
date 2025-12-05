import sys
import os
from p2p_core import FileSender, FileReceiver, get_local_ip

def main():
    print("=== P2P File Transfer ===")
    print(f"Tu IP local es: {get_local_ip()}")
    print("1. Enviar archivo")
    print("2. Recibir archivo")
    
    choice = input("Selecciona una opción (1/2): ").strip()
    
    if choice == "1":
        sender = FileSender()
        target_ip = input("Ingresa la IP del destinatario: ").strip()
        filepath = input("Ingresa la ruta del archivo a enviar: ").strip()
        
        # Remove quotes if user dragged and dropped file
        filepath = filepath.replace('"', '').replace("'", "")
        
        if os.path.exists(filepath):
            sender.send_file(target_ip, 5001, filepath)
        else:
            print("[-] El archivo no existe.")
            
    elif choice == "2":
        receiver = FileReceiver()
        receiver.start()
        
    else:
        print("Opción no válida.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSalida interrumpida por el usuario.")
        sys.exit(0)
