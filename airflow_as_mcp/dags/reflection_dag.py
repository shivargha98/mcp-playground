from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable
import logging
import os,json
from datetime import datetime,timedelta

DAG_ID = 'council_review_workflow'
BASE_DATA_PATH = '/opt/airflow/projectdata/'

default_args = {

    'owner':'shivargha',
    'retries':1,
    'retry_delay':timedelta(minutes=1),
    'start_date':datetime(2024,1,1)
}

dag =  DAG(
    DAG_ID,
    default_args = default_args,
    description = 'Gemini reflection pipeline',
    schedule = None,
    catchup = False,
    tags = ['mlops','gemini','mongo']
)
    
    ### Task 1 -> install the dependencies ###
task_install_deps = BashOperator(
        task_id = "install_dependencies",
        bash_command = "pip install pymongo langchain-google-genai langchain",
        dag= dag
    )


### Task 2 -> Reading a local file & push to mongo###
def push_data_mongo(**kwargs):

    '''
    Pushing data to our mongodb database        
    :param kwargs: ~ taskinstance cross comms data
    '''

    import pymongo

    ### Processing filenames ###
    doneProcessfilename = [i for i in os.listdir(os.path.join(BASE_DATA_PATH,'doneProcessing'))][0]
    stagedProcessfilename = [i for i in os.listdir(os.path.join(BASE_DATA_PATH,'stagingArea'))][0]

    with open(os.path.join(BASE_DATA_PATH,'doneProcessing')+'/'+doneProcessfilename,'r') as file:
        data1 = json.load(file)

    with open(os.path.join(BASE_DATA_PATH,'stagingArea')+'/'+stagedProcessfilename,'r') as jfile:
        data2 = json.load(jfile)

    ### Creating a new dictionary ###
    document = {'analyst_review':data1,
                'claude_critique':data2,
                'timestamp':str(datetime.now().isoformat())}
    
    ### Mongo Connections and push to database ###
    uri_mongo = Variable.get("MONGO_URI")
    mongo_client = pymongo.MongoClient(uri_mongo)
    db = mongo_client['analyst_reviews']
    collection = db["reviews"]

    inserted = collection.insert_one(document)
    print(f'Inserted to reviews collection : {inserted.inserted_id}')

    return str(inserted.inserted_id)


task_push_mongodb = PythonOperator(
    task_id = 'MongoPush1',
    python_callable = push_data_mongo,
     dag= dag
)


### Task 3 -> Reflection of the Claude critique ###
def reflection(**kwargs):
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage,AIMessage
    from langchain_core.prompts import ChatPromptTemplate

    ### Processing filenames ###
    doneProcessfilename = [i for i in os.listdir(os.path.join(BASE_DATA_PATH,'doneProcessing'))][0]

    ### loading of the json files ###
    with open(os.path.join(BASE_DATA_PATH,'doneProcessing')+'/'+doneProcessfilename,'r') as file:
        data1 = json.load(file)


    api_key = Variable.get('GOOGLE_API_KEY')
    llm_model = ChatGoogleGenerativeAI(model = 'gemini-2.0-flash',max_retries=2,api_key=api_key)

    document = {'analyst_review':data1}
    document_as_str = json.dumps(document)

    prompt_template = ChatPromptTemplate.from_template(
        '''
            You are a senior financial analyst, who looks at various reviews of stocks and critique the the analysis made by a
            junior analyst in 4-5 sentences, look for logical fallacies, biases and the missed analysis points.
            Review made by the Junior Analyst for a particular stock : {document_as_str}
        '''
    )

    chain = prompt_template | llm_model
    chain_response = chain.invoke({'document_as_str':document_as_str})
    response = chain_response.content

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.info("Response from gemini in reflection function: %s",response)

    return response


task_gemini_reflect = PythonOperator(
    task_id = 'gemini_reflection',
    python_callable = reflection,
     dag= dag
) 


### Task 4 -> Push to MongoDB ####

def push_final_mongodb(**kwargs):

    import pymongo

    ## task instance## ~ task instance && kwargs helps in pulling the data returned by previous function
    ti = kwargs['ti']
    ## get the reflection text ###
    reflection_text = ti.xcom_pull(task_ids = 'gemini_reflection') ## ~ getting the data from the reflection text ##

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.info("Response from gemini, final mongo push function:%s",reflection_text)

    ### Processing filenames ###
    doneProcessfilename = [i for i in os.listdir(os.path.join(BASE_DATA_PATH,'doneProcessing'))][0]
    stagedProcessfilename = [i for i in os.listdir(os.path.join(BASE_DATA_PATH,'stagingArea'))][0]

    with open(os.path.join(BASE_DATA_PATH,'doneProcessing')+'/'+doneProcessfilename,'r') as file:
        data1 = json.load(file)

    with open(os.path.join(BASE_DATA_PATH,'stagingArea')+'/'+stagedProcessfilename,'r') as jfile:
        data2 = json.load(jfile)

    ### Creating a new dictionary ###
    document = {'analyst_review':data1,
                'claude_critique':data2,
                'gemini_reflect':reflection_text,
                'timestamp':str(datetime.now().isoformat())}
    
    ### Mongo Connections and push to database ###
    uri_mongo = Variable.get("MONGO_URI")
    mongo_client = pymongo.MongoClient(uri_mongo)
    db = mongo_client['analyst_reviews']
    collection = db["council_review"]

    inserted = collection.insert_one(document)
    print(f'Inserted to reviews collection : {inserted.inserted_id}')

    return str(inserted.inserted_id)


task_mongo_final = PythonOperator(
    task_id = 'final_mongodb',
    python_callable = push_final_mongodb,
     dag= dag
)


### dependenices ###
task_install_deps >> task_push_mongodb >> task_gemini_reflect >> task_mongo_final