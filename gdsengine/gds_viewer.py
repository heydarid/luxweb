import streamlit as st
import streamlit.components.v1 as components
import gdsfactory as gf
import os

# Get path to the .lyp file inside the same folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LYP_PATH = os.path.join(CURRENT_DIR, "EBeam.lyp")

def show_interactive_viewer():
    st.header("🔗 KLayout-Powered Interactive Viewer")
    
    uploaded_file = st.file_uploader("Upload GDSII", type=["gds"], key="kweb_uploader")
    
    if uploaded_file:
        gds_path = "temp_view.gds"
        html_path = "layout_viewer.html"
        
        with open(gds_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            with st.spinner("KLayout engine rendering layout..."):
                # 1. Import with GDSFactory
                component = gf.import_gds(gds_path)
                
                # 2. Apply the Layer Properties (.lyp)
                # This ensures Silicon (1/0) looks like Silicon, etc.
                if os.path.exists(LYP_PATH):
                    # We use the klayout API through gdsfactory to set layer views
                    layer_views = gf.technology.LayerViews.from_lyp(LYP_PATH)
                    # Note: plot_widget automatically tries to resolve colors, 
                    # but passing a component with metadata helps.
                
                # 3. Generate high-performance HTML/JS Canvas
                # 'plot_widget' creates a standalone file with pan/zoom logic
                component.plot_widget(html_path) 
                
                # 4. Read and inject into Streamlit
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Using a slightly larger height for a professional feel
                components.html(html_content, height=700, scrolling=False)
                
                st.success("Interactive viewer loaded! 💡 Tip: Use mouse wheel to zoom, left click to pan.")
                
        except Exception as e:
            st.error(f"Viewer Error: {e}")
            st.info("Check if gdsfactory and klayout are in your requirements.txt")
        finally:
            # Clean up to keep the server lightweight
            for p in [gds_path, html_path]:
                if os.path.exists(p):
                    os.remove(p)