import streamlit as st
from pymongo import MongoClient 
import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
import uuid
import tempfile
from pathlib import Path
from langchain.document_loaders import PyPDFLoader, Docx2txtLoader
from azure.search.documents.indexes.models import SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField, VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration, AzureOpenAIVectorizer,AzureOpenAIVectorizerParameters
from azure.search.documents.indexes import SearchIndexClient

# Set page configuration
st.set_page_config(layout="wide")

if "sql_client" not in st.session_state:
    st.session_state.sql_client = MongoClient(os.environ['PYMONGO_CONNECTION_STRING'])

chatbot_db = st.session_state.sql_client['chatbot']  # Use the chatbot database
context_collection = chatbot_db['chatbot_context']

def context_uploader_page():

    st.title("Chatbot customisation")
    # Create tabs for different file formats
    context_tab, information_tab, notes_tab = st.tabs(["Upload Context Tab", "Upload Information Tab", "Upload Notes Tab"])

    with context_tab:
        st.markdown("### **🔒 Enter Your Chatbot Context here:**")

        st.info("""
        ### **Why define a context?**
                        
        Your chatbot will only respond to topics within the context you define.\n
        This ensures users cannot ask unrelated questions.

        📌 **How to Specify the Context?**
        Enter a short phrase describing the chatbot’s domain and scope:

        **Format:**  
        📍 `[Industry/Field] [Main Focus] [Relevant Topics]`

        ✅ **Examples**:
        - **Healthcare**: "hospital patient admission and medical records management"
        - **Retail**: "e-commerce fashion inventory and customer support"
        - **Education**: "university course registration and student academic records"
        """)

        if "context_success" not in st.session_state:
            st.session_state.context_success = False  # Initialize session state variable

        if "chatbot_context" not in st.session_state:
            existing_context = context_collection.find_one({}, {"_id": 0, "context": 1}) or {}
            st.session_state.chatbot_context = existing_context.get("context", "")
        
        st.write("**This is the current context:**", st.session_state.chatbot_context)
        context_phrase = st.text_input("Context", label_visibility="collapsed")

        if st.button("Save Context"):
            new_context = context_phrase.strip()
            if new_context and new_context != st.session_state.chatbot_context:
                if st.session_state.chatbot_context:
                    # Update existing context
                    context_collection.update_one({}, {"$set": {"context": new_context}})
                else:
                    # Insert a new context if it doesn't exist
                    context_collection.insert_one({"context": new_context})

                # Update session state
                st.session_state.chatbot_context = new_context
                st.session_state.context_success = True
                st.rerun()  # Force rerun for immediate UI update

        # Show success message after rerun
        if st.session_state.context_success:
            st.success("✅ Context updated successfully!")

        

    with information_tab:
        st.markdown("### **🔒 Upload information context for the chatbot here:**")

        st.info("""
        ### **Why upload documents?**
        
        This feature allows you to provide your own context to the chatbot. 
                
        Upload documents containing:
        
        • Personal or business FAQs
        • Company policies or procedures
        • Product information
        • Specialized knowledge not available to the general AI
        
        The chatbot will use this information to provide personalized responses based on your uploaded content. Without these documents, the chatbot won't have access to your specific information.
        
        Simply upload your files and click "Process Files" to enhance the chatbot with your context.
        """)

         # Store uploaded file in session state
        if "uploaded_information_file" not in st.session_state:
            st.session_state.uploaded_information_file = None

        uploaded_information_files = st.file_uploader(
            "Choose files",
            type=["pdf", "docx"],
            help="Supported formats: PDF, Word",
            accept_multiple_files=True,  # Allow multiple files
            key="information_uploader"
        )

        if uploaded_information_files:
            st.session_state.uploaded_information_files = uploaded_information_files

            if st.button("Process Files"):
                # Create a placeholder for status messages
                status_text = st.empty()
                # Create a progress bar
                progress_bar = st.progress(0)
                
                documents = []
                temp_dir = tempfile.TemporaryDirectory()
                try:
                    total_files = len(uploaded_information_files)
                    
                    # Process each uploaded file
                    for i, file in enumerate(uploaded_information_files):
                        # Update progress text and bar
                        progress_value = (i) / total_files
                        status_text.text(f"Processing file {i+1} of {total_files}: {file.name}")
                        progress_bar.progress(progress_value)
                        
                        # Save to temporary file
                        temp_path = os.path.join(temp_dir.name, file.name)
                        with open(temp_path, "wb") as f:
                            f.write(file.getbuffer())
                            
                        # Load document based on file type
                        if file.name.endswith(".pdf"):
                            loader = PyPDFLoader(temp_path)
                        elif file.name.endswith(".docx"):
                            loader = Docx2txtLoader(temp_path)
                        else:
                            continue
                            
                        loaded_docs = loader.load()
                        
                        # Add source metadata
                        for doc in loaded_docs:
                            doc.metadata['source'] = file.name
                        documents.extend(loaded_docs)
                    
                    # Update status for index operations
                    status_text.text("Preparing document index...")
                    progress_bar.progress(0.8)
                    
                    delete_index(index_name="course_info")
                    create_index(index_name="information", embedding_dimension=1536)
                    
                    # Update status for final processing
                    status_text.text("Adding documents to index...")
                    progress_bar.progress(0.9)
                    
                    # Call your document processing function
                    result = add_or_update_docs(
                        documents=documents,
                        index_name="information"  # Replace with your actual index name
                    )
                    
                    # Complete the progress bar
                    progress_bar.progress(1.0)
                    
                    if result is True:
                        status_text.text("Processing complete!")
                        st.success("Files processed successfully!")
                    else:
                        st.error(f"Error processing files: {result}")
                finally:
                    temp_dir.cleanup()
                    st.balloons()
                    

    with notes_tab:
        st.markdown("### **🔒 Upload extra notes for your chatbot here:**")

        st.info("""
        ### **Enhance Your Conversations with Notes & Documents**

        Upload any text-based materials to provide additional context for the chatbot:

        - Study notes and learning materials
        - Research papers and articles 
        - Books and published content
        - Meeting notes or presentations
        - Project documentation
        - Any text you want the chatbot to reference

        Adding these documents helps the chatbot provide more relevant and informed responses based on your specific materials. The chatbot will reference these documents when answering your questions, making conversations more productive and tailored to your needs.

        Simply upload your files and click "Process Files" to get started.
        """)

        uploaded_notes_files = st.file_uploader(
            "Choose files",
            type=["pdf", "docx"],
            help="Supported formats: PDF, Word",
            accept_multiple_files=True,  # Allow multiple files
            key="notes_uploader"
        )

        if uploaded_notes_files:
            st.session_state.uploaded_notes_files = uploaded_notes_files

            if st.button("Process Note Files"):
                # Create a placeholder for status messages
                status_text = st.empty()
                # Create a progress bar
                progress_bar = st.progress(0)
                
                documents = []
                temp_dir = tempfile.TemporaryDirectory()
                try:
                    total_files = len(uploaded_notes_files)
                    
                    # Process each uploaded file
                    for i, file in enumerate(uploaded_notes_files):
                        # Update progress text and bar
                        progress_value = (i) / total_files
                        status_text.text(f"Processing file {i+1} of {total_files}: {file.name}")
                        progress_bar.progress(progress_value)
                        
                        # Save to temporary file
                        temp_path = os.path.join(temp_dir.name, file.name)
                        with open(temp_path, "wb") as f:
                            f.write(file.getbuffer())
                            
                        # Load document based on file type
                        if file.name.endswith(".pdf"):
                            loader = PyPDFLoader(temp_path)
                        elif file.name.endswith(".docx"):
                            loader = Docx2txtLoader(temp_path)
                        else:
                            continue
                            
                        loaded_docs = loader.load()
                        
                        # Add source metadata
                        for doc in loaded_docs:
                            doc.metadata['source'] = file.name
                        documents.extend(loaded_docs)
                    
                    # Update status for index operations
                    status_text.text("Preparing document index...")
                    progress_bar.progress(0.8)
                    
                    delete_index(index_name="course_info")
                    create_index(index_name="notes", embedding_dimension=1536)
                    
                    # Update status for final processing
                    status_text.text("Adding documents to index...")
                    progress_bar.progress(0.9)
                    
                    # Call your document processing function
                    result = add_or_update_docs(
                        documents=documents,
                        index_name="notes"  # Replace with your actual index name
                    )
                    
                    # Complete the progress bar
                    progress_bar.progress(1.0)
                    
                    if result is True:
                        status_text.text("Processing complete!")
                        st.success("Files processed successfully!")
                    else:
                        st.error(f"Error processing files: {result}")
                finally:
                    temp_dir.cleanup()
                    st.balloons()

