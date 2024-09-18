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

```default
Can you generate 10 fictional products for a clothing store in JSON. The products have the fields name, description and price. 
```

For example:

```json
{ 
    "id": 10,
    "name": "Eco-Friendly T-Shirt",  
    "description": "A soft, organic green cotton t-shirt that's perfect for everyday wear.",  
    "price": 25.99,
    "image": "10.jpeg",
    "embedding": null
  },  
  {  
    "id": 11,
    "name": "Vintage Denim Jacket",  
    "description": "A classic denim jacket with a retro design and a modern fit.",  
    "price": 89.99,
    "image": "11.jpeg",
    "embedding": null
  }
  ```


For each item, put it into the `api/data/test.json` file and run the `seed_embeddings` function from an API call.
This will calculate the embeddings for each item that does not have an embedding field..

## Query Preparation Stage

When using vector search, you often want to combine the similarity (vector) search with a full-text search. This is because the vector search will return the most similar items, but you may want to filter these items based on a user's query.
Because user queries are often in natural language, you need to convert these queries into a form that can be used in a vector search. This is called the query preparation stage.

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



## Uploading images

### Azurite Storage Emulator

Download the [Azurite Storage Emulator](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite?tabs=visual-studio-code%2Cblob-storage) for VS Code. This is included in the DevContainer for this project.

### Azure Storage Accounts

Download the [Azure Storage Explorer](https://azure.microsoft.com/en-us/products/storage/storage-explorer/) and connect to the storage account.

## Common Errors

### Starting functions

```Azure.Core: Connection refused (127.0.0.1:10001). System.Net.Http: Connection refused (127.0.0.1:10001). System.Net.Sockets: Connection refused.```

This error occurs when the Azurite Storage Emulator is not running. Start the Blob Service and the Queue Service and try again.
