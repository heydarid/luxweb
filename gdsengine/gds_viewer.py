import streamlit as st
import os
import math
import gdstk
import xml.etree.ElementTree as ET
from collections import defaultdict
import streamlit.components.v1 as components

_LAYER_COLORS = [
    "#4e9af1", "#f14e4e", "#4ef18a", "#f1c44e", "#ae4ef1",
    "#4ef1e8", "#f18a4e", "#8af14e", "#f14eae", "#e8f14e",
    "#f14e8a", "#4e8af1",
]

_HATCH_ANGLES = [0, 45, 90, 135, 22, 67, 112, 157, 0, 45, 90, 135]
_HATCH_LW = [0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.18, 0.18, 0.18, 0.18]

def _hatch_pattern(pat_id, color, ps, idx):
    angle = _HATCH_ANGLES[idx % 12]
    lw = ps * _HATCH_LW[idx % 12]
    h = ps / 2
    rot = f' patternTransform="rotate({angle})"' if angle else ''
    return (
        f'<pattern id="{pat_id}" x="0" y="0" width="{ps:.6g}" height="{ps:.6g}" '
        f'patternUnits="userSpaceOnUse"{rot}>'
        f'<rect width="{ps:.6g}" height="{ps:.6g}" fill="{color}" fill-opacity="0.25"/>'
        f'<line x1="0" y1="{h:.6g}" x2="{ps:.6g}" y2="{h:.6g}" '
        f'stroke="{color}" stroke-width="{lw:.6g}" stroke-opacity="0.9"/>'
        f'</pattern>'
    )

def _parse_lyp(lyp_bytes):
    layer_colors = {}
    try:
        root = ET.fromstring(lyp_bytes)
        for props in root.findall(".//properties"):
            if props.findtext("visible", "true").strip().lower() == "false":
                continue
            source = props.findtext("source", "").strip()
            color = props.findtext("fill-color", "").strip()
            if source and color:
                try:
                    layer = int(source.split("/")[0])
                    layer_colors[layer] = color
                except: continue
    except: pass
    return layer_colors

def _svg_id(name):
    return "c" + "".join(c if c.isalnum() or c == "-" else "_" for c in str(name))

def _svg_transform(ox, oy, rotation, magnification, x_reflection):
    parts = [f"translate({ox:.4f},{oy:.4f})"]
    if rotation: parts.append(f"rotate({math.degrees(rotation):.4f})")
    if magnification and abs(magnification - 1.0) > 1e-9: parts.append(f"scale({magnification:.6g})")
    if x_reflection: parts.append("scale(1,-1)")
    return " ".join(parts)

