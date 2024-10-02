import azure.functions as func
import logging
import json

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI
import os
import pathlib
from base64 import b64encode
from embeddings import fetch_embedding, fetch_computer_vision_image_embedding

client: AzureOpenAI
DEVELOPMENT = bool(int(os.getenv("DEVELOPMENT", 0)))

# Set to False if you don't have access to the Azure Computer Vision API
USE_COMPUTER_VISION = True

if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_KEY"):
    client = AzureOpenAI(
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY")
    )
    token_provider = None
else:
    azure_credential = AzureCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"))
    token_provider = get_bearer_token_provider(azure_credential,
        "https://cognitiveservices.azure.com/.default")
    client = AzureOpenAI(
        api_version="2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_ad_token_provider=token_provider
    )

completions_deployment = os.getenv("CHAT_DEPLOYMENT_NAME", "gpt-4o")
embeddings_deployment = os.getenv("EMBEDDINGS_DEPLOYMENT_NAME", "text-embedding-3-small")
vision_endpoint = os.getenv("VISION_ENDPOINT")
vision_api_key = os.getenv("VISION_API_KEY")

if not os.getenv("AZURE_COSMOS_CONNECTION_STRING"):
    from backends.local import search_products, search_images

    USE_COSMOSDB = False
else:
    from backends.azure_cosmos import search_products, search_images, \
                                      DEFAULT_DATABASE_NAME, DEFAULT_CONTAINER_NAME, \
                                      update_product, \
                                      DESCRIPTION_EMBEDDING_FIELD, IMAGE_EMBEDDING_FIELD

    USE_COSMOSDB = True

app = func.FunctionApp()


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
                Generate a full-text search query for a SQL database based on a user query. 
                Do not generate the whole SQL query; only generate string to go inside the MATCH parameter for FTS5 indexes. 
                Use SQL boolean operators if the user has been specific about what they want to exclude in the search.
                If the query is not in English, always translate the query to English.
                If you cannot generate a search query, return just the number 0.
            """
        },
        {   "role": "user",
            "content": f"Generate a search query for: A really nice winter jacket"
        },
        {  "role": "assistant",
            "content": "winter jacket"
        },
        {   "role": "user",
            "content": "Generate a search query for: 夏のドレス"
        },
        {   "role": "assistant",
            "content": "summer dress"
        },
        {
            "role": "user",
            "content": f"Generate a search query for: {query}"
        }],
        max_tokens=100, # maximum number of tokens to generate
        n=1, # return only one completion
        stop=None, # stop at the end of the completion
        temperature=0.3, # more predictable
        stream=False, # return the completion as a single string
        seed=1, # seed for reproducibility
    )
    search_query = completion.choices[0].message.content
    ### End of implementation
    return search_query


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
    embedding = fetch_embedding(client, embeddings_deployment, query)
    sql_results = search_products(query, fts_query, embedding)

    return func.HttpResponse(json.dumps({
        "keywords": fts_query,
        "results": [product.model_dump() for product in sql_results]
        }
    ))


@app.route(methods=['post'], auth_level="anonymous",
           route="match")
def match(req: func.HttpRequest) -> func.HttpResponse:
    """
    Matches the image upload with the product in the database with the closest embedding.
    """
    image = req.files.get('image_upload')
    max_items = req.form.get('max_items', 2)
    language = req.form.get('language', 'English')
    if not image:
        return func.HttpResponse(
            "{'error': 'Please pass an image in the request body'}",
            status_code=400
        )
    image_contents = image.stream.read()
    image_type = image.mimetype

    base64_image = b64encode(image_contents).decode('utf-8')

    # 1. Ask the model to describe the image
    description = client.chat.completions.create(
        model=completions_deployment,
        messages= [
        {
            "role": "system",
            "content": 
            f"""  
                Generate a text description the clothes worn by the person in the image.
                Write the response in {language}.
            """
        },
        {   
            "role": "user",
            "content": [
                { "type": "text", "content": "Describe the clothes in this image" },
                { "type": "image_url", "image_url": { "url": f"data:{image_type};base64,{base64_image}" } }
            ]
        }
        ],
        max_tokens=500, # maximum number of tokens to generate
        n=1, # return only one completion
        stop=None, # stop at the end of the completion
        temperature=0.3, # more predictable
        stream=False, # return the completion as a single string
        seed=1, # seed for reproducibility
    )
    image_description = description.choices[0].message.content

    embedding_source = req.form.get('embedding_source', 'image')

    if USE_COMPUTER_VISION and embedding_source == 'image':
        image_embedding = fetch_computer_vision_image_embedding(vision_endpoint, vision_api_key, token_provider, image_contents, image_type)
        sql_results = search_images(image_embedding)[:max_items]
    else:
        # Do a product search with the text embedding
        text_embedding = fetch_embedding(client, embeddings_deployment, image_description)
        sql_results = search_products(image_description, image_description, text_embedding)[:max_items]

    return func.HttpResponse(json.dumps({
        "keywords": image_description,
        "results": [product.model_dump() for product in sql_results],
        }))

if USE_COSMOSDB and False:
    @app.function_name(name="CosmosDBTrigger")
    @app.cosmos_db_trigger(arg_name="documents", 
                        connection="AZURE_COSMOS_CONNECTION_STRING", 
                        database_name=DEFAULT_DATABASE_NAME, 
                        container_name=DEFAULT_CONTAINER_NAME, 
                        lease_container_name="leases",
                        create_lease_container_if_not_exists="true")
    def update_embedding_for_document(documents: func.DocumentList) -> str:
        if documents:
            logging.info('Document id: %s', documents[0]['id'])
        
        for doc in documents:
            has_changes = False
            # Determine if the name or description has changed
            embedding = fetch_embedding(client, embeddings_deployment, doc['name'] + " " + doc['description'])
            if doc.get(DESCRIPTION_EMBEDDING_FIELD) != embedding:
                has_changes = True
                doc[DESCRIPTION_EMBEDDING_FIELD] = embedding
                logging.info(f"Updated embedding for {doc['name']}")

            if USE_COMPUTER_VISION:
                image_embedding = fetch_computer_vision_image_embedding(vision_api_key=vision_api_key,
                                                                        vision_endpoint=vision_endpoint,
                                                                        token_provider=token_provider,
                                                                        data=pathlib.Path("../html/images/products/") / doc['image'], 
                                                                        mimetype="image/jpeg")
                if doc.get(IMAGE_EMBEDDING_FIELD) != image_embedding:
                    has_changes = True
                    doc[IMAGE_EMBEDDING_FIELD] = image_embedding
                    logging.info(f"Updated image embedding for {doc['name']}")

            if has_changes:
                update_product(doc)

if DEVELOPMENT:
    from dev_functions import add_dev_functions

    add_dev_functions(app, client, completions_deployment, embeddings_deployment, vision_api_key, vision_endpoint, token_provider, USE_COMPUTER_VISION)
