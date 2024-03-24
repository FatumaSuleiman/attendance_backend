




import requests
from dotenv import load_dotenv
load_dotenv('.env')
import os,sys


token_url = os.environ['PINDO_TOKEN_URL']

BASE_DIR= os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))
sys.path.append(BASE_DIR)

class PindoSMS():
    @staticmethod
    def get_pindo_token():

        # authorization=HTTPBasicAuth(settings.API_USER, settings.API_KEY)
        #authorization = (PINDO_USERNAME, settings.PINDO_PASSWORD)
        authorization = (os.environ['PINDO_USERNAME'], os.environ['PINDO_PASSWORD'])
        try:
            #
            r = requests.get(token_url,
                             auth=authorization,)
            print("This is the tocken")
            print(r.json)
            return r.json()
        except Exception as e:
            print(e)
        return None

    @staticmethod
    def sendSMS(to, text):
        token = PindoSMS.get_pindo_token()
        if not token is None:
            access_token = token['token']

            # print(authorization)
            try:
                headers = {'Authorization': 'Bearer ' + access_token}
                data = {'to': to, 'text': text, 'sender': os.environ['PINDO_SENDER']}
                url = os.environ['PINDO_SEND_URL']
                response = requests.post(url, json=data, headers=headers)
                print(response)
                print(response.json())

                return response.json()

            except ValueError as e:
                print(e)
                return None

        else:
            return None
