import os
import zipfile
import subprocess
import tkinter as tk
from tkinter import messagebox, Listbox, Scrollbar, RIGHT, LEFT, BOTH, END, Y, X
import webbrowser
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import json

CONFIG_FILE = 'config.json'
TEMP_DIR = os.path.join(os.getenv('TEMP'), 'FileFinder')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

log_path = os.path.join(TEMP_DIR, 'app.log')
logging.basicConfig(filename=log_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def is_hidden(path):
    """Проверка на скрытые файлы и папки."""
    if os.name == 'nt':
        # На Windows файлы/папки скрыты, если у них установлен скрытый атрибут
        try:
            return bool(os.stat(path).st_file_attributes & 0x2)
        except AttributeError:
            return False
    else:
        # На Unix-подобных системах скрыты те, которые начинаются с '.'
        return os.path.basename(path).startswith('.')

def open_executable_directory():
    """Открыть папку, где находится исполняемый файл."""
    try:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        if os.name == 'nt':  # Windows
            os.startfile(exe_dir)
        elif os.name == 'posix':  # macOS, Linux
            subprocess.call(['xdg-open', exe_dir])  # Используем xdg-open для Linux
    except Exception as e:
        logger.error(f"Ошибка открытия папки {exe_dir}: {e}")
        messagebox.showerror("Ошибка", f"Ошибка открытия папки {exe_dir}: {e}")


def check_jar_for_suspicious_strings(file_path, suspicious_keywords):
    """Проверка содержимого .jar файла на подозрительные строки."""
    try:
        with zipfile.ZipFile(file_path, 'r') as jar_file:
            for file in jar_file.namelist():
                with jar_file.open(file) as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    if any(keyword in content.lower() for keyword in suspicious_keywords):
                        return True
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки содержимого .jar файла {file_path}: {e}")
        return False


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Настройка логирования
log_path = os.path.join(BASE_DIR, 'app.log')
logging.basicConfig(filename=log_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()




# Цвета для интерфейса
THEMES = {
    'light': {
        'background': '#F0F0F0',  # Светлый фон
        'button': '#DDDDDD',      # Светлый цвет кнопок
        'text': '#000000'         # Черный цвет текста
    },
    'dark': {
        'background': '#1E1E1E',  # Темный фон
        'button': '#333333',      # Темные кнопки
        'text': '#FFFFFF'         # Белый текст
    }
}

current_theme = 'light'  # По умолчанию светлая тема

configS = {
    'theme': 'light'
}

def apply_theme(widget, theme):
    """Применить тему к виджету."""
    colors = THEMES[theme]
    widget.config(bg=colors['background'])
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            child.config(bg=colors['background'], fg=colors['text'])
        elif isinstance(child, tk.Button):
            child.config(bg=colors['button'], fg=colors['text'])
        elif isinstance(child, tk.Listbox):
            child.config(bg=colors['button'], fg=colors['text'])
        elif isinstance(child, tk.Frame):
            apply_theme(child, theme)

def save_run_history(total_files, total_folders, total_cheats):
    """Сохранить количество запусков проверки, дату/время и информацию о читах."""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history_path = os.path.join(TEMP_DIR, "check_history.txt")
        
        if os.path.exists(history_path):
            with open(history_path, "r") as file:
                lines = file.readlines()
            count = int(lines[0].strip().split(': ')[1])
            count += 1
            with open(history_path, "w") as file:
                file.write(f"Запусков: {count}\n")
                file.write(f"Последний запуск: {now}\n")
                file.write(f"Обнаружено файлов: {total_files}\n")
                file.write(f"Обнаружено папок: {total_folders}\n")
                file.write(f"Обнаружено читов: {total_cheats}\n")
        else:
            with open(history_path, "w") as file:
                file.write("Запусков: 1\n")
                file.write(f"Первый запуск: {now}\n")
                file.write(f"Обнаружено файлов: {total_files}\n")
                file.write(f"Обнаружено папок: {total_folders}\n")
                file.write(f"Обнаружено читов: {total_cheats}\n")
        logger.info(f"История проверки сохранена: {total_files} файлов, {total_folders} папок, {total_cheats} читов")
    except Exception as e:
        logger.error(f"Ошибка сохранения истории: {e}")



def load_run_history():
    """Загрузить историю запусков и отобразить ее в приложении."""
    history_text = ""
    try:
        history_path = os.path.join(TEMP_DIR, "check_history.txt")
        if os.path.exists(history_path):
            with open(history_path, "r") as file:
                history_text = file.read()
        else:
            history_text = "История запусков не найдена."
    except Exception as e:
        logger.error(f"Ошибка загрузки истории: {e}")
        history_text = "Ошибка загрузки истории."
    return history_text


def find_files_by_keywords(root_dir, keywords):
    """Поиск файлов по ключевым словам, включая скрытые файлы."""
    found_files = []
    keywords = [keyword.lower() for keyword in keywords]
    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                is_hidden_file = is_hidden(full_path)
                
                filename_lower = filename.lower()
                if any(keyword in filename_lower for keyword in keywords):
                    # Указываем, если файл скрыт
                    if is_hidden_file:
                        found_files.append(f"{full_path} (скрытый)")
                    else:
                        found_files.append(full_path)
    except Exception as e:
        logger.error(f"Ошибка поиска файлов: {e}")
        print(f"Ошибка поиска файлов: {e}")
    return found_files


def find_folders_by_keywords(root_dir, folder_keywords, blacklisted_folders):
    """Поиск папок по ключевым словам, включая скрытые папки."""
    found_folders = set()
    folder_keywords = [keyword.lower() for keyword in folder_keywords]
    blacklisted_folders = [folder.lower() for folder in blacklisted_folders]
    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for dirname in dirnames:
                full_path = os.path.join(dirpath, dirname)
                is_hidden_folder = is_hidden(full_path)
                
                dirname_lower = dirname.lower()
                if dirname_lower in blacklisted_folders:
                    continue
                if any(keyword in dirname_lower for keyword in folder_keywords):
                    # Указываем, если папка скрыта
                    if is_hidden_folder:
                        found_folders.add(f"{full_path} (скрытая)")
                    else:
                        found_folders.add(full_path)
    except Exception as e:
        logger.error(f"Ошибка поиска папок: {e}")
        print(f"Ошибка поиска папок: {e}")
    return list(found_folders)

def analyze_jar_file(file_path):
    """Анализ содержимого .jar файла."""
    try:
        with zipfile.ZipFile(file_path, 'r') as jar_file:
            for file in jar_file.namelist():
                if any(keyword in file.lower() for keyword in ["xray", "baritone", "meteorclient", "aristois", "killaura", "rage", "antiafk", "autototem", "autoeat", "wallhack"]):
                    return True
        return False
    except Exception as e:
        print(f"Ошибка анализа файла {file_path}: {e}")
        return False

def analyze_file(file_path):
    """Анализ содержимого файла."""
    try:
        if file_path.endswith(".jar"):
            return analyze_jar_file(file_path)
        with open(file_path, 'r', errors='ignore') as file:
            content = file.read()
            cheat_signatures = [
                "class xray", "baritone", "meteorclient", "aristois",
                "modded client", "freecam", "aimbot", "esp", "wallhack"
            ]
            for signature in cheat_signatures:
                if signature in content.lower():
                    return True
        return False
    except Exception as e:
        logger.error(f"Ошибка анализа файла {file_path}: {e}")
        print(f"Ошибка анализа файла {file_path}: {e}")
        return False


def open_folder_of_file(file_path):
    """Открыть папку с файлом."""
    try:
        folder_path = os.path.dirname(file_path)
        if os.name == 'nt':  # Windows
            os.startfile(folder_path)
        elif os.name == 'posix':  # macOS, Linux
            subprocess.call(['xdg-open', folder_path])  # Используем xdg-open для Linux
    except Exception as e:
        logger.error(f"Ошибка открытия папки {folder_path}: {e}")
        print(f"Ошибка открытия папки {folder_path}: {e}")

def open_folder_of_path(path):
    """Открыть папку по пути."""
    try:
        if os.name == 'nt':  # Windows
            os.startfile(path)
        elif os.name == 'posix':  # macOS, Linux
            subprocess.call(['xdg-open', path])  # Используем xdg-open для Linux
    except Exception as e:
        logger.error(f"Ошибка открытия {path}: {e}")
        print(f"Ошибка открытия {path}: {e}")


def find_minecraft_directory():
    """Найти директорию .minecraft."""
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, 'AppData', 'Roaming', '.minecraft')

async def on_check():
    """Запуск проверки на читы."""
    try:
        listbox.delete(0, END)  # Очищаем список перед новой проверкой
        root_dir = find_minecraft_directory()

        if not os.path.isdir(root_dir):
            messagebox.showerror("Ошибка", f".minecraft не найдена по пути: {root_dir}")
            logger.error(f".minecraft не найдена по пути: {root_dir}")
            return
        
        keywords = [
            'xray', 'impact', 'meteorclient', 'fullbright', 'freecam', 
            'aristois', 'auto aim', 'chestesp', 'trajectory preview', 
            'x-ray', 'baritone', 'fabritone', 'entity outliner',
            'wwe', 'matix', 'enemyz', 'noplayerdamage', 
            'detection', 'player highlighter'
        ]

        folder_keywords = ['impact', 'cheat', 'hacks', 'aristois', 'meteorclient', 'hack']
        blacklisted_folders = ['grossjava9hacks']

        found_files = await find_files_by_keywords_async(root_dir, keywords)
        found_folders = await find_folders_by_keywords_async(root_dir, folder_keywords, blacklisted_folders)

        total_cheats = 0

        if not found_files and not found_folders:
            listbox.insert(END, "Читов не обнаружено.")
            save_run_history(0, 0, 0)
            return

        # Обработка файлов
        if found_files:
            for file_path in found_files:
                if await analyze_file_async(file_path):
                    listbox.insert(END, f"Файл: {file_path} (чит)")
                    total_cheats += 1
                else:
                    listbox.insert(END, f"Файл: {file_path}")

        # Обработка папок с проверкой их существования
        if found_folders:
            for folder_path in found_folders:
                logger.info(f"Найдена папка: {folder_path}")  # Логируем путь найденной папки
                if os.path.exists(folder_path):  # Проверяем, существует ли папка
                    listbox.insert(END, f"Папка: {folder_path} (чит)")
                    total_cheats += 1
                else:
                    logger.info(f"Папка была удалена: {folder_path}")  # Логируем, что папка была удалена

        save_run_history(len(found_files), len(found_folders), total_cheats)

        # Отключаем кнопку "Открыть" до тех пор, пока не будет выбран элемент
        open_button.config(state=tk.DISABLED)

    except Exception as e:
        logger.error(f"Ошибка проверки: {e}")
        messagebox.showerror("Ошибка", f"Ошибка: {e}")




def open_selected_item():
    """Открыть выбранный файл или папку."""
    try:
        selected = listbox.curselection()
        if selected:
            item = listbox.get(selected[0]).strip()
            if item.startswith("Файл:"):
                file_path = item[len("Файл: "):].split(" (чит)")[0].strip()
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Файл не найден: {file_path}")
                open_folder_of_file(file_path)
            elif item.startswith("Папка:"):
                folder_path = item[len("Папка: "):].split(" (чит)")[0].strip()
                if not os.path.exists(folder_path):
                    raise FileNotFoundError(f"Папка не найдена: {folder_path}")
                open_folder_of_path(folder_path)
    except FileNotFoundError as e:
        logger.error(f"Ошибка: {e}")
        messagebox.showerror("Ошибка", str(e))
    except Exception as e:
        logger.exception("Ошибка открытия")
        messagebox.showerror("Ошибка", f"Ошибка открытия: {e}")


def on_select(event):
    """Обработчик выбора элемента из списка."""
    if listbox.curselection():
        open_button.config(state=tk.NORMAL)
    else:
        open_button.config(state=tk.DISABLED)

def show_help():
    """Показать окно помощи."""
    global help_window  # Declare help_window as global
    help_window = tk.Toplevel(root)
    help_window.title("Инструкция")
    help_window.geometry("600x300")  # Размер окна
    apply_theme(help_window, current_theme)
    help_window.minsize(width=600, height=300)

    help_text = """
    В этом приложении можно проверить папку .minecraft на наличие читов и модов.
    Для этого выполните следующие шаги:
    
    1. Нажмите кнопку "Искать", чтобы начать проверку файлов и папок.
    2. Результаты проверки отобразятся в списке справа.
    3. Вы можете открыть любой найденный файл или папку, выбрав его и нажав кнопку "Открыть".
    4. Настройки приложения можно изменить через кнопку "Настройки".

    Если программа нашла папку которая не открывается и если это реально читы(программа может ошибаться мы проверяли) или вовсе не написала что у вас нету читов, то надо открыть архивочные приложение(WinRAR или 7-zip) Там ищите папку которая должна быть удалена и удаляйте её! Если вас такими темпами поймали на проверке, покажите инструкцию модератору чтобы он мог понять что у вас были читы, но они были удалены
    """
    label = tk.Label(help_window, text=help_text, wraplength=580, justify=tk.LEFT)
    label.pack(padx=10, pady=10, fill=BOTH, expand=True)

def show_settings():
    """Показать окно настроек."""
    settings_window = tk.Toplevel(root)
    settings_window.title("Настройки")
    settings_window.geometry("400x300")  # Размер окна
    apply_theme(settings_window, current_theme)

    def toggle_theme():
        """Toggle the theme."""
        global current_theme
        if dark_theme_var.get():
            current_theme = 'dark'
        else:
            current_theme = 'light'
        apply_theme(root, current_theme)
        apply_theme(settings_window, current_theme)
        if 'help_window' in globals() and help_window is not None:
            apply_theme(help_window, current_theme)

    def open_executable_location():
        """Открыть местоположение исполняемого файла."""
        try:
            folder_path = BASE_DIR
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            elif os.name == 'posix':  # macOS, Linux
                subprocess.call(['xdg-open', folder_path])  # Используем xdg-open для Linux
        except Exception as e:
            logger.error(f"Ошибка открытия папки {folder_path}: {e}")
            messagebox.showerror("Ошибка", f"Ошибка открытия папки: {e}")

    # Темная тема
    tk.Label(settings_window, text="Выберите тему:", fg=THEMES[current_theme]['text'], bg=THEMES[current_theme]['background'], font=('Arial', 12)).pack(pady=10)

    dark_theme_var = tk.BooleanVar()
    dark_theme_var.set(current_theme == 'dark')

    dark_theme_checkbutton = tk.Checkbutton(settings_window, text="Темная тема", variable=dark_theme_var, command=toggle_theme, bg=THEMES[current_theme]['background'], fg=THEMES[current_theme]['text'], font=('Arial', 12), selectcolor=THEMES[current_theme]['background'])
    dark_theme_checkbutton.pack(pady=10)

    # Кнопка для открытия местоположения исполняемого файла
    open_location_button = tk.Button(settings_window, text="Открыть местоположение файла", command=open_executable_location, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), bd=0)
    open_location_button.pack(pady=10)

    save_button = tk.Button(settings_window, text="Сохранить изменения", command=save_config, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), bd=0)
    save_button.pack(pady=10)


