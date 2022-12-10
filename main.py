# import argparse
import sys
import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import json
from PIL import Image, ImageTk

import ctypes

ctypes.windll.shcore.SetProcessDpiAwareness(1)  # do this once before starting the GUI to fix blurring in 1080p screens


DEFAULT_BOOKMARKS_TEXT_WIDTH = 40  # It is num chars. Also, height isn't required because it will expand vertically

_FOLDER_OF_THIS_PYTHON_FILE = os.path.split(sys.argv[0])[0]  # sys.argv[0] is the rel path to the file being run
SETTINGS_FILE_PATH = os.path.join(_FOLDER_OF_THIS_PYTHON_FILE, "data\\settings.json")

KEY_SETTING_GUI_GEOMETRY = "geometry"
KEY_SETTING_GUI_STATE = "state"  # maximized window, or normal window
CURRENTLY_OPENED_BOOK = "currently-opened-book"


KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS = set()
KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS.update(map(lambda x: f"F{x}", range(1, 12+1)))  # function keys
print("Keys that will be further processed in text bookmarks:", KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS)


KEY_CURRENT_OPENED_PAGE_NUM = "current-opened-page-num"

TAG_OBJECT = "obj"
TAG_PAGE_IMAGE = "pg-img"


def get_metadata_folder(book_folder):
    return os.path.join(book_folder, "metadata")


def get_bookmarks_file_path(book_metadata_folder):
    return os.path.join(book_metadata_folder, "bookmarks.json")


def get_book_settings_file_path(book_metadata_folder):
    return os.path.join(book_metadata_folder, "book_settings.json")


def get_annotations_file_path(book_metadata_folder):
    return os.path.join(book_metadata_folder, "annotations.json")


def get_page_path(book_folder, page_num):
    return os.path.join(book_folder, f'{str(page_num).rjust(6, "0")}.png')


