import http.client
import json
from pathlib import Path

class Response:

    status = None
    reason = None
    data = None

    def __init__(self, res):
        if (res.status == 200):
            try:
                self.data = json.loads(res.read().decode("utf-8"))
            except Exception:
                pass
        
        self.status = res.status
        self.reason = res.reason

class Api:

    isProd = False
    accessToken = None
    baseUrl = None
        
    def __init__(self):
        configFile = (Path(__file__).parent / "config2.json").resolve()
        with open(configFile, "r") as f:
            config = json.load(f)

            self.isProd = config["isProd"]
            self.baseUrl = config["api"]["url"]

            payload = json.dumps({
                "email": config["api"]["email"],
                "password": config["api"]["password"]
            })
            
            headers = {
                "content-type": "application/json"
            }

            conn = http.client.HTTPSConnection(self.baseUrl) if self.isProd else http.client.HTTPConnection(self.baseUrl)
            conn.request("POST", "/api/user/token", payload, headers)
            res = conn.getresponse()

            if res.status != 200:
                raise Exception(f"Could not authenticate. Response: {res.status} - {res.reason}")

            data = json.loads(res.read().decode("utf-8"))
            self.accessToken = data["token"]

            if self.accessToken == None:
                raise Exception("Could not get access token.")
        

    def get(self, endpoint):
        headers = {
            "content-type": "application/json",
            "Authorization": self.accessToken
        }

        conn = http.client.HTTPSConnection(self.baseUrl) if self.isProd else http.client.HTTPConnection(self.baseUrl)
        conn.request("GET", endpoint, None, headers)
        res = conn.getresponse()
        return Response(res)

    def post(self, endpoint, request):
        headers = {
            "content-type": "application/json",
            "Authorization": self.accessToken
        }

        conn = http.client.HTTPSConnection(self.baseUrl) if self.isProd else http.client.HTTPConnection(self.baseUrl)
        conn.request("POST", endpoint, json.dumps(request), headers)
        res = conn.getresponse()
        return Response(res)
