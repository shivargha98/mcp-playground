# /// script
# dependencies = [
#     "mcp",
#     "requests",
#     "datetime",
#     "pymongo"
# ]
# ///


from mcp.server.fastmcp import FastMCP
import os
import datetime
import requests
import pymongo
import json
import uuid

###DIRECTORIES###
DIR = 'D:/mcp-playground/projectdata/'
STAGING_DIR = 'D:/mcp-playground/projectdata/stagingArea/'
DRAFT_DIR = "D:/mcp-playground/projectdata/doneProcessing/"
mcp = FastMCP('mlops_control_center')


### TOOL1 : Check Nifi Staging area ###
@mcp.tool()
def check_nifi_staging_area() -> str:

    """
    Checks if the Nifi Staging folder has a new json file or not
    :rtype: str
    """
    if not os.path.exists(STAGING_DIR):
        return "Error : Directory doesnt exist"
    else:
        files_ = [f for f in os.listdir(STAGING_DIR) if f.endswith(".json")]
        if len(files_) > 0:
            return f"Found new files to process: {', '.join(files_)}"
        else:
            return f"No Files to process"
        
## TOOL2 : Read the analyst report ###
@mcp.tool()
def read_analyst_file(filename:str) -> dict[str,str | int | float]:
    '''
    Reads the content of the specific analyst file found in the staging area
    :param filename: The actual filepath of the analyst file, found in the stagingArea
    :type filename: str
    :return: Dictionary output (json file output)
    :rtype: dict[str, str | int]
    '''

    path = os.path.join(STAGING_DIR,filename)
    try:
        with open(path,'r') as file:
            data = json.load(file)
        return data
    except:
        return f"Error reading the file : {filename}"
    
## TOOL 3 : Saving the initial critique from claude##
@mcp.tool()
def save_initial_critique(
                          risk_score: int,
                          critique_summary: str):
    

    '''
    Function to save the Claude's critique and risk score of the analyst review    
    :param risk_score: Claude's risk score to the analyst review
    :type risk_score: int
    :param critique_summary: 4-5 line critique of the analyst review by Claude
    :type critique_summary: str
    '''
    try:
       
        structured_report = {
            "meta":{
                "timestamp":str(datetime.datetime.now().isoformat()),
            },

            "audit":{
                "risk_score":risk_score,
                "critique_summary":critique_summary
            }
            
        }

        save_filename = "analyst_review_draft_"+str(datetime.datetime.now().isoformat()).replace(":","_").replace(".","_")+".json"
        save_path = os.path.join(DRAFT_DIR,save_filename)
        with open(save_path,'w') as jfile:
            json.dump(structured_report,jfile,indent=3)

        return f"Success: Structured critique saved to {save_path}"

    except Exception as e:
        return f"Error saving the file, error : {e}"
    

## TOOL4 : Airflow LLM council ###
'''
Purpose:
Takes the files -> MongoDB updates -> Analysis of the critique with Gemini -> MongoDB update
'''
@mcp.tool()
def start_llm_council_reflection() -> str:

    '''
    Triggers an Airflow DAG which is an llm council reflecting on the analyst review
    :rtype: str
    '''

    try:
        
        base_url = 'http://localhost:8080'
        dag_id = 'council_review_workflow'

        ## get authentication payload ##
        auth_payload = {"username":"airflow","password":"airflow"}
        token_response = requests.post(f"{base_url}/auth/token",json=auth_payload)

        if token_response.status_code !=201:
            return f"Failed Authentication"
        access_token = token_response.json().get("access_token")
        
        #### Creating an unique id for the dag ###
        unique_id_dag = f"run_{uuid.uuid4().hex[:8]}"
        current_time = datetime.datetime.now(datetime.timezone.utc)
        future_time = current_time + datetime.timedelta(seconds=30)
        clean_timestamp = future_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        ## payload needs to have -> dag id, logical date ##
        payload_dag_run = {
            "dag_run_id": unique_id_dag,
            "logical_date": clean_timestamp,
            "conf":{}
        }

        ##DAG url endpoint setup##
        dag_trigger_url = f"{base_url}/api/v2/dags/{dag_id}/dagRuns"
        headers = {
            'Authorization':'Bearer ' + access_token,
            'Content-Type':'application/json'
        }

        response = requests.post(dag_trigger_url,
                                 headers=headers,
                                 json=payload_dag_run)

        if response.status_code == 200:
            return f"Pipeline has started executing, RunID : {unique_id_dag}, See Results in MongoDB"
        else:
            return f"Error {response.status_code} : {response.text}"

    except Exception as e:
        return f"Cannot Run Airflow DAG, error : {e}"

    

if __name__ == "__main__":
    mcp.run(transport="stdio")