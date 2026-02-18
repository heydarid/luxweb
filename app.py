import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain_pinecone import PineconeVectorStore, PineconeEmbeddings
from langchain.chains.retrieval_qa.base import RetrievalQA

# DO NOT put your actual keys here anymore!
# Streamlit will look for these in its "Advanced Settings" later.
os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
os.environ["PINECONE_API_KEY"] = st.secrets["PINECONE_API_KEY"]

# 2. Page Config
st.set_page_config(page_title="LuxAgent Photonics", page_icon="💡")
st.title("💡 LuxAgent: Silicon Photonics Expert")
st.markdown("Querying your private cloud-hosted knowledge base.")

# 3. Initialize the Brain (Gemma 3 on Groq)
llm = ChatGroq(model_name="gemma3-70b-it", temperature=0)

# 4. Initialize the Memory (Pinecone)
embeddings = PineconeEmbeddings(model="llama-text-embed-v2")
vectorstore = PineconeVectorStore(index_name="lux-kb", embedding=embeddings)

# 5. Create the "QA Chain"
qa = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectorstore.as_retriever(search_kwargs={"k": 3})
)

# 6. The UI
user_query = st.text_input("Ask a technical question about your papers:")

if user_query:
    with st.spinner("Analyzing papers..."):
        response = qa.invoke(user_query)
        st.write("### Answer:")
        st.write(response["result"])