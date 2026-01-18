# /// script
# dependencies = [
#     "mcp",
#     "requests",
#     "datetime"
# ]
# ///


from mcp.server.fastmcp import FastMCP
import os
import datetime
import requests

###DIRECTORIES###
DIR = 'D:/mcp-playground/projectdata/'
STAGING_DIR = 'D:/mcp-playground/projectdata/stagingArea/'

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
def read_analyst_file(filename:str) -> dict[str,str | int]:
    '''
    Docstring for read_analyst_file
    
    :param filename: The actual filepath of the 
    :type filename: str
    :return: Description
    :rtype: dict[str, str | int]
    '''


if __name__ == "__main__":
    mcp.run(transport="stdio")