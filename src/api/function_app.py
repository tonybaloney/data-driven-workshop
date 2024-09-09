from typing import Optional
import azure.functions as func
import logging
import json

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import NOT_GIVEN, AzureOpenAI, NotGiven
import os

client: AzureOpenAI
DEVELOPMENT = os.getenv("DEVELOPMENT", True)

if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_KEY"):
    client = AzureOpenAI(
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY")
    )
else:
    azure_credential = AzureCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"))
    token_provider = get_bearer_token_provider(azure_credential,
        "https://cognitiveservices.azure.com/.default")
    client = AzureOpenAI(
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_ad_token_provider=token_provider
    )

completions_deployment = os.getenv("CHAT_DEPLOYMENT_NAME", "gpt-35-turbo")
embeddings_deployment = os.getenv("EMBEDDINGS_DEPLOYMENT_NAME", "text-embedding-ada-002")

if DEVELOPMENT:
    from backends.local import search_products
else:
    from backends.azure_cosmos import search_products

app = func.FunctionApp()

@app.blob_trigger(arg_name="imageblob", path="uploads",
                  connection="ImagesConnection") 
def image_trigger(imageblob: func.InputStream):
    logging.info(f"Python blob trigger function processing blob"
                f"Name: {imageblob.name}"
                f"Blob Size: {imageblob.length} bytes")
    # 1. Create an embedding from the file

    # 2. Save the embedding to the database

    # 3. Return the URL of the image and the embedding


def prep_search(query: str) -> str:
    """
    Generate a full-text search query for a SQL database based on a user question.
    Use SQL boolean operators if the user has been specific about what they want to exclude in the search.
    If the question is not in English, translate the question to English before generating the search query.
    If you cannot generate a search query, return just the number 0.
    """

    ### Start of implementation
    completion = client.chat.completions.create(
        model=completions_deployment,
        messages= [
        {
            "role": "system",
            "content": 
            """  
                Generate a full-text search query for a SQL database based on a user question. 
                Do not generate the whole SQL query; only generate string to go inside the MATCH parameter for FTS5 indexes. 
                Use SQL boolean operators if the user has been specific about what they want to exclude in the search.
                If the question is not in English, translate the question to English before generating the search query.
                If you cannot generate a search query, return just the number 0.
            """
        }, 
        {
            "role": "user",
            "content": f"Generate a search query for: {query}"
        }],
        max_tokens=100, # maximum number of tokens to generate
        n=1, # return only one completion
        stop=None, # stop at the end of the completion
        temperature=0.3, # more predictable
        stream=False # return the completion as a single string
    )
    search_query = completion.choices[0].message.content
    ### End of implementation
    return search_query

def fetch_embedding(input: str, dimensions: int | NotGiven = NOT_GIVEN, model: Optional[str] = embeddings_deployment) -> list[float]:
    embedding = client.embeddings.create(
        input=input,
        model=model,
        dimensions=dimensions
    )
    return embedding.data[0].embedding

@app.route(methods=["post"], auth_level="anonymous",
                    route="search")
def search(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")
    query = req.form.get('query')
    if not query:
        return func.HttpRequest(
            "{'error': 'Please pass a query on the query string or in the request body'}",
            status_code=400
        )

    fts_query = prep_search(query)

    embedding_model = req.form.get('embedding-model', 'text-embedding-ada-002')
    if embedding_model == 'text-embedding-ada-002':
        dimensions = NOT_GIVEN
        embedding_field = 'embedding'
    elif embedding_model == 'text-embedding-3-large':
        dimensions = 1024
        embedding_field = 'embedding_large'
    else:
        raise ValueError("Invalid embedding model")

    if req.form.get('similarity-mode', 'similarity-processed') == 'similarity-processed':
        embedding = fetch_embedding(fts_query, model=embedding_model, dimensions=dimensions)
    else:
        embedding = fetch_embedding(query, model=embedding_model, dimensions=dimensions)

    sql_results = search_products(query, fts_query, embedding, embedding_field)

    return func.HttpResponse(json.dumps({
        "keywords": fts_query,
        "results": [product.model_dump() for product in sql_results]
        }
    ))


@app.route(methods=["get"], auth_level="anonymous",
           route="seed_embeddings")
def seed_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    # Seed the embeddings for the products in the database by calling the OpenAI API
    with open('data/test.json') as f:
        data = json.load(f)
        for product in data:
            if 'embedding' not in product or product['embedding'] is None:
                product['embedding'] = fetch_embedding(product['name'] + ' ' + product['description'])

        # Write the embeddings back to the test data
        with open('data/test.json', 'w') as f:
            json.dump(data, f)
                
        return func.HttpResponse("Successfully seeded embeddings")

@app.route(methods=["get"], auth_level="anonymous",
           route="seed_embeddings_large")
def seed_large_embeddings(req: func.HttpRequest) -> func.HttpResponse:
    # Seed the embeddings for the products in the database by calling the OpenAI API
    with open('data/test.json') as f:
        data = json.load(f)
        for product in data:
            if 'embedding_large' not in product or product['embedding_large'] is None:
                product['embedding_large'] = fetch_embedding(product['name'] + ' ' + product['description'], dimensions=1024, model="text-embedding-3-large")

        # Write the embeddings back to the test data
        with open('data/test.json', 'w') as f:
            json.dump(data, f)
                
        return func.HttpResponse("Successfully seeded large embeddings")