def open_website():
    """Открыть веб-сайт."""
    webbrowser.open("https://filefinder.mutetds.ru")  # Замените на ваш сайт

def show_history():
    """Показать окно истории запусков."""
    history_window = tk.Toplevel(root)
    history_window.title("История запусков")
    history_window.geometry("600x300")  # Размер окна
    apply_theme(history_window, current_theme)

    history_text = load_run_history()  # Загрузка истории запусков
    history_label = tk.Label(history_window, text=history_text, fg=THEMES[current_theme]['text'], bg=THEMES[current_theme]['background'], font=('Arial', 12), wraplength=580, justify=tk.LEFT)
    history_label.pack(padx=10, pady=10, fill=BOTH, expand=True)

async def find_files_by_keywords_async(root_dir, keywords):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        found_files = await loop.run_in_executor(executor, find_files_by_keywords, root_dir, keywords)
    return found_files

async def find_folders_by_keywords_async(root_dir, folder_keywords, blacklisted_folders):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        found_folders = await loop.run_in_executor(executor, find_folders_by_keywords, root_dir, folder_keywords, blacklisted_folders)
    return found_folders

async def analyze_file_async(file_path):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, analyze_file, file_path)
    return result

def start_check():
    """Запуск проверки на читы в асинхронном режиме."""
    asyncio.run(on_check())

