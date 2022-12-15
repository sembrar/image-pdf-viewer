# import argparse
import sys
import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import simpledialog
from tkinter import messagebox
from tkinter import scrolledtext
import json
from PIL import Image, ImageTk
from collections import namedtuple  # for sending a temp Event type objects with just required data members
from datetime import datetime

import ctypes

ctypes.windll.shcore.SetProcessDpiAwareness(1)  # do this once before starting the GUI to fix blurring in 1080p screens


ALLOW_DEBUGGING = False


DEFAULT_BOOKMARKS_TEXT_WIDTH = 40  # It is num chars. Also, height isn't required because it will expand vertically

_FOLDER_OF_THIS_PYTHON_FILE = os.path.split(sys.argv[0])[0]  # sys.argv[0] is the rel path to the file being run
SETTINGS_FILE_PATH = os.path.join(_FOLDER_OF_THIS_PYTHON_FILE, "data\\settings.json")

KEY_SETTING_GUI_GEOMETRY = "geometry"
KEY_SETTING_GUI_STATE = "state"  # maximized window, or normal window
KEY_CURRENTLY_OPENED_BOOK = "currently-opened-book"

KEY_CURRENTLY_VISIBLE_PAGES = "currently-visible-pages"

KEY_RECENTLY_OPENED_BOOKS = "recently-opened-books"
NUM_BOOKS_TO_STORE_IN_RECENTLY_OPENED_BOOKS = 10
_DATETIME_FORMAT_TO_SAVE = "%Y-%m-%d-%H-%M-%S-%f"

KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS = set()
KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS.update(map(lambda x: f"F{x}", range(1, 12+1)))  # function keys
if ALLOW_DEBUGGING:
    print("Keys that will be further processed in text bookmarks:",
          KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS)

TAG_OBJECT = "obj"
TAG_PAGE_IMAGE = "pg-img"
PREFIX_TAG_PAGE_NUM = "pg-num"  # this is used in tag.startswith, so, this must be unique prefix
PREFIX_TAG_ANNOTATION_ARROW_DELTAS = "ann_del"  # this is used in tag.startswith, so, this must also be unique

TAG_BOOKMARK = "bm"


NUM_PIXELS_TO_SCROLL = 80
PIXELS_BETWEEN_PAGES = 20
NUM_PAGE_IMAGE_RANGE_TO_KEEP = 3  # this means from current page num +-3 are kept


_COLOR_LAVENDER = "#e6e6fa"
_COLOR_TEAL = "#008080"
_COLOR_CHERRY_RED = "#d2042d"
_COLOR_WHITE = "#ffffff"
_COLOR_LIGHT_BLUE = "#add8e6"
_COLOR_DARK_BLUE = "#00008b"
_COLOR_SKY_BLUE = "#87ceeb"


ANNOTATION_ARROW_COLOR = _COLOR_CHERRY_RED
ANNOTATION_ARROW_LENGTH = 100  # pixels
ANNOTATION_ARROW_WIDTH = 3
ANNOTATION_ARROW_SHAPE = (8, 10, 3)  # see the shape explanation below
TAG_ANNOTATION = "ann"
TAG_ARROW = "arr"
"""
arrow shape: (d1, d2, d3)
The following arrow is pointing to right (like -->)
         |
-------------
         |
d1 is the horizontal part of the arrow tip
d2 is the diagonal part of the arrow tip (not drawn above: imagine a digonal line )
d3 is the vertical part of the arrow tip
tkinter's default is (8, 10, 3)
"""

TAG_TEXT = "txt"
ANNOTATION_TEXT_COLOR = _COLOR_CHERRY_RED
ANNOTATION_TEXT_DEFAULT_ANCHOR = "n"
ANNOTATION_TEXT_DEFAULT_JUSTIFY = tk.CENTER

TAG_ANNOTATION_HIGHLIGHTED = "ann-hl"
TAG_BBOX = "bbox"
ANNOTATION_HIGHLIGHT_COLOR = _COLOR_TEAL
ANNOTATION_HIGHLIGHT_WIDTH = 2
ANNOTATION_HIGHLIGHT_BBOX_PADDING = 5
ANNOTATION_HIGHLIGHTED_BRING_TO_SIGHT_PADDING = 100  # the out of sight annotations are
# brought to this many pixels into the visible area

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


def get_tag_annotation_arrow_deltas(dx, dy):
    return f"{PREFIX_TAG_ANNOTATION_ARROW_DELTAS}_{int(dx)}_{int(dy)}"


def get_dx_dy_from_tag_annotation_arrow_deltas(tag_annotation_arrow_deltas):
    _, dx, dy = str.rsplit(tag_annotation_arrow_deltas, "_", 2)  # 2 breaking points from right side at the split char
    return int(dx), int(dy)


class _QueryTextAnnotationDialog(simpledialog.Dialog):

    def __init__(self, title, prompt, initial_value=None, parent=None):

        self.prompt = prompt
        self.initial_value = initial_value
        self.entry = None

        simpledialog.Dialog.__init__(self, parent, title)

    def destroy(self):
        self.entry = None
        simpledialog.Dialog.destroy(self)

    def body(self, master):
        w = tk.Label(master, text=self.prompt, justify=tk.LEFT)
        w.grid(row=0, padx=5, sticky=tk.W)

        self.entry = scrolledtext.ScrolledText(master)
        self.entry.grid(row=1, padx=5, sticky=tk.W + tk.E)

        if self.initial_value is not None:
            self.entry.insert("1.0", self.initial_value)

        return self.entry  # this will have initial focus

    def buttonbox(self):
        super(_QueryTextAnnotationDialog, self).buttonbox()
        self.unbind("<Return>")  # by default, in super class' buttonbox function, the Return event on "self" is bound
        # to self.ok function which closes the dialog and returns the result, but, for text, we need Return to just
        # take the cursor to the next line, so, we unbind the above event AFTER the call to superclass' buttonbox is
        # finished. We can bind "Control-Return" instead as follows  // https://stackoverflow.com/a/62115918
        self.bind("<Control-Return>", self.ok)

    def validate(self):
        self.result = self.entry.get("1.0", tk.END)
        return 1