def add_or_update_docs(documents, index_name):
    try:

        embeddings = AzureOpenAIEmbeddings(azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'], 
                                   api_key=os.environ['AZURE_OPENAI_APIKEY'], 
                                   model=os.environ['TEXT_EMBEDDING_MODEL_NAME'],
                                   azure_deployment=os.environ['TEXT_EMBEDDING_DEPLOYMENT_NAME'])

        search_client = SearchClient(
            endpoint=os.environ.get('AZURE_AI_SEARCH_ENDPOINT'), 
            index_name=index_name, 
            credential= AzureKeyCredential(os.environ.get('AZURE_AI_SEARCH_API_KEY'))
        )

        text_splitter = CharacterTextSplitter(chunk_size= 1500, chunk_overlap=500)
        
        # List to store all the docs that need to be added
        docs_to_add_final = []

        # List to store all the docs that need to be updated
        docs_to_update_final = []

        # Loop to separate the docs that need to be updated from the docs that need to be added
        for doc in documents:
            filename = Path(doc.metadata['source']).name
            search_results = list(search_client.search(filter=f"filename eq '{filename}'"))
            split_docs = text_splitter.split_documents([doc])

            if search_results:
                print("update!")
                docs_to_update_id = [result['id'] for result in search_results] 
                docs_to_update_page_content = [sdoc.page_content for sdoc in split_docs] 
                docs_to_update_embeddings = embeddings.embed_documents(docs_to_update_page_content) 

                for i, sdoc in enumerate(split_docs):
                    docs_to_update_final.append({
                        'id': docs_to_update_id[i],
                        'content': sdoc.page_content,
                        'content_vector': docs_to_update_embeddings[i],
                        'filename': filename
                    })
            else:
                print("add!")
                docs_to_add_page_content = [sdoc.page_content for sdoc in split_docs]
                docs_to_add_embeddings = embeddings.embed_documents(docs_to_add_page_content)

                for i, sdoc in enumerate(split_docs):
                    docs_to_add_final.append({
                        'id': str(uuid.uuid4()),
                        'content': sdoc.page_content,
                        'content_vector': docs_to_add_embeddings[i],
                        'filename': filename
                    })

        if docs_to_update_final:
            search_client.merge_documents(docs_to_update_final)

        if docs_to_add_final:
            search_client.upload_documents(docs_to_add_final)

        return True

    except Exception as e:
        print(f"An error occurred: {e}")
        return e
    
