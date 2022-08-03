from tkinter import *
from tkinter.filedialog import asksaveasfilename

from numpy import save

compiler = Tk()
compiler.title('Ezap editor')

def save_as():
    path = asksaveasfilename(filetypes=[('Python Files', '*.py')])
    with open(path, 'w') as file:
        code = editor.get('1.0', END)
        file.write(code)

def run():
    code = editor.get('1.0', END)
    exec(code)

menu_bar = Menu(compiler)

run_bar = Menu(menu_bar, tearoff=0)
run_bar.add_command(label='Run', command=run)
menu_bar.add_cascade(label='Run', menu=run_bar)

file_menu = Menu(menu_bar, tearoff=0)
file_menu.add_command(label='Open', command=run)
file_menu.add_command(label='Save', command=run)  #edit later
file_menu.add_command(label='Save As', command=save_as)
file_menu.add_command(label='Exit', command=exit)
menu_bar.add_cascade(label='File', menu=file_menu)

compiler.config(menu=menu_bar)

editor = Text()
editor.pack()

compiler.mainloop()
