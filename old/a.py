import tkinter as tk
from PIL import Image, ImageTk

class SlicedBorderWindow(tk.Tk):
    def __init__(self, border_image_path, border_thickness=15):
        super().__init__()
        
        # 1. Remove standard Windows borders
        self.overrideredirect(True)
        self.geometry("500x400+400+200") # Width x Height + X_offset + Y_offset
        
        self.border_thick = border_thickness
        self.bg_color = "#000000" # Match this to your border's inner color
        
        # Load and prepare the base border image
        self.base_image = Image.open(border_image_path).convert("RGBA")
        
        # Create a canvas that fills the entire window
        self.canvas = tk.Canvas(self, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind resize event to recalculate the 9-slice border
        self.canvas.bind("<Configure>", self.draw_9_slice_border)
        
        # 2. Add custom Title Bar / Draggable area inside the border
        self.title_bar = tk.Frame(self.canvas, bg="#2d2d2d", height=30)
        # Position it just inside the top border
        self.title_bar.place(x=self.border_thick, y=self.border_thick, 
                             relwidth=1.0, width=-(self.border_thick * 2))
        self.title_bar.pack_propagate(False)
        
        # Close Button
        self.close_btn = tk.Button(self.title_bar, text="✕", bg="#2d2d2d", fg="white", 
                                   bd=0, activebackground="#e81123", activeforeground="white",
                                   command=self.destroy)
        self.close_btn.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        # Window Title text
        self.title_label = tk.Label(self.title_bar, text="9-Slice Custom Window", bg="#2d2d2d", fg="white")
        self.title_label.pack(side=tk.LEFT, padx=10)
        
        # Window Content Area
        self.content = tk.Frame(self.canvas, bg=self.bg_color)
        self.content.place(x=self.border_thick, y=self.border_thick + 30, 
                           relwidth=1.0, relheight=1.0, 
                           width=-(self.border_thick * 2), height=-(self.border_thick * 2 + 30))
        
        # Add a test widget inside
        tk.Label(self.content, text="Hello from inside a 9-sliced frame!", 
                 bg=self.bg_color, fg="white", font=("Arial", 12)).pack(pady=40)
        
        # Bind window dragging events
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<Button-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)

    def draw_9_slice_border(self, event=None):
        """Slices the source image and stretches it to fit the current window size."""
        w = self.winfo_width()
        h = self.winfo_height()
        t = self.border_thick
        
        img_w, img_h = self.base_image.size
        
        # Define the coordinates for the 9 slices on the source image
        # (Assuming the texture's border width matches self.border_thick)
        src_left = t
        src_right = img_w - t
        src_top = t
        src_bottom = img_h - t
        
        # Define target coordinates
        dst_right = w - t
        dst_bottom = h - t
        
        # Box definitions: (left, upper, right, lower)
        slices = {
            "top_left":     (0, 0, src_left, src_top),
            "top":          (src_left, 0, src_right, src_top),
            "top_right":    (src_right, 0, img_w, src_top),
            "left":         (0, src_top, src_left, src_bottom),
            "center":       (src_left, src_top, src_right, src_bottom),
            "right":        (src_right, src_top, img_w, src_bottom),
            "bottom_left":  (0, src_bottom, src_left, img_h),
            "bottom":       (src_left, src_bottom, src_right, img_h),
            "bottom_right": (src_right, src_bottom, img_w, img_h)
        }
        
        # Target sizes for scaling
        targets = {
            "top_left":     (t, t),
            "top":          (dst_right - t, t),
            "top_right":    (t, t),
            "left":         (t, dst_bottom - t),
            "center":       (dst_right - t, dst_bottom - t),
            "right":        (t, dst_bottom - t),
            "bottom_left":  (t, t),
            "bottom":       (dst_right - t, t),
            "bottom_right": (t, t)
        }
        
        # Target placements on the Canvas
        positions = {
            "top_left":     (0, 0),
            "top":          (t, 0),
            "top_right":    (dst_right, 0),
            "left":         (0, t),
            "center":       (t, t),
            "right":        (dst_right, t),
            "bottom_left":  (0, dst_bottom),
            "bottom":       (t, dst_bottom),
            "bottom_right": (dst_right, dst_bottom)
        }
        
        # Render the slices
        self.canvas.delete("border") # Clear old border graphics
        self.images = {} # Keep references to prevent garbage collection
        
        for key in slices:
            # Crop the slice out of the original texture
            part = self.base_image.crop(slices[key])
            # Resize it to fill the target destination size
            part = part.resize(targets[key], Image.Resampling.LANCZOS)
            
            # Convert to Tkinter-compatible image
            self.images[key] = ImageTk.PhotoImage(part)
            
            # Draw it onto the canvas
            self.canvas.create_image(positions[key][0], positions[key][1], 
                                     image=self.images[key], anchor=tk.NW, tags="border")
            
        # Lift UI elements back to the top layer above the background canvas graphics
        self.title_bar.lift()
        self.content.lift()

    # Window Dragging Logic
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    # Create a quick dummy 9-slice border image if you don't have one
    # This creates a 45x45 image with red corners, blue edges, and a dark center
    dummy_img = Image.new("RGBA", (45, 45), "#202020")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(dummy_img)
    draw.rectangle([0, 0, 44, 44], outline="blue", width=15) # Edges
    draw.rectangle([0, 0, 14, 14], fill="red") # Top Left
    draw.rectangle([30, 0, 44, 14], fill="red") # Top Right
    draw.rectangle([0, 30, 14, 44], fill="red") # Bottom Left
    draw.rectangle([30, 30, 44, 44], fill="red") # Bottom Right
    #dummy_img.save("border_texture.png")
    
    # Run application
    app = SlicedBorderWindow("border_texture.png", border_thickness=15)
    app.mainloop()