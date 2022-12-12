# import argparse
import sys
import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import simpledialog
from tkinter import scrolledtext
import json
from PIL import Image, ImageTk
from collections import namedtuple  # for sending a temp Event type objects with just required data members

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


KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS = set()
KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS.update(map(lambda x: f"F{x}", range(1, 12+1)))  # function keys
if ALLOW_DEBUGGING:
    print("Keys that will be further processed in text bookmarks:",
          KEY_PRESSES_TO_ALLOW_FURTHER_HANDLING_IN_TEXT_BOOKMARKS)

TAG_OBJECT = "obj"
TAG_PAGE_IMAGE = "pg-img"
PREFIX_TAG_PAGE_NUM = "pg-num"  # this is used in tag.startswith, so, this must be unique prefix

TAG_BOOKMARK = "bm"


NUM_PIXELS_TO_SCROLL = 40
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

        return self.entry

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

        self._canvas.bind("<Button-1>", self._left_click_on_canvas)
        self._canvas.bind("<Button-3>", self._right_click_on_canvas)
        self._canvas.bind("<Button-2>", self._middle_click_in_canvas)

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

        # save the annotations of the current book
        if self._gui_settings.get(KEY_CURRENTLY_OPENED_BOOK, None) is not None:
            self._save_annotations()
            self._save_book_settings()

        self._gui_settings[KEY_CURRENTLY_OPENED_BOOK] = result

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
            self._canvas.delete(TAG_OBJECT)  # delete all objects on canvas
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

        # now, if a page is going beyond boundaries, then next / previous page has to be shown for continuous scroll
        # if scrolling up, consider page at the top most (of the screen), if scrolling down, the bottom most
        page_to_consider = None
        page_obj = None
        for v in objects_in_scroll_distance:
            page_num = self._dict_canvas_id_to_page_num.get(v, None)
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
                    print("Page scrolled up. Show next page i.e. Page", page_to_consider + 1)
                    print("Existing pages on canvas:")
                    for p in sorted(self._dict_page_num_to_canvas_id.keys()):
                        canvas_id = self._dict_page_num_to_canvas_id[p]
                        print(f"Page-{p}:"
                              f" Tags: {self._canvas.gettags(canvas_id)}"
                              f" Bbox: {self._canvas.bbox(canvas_id)}")

                self._load_page(page_to_consider + 1, delete_all_objects=False, y=y2 + PIXELS_BETWEEN_PAGES)
            else:
                if ALLOW_DEBUGGING:
                    print("Page hasn't scrolled up enough to reveal next page")

        else:  # scrolling up  (event.delta > 0)
            _, y1, _, _ = self._canvas.bbox(page_obj)

            if ALLOW_DEBUGGING:
                print("The top most y coordinate of the page:", y1)

            if y1 > PIXELS_BETWEEN_PAGES:
                if ALLOW_DEBUGGING:
                    print("Page scrolled down. Show previous page i.e. Page", page_to_consider - 1)
                    print("Existing pages on canvas:")
                    for p in sorted(self._dict_page_num_to_canvas_id.keys()):
                        canvas_id = self._dict_page_num_to_canvas_id[p]
                        print(f"Page-{p}:"
                              f" Tags: {self._canvas.gettags(canvas_id)}"
                              f" Bbox: {self._canvas.bbox(canvas_id)}")
                self._load_page(page_to_consider - 1, delete_all_objects=False, y=y1 - PIXELS_BETWEEN_PAGES,
                                anchor="sw")
            else:
                if ALLOW_DEBUGGING:
                    print("Page hasn't scrolled down enough to reveal previous page")

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

    def _left_click_on_canvas(self, event):
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

        page_num_tag = None
        for t in tags_of_this_object:
            if str.startswith(t, PREFIX_TAG_PAGE_NUM):
                page_num_tag = t
                break

        annotation_id = self._canvas.create_line(
            canvas_x, canvas_y, canvas_x - ANNOTATION_ARROW_LENGTH, canvas_y,
            arrow=tk.FIRST, arrowshape=ANNOTATION_ARROW_SHAPE,
            fill=ANNOTATION_ARROW_COLOR, width=ANNOTATION_ARROW_WIDTH,
            tags=(TAG_OBJECT, TAG_ANNOTATION, TAG_ARROW, page_num_tag)
        )
        if ALLOW_DEBUGGING:
            print("Arrow annotation added with id:", annotation_id, "tags:", self._canvas.gettags(annotation_id))

    def _right_click_on_canvas(self, event):
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
        page_bbox = None  # page bbox is used to store the annotations by relative position to the page

        for o in objects_with_page_num_tag:
            tags = self._canvas.gettags(o)
            bbox = self._canvas.bbox(o)

            if ALLOW_DEBUGGING:
                print("Object with id:", o, "Tags:", tags, "Bbox:", bbox)

            x1, y1, x2, y2 = bbox

            if TAG_ARROW in tags:
                self._annotations[str(page_num)].append([x2, (y1 + y2) // 2, TAG_ARROW])
            elif TAG_TEXT in tags:
                self._annotations[str(page_num)].append([(x1 + x2) // 2, y1, TAG_TEXT,  # using default anchor position
                                                         self._canvas.itemcget(o, 'text')])
                # note: using itemcget, other options can also be saved
            elif TAG_PAGE_IMAGE in tags:  # this is the page
                page_bbox = bbox

        # make all x and y relative to the page
        if page_bbox is None:
            print("Error: In save annotations back to the dict for page", page_num, "no page image exists on canvas")
            return
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
                self._left_click_on_canvas(namedtuple("tempEvent", ["x", "y"])(x1 + dx, y1 + dy))
            elif ann_type == TAG_TEXT:
                text = a[3]
                self._middle_click_in_canvas(namedtuple("tempEvent", ["x", "y"])(x1 + dx, y1 + dy), text)

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

    def _middle_click_in_canvas(
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
            self._hot_key_bindings = {"o": self._open_a_book, "r": self._open_a_recent_book}
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


def main():

    # parser = argparse.ArgumentParser()

    # args = parser.parse_args()

    PdfViewer().mainloop()

    return


if __name__ == '__main__':
    main()