def load_config():
    """Load configuration from the config file and apply it."""
    global current_theme
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as conf:
            config = json.load(conf)
            current_theme = config.get('theme', 'light')
            apply_theme(root, current_theme)
    else:
        save_config()  # Save default config if not exists

def save_config():
    """Save current configuration to the config file."""
    configS['theme'] = current_theme
    with open(CONFIG_FILE, 'w') as conf:
        json.dump(configS, conf, indent=4)
    logger.info('Configuration saved successfully')

# Создаем GUI
root = tk.Tk()
root.title("FileFinder v1.0")
root.geometry("800x400")  # Размер окна
apply_theme(root, current_theme)  # Применяем тему к основному окну
root.minsize(width=800, height=400)
load_config()

frame_left = tk.Frame(root, bg=THEMES[current_theme]['background'])
frame_left.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)

frame_right = tk.Frame(root, bg=THEMES[current_theme]['background'])
frame_right.pack(side=RIGHT, fill=BOTH, expand=True, padx=10, pady=10)

# Левый фрейм с кнопками
label = tk.Label(frame_left, text="FileFinder v1.0", fg=THEMES[current_theme]['text'], bg=THEMES[current_theme]['background'], font=('Arial', 14))
label.pack(pady=5)

check_button = tk.Button(frame_left, text="Искать", command=start_check, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), width=15, bd=0)
check_button.pack(pady=5)

