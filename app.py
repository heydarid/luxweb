import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain_pinecone import PineconeVectorStore, PineconeEmbeddings
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from gdsengine.gds_viewer import show_interactive_viewer # Note: updated name

# 1. Environment Setup
os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
os.environ["PINECONE_API_KEY"] = st.secrets["PINECONE_API_KEY"]

# 2. Initialize Brain & Memory (Must happen before UI usage)
@st.cache_resource # This prevents the app from reloading the brain on every click
def init_qa_chain():
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
    embeddings = PineconeEmbeddings(model="llama-text-embed-v2")
    vectorstore = PineconeVectorStore(index_name="lux-kb", embedding=embeddings)
    
    system_prompt = (
        "You are an expert silicon photonics assistant. Use the following retrieved context "
        "to answer the user's question. If you don't know, say you don't know.\n\n"
        "Context: {context}"
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(
        vectorstore.as_retriever(search_kwargs={"k": 3}), 
        combine_docs_chain
    )

qa = init_qa_chain()

# 3. Page Config & Tabs
st.set_page_config(page_title="LuxAgent Photonics", page_icon="💡", layout="wide")

tab1, tab2 = st.tabs(["💬 AI Assistant", "🏗️ GDS Viewer"])

with tab1:
    st.title("💡 LuxAgent: Silicon Photonics Expert")
    st.markdown("Querying your private knowledge base.")
    
    # Use a unique key to prevent duplicate ID errors
    user_query = st.text_input("Ask a technical question about your papers:", key="user_chat_input")
    
    if user_query:
        with st.spinner("Analyzing papers..."):
            response = qa.invoke({"input": user_query})
            st.write("### Answer:")
            st.write(response["answer"])

with tab2:
    # This calls your interactive kweb/gdsfactory logic
    show_interactive_viewer()