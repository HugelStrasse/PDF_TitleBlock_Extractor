import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import fitz  # PyMuPDF
import json
import os
import csv
import glob
import multiprocessing

# === PDF text extraction function for worker ===

def convert_bbox(area, page_height, shrink=0):
    """
    Convert a bbox from PDF (origin bottom-left) to PyMuPDF (origin top-left),
    and optionally shrink it on all sides.

    Args:
        area (tuple): (x0, y0, x1, y1) in PDF coordinates.
        page_height (float): Page height to flip Y coordinates.
        shrink (float): Margin to subtract from all four sides.

    Returns:
        tuple: (x0, y0, x1, y1) ready to pass to fitz.Rect(*coords)
    """
    x0, y0, x1, y1 = area

    # Convert to PyMuPDF coordinate system 
    top =  y1
    bottom = y0
    left = x0
    right = x1

    # Apply shrinking
    if shrink > 0:
        left += shrink
        right -= shrink
        top -= shrink
        bottom += shrink

    return (left, bottom, right, top)


def extract_text_from_pdf(args):
    pdf_path, bbox_dict, debug = args
    row = {'filename': os.path.basename(pdf_path)}
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        for name, coords in bbox_dict.items():
            coords = convert_bbox(coords, page.rect.height, shrink=0)
            rect = fitz.Rect(*coords)

            # DEBUG: draw the rectangle in red
            if debug:
                page.draw_rect(rect, color=(1, 0, 0), width=1)

            text = page.get_textbox(rect)
            if text:
                text = text.replace('\n', ' ').replace('\r', ' ')
            row[name] = text

        # DEBUG: save PDF with boxes if debug mode is on
        if debug:
            debug_path = os.path.splitext(pdf_path)[0] + "_debug.pdf"
            doc.save(debug_path)
        doc.close()

    except Exception as e:
        row['error'] = f"{e} (file: {pdf_path})"

    return row

