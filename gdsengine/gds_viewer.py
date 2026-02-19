import streamlit as st
import os
from collections import defaultdict
import streamlit.components.v1 as components

# One color per layer index, cycling if there are more layers than colors
_LAYER_COLORS = [
    "#4e9af1", "#f14e4e", "#4ef18a", "#f1c44e", "#ae4ef1",
    "#4ef1e8", "#f18a4e", "#8af14e", "#f14eae", "#e8f14e",
    "#f14e8a", "#4e8af1",
]

def _build_svg(top_cells):
    """Flatten all polygons into one SVG <path> per layer."""
    layer_paths = defaultdict(list)
    all_x, all_y = [], []

    for cell in top_cells:
        for poly in cell.get_polygons():
            pts = poly.points
            if len(pts) < 2:
                continue
            xs = pts[:, 0]
            ys = -pts[:, 1]          # flip Y: GDS y-up → SVG y-down
            all_x.extend(xs)
            all_y.extend(ys)
            # SVG path: Move to first point, Line to rest, Close
            coords = " L".join(f"{x:.3g},{y:.3g}" for x, y in zip(xs, ys))
            layer_paths[poly.layer].append(f"M{coords}Z")

    if not all_x:
        return None

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    pad = max(max_x - min_x, max_y - min_y) * 0.02 or 1
    vb = f"{min_x-pad:.3g} {min_y-pad:.3g} {max_x-min_x+2*pad:.3g} {max_y-min_y+2*pad:.3g}"

    paths_html = ""
    for i, layer in enumerate(sorted(layer_paths)):
        color = _LAYER_COLORS[i % len(_LAYER_COLORS)]
        d = " ".join(layer_paths[layer])
        paths_html += f'<path d="{d}" fill="{color}" fill-opacity="0.75" stroke="none"/>\n'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{vb}" style="width:100%;height:100%;display:block">'
        f'{paths_html}</svg>'
    )


def show_interactive_viewer():
    st.header("🔗 KLayout-Powered Interactive Viewer")
    uploaded_file = st.file_uploader("Upload GDSII", type=["gds"], key="kweb_uploader")

    if uploaded_file:
        gds_path = "temp_view.gds"
        with open(gds_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        try:
            import gdstk

            with st.spinner("Rendering layout..."):
                lib = gdstk.read_gds(gds_path)
                top_cells = lib.top_level()
                if not top_cells:
                    st.error("No top-level cell found in GDS file.")
                    return

                svg = _build_svg(top_cells)
                if not svg:
                    st.error("No geometry found in GDS file.")
                    return

                html = f"""<!DOCTYPE html>
<html><head><style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#1e1e2e;overflow:hidden;width:100%;height:600px}}
  #c{{width:100%;height:600px;overflow:hidden;cursor:grab;position:relative}}
  #w{{width:100%;height:100%;transform-origin:0 0;will-change:transform}}
</style></head><body>
<div id="c"><div id="w">{svg}</div></div>
<script>
  const c=document.getElementById('c'),w=document.getElementById('w');
  let s=1,ox=0,oy=0,panning=false,px,py;
  const apply=()=>w.style.transform=`translate(${{ox}}px,${{oy}}px) scale(${{s}})`;

  // Scroll wheel → zoom toward cursor
  c.addEventListener('wheel',e=>{{
    e.preventDefault();
    const r=c.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
    const d=e.deltaY<0?1.15:1/1.15;
    ox=mx-(mx-ox)*d; oy=my-(my-oy)*d; s*=d; apply();
  }},{{passive:false}});

  // Left OR middle mouse button → pan
  c.addEventListener('mousedown',e=>{{
    if(e.button===0||e.button===1){{
      panning=true; px=e.clientX-ox; py=e.clientY-oy;
      c.style.cursor='grabbing'; e.preventDefault();
    }}
  }});
  window.addEventListener('mousemove',e=>{{
    if(panning){{ox=e.clientX-px; oy=e.clientY-py; apply();}}
  }});
  window.addEventListener('mouseup',()=>{{panning=false;c.style.cursor='grab';}});

  // Double-click → reset view
  c.addEventListener('dblclick',()=>{{s=1;ox=0;oy=0;apply();}});
</script></body></html>"""

                components.html(html, height=620)
                st.caption("Scroll to zoom · Drag or middle-click to pan · Double-click to reset")

        except Exception as e:
            st.error(f"Viewer Error: {e}")
        finally:
            if os.path.exists(gds_path):
                os.remove(gds_path)
