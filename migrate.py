import os
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore, PineconeEmbeddings

# 1. SET YOUR API KEY HERE
os.environ["PINECONE_API_KEY"] = "pcsk_4id9Jd_NiJSvPKW6mzGdTBLZNFhTGpXFk6gsnd5em2VGBLND48L8WSo7A5QqDQ85kG1yDC"
INDEX_NAME = "lux-kb"

# 2. Initialize the 1024-dimension Embedding Model
embeddings = PineconeEmbeddings(
    model="llama-text-embed-v2"
)

# 3. Load ALL PDFs from the folder
# We use DirectoryLoader to ensure it finds everything
print("Scanning for PDFs in ./data...")
loader = PyPDFDirectoryLoader("./data")
documents = loader.load()

if not documents:
    print("❌ Error: No PDF files found in ./data. Double check your symlink!")
    exit()

print(f"Successfully loaded {len(documents)} pages.")

# 4. Chunk the text
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
docs = text_splitter.split_documents(documents)

# 5. Upload to Cloud
print(f"Uploading {len(docs)} chunks to Pinecone... (This might take a few minutes)")
vector_store = PineconeVectorStore.from_documents(
    docs, 
    embeddings, 
    index_name=INDEX_NAME
)

print("✅ Success! Your Photonics library is now live in the cloud.")