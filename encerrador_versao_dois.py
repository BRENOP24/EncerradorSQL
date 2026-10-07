import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import mysql.connector
import configparser
import os
import sys
import ctypes
from datetime import datetime

# Identificação do processo no Windows
try:
    myappid = 'softpharma.encerrador.sql.2.0' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

INI_PATH = r"C:\Softpharma\sistema.ini"

def caminho_recurso(rel_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

def ler_config():
    if not os.path.exists(INI_PATH):
        raise Exception("sistema.ini não encontrado em C:\\Softpharma")

    config = configparser.ConfigParser()
    config.read(INI_PATH)

    if "Configuracao_Sistema" not in config:
        raise Exception("Seção [Configuracao_Sistema] não encontrada")

    secao = config["Configuracao_Sistema"]
    host = secao.get("Servidor")
    port = secao.get("Porta", 3306)
    database = secao.get("Local_Banco")

    if not host or not database:
        raise Exception("Dados de conexão incompletos")

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

# ---------------- LOGIN ---------------- #

def abrir_tela_login():
    login_window = ctk.CTkToplevel(janela)
    login_window.title("Autenticação")
    login_window.geometry("320x300")
    login_window.resizable(False, False)
    login_window.grab_set()

    # usar mesmo ícone da principal
    try:
        icon_path = caminho_recurso("encerramento.ico")
        if os.path.exists(icon_path):
            login_window.iconbitmap(icon_path)
    except:
        pass

    # container principal
    frame = ctk.CTkFrame(login_window, corner_radius=10)
    frame.pack(expand=True, fill="both", padx=20, pady=20)

    # título
    titulo = ctk.CTkLabel(
        frame,
        text="Autenticação",
        font=("Arial", 16, "bold")
    )
    titulo.pack(pady=(10, 15))

    # usuário
    entry_usuario = ctk.CTkEntry(
        frame,
        placeholder_text="Usuário"
    )
    entry_usuario.pack(pady=5, fill="x", padx=10)

    # senha
    entry_senha = ctk.CTkEntry(
        frame,
        placeholder_text="Senha",
        show="*"
    )
    entry_senha.pack(pady=5, fill="x", padx=10)

    resultado = []

    def confirmar():
        usuario = entry_usuario.get().strip().lower()
        senha = entry_senha.get().strip()

        if not usuario or not senha:
            messagebox.showwarning("Aviso", "Informe usuário e senha.")
            return

        if usuario != "softpharma":
            messagebox.showerror("Erro", "Usuário deve ser: softpharma")
            return

        resultado.append((usuario, senha))
        login_window.destroy()

    # botões
    frame_botoes = ctk.CTkFrame(frame, fg_color="transparent")
    frame_botoes.pack(pady=15)

    btn_confirmar = ctk.CTkButton(
        frame_botoes,
        text="Confirmar",
        command=confirmar,
        width=100
    )
    btn_confirmar.grid(row=0, column=0, padx=5)

    btn_cancelar = ctk.CTkButton(
        frame_botoes,
        text="Cancelar",
        command=login_window.destroy,
        fg_color="#555",
        hover_color="#333",
        width=100
    )
    btn_cancelar.grid(row=0, column=1, padx=5)

    # ENTER e ESC
    login_window.bind("<Return>", lambda e: confirmar())
    login_window.bind("<Escape>", lambda e: login_window.destroy())

    entry_usuario.focus()

    janela.wait_window(login_window)
    return resultado[0] if resultado else None

# ---------------- ENCERRAMENTO ---------------- #

def executar_encerramento(conexao, usuario_usado, host_real, db):
    cursor = conexao.cursor(dictionary=True)
    cursor.execute("SHOW FULL PROCESSLIST")
    processos = cursor.fetchall()

    total = 0
    processos_encerrados = []

    # EXCEÇÕES
    USUARIOS_EXCECAO = ['replic_user', 'seq_user']

    limite = tempo_selecionado.get()

    for processo in processos:
        process_id = processo["Id"]
        tempo = processo["Time"]
        usuario_processo = processo["User"]
        comando = str(processo["Command"]).lower() if processo["Command"] else ""

        if process_id == conexao.connection_id:
            continue

        if usuario_processo in USUARIOS_EXCECAO:
            continue

        if comando == "sleep" and tempo > limite:
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
            f"- Tempo superior a {limite} segundos\n"
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

    messagebox.showinfo("Sucesso", f"Concluído! {total} processos encerrados.")

def encerrar_processos():
    try:
        db = ler_config()

        resultado = abrir_tela_login()
        if not resultado:
            return

        u, s = resultado

        conexao, usuario_usado, host_real = conectar_banco(
            db["host"], db["port"], db["database"], u, s
        )

        executar_encerramento(conexao, usuario_usado, host_real, db)

    except Exception as e:
        messagebox.showerror("Erro", str(e))

# ---------------- INTERFACE ---------------- #

janela = ctk.CTk()
janela.title("Encerrador SQLyog - Processos")
janela.geometry("400x300")
janela.resizable(False, False)

# 🔥 CORREÇÃO AQUI
tempo_selecionado = tk.IntVar(master=janela, value=1000)

# Ícone
try:
    icon_path = caminho_recurso("encerramento.ico")
    if os.path.exists(icon_path):
        janela.iconbitmap(icon_path)
except:
    pass

# seletor de tempo
label_tempo = ctk.CTkLabel(janela, text="Tempo mínimo (segundos):")
label_tempo.pack(pady=(30, 5))

combo_tempo = ctk.CTkComboBox(
    janela,
    values=["200", "400", "600", "800", "1000"],
    command=lambda v: tempo_selecionado.set(int(v))
)
combo_tempo.set("1000")
combo_tempo.pack()

# botão
botao = ctk.CTkButton(
    janela,
    text="Encerrar Processos",
    command=encerrar_processos,
    fg_color="#d32f2f",
    hover_color="#b71c1c",
    font=("Arial", 12, "bold"),
    width=260,
    height=40
)
botao.pack(pady=30)

label_assinatura = ctk.CTkLabel(
    janela,
    text="Desenvolvido por Breno Paz",
    font=("Arial", 10, "italic"),
    text_color="gray"
)
label_assinatura.pack(side="bottom", pady=5)

janela.mainloop()