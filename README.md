# Data Driven AI Workshop

# Pre-requisites

1. Python 3.11(Required)
2. Github account (Required)
3. Docker Desktop
4. An editor  – Vscode 
[Download Visual Studio Code](https://code.visualstudio.com/Download)
5. DevContainer Extension
In the Visual Studio Code extensions view search for "Dev Containers" in search box and click on "Install" button
6. Azure subscription  (Good to have) 

## Running the App within the DevContainer
1. Clone the project
```dotnetcli
git clone https://github.com/tonybaloney/data-driven-workshop.git

```
2. Start the Dev container
    a. Open a New Window in Visual Studio Code
    b. Open the folder data-driven-workshop . Visual Studio Code will then build the Docker image specified in your .devcontainer/Dockerfile and start a container with the configuration specified in your .devcontainer/devcontainer.json file. Once the container is running, your project will be opened inside the container, and you can start working with it as if it were running locally.
    
  ```dotnetcli
  cd /workspaces/data-driven-workshop
  ```
3. Create Python virtual Environment
```dotnetcli
    python -m venv .venv   
    source .venv/bin/activate 
```

4. Install the required python packages
```dotnetcli
pip install -r src/api/requirements.txt
```

5. Update local.settings.json file to integrate OpenAI models with backend app

```dotnetcli
  {  "IsEncrypted": false,  "Values": {   
     "AzureWebJobsStorage": "UseDevelopmentStorage=true",    
     "FUNCTIONS_WORKER_RUNTIME": "python",    
     "ImagesConnection": "UseDevelopmentStorage=true",    
     "AzureWebJobsFeatureFlags": "EnableWorkerIndexing",    
     "AZURE_OPENAI_ENDPOINT": "<Insert openAI endpoint>",
     "AZURE_OPENAI_KEY": "<Insert openAI key>",    
     "CHAT_DEPLOYMENT_NAME": "gpt-4o-mini",    
     "EMBEDDINGS_DEPLOYMENT_NAME": "text-embedding-3-small"
      },  
      "Host": {    
        "CORS": "*" 
     }
    }
```

5. Run the web server and start the backend function host server
```dotnetcli
make runserver
```


## Running the web server outside DevContainer

```console
npm install -g http-server
```

```console
http-server src/html
```

## Running the API (Functions Host)

The easiest way to run the functions host is from VS Code.

Click on Run and Debug and launch the "Attach to Python Functions" launch task.

## Running the API (console)

To launch the functions host from the CLI, run the following command:

```console
func host start
```

## Making test data

This solution comes with over 150 items in a test database. These items are all clothing for a fictional clothing store and were generated using GPT-4o. Each item has has an image, the embedding of the text for text-embedding-3-small and the text for the item.

For example, the 40th product in the database is:

```json
  "name": "Amber Glow Sweater",
  "description": "A cozy, amber orange sweater with a chunky knit design. Ideal for keeping warm during autumn and winter.",
  "price": 59.99,
```

With the image created by DALL-e 3:

![](src/html/images/products/40.jpeg

You can generate additional products by using the `/api/generate_test_data` endpoint. This will generate a new product using GPT-4o and add it to `src/api/data/test.json`.

If you want different types of test products, you can customize the prompt. The prompt is currently set to:

```default
Generate some test data in JSON. The data is for a clothing store. You should generate a 
list of products with the following fields: name, description, and price.
name: The name of the product, e.g. "The Ultimate Winter Jacket". Be creative with names. 
description: A two sentence description of the product with the color and some adjectives, e.g. "A forest green winter jacket. Ideal for autumn and winter. Made from 100% cotton."
price: The price of the product, e.g. 49.99
```

You can then pre-populate the `embeddings` field with the embeddings generated by the `text-embedding-3-small` model. This will allow you to use the vector search feature with the new products. The `/api/generate_embeddings` endpoint automates this process. 

This sample comes with pre-calculated embeddings.

## Query Preparation Stage

When using vector search, you often want to combine the similarity (vector) search with a full-text search. This is because the vector search will return the most similar items, but you may want to filter these items based on a user's query.
Because user queries are often in natural language, you need to convert these queries into a form that can be used in a vector search. This is called the query preparation stage.

Vector Search is also more effective when the user query is translated to the same language as the items in the database. This is because the embeddings are trained on a specific language, and the embeddings will be more accurate if the query is in the same language. Vector similarity will still work across languages, but the similarity scores will be higher for text in the same language.

GPT models are good at extracting keywords from a user query, and you can use these keywords to search for similar items in a vector search. Here are some example prompts. Use the AI Playground to test your system prompt and try different prompts to see how well it works.

### Example prompts

#### Basic

```default
Extract the keywords from the user query.
```

#### Better

Specify that the AI converts the user query into English (or the target language) and extracts the keywords.

```default
Translate the user query to English and extract the keywords.
```

#### Best

When developing the prompt, specify that the AI should use the keywords to generate a search query for a vector search.
Specify the Full-Text Search (FTS) query type that should be generated.
Tell the AI to return 0 if it cannot generate a search query.

```default
Generate a full-text search query for a SQL database based on a user question. 
Do not generate the whole SQL query; only generate string to go inside the MATCH parameter for FTS5 indexes. 
Use SQL boolean operators if the user has been specific about what they want to exclude in the search, only use the AND operator for nouns, for descriptive adjectives use OR.
If the question is not in English, translate the question to English before generating the search query.
If you cannot generate a search query, return just the number 0.
```

### Improving the prompt with few-shot learning

You can improve the prompt by providing examples of the user query and the expected output. This is called few-shot learning.

```default
Generate a full-text search query for a SQL database based on a user question.
Do not generate the whole SQL query; only generate string to go inside the MATCH parameter for FTS5 indexes.
Use SQL boolean operators if the user has been specific about what they want to exclude in the search, only use the AND operator for nouns, for descriptive adjectives use OR.
If the question is not in English, translate the question to English before generating the search query.
If you cannot generate a search query, return just the number 0.
```

#### Examples

```default
User query: "What are the best restaurants in Paris?"
Expected output: "best restaurants Paris"
```

```default
User query: "What are the best restaurants in Paris that serve vegan food?"
Expected output: "best restaurants Paris vegan"
```

```default
User query: "What are the best restaurants in Paris that serve vegan food but are not too expensive?"
Expected output: "best restaurants Paris vegan expensive"
```

When providing examples, use the GPT API to give a history of the conversation, for example:

```python
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
    temperature=0.3, # more predictable (less random) completions
    stream=False, # return the completion as a single string
)
search_query = completion.choices[0].message.content
```

## Adding Cosmos DB support

See [Enroll in the Vector Search Preview Feature](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/vector-search#enroll-in-the-vector-search-preview-feature) for details on how to enable the Vector Search feature in Cosmos DB.

## Azure Computer Vision Support

This sample comes with optional support for the [Florence Model in Azure Computer Vision](https://azure.microsoft.com/en-us/blog/announcing-a-renaissance-in-computer-vision-ai-with-microsofts-florence-foundation-model/?msockid=12cb358a5eb267762fff21695f5066a3). The Florence model is an embedding model specifically for images.

In the "Match my Outfit" feature of this sample, you have two options for finding the best matching outfit:

1. Generating a text description of the image using GPT-4o's vision support, then using a similarity search of the text embeddings.
2. Using the Florence model to generate an embedding of the image and using a similarity search of the image embeddings.

There are benefits to using the Florence model which can be seen by uploading an image with multiple characteristics.

For example, the test image of a woman wearing a Denim jacket and a green backpack:

![](/tests/test%20images/woman-2564660_1280.jpg)

For GPT-4o text descriptions, the description will include the woman, the fluffy chain, the denim jacket, and the green backpack. The similarity search will return items that are similar to the text description. But, this will include mostly denim products.

For the Florence model, the image will be embedded and the similarity search will return items that are visually similar to the image. This will include a denim jacket first and then a green backpack second.

This demonstrates how the Florence model is better at finding multiple characteristics in an image, while GPT-4o embeddings are finding the most prominent characteristic.

## Uploading images

### Azurite Storage Emulator

Download the [Azurite Storage Emulator](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite?tabs=visual-studio-code%2Cblob-storage) for VS Code. This is included in the DevContainer for this project.

### Azure Storage Accounts

Download the [Azure Storage Explorer](https://azure.microsoft.com/en-us/products/storage/storage-explorer/) and connect to the storage account.

## Common Errors

### Starting functions

```Azure.Core: Connection refused (127.0.0.1:10001). System.Net.Http: Connection refused (127.0.0.1:10001). System.Net.Sockets: Connection refused.```

This error occurs when the Azurite Storage Emulator is not running. Start the Blob Service and the Queue Service and try again.