def _build_svg(top_cells, layer_colors=None, use_hatches=True, density=0.01):
    def color_for(layer):
        if layer_colors and layer in layer_colors: return layer_colors[layer]
        return _LAYER_COLORS[layer % len(_LAYER_COLORS)]

    visited, symbols, all_layers = set(), [], set()

    def process(cell):
        if cell.name in visited: return
        visited.add(cell.name)
        for ref in cell.references:
            if ref.cell: process(ref.cell)
        
        lpaths = defaultdict(list)
        for poly in cell.polygons:
            pts = poly.points
            if len(pts) < 2: continue
            coords = " L".join(f"{x:.3f},{y:.3f}" for x, y in zip(pts[:, 0], pts[:, 1]))
            lpaths[poly.layer].append(f"M{coords}Z")
            all_layers.add(poly.layer)

        parts = []
        for layer in sorted(lpaths):
            d = " ".join(lpaths[layer])
            fill = f"url(#pat_L{layer})" if use_hatches else color_for(layer)
            parts.append(f'<path d="{d}" fill="{fill}" stroke="none"/>')

        for ref in cell.references:
            if not ref.cell: continue
            t = _svg_transform(ref.origin[0], ref.origin[1], ref.rotation or 0, ref.magnification or 1, ref.x_reflection)
            parts.append(f'<use href="#{_svg_id(ref.cell.name)}" transform="{t}"/>')
        
        symbols.append(f'<symbol id="{_svg_id(cell.name)}" overflow="visible">{"".join(parts)}</symbol>')

    for cell in top_cells: process(cell)

    bbox = None
    for cell in top_cells:
        bb = cell.bounding_box()
        if not bb: continue
        (x0, y0), (x1, y1) = bb
        if bbox is None: bbox = [x0, y0, x1, y1]
        else:
            bbox[0]=min(bbox[0],x0); bbox[1]=min(bbox[1],y0)
            bbox[2]=max(bbox[2],x1); bbox[3]=max(bbox[3],y1)

    xmin, ymin, xmax, ymax = bbox or (0, 0, 100, 100)
    ps = (xmax - xmin) * density or 10
    
    patterns = [_hatch_pattern(f"pat_L{l}", color_for(l), ps, i) for i, l in enumerate(sorted(all_layers))] if use_hatches else []
    
    pad = (xmax - xmin) * 0.05 or 10
    vb_x, vb_w = xmin - pad, (xmax - xmin) + 2*pad
    vb_h = (ymax - ymin) + 2*pad
    vb_y = -(ymax + pad)

    defs = "<defs>" + "".join(patterns) + "".join(symbols) + "</defs>"
    svg = (f'<svg id="gds" xmlns="http://www.w3.org/2000/svg" viewBox="{vb_x} {vb_y} {vb_w} {vb_h}" '
           f'style="width:100%;height:100%;display:block;background:#1e1e2e;">{defs}'
           f'<g transform="scale(1,-1)">' + "".join([f'<use href="#{_svg_id(c.name)}"/>' for c in top_cells]) + '</g></svg>')
    
    return svg, vb_x, vb_y, vb_w, vb_h

def show_interactive_viewer():
    st.sidebar.markdown("### 🖥️ Display Settings")
    show_hatches = st.sidebar.checkbox("Enable Hatching", value=True)
    hatch_density = st.sidebar.slider("Hatch Density", 0.001, 0.05, 0.01, step=0.001)

    uploaded_file = st.file_uploader("Upload GDSII", type=["gds"])
    uploaded_lyp = st.file_uploader("Layer Properties (.lyp)", type=["lyp"])

    if uploaded_file:
        with open("temp.gds", "wb") as f: f.write(uploaded_file.getbuffer())
        lib = gdstk.read_gds("temp.gds")
        top_cells = lib.top_level()
        
        lyp_colors = _parse_lyp(uploaded_lyp.getvalue()) if uploaded_lyp else None
        svg_data = _build_svg(top_cells, lyp_colors, show_hatches, hatch_density)
        
        svg, vx, vy, vw, vh = svg_data
        
        html_code = f"""
        <html><body style="margin:0; background:#d4d0c8; font-family:sans-serif;">
        <div style="padding:5px; background:#d4d0c8; border-bottom:2px solid #808080; display:flex; gap:10px;">
            <button style="border:2px solid; border-color:#fff #404040 #404040 #fff; padding:2px 10px;">Reset View</button>
        </div>
        <div id="container" style="width:100%; height:600px; background:#000; overflow:hidden;">{svg}</div>
        <script>
            const svg = document.getElementById('gds');
            let isPanning = false;
            let startX, startY, viewBox = {{ x: {vx}, y: {vy}, w: {vw}, h: {vh} }};

            window.addEventListener('wheel', e => {{
                e.preventDefault();
                const delta = e.deltaY > 0 ? 1.1 : 0.9;
                viewBox.w *= delta; viewBox.h *= delta;
                svg.setAttribute('viewBox', `${{viewBox.x}} ${{viewBox.y}} ${{viewBox.w}} ${{viewBox.h}}`);
            }}, {{passive: false}});
        </script></body></html>
        """
        components.html(html_code, height=650)

if __name__ == "__main__":
    show_interactive_viewer()