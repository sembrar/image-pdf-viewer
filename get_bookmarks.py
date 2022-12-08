import argparse
import os
import PyPDF2
import json


# The following function code from: https://stackoverflow.com/a/54363890
def show_tree(bookmark_list, indent=0):
    for item in bookmark_list:
        if isinstance(item, list):
            # recursive call with increased indentation
            show_tree(item, indent + 4)
        else:
            print(" " * indent + item.title)


# The following function is also from the same answer but a little bit modified
def get_bookmarks_list_with_page_numbers(bookmark_list, pdf_reader_obj, indent=0):
    result = []
    for item in bookmark_list:
        if isinstance(item, list):
            # recursive call
            result.extend(get_bookmarks_list_with_page_numbers(item, pdf_reader_obj, indent + 1))
        else:
            result.append([indent, item.title, pdf_reader_obj.getDestinationPageNumber(item)])
    return result


def main():
    parser = argparse.ArgumentParser(
        description=""
        "Writes the bookmarks of a given pdf file to an output json file.\n"
        "The json will have written to it a list of tuples. Each tuple a bookmark.\n"
        "Each tuple has the following data:\n"
        "indent, title, pageNumber\n"
        "where:\n"
        "indent tells it's nested level\n"
        "    0 => top level bookmark\n"
        "    1 => it's inside a 0 level bookmark and so on\n"
        "title and pageNumber are self-explanatory\n"
        "\n"
        "Command line args:\n\n"
        "Required arguments:\n\n"
        "input_file_path: a valid path to a pdf file\n\n"
        "Optional arguments:\n\n"
        "output_json_file_path: \n"
        "    Need not exist, just directory to write to should exist.\n"
        "    If not given, the data is printed, along with the index of each bookmark on the list.\n\n"
        "deltas:\n"
        "    Sometimes, the page number given by PyPDF2 may not match with the actual page number.\n"
        "    For example, xpdf tools when convert pdf to png images start page number at 1.\n"
        "    PyPDF2 may use 0 indexed page numbers.\n"
        "    If such discrepancy is seen, this command-line-arg can be used "
        "to add same or different values to bookmark page numbers.\n"
        "    This must be a string of semi-colon separated sub strings.\n"
        "    Each substring has 3 comma-separated numbers. They are start_index,end_index,delta.\n"
        "    So, the page numbers of all the bookmarks whose indices range "
        "from start_index and end_index (both inclusive) will be added the given value.\n"
        "    If there are multiple such ranges using a semi-colon to separate the substrings.\n"
        "    Example: Suppose there are 100 bookmarks in a book (we can see how many "
        "bookmarks there are by not giving -o command-line-arg, because, "
        "the index of the bookmark in the list is also printed.\n"
        "        Now, if we want to add 1 to all bookmarks, then, deltas command-line-args would be:\n"
        "           0,99,1\n"
        "        If we want to add 1 to first 10 bookmarks and -1 to last 10 bookmarks, then, it would be:\n"
        "           0,9,1;90,99,-1",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_file_path")
    parser.add_argument("-o", "--output_json_file_path")
    parser.add_argument("-d", "--deltas")
    args = parser.parse_args()
    # print(args)

    input_file_path = args.input_file_path

    if (not input_file_path.lower().endswith(".pdf")) or (not os.path.isfile(input_file_path)):
        print("Not a valid pdf file:", input_file_path)
        return

    pdf_reader = PyPDF2.PdfFileReader(input_file_path)
    # show_tree(pdf_reader.getOutlines())
    bookmarks = get_bookmarks_list_with_page_numbers(pdf_reader.getOutlines(), pdf_reader)

    if args.deltas is not None:
        print("Adding deltas:")
        deltas_sub_commands = args.deltas.strip().split(";")
        # print(deltas_sub_commands)
        for sub_command in deltas_sub_commands:
            first_index, last_index, delta_value = tuple(map(int, sub_command.split(",")))
            print(f"Adding {delta_value} to bookmarks of indices in range [{first_index}, {last_index}]")
            for i in range(first_index, last_index + 1):
                bookmarks[i][-1] += delta_value

    for i in range(len(bookmarks)):
        print(f"{i}:", bookmarks[i])

    if args.output_json_file_path is not None:
        output_json_file_path = args.output_json_file_path
        print("Writing bookmarks list to", output_json_file_path)
        if not os.path.isdir(os.path.split(output_json_file_path)[0]):
            print("The directory is not valid")
            return
        if not output_json_file_path.lower().endswith(".json"):
            print("Output file name should end with .json")
            return
        with open(output_json_file_path, 'w') as f:
            f.write(json.dumps(bookmarks, indent=2))


if __name__ == '__main__':
    main()