def ask_text(title, prompt, initial_value=None):
    d = _QueryTextAnnotationDialog(title, prompt, initial_value)
    return d.result


class _QueryRecentBooksDialog(simpledialog.Dialog):

    def __init__(self, title, prompt, recent_books, parent=None):
        self._prompt = prompt
        self._recent_books = recent_books
        self._book_button_widgets = {}

        self._selected_bg = "light blue"
        self._deselected_bg = "white"

        simpledialog.Dialog.__init__(self, parent, title)

    def destroy(self):
        self._book_button_widgets = None
        simpledialog.Dialog.destroy(self)

    def body(self, master):
        w = tk.Label(master, text=self._prompt, justify=tk.LEFT)
        w.grid(row=0, column=0, sticky='w')

        frame = ttk.Frame(master)
        frame.grid(row=1, column=0, sticky='w')

        for i in range(len(self._recent_books)):
            book_path = self._recent_books[i]
            book_name = os.path.split(book_path)[-1]

            button = tk.Button(frame, text=book_name, bg=self._deselected_bg, relief="flat", anchor="w")
            button.grid(row=i, column=0, sticky="ew")

            button.bind("<Button-1>", self._select_this)

            self._book_button_widgets[str(button)] = button

            button.book_path = book_path

    def validate(self):
        result = None
        for i in self._book_button_widgets:
            button = self._book_button_widgets[i]
            if button.cget("bg") == self._selected_bg:
                result = button.book_path
                break
        self.result = result
        return 1

    def _select_this(self, event):
        for i in self._book_button_widgets:
            self._book_button_widgets[i].configure(bg=self._deselected_bg)
        self._book_button_widgets[str(event.widget)].configure(bg=self._selected_bg)


def ask_recent_book(title, prompt, recent_books):
    d = _QueryRecentBooksDialog(title, prompt, recent_books)
    return d.result