def create_index(index_name, embedding_dimension):
    try:
        # Defines instance of SearchIndexClient class
        search_index_client = SearchIndexClient(
            os.environ.get('AZURE_AI_SEARCH_ENDPOINT'), 
            AzureKeyCredential(os.environ.get('AZURE_AI_SEARCH_API_KEY'))
        )
        
        # Defines the structure of the search index
        fields = [
            # Basic indexing
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
                retrievable=True,
                stored=True,
                sortable=False,
                facetable=False
            ),
            # Main content field
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=False,
                retrievable=True,
                stored=True,
                sortable=False,
                facetable=False
            ),
            # Filename
            SearchableField(
            name="filename",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
            ),
            # Content embeddings vector
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=embedding_dimension,  # Use the same embedding dimension
                vector_search_profile_name="myHnswProfile"
            )
        ]

        # Configure the vector search configuration  
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="myHnsw"
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="myHnswProfile",
                    algorithm_configuration_name="myHnsw",
                    vectorizer_name="myVectorizer"
                )
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name="myVectorizer",
                    parameters=AzureOpenAIVectorizerParameters(
                        resource_url=os.environ.get('AZURE_OPENAI_ENDPOINT'),
                        api_key=os.environ.get('AZURE_OPENAI_APIKEY'),
                        model_name=os.environ.get('TEXT_EMBEDDING_MODEL_NAME'),
                        deployment_name=os.environ.get('TEXT_EMBEDDING_DEPLOYMENT_NAME')
                    )
                )
            ]
        )

        # Define the search index
        searchindex = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
        search_index_client.create_or_update_index(index=searchindex)
        return index_name
    except Exception as e:
        print(f"Error creating index: {e}")
        return None
    
def delete_index(index_name):
    search_index_client = SearchIndexClient(os.environ.get('AZURE_AI_SEARCH_ENDPOINT'), 
                                   AzureKeyCredential(os.environ.get('AZURE_AI_SEARCH_API_KEY')))
    try:
       search_index_client.delete_index(index_name)
       return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

context_uploader_page()