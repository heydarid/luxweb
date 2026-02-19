import streamlit as st
import gdsfactory as gf
import os
import streamlit.components.v1 as components
from kweb.main import save_stack # This is the "magic" exporter

def show_interactive_viewer():
    st.header("🔗 KLayout-Powered Interactive Viewer")
    uploaded_file = st.file_uploader("Upload GDSII", type=["gds"], key="kweb_uploader")
    
    if uploaded_file:
        gds_path = "temp_view.gds"
        html_path = "layout_viewer.html"
        
        with open(gds_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            with st.spinner("KLayout engine rendering..."):
                # 1. Load the GDS
                c = gf.import_gds(gds_path)
                
                # 2. Use kweb's internal exporter to create the HTML file
                # This bypasses the 'plot' TypeError and goes straight to the source
                save_stack(c, html_path)
                
                # 3. Read and display
                if os.path.exists(html_path):
                    with open(html_path, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    
                    # Increase height to 700 for better visibility
                    components.html(html_content, height=700, scrolling=False)
                    st.success("Interactive viewer loaded!")
                else:
                    st.error("Failed to generate HTML layout.")
                    
        except Exception as e:
            st.error(f"Viewer Error: {e}")
            st.info("Try checking if 'kweb' and 'gdsfactory' versions are compatible.")
        finally:
            # Clean up files so they don't sit on the Streamlit server
            for p in [gds_path, html_path]:
                if os.path.exists(p):
                    os.remove(p)