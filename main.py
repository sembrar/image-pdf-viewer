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


ALLOW_DEBUGGING = True


DEFAULT_BOOKMARKS_TEXT_WIDTH = 40  # It is num chars. Also, height isn't required because it will expand vertically

_FOLDER_OF_THIS_PYTHON_FILE = os.path.split(sys.argv[0])[0]  # sys.argv[0] is the rel path to the file being run
SETTINGS_FILE_PATH = os.path.join(_FOLDER_OF_THIS_PYTHON_FILE, "data\\settings.json")

KEY_SETTING_GUI_GEOMETRY = "geometry"
KEY_SETTING_GUI_STATE = "state"  # maximized window, or normal window
CURRENTLY_OPENED_BOOK = "currently-opened-book"


KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS = set()
KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS.update(map(lambda x: f"F{x}", range(1, 12+1)))  # function keys
if ALLOW_DEBUGGING:
    print("Keys that will be further processed in text bookmarks:",
          KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS)


KEY_CURRENT_OPENED_PAGE_NUM = "current-opened-page-num"

TAG_OBJECT = "obj"
TAG_PAGE_IMAGE = "pg-img"
PREFIX_TAG_PAGE_NUM = "pg-num"  # this is used in tag.startswith, so, this must be unique prefix


NUM_PIXELS_TO_SCROLL = 40
PIXELS_BETWEEN_PAGES = 20
NUM_PAGE_IMAGE_RANGE_TO_KEEP = 3  # this means from current page num +-3 are kept


# some helper functions


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


def get_page_num_tag(page_num):
    return f"{PREFIX_TAG_PAGE_NUM}-{page_num}"


