# PDF TitleBlock Text Extractor

A Python tool for interactively selecting areas on the first page of PDF files and extracting text from those areas across multiple PDFs. The extracted text is saved to a CSV file for easy analysis.

## Features
- **Graphical Area Selection:** Use a Tkinter GUI to draw rectangles on the first page of a sample PDF and name each area.
- **Bounding Box Saving:** Save and reuse bounding box definitions for future extractions.
- **Batch Extraction:** Extracts text from the defined areas for all PDFs in a selected folder.
- **CSV Export:** Outputs a CSV file with the extracted text for each area and PDF.
- **Progress Bar:** Visual feedback during extraction.

## Requirements
- Python 3.7+
- [pdfplumber](https://github.com/jsvine/pdfplumber)
- [Pillow](https://python-pillow.org/)

Install dependencies with:
```bash
pip install -r requirements.txt
```

## Usage
1. **Run the script:**
   ```bash
   python main.py
   ```
2. **Select the folder** containing your PDF files when prompted.
3. **Draw and name areas** on the first page of the first PDF using the GUI. Click "Save Area" for each region. Click "Finish" when done.
4. The tool will extract text from the defined areas for all PDFs in the folder and save the results to `extracted_text.csv` in the same folder.

- Bounding box definitions are saved as `bounding_boxes.json` for reuse.

## Output Files
- `bounding_boxes.json`: Stores the coordinates and names of selected areas.
- `extracted_text.csv`: Contains the extracted text for each area and PDF.

## Notes
- Only the **first page** of each PDF is processed.
- The tool supports zooming and panning for precise area selection.
- If `bounding_boxes.json` exists, it will be loaded and the GUI will be skipped.

## License

Copyright (c) 2025 Digital Guerrilla

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Acknowledgements
- [pdfplumber](https://github.com/jsvine/pdfplumber)
- [Pillow](https://python-pillow.org/)
- Tkinter (Python standard library)
