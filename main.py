# import argparse
import sys
import os
import tkinter as tk
from tkinter import ttk
import json

import ctypes

ctypes.windll.shcore.SetProcessDpiAwareness(1)  # do this once before starting the GUI to fix blurring in 1080p screens


DEFAULT_BOOKMARKS_TEXT_WIDTH = 40  # It is num chars. Also, height isn't required because it will expand vertically

_FOLDER_OF_THIS_PYTHON_FILE = os.path.split(sys.argv[0])[0]  # sys.argv[0] is the rel path to the file being run
SETTINGS_FILE_PATH = os.path.join(_FOLDER_OF_THIS_PYTHON_FILE, "data\\settings.json")

KEY_SETTING_GUI_GEOMETRY = "geometry"
KEY_SETTING_GUI_STATE = "state"  # maximized window, or normal window


class PdfViewer(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.set_default_title()

        # a frame for bookmarks
        # it holds a text and 2 scrolls (horizontal and vertical)

        self._frame_bookmarks = tk.Frame(self, bg="light blue")
        # let this only fill required amount of space at horizontally
        self._frame_bookmarks.grid(row=0, column=0, sticky='ns')
        self.rowconfigure(0, weight=1)

        # the text for bookmarks and the two scrolls

        self._text_bookmarks = tk.Text(self._frame_bookmarks, width=DEFAULT_BOOKMARKS_TEXT_WIDTH, wrap=tk.NONE)
        self._text_bookmarks.grid(row=0, column=0, sticky='ns')
        self._frame_bookmarks.rowconfigure(0, weight=1)

        self._v_scroll_bookmarks = ttk.Scrollbar(self._frame_bookmarks, orient=tk.VERTICAL,
                                                 command=self._text_bookmarks.yview)
        self._v_scroll_bookmarks.grid(row=0, column=1, sticky='ns')

        self._h_scroll_bookmarks = ttk.Scrollbar(self._frame_bookmarks, orient=tk.HORIZONTAL,
                                                 command=self._text_bookmarks.xview)
        self._h_scroll_bookmarks.grid(row=1, column=0, sticky='ew')

        self._text_bookmarks.configure(xscrollcommand=self._h_scroll_bookmarks.set,
                                       yscrollcommand=self._v_scroll_bookmarks.set)

        # a sizegrip like frame (tk Frame for background color)
        # this is used to change the width of the bookmarks text by clicking and dragging
        self._size_grip_like_frame = tk.Frame(self._frame_bookmarks, bg="blue")
        self._size_grip_like_frame.grid(row=1, column=1, sticky='news')

        # the canvas to show images

        self._canvas = tk.Canvas(self, bg="light green")
        self._canvas.grid(row=0, column=2, sticky='news')
        self.columnconfigure(2, weight=1)

        self._load_gui_settings()

        # bindings

        self._size_grip_like_frame.bind("<Button-1>", self._left_click_on_size_grip_like_frame)
        self._size_grip_like_frame.bind("<Motion>", self._motion_in_size_grip_like_frame)
        # note: After left clicking, even moving outside of the widget will register the Motion event, which is useful
        #  If not left clicked, only the motion inside the widget is registered

    def set_default_title(self):
        self.title("PdfViewer")

    def _left_click_on_size_grip_like_frame(self, event):
        print("left_click_on_size_grip_like_canvas")

    def _motion_in_size_grip_like_frame(self, event):
        try:
            self._i += 1
        except:
            self._i = 0
        print("_motion_in_size_grip_like_canvas", self._i)

    def destroy(self):
        self._save_gui_settings()
        tk.Tk.destroy(self)

    def _save_gui_settings(self):
        settings = {KEY_SETTING_GUI_STATE: self.state()}
        if settings[KEY_SETTING_GUI_STATE] == "zoomed":  # if zoomed, make it normal to get underlying geometry string
            self.state("normal")
        settings[KEY_SETTING_GUI_GEOMETRY] = self.winfo_geometry()

        # todo save which book is opened

        # print(settings)

        try:
            with open(SETTINGS_FILE_PATH, 'w') as f:
                f.write(json.dumps(settings, indent=2))
        except IOError:
            print("IOError while writing settings to", SETTINGS_FILE_PATH)

    def _load_gui_settings(self):
        try:
            with open(SETTINGS_FILE_PATH) as f:
                settings = json.loads(f.read())  # type: dict
        except IOError:
            print(f'IOError while reading settings from "{SETTINGS_FILE_PATH}". The file may not exist yet.')
            return
        self.geometry(newGeometry=settings.get(KEY_SETTING_GUI_GEOMETRY, None))
        self.state(newstate=settings.get(KEY_SETTING_GUI_STATE, None))


def main():

    # parser = argparse.ArgumentParser()

    # args = parser.parse_args()

    PdfViewer().mainloop()

    return


if __name__ == '__main__':
    main()