class PdfViewer(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.set_default_title()

        self._gui_settings = dict()
        self._loaded_images = dict()
        self._canvas_id_to_page_num = dict()
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

        self._canvas.bind("<MouseWheel>", self._mouse_wheel_in_canvas)
        # this is working as expected to work, i.e. even though focus is in some other widget, if mouse is scrolled
        # in this widget, the event is being registered

        # if there is a previously opened book, open it
        currently_opened_book = self._gui_settings.get(CURRENTLY_OPENED_BOOK, None)
        if currently_opened_book is not None and os.path.isdir(currently_opened_book):
            self._load_book(currently_opened_book)

    def set_default_title(self):
        if ALLOW_DEBUGGING:
            print("\nSet default title")
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
        if ALLOW_DEBUGGING:
            print("\nSave GUI settings")

        # there may already be some settings in self._gui_settings like currently-opened-book etc
        # here, we add some additional ones like state i.e. zoomed/normal, application geometry string
        self._gui_settings[KEY_SETTING_GUI_STATE] = self.state()
        if self._gui_settings[KEY_SETTING_GUI_STATE] == "zoomed":
            # if zoomed, make it normal to get underlying geometry string
            self.state("normal")
        self._gui_settings[KEY_SETTING_GUI_GEOMETRY] = self.winfo_geometry()

        if ALLOW_DEBUGGING:
            print("GUI settings being saved:", self._gui_settings)

        try:
            with open(SETTINGS_FILE_PATH, 'w') as f:
                f.write(json.dumps(self._gui_settings, indent=2))
        except IOError:
            print("IOError while writing settings to", SETTINGS_FILE_PATH)

    def _load_gui_settings(self):
        if ALLOW_DEBUGGING:
            print("\nLoad GUI settings")

        try:
            with open(SETTINGS_FILE_PATH) as f:
                self._gui_settings = json.loads(f.read())  # type: dict
        except IOError:
            print(f'IOError while reading settings from "{SETTINGS_FILE_PATH}". The file may not exist yet.')
            return

        if ALLOW_DEBUGGING:
            print("Loaded GUI settings:", self._gui_settings)

        self.geometry(newGeometry=self._gui_settings.get(KEY_SETTING_GUI_GEOMETRY, None))
        self.state(newstate=self._gui_settings.get(KEY_SETTING_GUI_STATE, None))

    def _open_a_book(self, _event):

        if ALLOW_DEBUGGING:
            print("\nOpen a book")

        initial_dir_for_ask_dir_dialog = None

        # find the initial directory for ask directory dialog:
        # if a book is opened currently, use its parent directory as initial directory, else use the Drive letter
        currently_opened_book = self._gui_settings.get(CURRENTLY_OPENED_BOOK, None)
        if currently_opened_book is not None:
            parent_dir_of_currently_opened_book = os.path.split(currently_opened_book)[0]
            if os.path.isdir(parent_dir_of_currently_opened_book):
                initial_dir_for_ask_dir_dialog = parent_dir_of_currently_opened_book

        if initial_dir_for_ask_dir_dialog is None:  # if it is still None, use the drive letter
            initial_dir_for_ask_dir_dialog = os.path.splitdrive(sys.argv[0])[0]

        result = filedialog.askdirectory(initialdir=initial_dir_for_ask_dir_dialog)
        if result == "":
            if ALLOW_DEBUGGING:
                print("Open a book cancelled")
            return

        if ALLOW_DEBUGGING:
            print(f"Chosen folder {result} for open a book.")

        self._gui_settings[CURRENTLY_OPENED_BOOK] = result

        self._load_book(result)

    # this function should provide a list of recently opened books to choose from quickly
    def _open_a_recent_book(self, event):
        return

    def _key_press_in_text_bookmarks(self, event):
        if ALLOW_DEBUGGING:
            print("\nKey press in text bookmarks:", event.keysym)

        try:
            # if there is any hot key binding to this key, do it
            # todo disallow running hot key binding if unnecessary modifiers are there like shift, control etc
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
        if ALLOW_DEBUGGING:
            print("\nLoad book", book_directory)

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

    def _load_page(self, page_num, delete_all_objects=True, x=2, y=2, anchor="nw"):

        if ALLOW_DEBUGGING:
            print(f"\nLoad page {page_num} anchored at at {anchor} of ({x}, {y})"
                  f" Delete all objects: {delete_all_objects}")

        # (x,y) is northwest point of image
        if delete_all_objects:
            self._canvas.delete(TAG_OBJECT)
            self._loaded_images.clear()
            self._canvas_id_to_page_num.clear()
            # todo see if all required items are cleared

        tag_for_this_page_num = get_page_num_tag(page_num)

        if page_num in self._loaded_images:

            if ALLOW_DEBUGGING:
                print(f"Page-{page_num} was already loaded. Just scrolling to that page")
                print("It's bbox:", self._canvas.bbox(tag_for_this_page_num))

            _, y1, _, _ = self._canvas.bbox(tag_for_this_page_num)
            dy = y - y1
            self._canvas.move(TAG_OBJECT, 0, dy)  # move all canvas objects by that amount

            if ALLOW_DEBUGGING:
                print("It's new bbox:", self._canvas.bbox(tag_for_this_page_num))

        else:

            if ALLOW_DEBUGGING:
                print("This page has to be loaded")

            page_png_image_path = get_page_path(self._gui_settings[CURRENTLY_OPENED_BOOK], page_num)
            # PIL needs lingering reference (otherwise, the image gets garbage collected and unavailable)
            self._loaded_images[page_num] = ImageTk.PhotoImage(Image.open(page_png_image_path))

            img_id = self._canvas.create_image(x, y, anchor=anchor, image=self._loaded_images[page_num],
                                               tags=(TAG_OBJECT, TAG_PAGE_IMAGE, tag_for_this_page_num))
            self._canvas_id_to_page_num[img_id] = page_num

            # delete images on canvas that are far away todo
            # although this section can be moved out of the parent if block, it is kept here, the idea is
            # delete things only when new things are added (otherwise, it's ok to keep things in memory)
            # loaded_images_page_numbers = tuple(self._loaded_images.keys())
            # for p in loaded_images_page_numbers:
            #     if abs(p - page_num) > NUM_PAGE_IMAGE_RANGE_TO_KEEP:
            #         self._canvas.delete(get_page_num_tag(p))
            #         print("Deleted page", p, "from canvas")
            #         self._loaded_images.pop(p)
            #         self._canvas_id_to_page_num

    def _mouse_wheel_in_canvas(self, event):
        # try:
        #     self._i += 1
        # except AttributeError:
        #     self._i = 0
        # print("Mouse wheel in canvas", self._i, event.delta)
        # scrolling down gives negative multiples of 120
        # scrolling up gives positive multiples of 120

        if ALLOW_DEBUGGING:
            print("\nMouse wheel in canvas", event.delta)

        # print("Canvas geo:", self._canvas.winfo_geometry(),
        #       "width:", self._canvas.winfo_width(),
        #       "height:", self._canvas.winfo_height(),
        #       "Root geo:", self.winfo_toplevel().winfo_geometry())
        # canvas's winfo_width and height are giving correct values along with canvas' geo string

        canvas_width = self._canvas.winfo_width()
        canvas_height = self._canvas.winfo_height()

        if ALLOW_DEBUGGING:
            print("Canvas width:", canvas_width, "Canvas height:", canvas_height)

        scroll_amount = (event.delta // 120) * NUM_PIXELS_TO_SCROLL

        objects_in_scroll_distance = self._canvas.find_overlapping(
            0, -scroll_amount, canvas_width, canvas_height - scroll_amount)
        # note: using +scroll_amount above is causing a bug:
        # which is, after scrolling the page, and it fully goes beyond top boundary, it is not coming back,
        # the same bug is also caused if we used 0 in the place of scroll_amount above i.e. visible screen

        if ALLOW_DEBUGGING:
            print("Objects in scroll distance:", objects_in_scroll_distance)
            for v in objects_in_scroll_distance:
                print("Id:", v, "Tags:", self._canvas.gettags(v), "Bbox:", self._canvas.bbox(v))

        if len(objects_in_scroll_distance) > 0:
            self._canvas.move(TAG_OBJECT, 0, scroll_amount)  # move all objects on canvas

        # now, if a page is going beyond boundaries, then next / previous page has to be shown for continuous scroll
        # if scrolling up, consider page at the top most (of the screen), if scrolling down, the bottom most
        page_to_consider = None
        page_obj = None
        for v in objects_in_scroll_distance:
            page_num = self._canvas_id_to_page_num.get(v, None)
            if page_num is None:  # this canvas object isn't a page image
                continue

            if page_to_consider is None:
                page_to_consider = page_num
                page_obj = v
                continue

            if event.delta < 0:  # scrolling down
                if page_num > page_to_consider:
                    page_to_consider = page_num
                    page_obj = v
            else:
                if page_num < page_to_consider:
                    page_to_consider = page_num
                    page_obj = v

        if ALLOW_DEBUGGING:
            print("For showing next/previous page: Page to consider:", page_to_consider, "Page object:", page_obj)

        if page_to_consider is None:
            return

        if event.delta < 0:  # scrolling down
            _, _, _, y2 = self._canvas.bbox(page_obj)

            if ALLOW_DEBUGGING:
                print("The bottom most y coordinate of the page:", y2)

            if y2 < canvas_height - PIXELS_BETWEEN_PAGES:
                if ALLOW_DEBUGGING:
                    print("Page scrolled up. Show next page")
                self._load_page(page_to_consider + 1, delete_all_objects=False, y=y2 + PIXELS_BETWEEN_PAGES)
            else:
                if ALLOW_DEBUGGING:
                    print("Page hasn't scrolled up enough to reveal next page")

        else:  # scrolling up
            pass


def main():

    # parser = argparse.ArgumentParser()

    # args = parser.parse_args()

    PdfViewer().mainloop()

    return


if __name__ == '__main__':
    main()
