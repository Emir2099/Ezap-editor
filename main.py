from tkinter import *

compiler = Tk()
compiler.title('Ezap editor')

def run():
    code = editor.get('1.0', END)
    exec(code)

menu_bar = Menu(compiler)

run_bar = Menu(menu_bar, tearoff=0)
run_bar.add_command(label='Run', command=run)
menu_bar.add_cascade(label='Run', menu=run_bar)

file_menu = Menu(menu_bar, tearoff=0)
file_menu.add_command(label='Open', command=run)
menu_bar.add_cascade(label='File', menu=file_menu)

compiler.config(menu=menu_bar)

editor = Text()
editor.pack()

compiler.mainloop()