class PdfViewer(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.set_default_title()

        self._settings = dict()
        self._loaded_images = dict()
        self._annotations = dict()

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

        try:
            self._hot_key_bindings = {"o": self._open_a_book, "r": self._open_a_recent_book}
        except AttributeError:
            print("Error: Some functions mentioned for key bindings in self._hot_key_bindings do not exist."
                  " No key bindings will be made.")
            self._hot_key_bindings = {}
        for k in self._hot_key_bindings:
            self.bind_all(f"<Key-{k}>", self._hot_key_bindings[k])

        self._text_bookmarks.bind("<Key>", self._key_press_in_text_bookmarks)
        # The idea is to make the text readonly but also respond to hot-keys
        # For this purpose, in the above event handler, hot key functions will be executed if there is one for the
        # event's keysym (i.e. the key pressed)
        # The event handler itself will return the string "break" so that the text widget doesn't get characters into it
        # This is working irrespective of whether this binding is done before the binding of hot keys above, or after

    def set_default_title(self):
        self.title("PdfViewer")

    def _left_click_on_size_grip_like_frame(self, event):
        # print("left_click_on_size_grip_like_canvas")
        pass

    def _motion_in_size_grip_like_frame(self, event):
        # try:
        #     self._i += 1
        # except:
        #     self._i = 0
        # print("_motion_in_size_grip_like_canvas", self._i)
        pass

    def destroy(self):
        self._save_gui_settings()
        tk.Tk.destroy(self)

    def _save_gui_settings(self):
        self._settings[KEY_SETTING_GUI_STATE] = self.state()
        if self._settings[KEY_SETTING_GUI_STATE] == "zoomed":
            # if zoomed, make it normal to get underlying geometry string
            self.state("normal")
        self._settings[KEY_SETTING_GUI_GEOMETRY] = self.winfo_geometry()

        # todo save which book is opened

        print(self._settings)

        try:
            with open(SETTINGS_FILE_PATH, 'w') as f:
                f.write(json.dumps(self._settings, indent=2))
        except IOError:
            print("IOError while writing settings to", SETTINGS_FILE_PATH)

    def _load_gui_settings(self):
        try:
            with open(SETTINGS_FILE_PATH) as f:
                self._settings = json.loads(f.read())  # type: dict
        except IOError:
            print(f'IOError while reading settings from "{SETTINGS_FILE_PATH}". The file may not exist yet.')
            return
        self.geometry(newGeometry=self._settings.get(KEY_SETTING_GUI_GEOMETRY, None))
        self.state(newstate=self._settings.get(KEY_SETTING_GUI_STATE, None))

    def _open_a_book(self, _event):

        initial_dir_for_ask_dir_dialog = None

        # find the initial directory for ask directory dialog:
        # if a book is opened currently, use its parent directory as initial directory, else use the Drive letter
        currently_opened_book = self._settings.get(CURRENTLY_OPENED_BOOK, None)
        if currently_opened_book is not None:
            parent_dir_of_currently_opened_book = os.path.split(currently_opened_book)[0]
            if os.path.isdir(parent_dir_of_currently_opened_book):
                initial_dir_for_ask_dir_dialog = parent_dir_of_currently_opened_book

        if initial_dir_for_ask_dir_dialog is None:  # if it is still None, use the drive letter
            initial_dir_for_file_dialog = os.path.splitdrive(sys.argv[0])[0]

        result = filedialog.askdirectory(initialdir=initial_dir_for_ask_dir_dialog)
        if result == "":
            print("Open a book cancelled")
            return

        print(f"Chosen folder {result} for open a book.")

        self._settings[CURRENTLY_OPENED_BOOK] = result

        self._load_book(result)

    def _open_a_recent_book(self, event):
        return

    def _key_press_in_text_bookmarks(self, event):
        print("Key press in text bookmarks:", event.keysym)
        try:
            # if there is any hot key binding to this key, do it
            self._hot_key_bindings[event.keysym](event)
        except KeyError:
            pass

        if event.keysym in KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS:
            # this will allow pressing "Alt F4" for further processing which will close the application
            # otherwise, pressing "Alt F4" when text bookmarks is in Focus will not close the application because
            # the event will be stopped from further processing because of returning "break"
            return None

        return "break"  # makes the text bookmark readonly by disallowing further processing of the event

    def _load_book(self, book_directory):
        metadata_folder = get_metadata_folder(book_directory)

        page_to_open = 1

        if os.path.exists(metadata_folder):

            # read book settings like which page opened
            try:
                with open(get_book_settings_file_path(metadata_folder)) as f:
                    book_settings = json.loads(f.read())  # type: dict
                page_to_open = book_settings.get(KEY_CURRENT_OPENED_PAGE_NUM, page_to_open)
            except IOError:
                print("Book-settings file doesn't exist for this book:", get_book_settings_file_path(metadata_folder))

            # read bookmarks
            self._text_bookmarks.delete("1.0", tk.END)
            try:
                with open(get_bookmarks_file_path(metadata_folder)) as f:
                    bookmarks = json.loads(f.read())
                self._text_bookmarks.insert("1.0", "\n".join(map(lambda x: f"{' ' * x[0]} {x[1]}  {x[2]}", bookmarks)))
            except IOError:
                print("Bookmarks file doesn't exist for this book:", get_bookmarks_file_path(metadata_folder))

            # read annotations

        self._load_page(page_to_open)

    def _load_page(self, page_num):
        self._canvas.delete(TAG_OBJECT)
        self._loaded_images.clear()

        page_png_image_path = get_page_path(self._settings[CURRENTLY_OPENED_BOOK], page_num)
        self._loaded_images[page_num] = ImageTk.PhotoImage(Image.open(page_png_image_path))

        self._canvas.create_image(2, 2, anchor="nw", image=self._loaded_images[page_num],
                                  tags=(TAG_OBJECT, TAG_PAGE_IMAGE))


def main():

    # parser = argparse.ArgumentParser()

    # args = parser.parse_args()

    PdfViewer().mainloop()

    return


if __name__ == '__main__':
    main()
