import os
import klayout.db as db
import klayout.lay as lay

# Get the path to the current folder (gdsengine)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LYP_PATH = os.path.join(CURRENT_DIR, "EBeam.lyp")

def get_klayout_snapshot(gds_path, width=1200, height=800):
    ly = db.Layout()
    ly.read(gds_path)
    
    view = lay.LayoutView()
    view.show_layout(ly, False)
    
    # Load the professional layer properties!
    if os.path.exists(LYP_PATH):
        view.load_layer_props(LYP_PATH)
    
    view.zoom_fit()
    img_path = gds_path.replace(".gds", "_preview.png")
    view.save_image(img_path, width, height)
    return img_path