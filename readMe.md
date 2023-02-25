## Image pdf viewer:

* This is not a pdf viewer.
But an image viewer for pdf files which are converted to images using `pdftopng` of xpdf command line tools.
* It's main use is **annotations**, which are saved automatically upon closing the current pdf book, or, opening a new one. 
  Also, we can cycle through the annotations easily.
  

## A gif showing the Image pdf viewer in action:

The following gif shows Image pdf viewer displaying a book.
It shows scrolling, adding arrow and text annotations, and cycling through the annotations.
Book-Credit: The book is printed from wikipedia page on Black hole.

![Showing image pdf viewer in action](extras/black-hole-wiki-book.gif)
  
## About Image pdf viewer, in a nutshell:
This is a python Tkinter GUI. Once a pdf file is converted into png images using `pdftopng` of xpdf command line tools, and stored in a directory,
this program can then be used to view the images just like a pdf file. We can add annotations like arrows and texts.
We can cycle through the annotations using up and down arrow keys.

## Requirements:
* [PIL](https://pypi.org/project/Pillow/) for displaying png images on Tkinter's Canvas.
* [PyPDF2](https://pypdf2.readthedocs.io/en/3.0.0/user/installation.html) for retrieving bookmarks of a pdf file. Used in `get_bookmarks.py`.
* [xpdf command line tools](https://www.xpdfreader.com/download.html) to convert pdf files to png images.

## How to use:

### Note: Preparing a pdf to use with this program may seem a bit tedious, but, it is a one time task per pdf file. And in future, this will be automated.

1. For a pdf file that we want to use with this, create an empty directory, preferably with the same name as the pdf file, for the images to be stored in.
   Please note that this folder will only have two things inside it:
   the png images which we will create (from the pdf) in the next step,
   and a sub-directory with a specific name which we will create in the step after.
2. Using `pdftopng` of xpdf command line tools, convert the pdf into images and save them in the above created directory.
   
   ***Extra step: Renaming the generated image files***:
   
   Note that `pdftopng` requires a `root` to be specified which it will prepend to the file names which are six-digit-0-filled numbers.
   
   For example, if we choose the root as `a` character, then, the first page will be named `a-000001.png`.
   
   Similarly, if we choose the root as empty character, then, the first page will be named `-000001.png`.
   
   One more example, if we choose root as `hello`, then the first page will be named `hello-000001.png`.
   
   But, the image pdf viewer just needs the image files with their page numbers as their names without the root and the accompanying `-` character, i.e. just `000001.png`.
   
   For this, please use the following script that renames the png files in the current directory. In future, this will be automated when a pdf file is converted to images from the GUI itself.
   
       import os
   
       def renamePNGfilesInCurDir():
           d = os.getcwd()
           l = [x for x in os.listdir(d) if x.lower().endswith(".png")]
           print("There are", len(l), "png files in", d)
           if len(l) == 0:
               print("No renaming required")
               return
           print("Example old name and new name:", l[0], l[0][l[0].rindex('-') + 1:])
           c = input("Do you want to rename? [yes]/no: ").lower().strip()
           if c != "yes" and c != "":
               print("Rename cancelled")
               return
           for i in l:
               os.rename(i, i[i.index('-') + 1:])
           print("Renaming finished")
3. Create a sub directory inside the above created directory and name it `metadata`.
   This is used by the python program to store annotations and book-specific settings.
   Please note that this `metadata` directory is to be manually created. In future, it will be automated.
   Please also note that this `metadata` folder exists beside the created png images i.e. at the same level in the directory hierarchy.
4. Getting bookmarks: Use `get_bookmarks.py` to get bookmarks from the pdf file and save them to a file.
   Please read its help text, by running it with `-h` for further instructions.
   Please note that the bookmarks need to be saved to a file named `bookmarks.json` in the above created `metadata` directory.
____
After all the above steps, preparing the pdf file for use with this program, which is a one-time task, is complete.

The folder structure should look something like this:

    (dir) the_top_most_dir_created_for_the_book 
        | (dir) metadata
            | (file) bookmarks.json
        | (file) 000001.png
        | (file) 000002.png
        | ... (all the png files)
____
5. Run the `main.py` which starts the Tkinter GUI. Press key 'o' (short for open-a-book) which opens a dialog to choose a directory.
   Choose the above created directory that holds the png images (**not** the metadata directory).
6. Now, the book is opened, we can view it just like a pdf file, i.e. with mouse scroll.
   Press key 'h' that shows help dialog to see all the available options.

## Known bugs:
### Note: All the bugs ***will be fixed***, however, workarounds are provided here for the time being.
1. Sometimes, while cycling through annotations, the page is not being shown.
   A workaround is to scroll on the empty canvas a few times and the page will be shown.
2. Text annotations after being created can also be edited.
   When a text annotation is edited, and its anchor is changed,
   the text isn't being anchored at the expected position.
   A workaround is to copy the text of the existing annotation,
   and create a new annotation and paste the copied text while choosing the required anchor position,
   and delete the old annotation. 
3. Sometimes, while cycling through annotations,
   more than one key presses of up/down keys are required to go to previous/next annotation.
   The reason is a bug which somehow duplicates the annotations.
   A workaround is to 'reset', which can be done in any of the following three ways.
   By clicking on a bookmark which opens a new page,
   or, by jumping to another page by pressing 'j' and entering a page number,
   or, by closing and reopening the GUI.

## Future improvements:
1. Getting bookmarks from the pdf file will be made part of the GUI. Currently, it is a separate script `get_bookmarks.py`
2. Converting a pdf file to images will also be made possible from the GUI. xpdf command line tools won't be included, but the user will be asked to point to the `pdftopng` when the feature is used.
3. Ability to move annotations.
4. Add new bookmarks.
5. A settings dialog to change GUI and book settings like widths of widgets, colors of annotations etc.
6. Other types of annotations may be added like box, oval, polygon, etc. Currently text and right-pointing fixed-length arrows are there.
