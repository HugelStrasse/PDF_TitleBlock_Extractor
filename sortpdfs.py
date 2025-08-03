import os
import shutil
import fitz  # PyMuPDF
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Common page sizes in points (1 pt = 1/72 inch)
PAGE_SIZES = {
    'A0': (2384, 3370),
    'A1': (1684, 2384),
    'A2': (1191, 1684),
    'A3': (842, 1191),
    'A4': (595, 842),
}


def main(source_dir: str, output_dir: str):
    """
    Main function to walk through a directory of PDFs and DWGs
    and sort PDFs based on size, orientation, and page count.
    """
    if not os.path.isdir(source_dir):
        logging.error(f"Source directory does not exist: {source_dir}")
        return

    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(source_dir):
        filepath = os.path.join(source_dir, filename)

        if os.path.isfile(filepath):
            ext = os.path.splitext(filename)[1].lower()

            if ext == '.pdf':
                try:
                    process_pdf(filepath, output_dir)
                except Exception as e:
                    logging.error(f"Failed to process {filename}: {e}")
            elif ext == '.dwg':
                logging.info(f"Skipping DWG (not supported yet): {filename}")
            else:
                logging.warning(f"Unsupported file type: {filename}")


def process_pdf(filepath: str, output_base: str):
    """
    Process a PDF to determine its page size, orientation, and page count.
    Moves it to the appropriate subfolder.
    """
    doc = fitz.open(filepath)
    page_count = doc.page_count

    first_page = doc.load_page(0)
    width, height = first_page.rect.width, first_page.rect.height

    page_size = match_page_size(width, height)
    orientation = 'LS' if width > height else 'PO'
    count_label = 'Single' if page_count == 1 else 'Multi'

    folder_name = f"{page_size}_{orientation}_{count_label}"
    destination_folder = os.path.join(output_base, folder_name)

    os.makedirs(destination_folder, exist_ok=True)

    shutil.copy(filepath, os.path.join(destination_folder, os.path.basename(filepath)))
    logging.info(f"Moved '{os.path.basename(filepath)}' → {folder_name}")


def match_page_size(width: float, height: float) -> str:
    """
    Match the page dimensions to the nearest standard A-size.
    Uses tolerance to handle minor variation in measurement.
    """
    tolerance = 10  # pts

    for size, (w, h) in PAGE_SIZES.items():
        if (abs(width - w) < tolerance and abs(height - h) < tolerance) or \
           (abs(width - h) < tolerance and abs(height - w) < tolerance):
            return size

    logging.warning(f"Unknown page size: {int(width)} x {int(height)}")
    return "Unknown"


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Sort PDFs by page size, orientation, and count.")
    parser.add_argument("source", help="Directory containing PDFs to process")
    parser.add_argument("output", help="Directory to move sorted PDFs into")

    args = parser.parse_args()
    main(args.source, args.output)
