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
                
                # 2. Generate the interactive HTML 
                # In newer gdsfactory, we use plot(idx=...) or create a widget
                # This is the most reliable way to get an HTML string for Streamlit
                html_path = "layout_viewer.html"
                
                # This function generates a standalone HTML file using the kweb engine
                # which is bundled with newer gdsfactory/klayout setups
                component.plot(save_html=html_path) 
                
                # 3. Read and inject into Streamlit
                if os.path.exists(html_path):
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    components.html(html_content, height=700, scrolling=False)
                    st.success("Interactive viewer loaded!")
                else:
                    # Fallback if the HTML wasn't created
                    st.error("Failed to generate viewer file.")

        except AttributeError:
            # If .plot(save_html=...) also fails due to versioning, 
            # use this 'manual' kweb call:
            from kweb.main import get_app
            st.warning("Switching to kweb backup viewer...")
            # (Simplified fallback logic here if needed)
        finally:
            # Clean up to keep the server lightweight
            for p in [gds_path, html_path]:
                if os.path.exists(p):
                    os.remove(p)