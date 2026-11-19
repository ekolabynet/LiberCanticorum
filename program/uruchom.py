#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Liber Canticorum – program uruchamiający (tylko biblioteka standardowa Pythona).

* przy pierwszym starcie tworzy środowisko z bibliotekami (venv), wspólne dla wszystkich wersji:
    Windows:      %LOCALAPPDATA%\\LiberCanticorum\\venv
    Linux/macOS:  ~/.local/share/LiberCanticorum/venv
  i pokazuje okienko z postępem (albo okno terminala, gdy w systemie nie ma Tkintera),
* może przejąć środowisko z poprzedniej instalacji (folder obok),
* po aktualizacji doinstalowuje brakujące pakiety,
* odświeża skrót z ikoną w folderze programu (Windows: „Liber Canticorum.lnk”, Linux: plik .desktop),
* uruchamia program.

Opcje: --odtwarzacz (doinstaluj odtwarzacz YouTube), --skrot (skrót w menu i na pulpicie), --konsola (bez okienka).
"""
import os
import platform
import shutil
import subprocess
import sys
import threading

PROG = os.path.dirname(os.path.abspath(__file__))           # folder „program”
TOP = os.path.dirname(PROG)                                  # folder aplikacji (po rozpakowaniu)
WIN = os.name == 'nt'
MAC = platform.system() == 'Darwin'
NAME = "Liber Canticorum"
REQ = os.path.join(PROG, "requirements.txt")


def data_dir():
    if WIN:
        return os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "LiberCanticorum")
    return os.path.join(os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share')), "LiberCanticorum")


def vpy(venv, gui=False):
    if WIN:
        return os.path.join(venv, "Scripts", "pythonw.exe" if gui else "python.exe")
    return os.path.join(venv, "bin", "python")


def find_venv():
    for local in (os.path.join(TOP, ".venv"), os.path.join(PROG, ".venv")):      # stara instalacja z własnym venv
        if os.path.exists(vpy(local)):
            return local
    return os.path.join(data_dir(), "venv")


def old_venvs():
    """Środowiska z poprzednich wersji obok (LiberCanticorum_*, Spiewnik_slajdy_*)."""
    import glob
    parent = os.path.dirname(TOP)
    out = []
    for pat in ("LiberCanticorum*", "Spiewnik_slajdy*"):
        for d in glob.glob(os.path.join(parent, pat)):
            for v in (os.path.join(d, ".venv"), os.path.join(d, "program", ".venv")):
                if os.path.exists(vpy(v)) and os.path.realpath(d) != os.path.realpath(TOP):
                    out.append(v)
    return sorted(out, key=os.path.getmtime, reverse=True)


def installed_ok(venv):
    mark = os.path.join(venv, ".zainstalowano")
    try:
        with open(REQ, 'rb') as a, open(mark, 'rb') as b:
            return a.read() == b.read()
    except OSError:
        return False


# ---------------------------------------------------------------------
# okienko postępu (Tkinter) albo konsola
# ---------------------------------------------------------------------
class Ui:
    def __init__(self, gui=True):
        self.tk = None
        if gui:
            try:
                import tkinter as tk
                from tkinter import ttk
                self.root = tk.Tk()
                self.root.title(NAME)
                self.root.geometry("560x340")
                try:
                    self.root.iconphoto(True, tk.PhotoImage(file=os.path.join(PROG, "ikony", "liber_canticorum_64.png")))
                except Exception:
                    pass
                frm = ttk.Frame(self.root, padding=16)
                frm.pack(fill='both', expand=True)
                try:
                    self.logo = tk.PhotoImage(file=os.path.join(PROG, "ikony", "liber_canticorum_64.png"))
                    ttk.Label(frm, image=self.logo).pack()
                except Exception:
                    pass
                ttk.Label(frm, text=NAME, font=("Georgia", 18)).pack()
                self.msg = ttk.Label(frm, text="Przygotowuję program…", wraplength=520, justify='center')
                self.msg.pack(pady=6)
                self.bar = ttk.Progressbar(frm, mode='indeterminate', length=500)
                self.bar.pack(pady=4)
                self.bar.start(12)
                self.log = tk.Text(frm, height=6, font=("TkFixedFont", 8), relief='flat', background="#f4f1ea")
                self.log.pack(fill='both', expand=True, pady=(6, 0))
                self.tk = tk
            except Exception:
                self.tk = None

    def status(self, text):
        if self.tk:
            self.root.after(0, lambda: self.msg.config(text=text))
        else:
            print("\n== " + text)

    def line(self, text):
        if self.tk:
            def add():
                self.log.insert('end', text.rstrip() + "\n")
                self.log.see('end')
            self.root.after(0, add)
        else:
            print(text.rstrip())

    def ask(self, question):
        if self.tk:
            from tkinter import messagebox
            return messagebox.askyesno(NAME, question, parent=self.root)
        if sys.stdin and sys.stdin.isatty():
            return input(question + " [T/n] ").strip().lower() not in ('n', 'nie')
        return True

    def error(self, text):
        if self.tk:
            from tkinter import messagebox
            self.root.after(0, lambda: (messagebox.showerror(NAME, text, parent=self.root), self.root.destroy()))
        else:
            print("\nBŁĄD: " + text)
            if sys.stdin and sys.stdin.isatty():
                input("Naciśnij Enter…")

    def run(self, work):
        """Wykonuje work() w tle (okienko) albo od razu (konsola)."""
        if not self.tk:
            return work()
        result = {}

        def bg():
            try:
                result['ok'] = work()
            except Exception as e:
                result['ok'] = False
                self.error(str(e))
                return
            self.root.after(0, self.root.destroy)
        threading.Thread(target=bg, daemon=True).start()
        self.root.mainloop()
        return result.get('ok', False)


def pip(ui, venv, *args):
    cmd = [vpy(venv), "-m", "pip", "--disable-pip-version-check"] + list(args)
    flags = subprocess.CREATE_NO_WINDOW if WIN else 0
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=PROG,
                         creationflags=flags, encoding='utf-8', errors='replace')
    for line in p.stdout:
        if line.startswith(("Collecting", "Downloading", "Installing", "Successfully", "ERROR", "Requirement")):
            ui.line(line)
            if line.startswith("Collecting"):
                ui.status("Pobieram biblioteki: " + line.split()[1])
    return p.wait() == 0


def prepare(ui, venv, extra=()):
    """Tworzy / uzupełnia środowisko. → True gdy gotowe."""
    if not os.path.exists(vpy(venv)):
        olds = old_venvs()
        if olds and ui.ask(f"Znaleziono biblioteki z poprzedniej instalacji:\n{olds[0]}\n\n"
                           "Przenieść je (szybko, bez pobierania z internetu)?"):
            os.makedirs(os.path.dirname(venv), exist_ok=True)
            shutil.move(olds[0], venv)
    if not os.path.exists(vpy(venv)):
        ui.status("Pierwsze uruchomienie: tworzę środowisko z bibliotekami (ok. 600 MB, kilka minut)…")
        os.makedirs(os.path.dirname(venv), exist_ok=True)
        import venv as _venv
        try:
            _venv.EnvBuilder(with_pip=True).create(venv)
        except Exception as e:
            hint = "\nNa Debianie/Ubuntu/Mincie zainstaluj: sudo apt install python3-venv" if not WIN else ""
            raise RuntimeError(f"Nie udało się utworzyć środowiska Pythona ({e}).{hint}")
        pip(ui, venv, "install", "-q", "--upgrade", "pip")
    if not installed_ok(venv):
        ui.status("Instaluję lub aktualizuję biblioteki programu…")
        if not pip(ui, venv, "install", "-r", REQ):
            raise RuntimeError("Nie udało się zainstalować bibliotek. Sprawdź połączenie z internetem.")
        shutil.copyfile(REQ, os.path.join(venv, ".zainstalowano"))
    for req in extra:
        ui.status("Doinstalowuję: " + os.path.basename(req))
        pip(ui, venv, "install", "-r", os.path.join(PROG, req))
    return True


# ---------------------------------------------------------------------
# skróty z ikoną
# ---------------------------------------------------------------------
DESKTOP = """[Desktop Entry]
Type=Application
Name=Liber Canticorum
GenericName=Śpiewnik i slajdy z pieśniami
Comment=Wolny śpiewnik dla wspólnot – slajdy, nuty, pilot w telefonie
Exec={exec}
Icon={icon}
Terminal=false
Categories=Office;Presentation;
Keywords=śpiewnik;pieśni;slajdy;rzutnik;nuty;kościół;
"""
# Exec w pliku .desktop: najpierw folder, w którym leży ten plik (%k), potem ostatnio znane położenie,
# a w ostateczności najnowszy rozpakowany LiberCanticorum* w katalogu domowym.
SH_LAUNCH = ('for d in "$(dirname "$1")" "{top}"; do if [ -f "$d/program/uruchom.py" ]; then cd "$d/program" && '
             'exec python3 uruchom.py; fi; done; for f in $(ls -t "$HOME"/LiberCanticorum*/program/uruchom.py '
             '"$HOME"/*/LiberCanticorum*/program/uruchom.py "$HOME"/*/*/LiberCanticorum*/program/uruchom.py 2>/dev/null); '
             'do cd "$(dirname "$f")" && exec python3 uruchom.py; done')


def desktop_exec(top=""):
    """Polecenie sh -c … zapisane wg reguł pliku .desktop (cudzysłowy i ukośniki)."""
    script = SH_LAUNCH.replace("{top}", top.replace('"', ''))
    q = "".join("\\" + c if c in '"`$\\' else c for c in script)
    return ('sh -c "' + q + '" sh %k').replace("\\", "\\\\")


def refresh_shortcuts(venv, menu=False):
    icon_png = os.path.join(PROG, "ikony", "liber_canticorum_256.png")
    if WIN:
        lnk = os.path.join(TOP, NAME + ".lnk")
        targets = [lnk]
        if menu:
            targets += [os.path.join(os.path.expanduser("~"), "Desktop", NAME + ".lnk"),
                        os.path.join(os.environ.get('APPDATA', ''), "Microsoft", "Windows", "Start Menu", "Programs", NAME + ".lnk")]
        stamp = os.path.join(TOP, NAME + ".lnk")
        for t in targets:
            if t == stamp and os.path.exists(t) and not menu and _lnk_ok(t):
                continue
            ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); $s.TargetPath='{py}'; "
                  "$s.Arguments='\"{script}\"'; $s.WorkingDirectory='{wd}'; $s.IconLocation='{ico}'; "
                  "$s.Description='Liber Canticorum – wolny śpiewnik liturgiczny dla muzyków, chórów i wspólnot Kościoła'; $s.Save()").format(
                lnk=t.replace("'", "''"), py=vpy(venv, gui=True).replace("'", "''"),
                script=os.path.join(PROG, "uruchom.py").replace("'", "''"), wd=PROG.replace("'", "''"),
                ico=os.path.join(PROG, "ikony", "liber_canticorum.ico").replace("'", "''"))
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=subprocess.CREATE_NO_WINDOW)
        # pliki dla innych systemów schowaj, żeby w folderze był porządek
        for f in (NAME + ".desktop", NAME + ".command"):
            p = os.path.join(TOP, f)
            if os.path.exists(p):
                subprocess.run(["attrib", "+h", p], creationflags=subprocess.CREATE_NO_WINDOW)
        return
    if MAC:
        return
    # Linux: plik .desktop w folderze programu (z ikoną) + opcjonalnie w menu
    d = os.path.join(TOP, NAME + ".desktop")
    try:
        with open(d, 'w', encoding='utf-8') as f:
            f.write(DESKTOP.format(exec=desktop_exec(TOP), icon=icon_png))
        os.chmod(d, 0o755)
        subprocess.run(["gio", "set", d, "metadata::trusted", "true"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except OSError:
        pass
    try:                                     # menedżery plików (Nautilus, Dolphin, Thunar) ukryją pliki z .hidden
        with open(os.path.join(TOP, ".hidden"), 'w', encoding='utf-8') as f:
            f.write(f"{NAME}.bat\n{NAME}.command\n")
    except OSError:
        pass
    if menu:
        apps = os.path.join(os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share')), "applications")
        os.makedirs(apps, exist_ok=True)
        with open(os.path.join(apps, "liber-canticorum.desktop"), 'w', encoding='utf-8') as f:
            f.write(DESKTOP.format(exec=f'python3 "{os.path.join(PROG, "uruchom.py")}"', icon=icon_png))


def _lnk_ok(lnk):
    """Czy skrót wskazuje na ten folder (po przeniesieniu folderu trzeba go odświeżyć)."""
    try:
        with open(lnk, 'rb') as f:
            data = f.read()
        return PROG.encode('utf-16-le') in data or PROG.encode('mbcs', 'ignore') in data
    except Exception:
        return False


def open_terminal_and_rerun(args):
    """Linux bez Tkintera: pokaż instalację w oknie terminala."""
    me = [sys.executable, os.path.abspath(__file__), "--konsola"] + args
    for term in (["x-terminal-emulator", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"], ["xfce4-terminal", "-x"],
                 ["mate-terminal", "-x"], ["lxterminal", "-e"], ["xterm", "-e"]):
        if shutil.which(term[0]):
            subprocess.Popen(term + me)
            return True
    return False


def main():
    args = [a for a in sys.argv[1:]]
    console = "--konsola" in args
    args = [a for a in args if a != "--konsola"]
    extra = ["requirements-odtwarzacz.txt"] if "--odtwarzacz" in args else []
    menu = "--skrot" in args
    args = [a for a in args if a not in ("--odtwarzacz", "--skrot")]
    venv = find_venv()
    need = not os.path.exists(vpy(venv)) or not installed_ok(venv) or extra
    if need and not console and not WIN and not MAC:
        try:
            import tkinter  # noqa: F401
        except ImportError:
            if not (sys.stdin and sys.stdin.isatty()) and open_terminal_and_rerun(sys.argv[1:]):
                return 0
    ui = Ui(gui=need and not console)
    if need:
        ok = ui.run(lambda: prepare(ui, venv, extra))
        if not ok:
            return 1
    try:
        refresh_shortcuts(venv, menu)
    except Exception:
        pass
    if menu:
        print("Dodano skrót do menu i na pulpit.")
    cmd = [vpy(venv, gui=True), os.path.join(PROG, "liber_canticorum.py")] + args
    if WIN:
        subprocess.Popen(cmd, cwd=PROG, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        os.chdir(PROG)
        os.execv(cmd[0], cmd)
    return 0


if __name__ == '__main__':
    sys.exit(main())
