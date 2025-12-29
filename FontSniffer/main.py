import sys
import os

if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS)

from gui_model import main

if __name__ == "__main__":
    main()