class PdfViewer(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.set_default_title()

        self._gui_settings = dict()

        self._dict_page_num_to_image = dict()
        self._dict_canvas_id_to_page_num = dict()
        self._dict_page_num_to_canvas_id = dict()
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

        self._bind_all_hot_keys()

        self._text_bookmarks.bind("<Key>", self._key_press_in_text_bookmarks)
        # The idea is to make the text readonly but also respond to hot-keys
        # For this purpose, in the above event handler, hot key functions will be executed if there is one for the
        # event's keysym (i.e. the key pressed)
        # The event handler itself will return the string "break" so that the text widget doesn't get characters into it
        # This is working irrespective of whether this binding is done before the binding of hot keys above, or after

        self._canvas.bind("<MouseWheel>", self._mouse_wheel_in_canvas)
        # this is working as expected to work, i.e. even though focus is in some other widget, if mouse is scrolled
        # in this widget, the event is being registered

        self._canvas.bind("<Button-2>", self._event_handler_for_arrow_annotation)  # middle click
        self._canvas.bind("<Control-Button-2>", self._event_handler_for_text_annotation)  # control-middle click
        self._canvas.bind("<Button-3>", self._event_handler_for_remove_annotation)  # right click

        self._text_bookmarks.tag_config(TAG_BOOKMARK, foreground="green")
        self._text_bookmarks.tag_bind(TAG_BOOKMARK, "<Button-1>", self._click_on_a_bookmark)

        # if there is a previously opened book, open it
        currently_opened_book = self._gui_settings.get(KEY_CURRENTLY_OPENED_BOOK, None)
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
        self._save_annotations()
        self._save_book_settings()

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

        # if there are more recently opened books than allowed, remove the older ones
        # this code is commented for now, meaning, all recent books will be saved
        # as, the dialog only shows max allowed number of books, it may be kept this way for now

        # recently_opened_books = self._gui_settings.get(KEY_RECENTLY_OPENED_BOOKS, {})
        # if len(recently_opened_books) > NUM_BOOKS_TO_STORE_IN_RECENTLY_OPENED_BOOKS:
        #     books_ordered_by_most_recent = sorted(recently_opened_books.keys(),
        #                                           key=lambda x: recently_opened_books[x], reverse=True)
        #     for i in range(NUM_BOOKS_TO_STORE_IN_RECENTLY_OPENED_BOOKS, len(books_ordered_by_most_recent)):
        #         recently_opened_books.pop(books_ordered_by_most_recent[i])

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
        currently_opened_book = self._gui_settings.get(KEY_CURRENTLY_OPENED_BOOK, None)
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

        self._save_current_book_and_clear_canvas_and_bookmarks_and_dictionaries()
        self._load_book(result)

    # this function should provide a list of recently opened books to choose from quickly
    def _open_a_recent_book(self, _event):
        if ALLOW_DEBUGGING:
            print("Open a recent book")

        recently_opened_books_dict = self._gui_settings.get(KEY_RECENTLY_OPENED_BOOKS, {})
        recently_opened_books = sorted(recently_opened_books_dict.keys(),
                                       key=lambda x: recently_opened_books_dict[x], reverse=True)
        if ALLOW_DEBUGGING:
            print("Recent books:", recently_opened_books)

        if len(recently_opened_books) == 0:
            if ALLOW_DEBUGGING:
                print("No recently opened books exist")
            else:
                messagebox.showinfo("Info", "No books were opened previously to choose from")
            return

        recently_opened_books = recently_opened_books[:NUM_BOOKS_TO_STORE_IN_RECENTLY_OPENED_BOOKS]
        result = ask_recent_book("Quick open", "Choose a recently opened book:", recently_opened_books)
        if ALLOW_DEBUGGING:
            print("Result:", result)

        if result is None:
            if ALLOW_DEBUGGING:
                print("Open recent book Cancelled")
            return
        if type(result) != str:
            if ALLOW_DEBUGGING:
                print("Unknown result type: Open recent book dialog returned something other than str")
            return

        self._save_current_book_and_clear_canvas_and_bookmarks_and_dictionaries()
        self._load_book(result)

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

    def _save_current_book_and_clear_canvas_and_bookmarks_and_dictionaries(self):
        # save the annotations, book-settings of the current book
        if self._gui_settings.get(KEY_CURRENTLY_OPENED_BOOK, None) is not None:
            self._save_annotations()
            self._save_book_settings()

        # clear canvas and bookmarks
        self._canvas.delete(TAG_OBJECT)  # delete all objects on canvas
        self._text_bookmarks.delete("1.0", tk.END)

        # clear all dictionaries
        self._dict_page_num_to_image.clear()
        self._dict_page_num_to_canvas_id.clear()
        self._dict_canvas_id_to_page_num.clear()
        self._annotations.clear()

    def _load_book(self, book_directory):
        if ALLOW_DEBUGGING:
            print("\nLoad book", book_directory)

        if not os.path.isdir(book_directory):
            print("ERROR: Book dir doesn't exist:", book_directory)
            return

        # the following setting is used in other functions, for example, in _load_page etc
        self._gui_settings[KEY_CURRENTLY_OPENED_BOOK] = book_directory

        # save the book directory to recently opened
        if KEY_RECENTLY_OPENED_BOOKS not in self._gui_settings:
            self._gui_settings[KEY_RECENTLY_OPENED_BOOKS] = {}
        self._gui_settings[KEY_RECENTLY_OPENED_BOOKS][book_directory] =\
            datetime.today().strftime(_DATETIME_FORMAT_TO_SAVE)

        metadata_folder = get_metadata_folder(book_directory)

        book_settings = {}

        if os.path.exists(metadata_folder):

            # read book settings like which page opened
            try:
                with open(get_book_settings_file_path(metadata_folder)) as f:
                    book_settings = json.loads(f.read())
            except IOError:
                print("Book-settings file doesn't exist for this book:", get_book_settings_file_path(metadata_folder))
            except json.JSONDecodeError:
                print("Bad json in book-settings file:", get_book_settings_file_path(metadata_folder))

            # read bookmarks
            self._text_bookmarks.delete("1.0", tk.END)
            try:
                with open(get_bookmarks_file_path(metadata_folder)) as f:
                    bookmarks = json.loads(f.read())
                for (indent, title, page_num) in bookmarks:
                    self._text_bookmarks.insert(tk.END, " " * indent, ())  # empty tuple as tags because,
                    # if not given, then tags at preceding/succeeding characters may be taken
                    self._text_bookmarks.insert(tk.END, title, (TAG_BOOKMARK,))  # note, tuple required for tags even
                    # when there is only one tag, because, for Text widget, if string is given, each individual letter
                    # will be applied as a separate tag
                    self._text_bookmarks.insert(tk.END, f"  {page_num}\n", ())
            except IOError:
                print("Bookmarks file doesn't exist for this book:", get_bookmarks_file_path(metadata_folder))

            # read annotations
            self._read_annotations()

        try:
            visible_pages = book_settings[KEY_CURRENTLY_VISIBLE_PAGES]
            assert type(visible_pages) == list
            assert len(visible_pages) > 0
            for page_num, x, y in visible_pages:
                self._load_page(page_num, x=x, y=y, delete_all_objects=False)
        except (KeyError, AssertionError, ValueError):
            self._load_page(1)

    def _load_page(self, page_num, delete_all_objects=True, x=2, y=2, anchor="nw"):

        if ALLOW_DEBUGGING:
            print(f"\nLoad page {page_num} anchored at at {anchor} of ({x}, {y})"
                  f" Delete all objects: {delete_all_objects}")

        # (x,y) is northwest point of image
        if delete_all_objects:
            for p in self._dict_page_num_to_image:
                self._save_annotations_back_to_the_dict_for_page(p)
            self._canvas.delete(TAG_OBJECT)
            self._dict_page_num_to_image.clear()
            self._dict_canvas_id_to_page_num.clear()
            self._dict_page_num_to_canvas_id.clear()
            # todo see if all required items are cleared

        tag_for_this_page_num = get_page_num_tag(page_num)
        # adding the above tag is necessary
        # reason: all the annotations that belong to a page can be removed along with the page

        if page_num in self._dict_page_num_to_image:

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

            page_png_image_path = get_page_path(self._gui_settings[KEY_CURRENTLY_OPENED_BOOK], page_num)
            if not os.path.isfile(page_png_image_path):
                if ALLOW_DEBUGGING:
                    print("There is no page with number:", page_num)
                return

            # PIL needs lingering reference (otherwise, the image gets garbage collected and unavailable)
            self._dict_page_num_to_image[page_num] = ImageTk.PhotoImage(Image.open(page_png_image_path))

            img_id = self._canvas.create_image(x, y, anchor=anchor, image=self._dict_page_num_to_image[page_num],
                                               tags=(TAG_OBJECT, TAG_PAGE_IMAGE, tag_for_this_page_num))
            self._dict_canvas_id_to_page_num[img_id] = page_num
            self._dict_page_num_to_canvas_id[page_num] = img_id

            self._draw_annotations_in_dict_on_to_canvas_for_page(page_num)

            # delete images on canvas that are far away
            # although this section can be moved out of the parent if block, it is kept here, the idea is,
            # delete things only when new things are added (otherwise, it's ok to keep things in memory)
            loaded_images_page_numbers = tuple(self._dict_page_num_to_image.keys())
            for p in loaded_images_page_numbers:
                if abs(p - page_num) > NUM_PAGE_IMAGE_RANGE_TO_KEEP:
                    self._delete_page_from_canvas(p)

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

        self._load_neighbor_pages_if_there_is_empty_space_on_visible_area()

    def _click_on_a_bookmark(self, _):
        bookmark_clicked = self._text_bookmarks.get("current linestart", "current lineend")
        if ALLOW_DEBUGGING:
            print("Clicked bookmark:", bookmark_clicked)

        try:
            page_num = int(str.rsplit(bookmark_clicked, " ", 1)[-1])
            # max-split argument in the above call to rsplit is 1, it means only one breaking point i.e.
            # the whole string is split into two parts at first space character from the right
        except ValueError:
            print("The page number extracted is not a valid integer")
            return

        if ALLOW_DEBUGGING:
            print("Page num:", page_num)

        self._load_page(page_num)

    def _event_handler_for_arrow_annotation(self, event):
        if ALLOW_DEBUGGING:
            print("Left click on canvas")
        canvas_x = self._canvas.canvasx(event.x)
        canvas_y = self._canvas.canvasy(event.y)

        # there should be an underlying page to add an arrow annotation
        closest = self._canvas.find_closest(canvas_x, canvas_y)  # either empty, or a singleton with closest object id
        if len(closest) == 0:
            if ALLOW_DEBUGGING:
                print("No page exists at this position, so, annotation can't be added")
            return

        obj_id = closest[0]
        tags_of_this_object = self._canvas.gettags(obj_id)
        if ALLOW_DEBUGGING:
            print("Underlying object:", obj_id, "with tags:", tags_of_this_object)
        if TAG_PAGE_IMAGE not in tags_of_this_object:
            if ALLOW_DEBUGGING:
                print("The underlying object is not a page image. So, annotation can't be added")
            return

        # the object given by obj_id is a page image object
        page_bbox = self._canvas.bbox(obj_id)
        x1, y1, _, _ = page_bbox
        dx = canvas_x - x1
        dy = canvas_y - y1
        page_num = self._dict_canvas_id_to_page_num[obj_id]
        self._add_arrow_annotation(dx, dy, page_num)

    def _add_arrow_annotation(self, dx, dy, page_num):
        # print(dx, dy, page_num)
        page_bbox = self._canvas.bbox(self._dict_page_num_to_canvas_id[page_num])
        x1, y1, _, _ = page_bbox

        annotation_id = self._canvas.create_line(
            x1 + dx, y1 + dy, x1 + dx - ANNOTATION_ARROW_LENGTH, y1 + dy,
            arrow=tk.FIRST, arrowshape=ANNOTATION_ARROW_SHAPE,
            fill=ANNOTATION_ARROW_COLOR, width=ANNOTATION_ARROW_WIDTH,
            tags=(TAG_OBJECT, TAG_ANNOTATION, TAG_ARROW, get_page_num_tag(page_num),
                  get_tag_annotation_arrow_deltas(dx, dy))
        )
        if ALLOW_DEBUGGING:
            print("Arrow annotation added with id:", annotation_id, "tags:", self._canvas.gettags(annotation_id))

    def _event_handler_for_remove_annotation(self, event):
        if ALLOW_DEBUGGING:
            print("Right click on canvas")
        canvas_x = self._canvas.canvasx(event.x)
        canvas_y = self._canvas.canvasy(event.y)
        closest = self._canvas.find_closest(canvas_x, canvas_y)
        if len(closest) == 0:
            if ALLOW_DEBUGGING:
                print("No close objects at this point")
            return
        obj_id = closest[0]  # closest is a singleton list, containing the id of an object on the canvas
        if ALLOW_DEBUGGING:
            print(f"Found object with {obj_id} near ({canvas_x}, {canvas_y})"
                  f" with tags {self._canvas.gettags(obj_id)}")
        if TAG_ANNOTATION in self._canvas.gettags(obj_id):
            self._canvas.delete(obj_id)
            if ALLOW_DEBUGGING:
                print("Deleted the annotation")

    def _delete_page_from_canvas(self, page_num):
        if ALLOW_DEBUGGING:
            print("Delete page", page_num, "from canvas")

        self._save_annotations_back_to_the_dict_for_page(page_num)

        page_obj_id = self._dict_page_num_to_canvas_id[page_num]

        self._canvas.delete(page_obj_id)
        self._dict_page_num_to_image.pop(page_num)
        self._dict_page_num_to_canvas_id.pop(page_num)
        self._dict_canvas_id_to_page_num.pop(page_obj_id)

    def _save_annotations_back_to_the_dict_for_page(self, page_num):
        if ALLOW_DEBUGGING:
            print("Save annotations back to the dict for page", page_num)

        # requires that the page still be present on canvas
        objects_with_page_num_tag = self._canvas.find_withtag(get_page_num_tag(page_num))

        if ALLOW_DEBUGGING:
            print(len(objects_with_page_num_tag), "objects found for this page")

        self._annotations[str(page_num)] = []  # string key because, this is saved to a json file, and,
        # json converts int keys to string keys while saving

        # page bbox is used to store the annotations by relative position to the page
        page_bbox = self._canvas.bbox(self._dict_page_num_to_canvas_id[page_num])

        for o in objects_with_page_num_tag:
            tags = self._canvas.gettags(o)
            bbox = self._canvas.bbox(o)

            if ALLOW_DEBUGGING:
                print("Object with id:", o, "Tags:", tags, "Bbox:", bbox)

            x1, y1, x2, y2 = bbox

            if TAG_ARROW in tags:
                tag_annotation_arrow_deltas = None
                for t in tags:
                    if t.startswith(PREFIX_TAG_ANNOTATION_ARROW_DELTAS):
                        tag_annotation_arrow_deltas = t
                        break
                if tag_annotation_arrow_deltas is None:
                    print("Critical warning: Tag annotation arrow deltas is None."
                          " It ir required to get dx and dy for arrow annotations."
                          " Otherwise, the arrows keep moving to the right everytime the book is reopened.")
                    self._annotations[str(page_num)].append([x2, (y1 + y2) // 2, TAG_ARROW])
                else:
                    dx, dy = get_dx_dy_from_tag_annotation_arrow_deltas(tag_annotation_arrow_deltas)
                    self._annotations[str(page_num)].append([page_bbox[0] + dx, page_bbox[1] + dy, TAG_ARROW])
                    # note that page_bbox[0] and page_bbox[1] are added above, because,
                    # at the end of the function, all x and y are made relative to the page
            elif TAG_TEXT in tags:
                self._annotations[str(page_num)].append([(x1 + x2) // 2, y1, TAG_TEXT,  # using default anchor position
                                                         self._canvas.itemcget(o, 'text')])
                # note: using itemcget, other options can also be saved

        # make all x and y relative to the page
        x1, y1, x2, y2 = page_bbox
        for i in range(len(self._annotations[str(page_num)])):
            x, y = self._annotations[str(page_num)][i][:2]
            self._annotations[str(page_num)][i][0] = x - x1
            self._annotations[str(page_num)][i][1] = y - y1

    def _draw_annotations_in_dict_on_to_canvas_for_page(self, page_num):
        if ALLOW_DEBUGGING:
            print("Draw annotations in dict on to canvas for page")

        if str(page_num) not in self._annotations:
            if ALLOW_DEBUGGING:
                print("No annotations exist for page", page_num)
            return

        page_obj = self._dict_page_num_to_canvas_id[page_num]
        page_bbox = self._canvas.bbox(page_obj)
        x1, y1, x2, y2 = page_bbox

        for a in self._annotations[str(page_num)]:
            dx, dy = a[:2]
            ann_type = a[2]
            if ann_type == TAG_ARROW:
                self._add_arrow_annotation(dx, dy, page_num)
            elif ann_type == TAG_TEXT:
                text = a[3]
                self._event_handler_for_text_annotation(namedtuple("tempEvent", ["x", "y"])(x1 + dx, y1 + dy), text)

    def _save_annotations(self):
        if ALLOW_DEBUGGING:
            print("Save annotations")

        # first, save annotations of page images being displayed on canvas back to dict
        for p in self._dict_page_num_to_image:
            self._save_annotations_back_to_the_dict_for_page(p)

        metadata_folder = get_metadata_folder(self._gui_settings[KEY_CURRENTLY_OPENED_BOOK])
        annotations_file_path = get_annotations_file_path(metadata_folder)
        try:
            with open(annotations_file_path, 'w') as f:
                f.write(json.dumps(self._annotations))
        except IOError:
            print("Couldn't write to annotations file:", annotations_file_path)

    def _read_annotations(self):
        if ALLOW_DEBUGGING:
            print("Read annotations")

        metadata_folder = get_metadata_folder(self._gui_settings[KEY_CURRENTLY_OPENED_BOOK])
        annotations_file_path = get_annotations_file_path(metadata_folder)
        try:
            with open(annotations_file_path) as f:
                self._annotations = json.loads(f.read())
            if ALLOW_DEBUGGING:
                print("Annotations:", self._annotations)
        except IOError:
            print("Couldn't write to annotations file:", annotations_file_path)
        except json.JSONDecodeError:
            print("Bad json in", annotations_file_path)

    def _event_handler_for_text_annotation(
            self, event,
            text=None, anchor=ANNOTATION_TEXT_DEFAULT_ANCHOR, justify=ANNOTATION_TEXT_DEFAULT_JUSTIFY):
        if ALLOW_DEBUGGING:
            print("Middle click on canvas")

        canvas_x = self._canvas.canvasx(event.x)
        canvas_y = self._canvas.canvasy(event.y)

        # there should be an underlying page to add a text annotation
        closest = self._canvas.find_closest(canvas_x, canvas_y)  # either empty, or a singleton with closest object id
        if len(closest) == 0:
            if ALLOW_DEBUGGING:
                print("No page exists at this position, so, annotation can't be added")
            return

        obj_id = closest[0]
        tags_of_this_object = self._canvas.gettags(obj_id)
        if ALLOW_DEBUGGING:
            print(obj_id, tags_of_this_object)
        if TAG_PAGE_IMAGE not in tags_of_this_object:
            if ALLOW_DEBUGGING:
                print("The underlying object is not a page image. So, annotation can't be added")
            return

        page_num_tag = None
        for t in tags_of_this_object:
            if str.startswith(t, PREFIX_TAG_PAGE_NUM):
                page_num_tag = t
                break

        if text is None:

            self._unbind_all_hot_keys()  # otherwise pressing any hot keys in the text dialog will run their handlers
            text = ask_text("Text Annotation", "Please enter string:")
            self._bind_all_hot_keys()

            if text is None:
                if ALLOW_DEBUGGING:
                    print("Text annotation cancelled")
                return

            text = text.strip()
            if text == "":
                if ALLOW_DEBUGGING:
                    print("Text annotation cancelled")
                return

            # todo other things like justify, anchor, movement can be asked too
            # note: anchor and movement can be used up and need not be saved, because,
            # bbox along with default anchor will suffice

        annotation_id = self._canvas.create_text(
            canvas_x, canvas_y,
            text=text, fill=ANNOTATION_TEXT_COLOR, anchor=anchor, justify=justify,
            tags=(TAG_OBJECT, TAG_ANNOTATION, TAG_TEXT, page_num_tag)
        )
        if ALLOW_DEBUGGING:
            print("Text annotation added with id:", annotation_id, "tags:", self._canvas.gettags(annotation_id))

    def _bind_all_hot_keys(self):
        if ALLOW_DEBUGGING:
            print("Bind all hot keys")
        try:
            self._hot_key_bindings = {"o": self._open_a_book, "r": self._open_a_recent_book,
                                      "Down": self._down_or_up_arrow, "Up": self._down_or_up_arrow,
                                      "j": self._jump_to_a_page, "h": self._show_help_text}
        except AttributeError:
            print("Error: Some functions mentioned for key bindings in self._hot_key_bindings do not exist."
                  " No key bindings will be made.")
            self._hot_key_bindings = {}
        for k in self._hot_key_bindings:
            self.bind_all(f"<Key-{k}>", self._hot_key_bindings[k])

    def _unbind_all_hot_keys(self):
        if ALLOW_DEBUGGING:
            print("Unbind all hot keys")
        for k in self._hot_key_bindings:
            self.unbind_all(f"<Key-{k}>")

    def _save_book_settings(self):
        if ALLOW_DEBUGGING:
            print("Save book settings")

        canvas_width = self._canvas.winfo_width()
        canvas_height = self._canvas.winfo_height()

        book_settings = {KEY_CURRENTLY_VISIBLE_PAGES: []}

        objects_in_visible_region = self._canvas.find_overlapping(0, 0, canvas_width, canvas_height)
        for o in objects_in_visible_region:
            tags = self._canvas.gettags(o)
            if ALLOW_DEBUGGING:
                print("Object", o, "in visible region with tags", tags)
            if TAG_PAGE_IMAGE not in tags:
                continue
            page_num = self._dict_canvas_id_to_page_num.get(o)
            bbox = self._canvas.bbox(o)
            x1, y1, _, _ = bbox
            book_settings[KEY_CURRENTLY_VISIBLE_PAGES].append([page_num, x1, y1])

        if ALLOW_DEBUGGING:
            print("Book settings to be saved:", book_settings)

        metadata_folder = get_metadata_folder(self._gui_settings[KEY_CURRENTLY_OPENED_BOOK])
        book_settings_file_path = get_book_settings_file_path(metadata_folder)
        try:
            with open(book_settings_file_path, 'w') as f:
                f.write(json.dumps(book_settings))
        except IOError:
            print("Error: Couldn't write to book settings file:", book_settings_file_path)

    def _down_or_up_arrow(self, event):
        if ALLOW_DEBUGGING:
            print("Down or Up arrow hot key event")

        """
        note: for the below discussion: annotations are ordered by sorting with x1 and then by y1 (of their bbox) 
        there are two possibilities: there is a highlighted annotation, there isn't
        if there isn't a highlighted annotation:
            again two possibilities: there are annotations on canvas, there aren't
            if there are annotations on canvas:
                first, try to choose the top-most among the visible annotations
                if can't then:
                if direction is up:
                    try to choose the ones beyond top of the visible portion
                    if still can't, need to load a new page (lesser page number) with annotations
                      (--check that volatile things like annotations are saved while loading the new page) 
                    and choose the bottom most annotation in it
                else i.e. direction is down:
                    try to choose the ones beyond the bottom of the visible portion
                    if still can't, need to load a new page (higher page number) with annotations
                      (--check that volatile things like annotations are saved while loading the new page)
                    and choose the top most annotation in it
            else:  i.e. there are NO annotations on canvas:
                if direction is up:
                    need to load a new page (lesser page number) with annotations 
                    and choose the bottom most annotation in it
                else i.e. direction is down:
                    need to load a new page (higher page number) with annotations
                    and choose the top most annotation in it
        else:  i.e. there IS a highlighted annotation 
            two possibilities: it is in the visible region, it is not in the visible region  (happens if scrolled)
            if it is NOT in the visible region:
                bring it into view
            else i.e. it is in the visible region:
                if direction is up:
                    try to go to an annotation above the current highlighted annotation
                    if can't, need to load a new page (lesser page number) with annotations
                      (--check that volatile things like annotations are saved while loading the new page) 
                    and choose the bottom most annotation in it
                else i.e. direction is down:
                    try to go to an annotation below the current highlighted annotation
                    if still can't, need to load a new page (higher page number) with annotations
                      (--check that volatile things like annotations are saved while loading the new page)
                    and choose the top most annotation in it
        """

        highlighted_annotations = self._canvas.find_withtag(TAG_ANNOTATION_HIGHLIGHTED)
        # there should either be none or one

        if ALLOW_DEBUGGING:
            print(f"Highlighted annotations:", highlighted_annotations)

        annotations_on_canvas = self._canvas.find_withtag(TAG_ANNOTATION)
        annotations_on_canvas_with_their_bbox = list(zip(
            annotations_on_canvas, map(lambda x: self._canvas.bbox(x), annotations_on_canvas)
        ))
        # sort by x1 in bbox
        annotations_on_canvas_with_their_bbox.sort(key=lambda x: x[1][0])  # x[1] is bbox; bbox[0] is x1
        # then, sort by y1 in bbox (so that sort by y1 is the most recent)
        annotations_on_canvas_with_their_bbox.sort(key=lambda x: x[1][1])  # x[1] is bbox; bbox[1] is y1

        direction_is_down = (event.keysym == "Down")
        canvas_height = self._canvas.winfo_height()

        annotation_to_highlight = None

        if len(highlighted_annotations) == 0:  # there isn't a highlighted annotation
            if len(annotations_on_canvas) > 0:  # there are annotations on canvas
                # try to choose the top-most visible annotation if any
                for a, bbox in annotations_on_canvas_with_their_bbox:
                    y1 = bbox[1]
                    if 0 <= y1 < canvas_height:
                        annotation_to_highlight = a
                        break
                if annotation_to_highlight is None:
                    if direction_is_down:
                        # try to choose the ones beyond the bottom of the visible portion
                        for a, bbox in annotations_on_canvas_with_their_bbox:
                            y1 = bbox[1]
                            if y1 > canvas_height:
                                annotation_to_highlight = a
                                break
                        if annotation_to_highlight is None:
                            # (handled at bottom)
                            # need to load a new page (higher page number) with annotations
                            # (--check that volatile things like annotations are saved while loading the new page)
                            # and choose the top most annotation in it
                            pass
                    else:
                        # try to choose the ones beyond top of the visible portion
                        for a, bbox in reversed(annotations_on_canvas_with_their_bbox):
                            # reversed because, we want to get bottom-most
                            y1 = bbox[1]
                            if y1 < 0:
                                annotation_to_highlight = a
                                break
                        if annotation_to_highlight is None:
                            # (handled at bottom)
                            # need to load a new page (lesser page number) with annotations
                            # (--check that volatile things like annotations are saved while loading the new page)
                            # and choose the bottom most annotation in it
                            pass
            else:  # there aren't any annotations on canvas
                if direction_is_down:
                    # (handled at bottom)
                    # need to load a new page (higher page number) with annotations
                    # and choose the top most annotation in it
                    pass
                else:
                    # (handled at bottom)
                    # need to load a new page (lesser page number) with annotations
                    # and choose the bottom most annotation in it
                    pass
        elif len(highlighted_annotations) == 1:
            current_highlighted_annotation = highlighted_annotations[0]
            _, y1_current_highlighted_annotation, _, y2_current_highlighted_annotation =\
                self._canvas.bbox(current_highlighted_annotation)
            if y2_current_highlighted_annotation < 0 or y1_current_highlighted_annotation >= canvas_height:
                # highlighted annotation is outside visible region
                annotation_to_highlight = current_highlighted_annotation
                pass
            else:  # highlighted annotation IS in the visible region
                if direction_is_down:
                    # try to go to an annotation below the current highlighted annotation
                    for i in range(len(annotations_on_canvas_with_their_bbox)):
                        a = annotations_on_canvas_with_their_bbox[i][0]
                        if a == current_highlighted_annotation:
                            if (i + 1) < len(annotations_on_canvas_with_their_bbox):
                                annotation_to_highlight = annotations_on_canvas_with_their_bbox[i+1][0]
                            break
                    if annotation_to_highlight is None:
                        # (handled at bottom)
                        # need to load a new page (higher page number) with annotations
                        # (--check that volatile things like annotations are saved while loading the new page)
                        # and choose the top most annotation in it
                        pass
                else:
                    # try to go to an annotation above the current highlighted annotation
                    for i in range(len(annotations_on_canvas_with_their_bbox)):
                        a = annotations_on_canvas_with_their_bbox[i][0]
                        if a == current_highlighted_annotation:
                            if i > 0:
                                annotation_to_highlight = annotations_on_canvas_with_their_bbox[i-1][0]
                            break
                    if annotation_to_highlight is None:
                        # (handled at bottom)
                        # need to load a new page (lesser page number) with annotations
                        # (--check that volatile things like annotations are saved while loading the new page)
                        # and choose the bottom most annotation in it
                        pass

        else:  # error there can't be more than 1 highlighted annotations
            print("Error: There can't be more than 1 highlighted annotations. Their details:")
            for a in highlighted_annotations:
                print("Object", a, "with tags:", self._canvas.gettags(a))
            # todo: un-highlight all annotations
            return

        if annotation_to_highlight is None:

            # need to load new page with annotations
            sorted_page_nums_with_annotations = sorted(
                map(int, self._annotations.keys()),
                reverse=(not direction_is_down))  # if direction is up, we get descending order

            page_to_load = None
            if direction_is_down:
                highest_page_num_on_canvas = max(self._dict_page_num_to_image.keys())
                for p in sorted_page_nums_with_annotations:
                    if p > highest_page_num_on_canvas and len(self._annotations[str(p)]) > 0:
                        page_to_load = p
                        break
            else:  # direction is up
                lowest_page_num_on_canvas = min(self._dict_page_num_to_image.keys())
                for p in sorted_page_nums_with_annotations:
                    if p < lowest_page_num_on_canvas and len(self._annotations[str(p)]) > 0:
                        page_to_load = p
                        break

            if page_to_load is None:
                if ALLOW_DEBUGGING:
                    print("No more annotations in this book")
                return

            self._load_page(page_to_load)  # note that this will also save any volatile annotations and clears canvas
            # and also draws annotations

            annotations_on_canvas = self._canvas.find_withtag(TAG_ANNOTATION)
            annotations_on_canvas_with_their_bbox = list(zip(
                annotations_on_canvas, map(lambda x: self._canvas.bbox(x), annotations_on_canvas)
            ))
            annotations_on_canvas_with_their_bbox.sort(key=lambda x: x[1][0])  # x[1] is bbox, x[1][0] is x1
            annotations_on_canvas_with_their_bbox.sort(key=lambda x: x[1][1])  # x[1] is bbox, x[1][1] is y1

            # now depending on the direction, scroll to the annotation
            if direction_is_down:  # highlight top most
                annotation_to_highlight = annotations_on_canvas_with_their_bbox[0][0]
            else:  # highlight bottom most
                annotation_to_highlight = annotations_on_canvas_with_their_bbox[-1][0]

        if annotation_to_highlight is None:
            print("Error: Annotation to highlight is None. This shouldn't happen.")
            return

        self._canvas.delete(TAG_BBOX)
        try:
            self._canvas.dtag(highlighted_annotations[0], TAG_ANNOTATION_HIGHLIGHTED)
        except IndexError:  # highlighted_annotations is either empty or singleton
            if ALLOW_DEBUGGING:
                print("No highlighted annotation exists yet to remove the tag from")
            pass

        self._canvas.addtag_withtag(TAG_ANNOTATION_HIGHLIGHTED, annotation_to_highlight)
        x1, y1, x2, y2 = self._canvas.bbox(annotation_to_highlight)
        x1 -= ANNOTATION_HIGHLIGHT_BBOX_PADDING
        y1 -= ANNOTATION_HIGHLIGHT_BBOX_PADDING
        x2 += ANNOTATION_HIGHLIGHT_BBOX_PADDING
        y2 += ANNOTATION_HIGHLIGHT_BBOX_PADDING
        self._canvas.create_rectangle(x1, y1, x2, y2, outline=ANNOTATION_HIGHLIGHT_COLOR,
                                      width=ANNOTATION_HIGHLIGHT_WIDTH,
                                      tags=(TAG_OBJECT, TAG_BBOX))
        if y1 > canvas_height or y2 < 0:  # the highlighted annotation is out of sight
            if direction_is_down:
                # bring to the top: it's y1 should be at top highlighted-padding
                dy = ANNOTATION_HIGHLIGHTED_BRING_TO_SIGHT_PADDING - y1
            else:  # direction is up
                # bring to the bottom: it's y2 should be at the bottom highlighted-padding
                dy = canvas_height - ANNOTATION_HIGHLIGHTED_BRING_TO_SIGHT_PADDING - y2
            self._canvas.move(TAG_OBJECT, 0, dy)
            self._load_neighbor_pages_if_there_is_empty_space_on_visible_area()

    def _load_neighbor_pages_if_there_is_empty_space_on_visible_area(self):
        if ALLOW_DEBUGGING:
            print("Load neighbor pages if there is empty space on visible area")

        # canvas_width = self._canvas.winfo_width()
        canvas_height = self._canvas.winfo_height()

        existing_pages_on_canvas = sorted(self._dict_page_num_to_image.keys())
        if len(existing_pages_on_canvas) == 0:
            if ALLOW_DEBUGGING:
                print("There are no pages on canvas")
            return 

        min_page = existing_pages_on_canvas[0]
        max_page = existing_pages_on_canvas[-1]

        min_page_bbox = self._canvas.bbox(self._dict_page_num_to_canvas_id[min_page])
        max_page_bbox = self._canvas.bbox(self._dict_page_num_to_canvas_id[max_page])

        _, min_page_top, _, _ = min_page_bbox
        _, _, _, max_page_bottom = max_page_bbox

        if min_page_top > PIXELS_BETWEEN_PAGES:
            if ALLOW_DEBUGGING:
                print("Empty space detected at top. Loading a previous neighbor page: Page", min_page - 1)
            self._load_page(min_page - 1, delete_all_objects=False, y=min_page_top-PIXELS_BETWEEN_PAGES, anchor="sw")
        else:
            if ALLOW_DEBUGGING:
                print("No empty space detected at top to load a neighbor page")

        if max_page_bottom < canvas_height - PIXELS_BETWEEN_PAGES:
            if ALLOW_DEBUGGING:
                print("Empty space detected at bottom. Loading a next page: Page", max_page + 1)
            self._load_page(max_page + 1, delete_all_objects=False, y=max_page_bottom+PIXELS_BETWEEN_PAGES)
        else:
            if ALLOW_DEBUGGING:
                print("No empty space detected at bottom to load a next neighbor page")

        # note that this function may be called inside _load_page itself, they will call each other recursively
        # until the entire visible region is filled (in case of short page heights), however, an infinite loop may
        # occur if the combined page heights along with the spaces between pages for the maximum number of pages
        # allowed to load (given by NUM_PAGE_IMAGE_RANGE_TO_KEEP), on a whole, is shorter than the visible region

    def _jump_to_a_page(self, _event):
        if ALLOW_DEBUGGING:
            print("Jump to a page")

        result = simpledialog.askinteger("Jump to", "Please enter a page number to jump to:")
        if ALLOW_DEBUGGING:
            print("Result:", result)

        if result is None:
            if ALLOW_DEBUGGING:
                print("Jump to a page cancelled")
            return

        self._load_page(result)

    @staticmethod
    def _show_help_text(_event):
        help_text =\
            "1. Left click to add arrow annotation\n" \
            "2. Middle click to add a text annotation\n" \
            "3. Right click on an existing annotation to remove it\n" \
            "4. Use 'Up' and 'Down' keys to navigate through annotations\n" \
            "Hot keys:\n" \
            "5. Click 'o' to open a new book\n" \
            "6. Click 'r' to choose from recently opened books\n" \
            "7. Click 'j' to jump to a page by page number"
        messagebox.showinfo("Help", help_text)


def main():

    # parser = argparse.ArgumentParser()

    # args = parser.parse_args()

    PdfViewer().mainloop()

    return


if __name__ == '__main__':
    main()
