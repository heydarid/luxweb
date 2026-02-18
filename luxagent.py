# -*- coding: utf-8 -*-

import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# --- 1. Load the "Memory" (ChromaDB) ---
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(
    persist_directory="data/vector_db", 
    embedding_function=embeddings,
    collection_name="lux_industrial_kb"
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# --- 2. Load the "Brain" (Ollama + Gemma) ---
# Ensure you have run 'ollama pull gemma3' in your terminal first!
llm = OllamaLLM(model="gemma3")

# --- 3. The Industrial Prompt ---
template = """
You are LuxAgent, a technical expert in Silicon Photonics and Co-Packaged Optics (CPO). 
Use the provided industrial paper snippets to answer the user's question.
If the answer isn't in the context, say you don't know based on current data.

Context:
{context}

Question: {question}

Answer:"""
prompt = ChatPromptTemplate.from_template(template)

# --- 4. The RAG Pipeline (LCEL) ---
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# --- 5. Interactive Chat ---
if __name__ == "__main__":
    print("🚀 LuxAgent Online. Ask about Silicon Photonics or CPO (type 'exit' to quit).")
    while True:
        query = input("\nUser: ")
        if query.lower() == "exit": break
        
        print("\nLuxAgent is analyzing papers...")
        response = rag_chain.invoke(query)
        print(f"\nLuxAgent: {response}")