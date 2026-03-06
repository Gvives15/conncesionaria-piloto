import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("Error: OPENAI_API_KEY not found in environment variables.")
    exit(1)

def fetch_logs():
    print("Attempting to fetch logs from OpenAI API...")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 4. Try Audit Logs (as hinted by user context)
    # Note: This usually requires an Admin API Key, not a standard User/Project Key.
    # And it returns administrative events (login, key creation), not chat content.
    print("\n--- Trying GET /v1/organization/audit_logs ---")
    url_audit = "https://api.openai.com/v1/organization/audit_logs"
    
    try:
        response = requests.get(url_audit, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Success! Audit logs retrieved.")
            # print("Response: ", json.dumps(data, indent=2)) 
            
            output_file = "openai_audit_logs.jsonl"
            with open(output_file, 'w', encoding='utf-8') as f:
                if 'data' in data and isinstance(data['data'], list):
                     for item in data['data']:
                        f.write(json.dumps(item) + '\n')
                     print(f"Saved {len(data['data'])} records to {output_file}")
                else:
                    f.write(json.dumps(data) + '\n')
                    print(f"Saved raw response to {output_file}")
        else:
            print("Response: ", response.text)
            if response.status_code in [401, 403]:
                print("\nNote: Accessing Audit Logs typically requires an 'Admin API Key' and an Enterprise/Organization account.")
                print("Your current key might be a standard Project/User key.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_logs()
