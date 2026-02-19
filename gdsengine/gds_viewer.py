import streamlit as st
import os
from collections import defaultdict
import streamlit.components.v1 as components

_LAYER_COLORS = [
    "#4e9af1", "#f14e4e", "#4ef18a", "#f1c44e", "#ae4ef1",
    "#4ef1e8", "#f18a4e", "#8af14e", "#f14eae", "#e8f14e",
    "#f14e8a", "#4e8af1",
]

def _unit_label(lib_unit):
    """Return a human-readable unit string from the GDS user unit (in metres)."""
    if abs(lib_unit - 1e-6) < 1e-9:
        return "µm"
    if abs(lib_unit - 1e-9) < 1e-12:
        return "nm"
    if abs(lib_unit - 1e-3) < 1e-6:
        return "mm"
    return "u"

def _build_svg(top_cells):
    """Flatten all polygons into one SVG <path> per layer.
    Returns (svg_string, vb_x, vb_y, vb_w, vb_h).
    Coordinates use :.3f (no scientific notation, 1nm precision for µm-unit GDS).
    """
    layer_paths = defaultdict(list)
    all_x, all_y = [], []

    for cell in top_cells:
        for poly in cell.get_polygons():
            pts = poly.points
            if len(pts) < 2:
                continue
            xs = pts[:, 0]
            ys = -pts[:, 1]   # flip Y: GDS y-up → SVG y-down
            all_x.extend(xs)
            all_y.extend(ys)
            coords = " L".join(f"{x:.3f},{y:.3f}" for x, y in zip(xs, ys))
            layer_paths[poly.layer].append(f"M{coords}Z")

    if not all_x:
        return None, 1

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    pad = max(max_x - min_x, max_y - min_y) * 0.02 or 1
    vb_x = min_x - pad
    vb_y = min_y - pad
    vb_w = max_x - min_x + 2 * pad
    vb_h = max_y - min_y + 2 * pad

    paths_html = ""
    for i, layer in enumerate(sorted(layer_paths)):
        color = _LAYER_COLORS[i % len(_LAYER_COLORS)]
        d = " ".join(layer_paths[layer])
        paths_html += (
            f'<path d="{d}" fill="{color}" fill-opacity="0.75" stroke="none"/>\n'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{vb_x:.3f} {vb_y:.3f} {vb_w:.3f} {vb_h:.3f}" '
        f'style="width:100%;height:100%;display:block">'
        f'{paths_html}</svg>'
    )
    return svg, vb_w


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

                svg, vb_w = _build_svg(top_cells)
                if not svg:
                    st.error("No geometry found in GDS file.")
                    return

                unit = _unit_label(lib.unit)

                html = f"""<!DOCTYPE html>
<html><head><style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#1e1e2e;overflow:hidden;width:100%;height:600px}}
  #c{{width:100%;height:600px;overflow:hidden;cursor:grab;position:relative}}
  #w{{width:100%;height:100%;transform-origin:0 0;will-change:transform}}
  #ruler{{
    position:absolute;bottom:18px;left:18px;z-index:10;
    color:#e0e0e0;font:11px/1.4 monospace;pointer-events:none;
  }}
  #rbar{{height:3px;background:#e0e0e0;border-radius:1px;margin-bottom:4px}}
  #rlabel{{text-align:center;text-shadow:0 0 4px #000}}
</style></head><body>
<div id="c">
  <div id="w">{svg}</div>
  <div id="ruler"><div id="rbar"></div><div id="rlabel"></div></div>
</div>
<script>
  const c=document.getElementById('c'),w=document.getElementById('w');
  const VBW={vb_w:.6f}, UNIT="{unit}";
  let s=1,ox=0,oy=0,panning=false,px,py;

  function niceNum(x){{
    const mag=Math.pow(10,Math.floor(Math.log10(x)));
    const f=x/mag;
    if(f<1.5) return 1*mag;
    if(f<3.5) return 2*mag;
    if(f<7.5) return 5*mag;
    return 10*mag;
  }}

  function updateRuler(){{
    const gdsPerPx=VBW/(c.offsetWidth*s);
    const gdsLen=niceNum(gdsPerPx*120);
    const barPx=gdsLen/gdsPerPx;
    document.getElementById('rbar').style.width=barPx+'px';
    // Format label: drop decimals if whole number
    const label=Number.isInteger(gdsLen)?gdsLen:gdsLen.toPrecision(3);
    document.getElementById('rlabel').textContent=label+' '+UNIT;
  }}

  function apply(){{
    w.style.transform=`translate(${{ox}}px,${{oy}}px) scale(${{s}})`;
    updateRuler();
  }}

  // Scroll wheel → zoom toward cursor
  c.addEventListener('wheel',e=>{{
    e.preventDefault();
    const r=c.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
    const d=e.deltaY<0?1.15:1/1.15;
    ox=mx-(mx-ox)*d; oy=my-(my-oy)*d; s*=d; apply();
  }},{{passive:false}});

  // Left OR middle mouse → pan
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

  // Double-click → reset
  c.addEventListener('dblclick',()=>{{s=1;ox=0;oy=0;apply();}});

  updateRuler();
</script></body></html>"""

                components.html(html, height=620)
                st.caption("Scroll to zoom · Drag or middle-click to pan · Double-click to reset")

        except Exception as e:
            st.error(f"Viewer Error: {e}")
        finally:
            if os.path.exists(gds_path):
                os.remove(gds_path)
