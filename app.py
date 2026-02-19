import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain_pinecone import PineconeVectorStore, PineconeEmbeddings
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from gds_viewer import show_gds_viewer

# DO NOT put your actual keys here anymore!
# Streamlit will look for these in its "Advanced Settings" later.
os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
os.environ["PINECONE_API_KEY"] = st.secrets["PINECONE_API_KEY"]

# 2. Page Config & Tabs
st.set_page_config(page_title="LuxAgent Photonics", page_icon="💡")

# Create Tabs
tab1, tab2 = st.tabs(["💬 AI Assistant", "🏗️ GDS Viewer"])

with tab1:
    st.title("💡 LuxAgent: Silicon Photonics Expert")
    user_query = st.text_input("Ask a technical question about your papers:")
    
    if user_query:
        with st.spinner("Analyzing..."):
            response = qa.invoke({"input": user_query})
            st.write("### Answer:")
            st.write(response["answer"])

with tab2:
    # Call the function from your separate file
    show_gds_viewer()

#### RAG and LLM ####
# Highly recommended for RAG and technical analysis
llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

# 4. Initialize the Memory (Pinecone)
embeddings = PineconeEmbeddings(model="llama-text-embed-v2")
vectorstore = PineconeVectorStore(index_name="lux-kb", embedding=embeddings)

# 5. Create the Modern "QA Chain" (LCEL)

# A. Define how the AI should behave and read the context
system_prompt = (
    "You are an expert silicon photonics assistant. Use the following retrieved context to answer the user's question. "
    "If you don't know the answer, just say that you don't know.\n\n"
    "Context: {context}"
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}")
])

# B. Create the chain that combines the documents (the "stuff" equivalent)
question_answer_chain = create_stuff_documents_chain(llm, prompt)

# C. Link the retriever and the document chain together
qa = create_retrieval_chain(
    vectorstore.as_retriever(search_kwargs={"k": 3}), 
    question_answer_chain
)

# 6. The UI
user_query = st.text_input("Ask a technical question about your papers:", key="user_chat_input")

if user_query:
    with st.spinner("Analyzing papers..."):
        # Pass the query as a dictionary with the key "input"
        response = qa.invoke({"input": user_query})
        
        st.write("### Answer:")
        # The modern chain outputs the final text under the "answer" key
        st.write(response["answer"])