class PDFCropper(tk.Toplevel):
    COLORS = ["red", "orange", "blue", "purple", "black", "green", "cyan", "magenta"]

    def __init__(self, master, image, scale, pdf_bbox, display_height, bbox_dict, pdf_path=None):
        super().__init__(master)
        self.title("Draw a box to select area")
        self.geometry("1920x1000")

        self.image = image
        self.scale = scale
        self.pdf_bbox = pdf_bbox
        self.bbox_dict = bbox_dict

        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.view_width = 1000
        self.view_height = 1000

        self.rect = None
        self.color_map = {}
        self.color_index = 0
        self.rectangles = []  # List of tuples (canvas_rect_id, bbox_name)

        # Toolbar frame (top horizontal bar)
        self.toolbar = tk.Frame(self)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        self.save_button = tk.Button(self.toolbar, text="Save Area", command=self.save_area)
        self.save_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.load_jsonbutton = tk.Button(self.toolbar, text="Load JSON", command=self.load_existing_bboxes)
        self.load_jsonbutton.pack(side=tk.LEFT, padx=5, pady=5)

        self.finish_button = tk.Button(self.toolbar, text="Finish", command=self.finish)
        self.finish_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Name entry below toolbar
        self.name_entry = tk.Entry(self)
        self.name_entry.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(0, 5))
        self.name_entry.insert(0, "Enter name for this area")

        # Result label at bottom
        self.result_label = tk.Label(self, text="Draw a rectangle to select area")
        self.result_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Canvas for image and drawing
        self.canvas = tk.Canvas(self, width=self.view_width, height=self.view_height)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Debug output checkbox
        self.debug_var = tk.BooleanVar(value=False)
        self.debug_checkbox = tk.Checkbutton(self.toolbar, text="Debug Output", variable=self.debug_var)
        self.debug_checkbox.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.start_x = self.start_y = self.end_x = self.end_y = 0
        self.display_height = display_height
        self.last_box = None
        self.finished = False
        self.pan_start = None
        self.tk_image = None

        # Bind mouse events
        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)

        # Right-click drag for panning
        self.canvas.bind('<ButtonPress-2>', self.on_pan_start)  # Middle mouse button
        self.canvas.bind('<B2-Motion>', self.on_pan_move)

        # Right-click to delete rectangles
        self.canvas.bind('<ButtonPress-3>', self.on_right_click_delete)

        # Mouse wheel for zooming
        self.canvas.bind('<MouseWheel>', self.on_mousewheel)
        self.canvas.bind('<Button-4>', self.on_mousewheel)  # Linux scroll up
        self.canvas.bind('<Button-5>', self.on_mousewheel)  # Linux scroll down

        # Resize events
        self.bind('<Configure>', self.on_window_resize)

        self.after(100, self.update_view)
        self.after(100, self.resize_image_to_window)

        if pdf_path:
            self.load_existing_bboxes(pdf_path)

    def generate_color(self, name):
        if name not in self.color_map:
            color = self.COLORS[self.color_index % len(self.COLORS)]
            self.color_map[name] = color
            self.color_index += 1
        return self.color_map[name]

    def load_existing_bboxes(self, json_path=None):
        if not json_path:
            json_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if not json_path:
                return
        try:
            with open(json_path, 'r') as f:
                existing = json.load(f)
            self.bbox_dict.clear()
            self.color_map.clear()
            self.color_index = 0
            self.rectangles.clear()
            self.bbox_dict.update({k: tuple(v) for k, v in existing.items()})
            self.update_view()
            self.result_label.config(text=f"Loaded {len(existing)} areas from JSON")
        except Exception as e:
            print(f"Error loading bounding boxes: {e}")
            self.result_label.config(text=f"Error loading JSON: {e}")

    def update_view(self):
        zoomed_w = int(self.image.width * self.zoom_level)
        zoomed_h = int(self.image.height * self.zoom_level)
        self.offset_x = min(max(self.offset_x, 0), max(0, zoomed_w - self.view_width))
        self.offset_y = min(max(self.offset_y, 0), max(0, zoomed_h - self.view_height))
        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.LANCZOS
        zoomed_image = self.image.resize((zoomed_w, zoomed_h), resample_filter)
        cropped = zoomed_image.crop((self.offset_x, self.offset_y, self.offset_x + self.view_width, self.offset_y + self.view_height))
        self.tk_image = ImageTk.PhotoImage(cropped)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.draw_existing_boxes()

    def draw_existing_boxes(self):
        # Delete all previous rectangles and texts from canvas
        for rect_id, _ in self.rectangles:
            self.canvas.delete(rect_id)
        self.rectangles.clear()

        for name, (x0, y0, x1, y1) in self.bbox_dict.items():
            color = self.generate_color(name)
            x0s = (x0 - self.pdf_bbox[0]) / (self.pdf_bbox[2] - self.pdf_bbox[0]) * self.image.width * self.zoom_level - self.offset_x
            y0s = (y0 - self.pdf_bbox[1]) / (self.pdf_bbox[3] - self.pdf_bbox[1]) * self.image.height * self.zoom_level - self.offset_y
            x1s = (x1 - self.pdf_bbox[0]) / (self.pdf_bbox[2] - self.pdf_bbox[0]) * self.image.width * self.zoom_level - self.offset_x
            y1s = (y1 - self.pdf_bbox[1]) / (self.pdf_bbox[3] - self.pdf_bbox[1]) * self.image.height * self.zoom_level - self.offset_y
            rect_id = self.canvas.create_rectangle(x0s, y0s, x1s, y1s, outline=color, width=2, tags=("rect",))
            text_id = self.canvas.create_text(x0s + 5, y0s + 10, text=name, anchor="nw", fill=color)
            self.rectangles.append((rect_id, name))
            self.rectangles.append((text_id, None))  # Text is not linked to bbox name

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red')

    def on_drag(self, event):
        self.end_x = event.x
        self.end_y = event.y
        self.canvas.coords(self.rect, self.start_x, self.start_y, self.end_x, self.end_y)

    def on_release(self, event):
        self.end_x = event.x
        self.end_y = event.y
        x0, y0 = min(self.start_x, self.end_x), min(self.start_y, self.end_y)
        x1, y1 = max(self.start_x, self.end_x), max(self.start_y, self.end_y)
        x0_img = (x0 + self.offset_x) / self.zoom_level
        x1_img = (x1 + self.offset_x) / self.zoom_level
        y0_img = (y0 + self.offset_y) / self.zoom_level
        y1_img = (y1 + self.offset_y) / self.zoom_level
        pdf_x0, pdf_y0, pdf_x1, pdf_y1 = self.pdf_bbox
        x0_pdf = pdf_x0 + (x0_img / self.image.width) * (pdf_x1 - pdf_x0)
        x1_pdf = pdf_x0 + (x1_img / self.image.width) * (pdf_x1 - pdf_x0)
        y0_pdf = pdf_y0 + (y0_img / self.image.height) * (pdf_y1 - pdf_y0)
        y1_pdf = pdf_y0 + (y1_img / self.image.height) * (pdf_y1 - pdf_y0)
        self.last_box = (min(x0_pdf, x1_pdf), min(y0_pdf, y1_pdf), max(x0_pdf, x1_pdf), max(y0_pdf, y1_pdf))
        self.result_label.config(
            text=f"Selected area: x0={self.last_box[0]:.2f}, y0={self.last_box[1]:.2f}, x1={self.last_box[2]:.2f}, y1={self.last_box[3]:.2f}"
        )

    def save_area(self):
        name = self.name_entry.get().strip()
        if name and self.last_box:
            self.bbox_dict[name] = self.last_box
            self.result_label.config(text=f"Saved area '{name}'")
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, "Enter name for this area")
            self.last_box = None
            if self.rect:
                self.canvas.delete(self.rect)
            self.update_view()
        else:
            self.result_label.config(text="Please select an area and enter a name.")

    def on_right_click_delete(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(x, y, x, y)
        for item in overlapping:
            tags = self.canvas.gettags(item)
            if "rect" in tags:
                # Find bbox name linked to this rectangle
                for rect_id, name in self.rectangles:
                    if rect_id == item and name is not None:
                        self.canvas.delete(rect_id)
                        if name in self.bbox_dict:
                            del self.bbox_dict[name]
                        self.rectangles = [r for r in self.rectangles if r[0] != rect_id]
                        self.update_view()
                        self.result_label.config(text=f"Deleted area '{name}'")
                        return

    def on_pan_start(self, event):
        self.pan_start = (event.x, event.y)

    def on_pan_move(self, event):
        if self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.offset_x -= dx
            self.offset_y -= dy
            self.pan_start = (event.x, event.y)
            self.update_view()

    def on_mousewheel(self, event):
        delta = getattr(event, 'delta', 0)
        if delta > 0 or getattr(event, 'num', None) == 4:
            self.zoom_in()
        elif delta < 0 or getattr(event, 'num', None) == 5:
            self.zoom_out()

    def zoom_in(self):
        self.set_zoom(self.zoom_level * 1.25)

    def zoom_out(self):
        self.set_zoom(self.zoom_level / 1.25)

    def set_zoom(self, new_zoom):
        if 0.2 <= new_zoom <= 10:
            cx = self.offset_x + self.view_width // 2
            cy = self.offset_y + self.view_height // 2
            rel_x = cx / (self.image.width * self.zoom_level)
            rel_y = cy / (self.image.height * self.zoom_level)
            self.zoom_level = new_zoom
            new_w = int(self.image.width * new_zoom)
            new_h = int(self.image.height * new_zoom)
            self.offset_x = int(rel_x * new_w - self.view_width // 2)
            self.offset_y = int(rel_y * new_h - self.view_height // 2)
            self.update_view()

    def resize_image_to_window(self):
        win_width = self.winfo_width()
        win_height = self.winfo_height() - 100
        if win_width > 1 and win_height > 1:
            self.view_width = win_width
            self.view_height = win_height
            self.canvas.config(width=self.view_width, height=self.view_height)
            self.update_view()

    def on_window_resize(self, event):
        if event.widget == self:
            self.view_width = max(200, event.width)
            self.view_height = max(200, event.height - 100)
            self.canvas.config(width=self.view_width, height=self.view_height)
            self.update_view()

    def finish(self):
        self.finished = True
        self.destroy()





if __name__ == '__main__':
    multiprocessing.freeze_support()  # Needed for Windows executables

    # === GUI INIT: Select PDF Folder ===
    root = tk.Tk()
    pdf_folder = filedialog.askdirectory(title="Select folder containing PDFs")
    if not pdf_folder:
        print("No folder selected. Exiting.")
        root.destroy()
        exit(1)

    pdf_files = sorted(glob.glob(os.path.join(pdf_folder, '*.pdf')))
    if not pdf_files:
        print("No PDF files found in the selected folder.")
        root.destroy()
        exit(1)

    pdf_path = pdf_files[0]


    MAX_WIDTH, MAX_HEIGHT = 2000, 2000

    doc = fitz.open(pdf_path)
    page = doc.load_page(0)  # first page
    pix = page.get_pixmap(dpi=150, alpha=False)
    pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    orig_width, orig_height = pil_image.size
    scale = min(MAX_WIDTH / orig_width, MAX_HEIGHT / orig_height, 1.0)
    display_image = pil_image.resize(
        (int(orig_width * scale), int(orig_height * scale)),
        Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
    )

    pdf_x0, pdf_y0, pdf_x1, pdf_y1 = page.rect

    # === Bounding Box Loading or Selection ===
    bbox_json_path = os.path.join(pdf_folder, 'bounding_boxes.json')
    csv_path = os.path.join(pdf_folder, 'extracted_text.csv')
    bbox_dict = {}

    if os.path.exists(bbox_json_path):
        with open(bbox_json_path, 'r', encoding='utf-8') as f:
            bbox_dict = json.load(f)
        print(f"Loaded bounding boxes from {bbox_json_path}")
    else:
        root.withdraw()
        app = PDFCropper(root, display_image, scale, (pdf_x0, pdf_y0, pdf_x1, pdf_y1), display_image.height, bbox_dict)
        app.grab_set()
        app.wait_window()
        if bbox_dict:
            with open(bbox_json_path, 'w', encoding='utf-8') as f:
                json.dump(bbox_dict, f, indent=2)
            print(f"Saved bounding boxes to {bbox_json_path}")

    # === Only now run multiprocessing on prepared file list ===
    if bbox_dict:
        cpu_count = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(cpu_count)
        debug_mode = app.debug_var.get()  # or False
        tasks = [(pdf_path, bbox_dict, debug_mode) for pdf_path in pdf_files]

        # Progress GUI
        progress_win = tk.Toplevel(root)
        progress_win.title("Extracting Text from PDFs (Parallel)")
        progress_label = tk.Label(progress_win, text="Extracting text from PDFs...")
        progress_label.pack(padx=20, pady=(20, 5))
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_win, variable=progress_var, maximum=len(pdf_files), length=400)
        progress_bar.pack(padx=20, pady=(0, 20))
        progress_win.update()

        csv_rows = []
        errors = []

        for idx, result in enumerate(pool.imap_unordered(extract_text_from_pdf, tasks)):
            if result is None:
                continue
            if 'error' in result:
                errors.append(result)
            csv_rows.append(result)
            progress_var.set(idx + 1)
            progress_win.update()

        pool.close()
        pool.join()

        if errors:
            error_log_path = os.path.splitext(csv_path)[0] + "_errors.log"
            with open(error_log_path, 'w', encoding='utf-8') as ef:
                for err in errors:
                    ef.write(err['error'] + '\n')
            print(f"\n{len(errors)} file(s) failed. Details saved to {error_log_path}")

        # Save CSV
        header = ['filename'] + list(bbox_dict.keys())
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for row in csv_rows:
                writer.writerow(row)

        progress_label.config(text=f"Saved extracted text to {csv_path}")
        progress_win.update()
        progress_win.after(1500, progress_win.destroy)
    else:
        print("No areas were selected.")
