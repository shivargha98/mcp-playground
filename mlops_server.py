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
    





    

if __name__ == "__main__":
    mcp.run(transport="stdio")