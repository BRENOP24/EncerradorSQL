import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import mysql.connector
import configparser
import os
import sys
import ctypes
from datetime import datetime

# Identificação do processo no Windows para o ícone aparecer na Barra de Tarefas
try:
    myappid = 'softpharma.encerrador.sql.1.0' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

INI_PATH = r"C:\Softpharma\sistema.ini"
TEMPO_LIMITE = 1000 

def caminho_recurso(rel_path):
    """ Retorna o caminho absoluto para o recurso, funciona em dev e PyInstaller """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

def ler_config():
    if not os.path.exists(INI_PATH):
        raise Exception("sistema.ini não encontrado em C:\\Softpharma")

    config = configparser.ConfigParser()
    config.read(INI_PATH)

    if "Configuracao_Sistema" not in config:
        raise Exception("Seção [Configuracao_Sistema] não encontrada no sistema.ini")

    secao = config["Configuracao_Sistema"]
    host = secao.get("Servidor")
    port = secao.get("Porta", 3306)
    database = secao.get("Local_Banco")

    if not host or not database:
        raise Exception("Dados de conexão incompletos no sistema.ini")

    return {
        "host": host.strip(),
        "port": int(port),
        "database": database.strip()
    }

def conectar_banco(host, port, database, user, password):
    hosts_para_testar = [host]
    if host == "127.0.0.1": hosts_para_testar.append("localhost")
    elif host == "localhost": hosts_para_testar.append("127.0.0.1")

    ultimo_erro = ""
    for host_teste in hosts_para_testar:
        try:
            conexao = mysql.connector.connect(
                host=host_teste,
                port=port,
                user=user,
                password=password,
                database=database,
                charset='utf8',
                use_unicode=True
            )
            return conexao, user, host_teste
        except Exception as e:
            ultimo_erro = str(e)
    raise Exception(ultimo_erro)

def abrir_tela_login():
    login_window = tk.Toplevel(janela)
    login_window.title("Autenticação Necessária")
    login_window.geometry("300x250")
    login_window.resizable(False, False)
    login_window.grab_set()

    tk.Label(login_window, text="Usuário:").pack(pady=(15, 5))
    entry_usuario = tk.Entry(login_window)
    entry_usuario.pack()

    tk.Label(login_window, text="Senha:").pack(pady=(10, 5))
    entry_senha = tk.Entry(login_window, show="*")
    entry_senha.pack()

    resultado = []

    def confirmar():
        usuario = entry_usuario.get().strip()
        senha = entry_senha.get().strip()
        if not usuario or not senha:
            messagebox.showwarning("Aviso", "Informe usuário e senha.")
            return
        resultado.append((usuario, senha))
        login_window.destroy()

    tk.Button(login_window, text="Confirmar", command=confirmar).pack(pady=10)
    tk.Button(login_window, text="Cancelar", command=login_window.destroy).pack()

    janela.wait_window(login_window)
    return resultado[0] if resultado else None

def executar_encerramento(conexao, usuario_usado, host_real, db):
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("SHOW FULL PROCESSLIST")
    processos = cursor.fetchall()

    total = 0
    processos_encerrados = []
    
    # --- LISTA DE EXCEÇÕES ---
    USUARIOS_EXCECAO = ['replic_user', 'seq_user']

    for processo in processos:
        process_id = processo["Id"]
        tempo = processo["Time"]
        usuario_processo = processo["User"]
        comando = str(processo["Command"]).lower() if processo["Command"] else ""

        if process_id == conexao.connection_id:
            continue
            
        if usuario_processo in USUARIOS_EXCECAO:
            continue

        if comando == "sleep" and tempo > TEMPO_LIMITE:
            try:
                cursor.execute(f"KILL {process_id}")
                total += 1
                processos_encerrados.append(processo)
            except Exception:
                pass

    cursor.close()
    conexao.close()

    caminho = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Arquivo de texto", "*.txt")],
        title="Salvar Log de Encerramento"
    )

    if caminho:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conteudo = (
            f"Data/Hora: {agora}\n"
            f"Servidor: {host_real}:{db['port']}\n"
            f"Banco: {db['database']}\n"
            f"Usuário executor: {usuario_usado}\n\n"
            f"Filtro aplicado:\n"
            f"- Apenas status 'Sleep'\n"
            f"- Tempo superior a {TEMPO_LIMITE} segundos\n"
            f"- Exceções preservadas: {', '.join(USUARIOS_EXCECAO)}\n\n"
            f"Total de processos analisados: {len(processos)}\n"
            f"Total de processos encerrados: {total}\n"
        )

        if total > 0:
            conteudo += "\nDetalhes dos processos encerrados:\n"
            for p in processos_encerrados:
                conteudo += f"ID: {p['Id']} | User: {p['User']} | Host: {p['Host']} | Time: {p['Time']}s\n"

        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)

    messagebox.showinfo("Sucesso", f"Concluído! {total} processos encerrados.\nExceções {', '.join(USUARIOS_EXCECAO)} mantidas.")

def encerrar_processos():
    try:
        db = ler_config()
        try:
            conexao, usuario_usado, host_real = conectar_banco(
                db["host"], db["port"], db["database"], "seq_user", "seq_password"
            )
        except:
            resultado = abrir_tela_login()
            if not resultado: return
            u, s = resultado
            conexao, usuario_usado, host_real = conectar_banco(
                db["host"], db["port"], db["database"], u, s
            )
        executar_encerramento(conexao, usuario_usado, host_real, db)
    except Exception as e:
        messagebox.showerror("Erro", str(e))

# --- INTERFACE GRÁFICA ---
janela = ctk.CTk() # Usando o CTK para evitar conflitos de estilo
janela.title("Encerrador SQLyog - Processos")
janela.geometry("400x260")
janela.resizable(False, False)

# Carregamento do Ícone
try:
    icon_path = caminho_recurso("encerramento.ico")
    if os.path.exists(icon_path):
        janela.iconbitmap(icon_path)
except:
    pass

botao = tk.Button(
    janela, text="Encerrar Processos", 
    command=encerrar_processos, 
    bg="#d32f2f", fg="white", font=("Arial", 11, "bold"),
    height=2, width=32
)
botao.pack(pady=70)

label_assinatura = ctk.CTkLabel(
    janela, text="Desenvolvido por Breno Paz",
    font=("Arial", 10, "italic"), text_color="gray"
)
label_assinatura.pack(side="bottom", pady=5)

janela.mainloop()