import requests
base_url = 'http://localhost:8080'
dag_id = 'council_review_worflow'

## get authentication payload ##
auth_payload = {"username":"airflow","password":"airflow"}
token_response = requests.post(f"{base_url}/auth/token",json=auth_payload)

print(token_response.json().get("access_token"))