help_button = tk.Button(frame_left, text="Инструкция", command=show_help, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), width=15, bd=0)
help_button.pack(pady=5)

website_button = tk.Button(frame_left, text="Посетить сайт", command=open_website, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), width=15, bd=0)
website_button.pack(pady=5)

settings_button = tk.Button(frame_left, text="Настройки", command=show_settings, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), width=15, bd=0)
settings_button.pack(pady=5)

# Добавляем кнопку "История" в левом фрейме
history_button = tk.Button(frame_left, text="История", command=show_history, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), width=15, bd=0)
history_button.pack(pady=5)

exit_button = tk.Button(frame_left, text="Выход", command=root.destroy, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), width=15, bd=0)
exit_button.pack(pady=5)

# Правый фрейм с результатами и скроллом
listbox_frame = tk.Frame(frame_right, bg=THEMES[current_theme]['background'])
listbox_frame.pack(fill=BOTH, expand=True)

scrollbar_y = Scrollbar(listbox_frame)
scrollbar_y.pack(side=RIGHT, fill=Y)

scrollbar_x = Scrollbar(listbox_frame, orient=tk.HORIZONTAL)
scrollbar_x.pack(side=tk.BOTTOM, fill=X)

listbox = Listbox(listbox_frame, yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set, height=15, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 10), bd=0, highlightthickness=0)
listbox.pack(fill=BOTH, expand=True)

scrollbar_y.config(command=listbox.yview)
scrollbar_x.config(command=listbox.xview)

# Кнопка для открытия выбранного элемента
open_button = tk.Button(frame_right, text="Открыть", command=open_selected_item, bg=THEMES[current_theme]['button'], fg=THEMES[current_theme]['text'], font=('Arial', 12), width=30, bd=0)
open_button.pack(pady=10)
open_button.config(state=tk.DISABLED)  # По умолчанию отключена

# Привязываем обработчик события выбора элемента
listbox.bind('<<ListboxSelect>>', on_select)

root.mainloop()
