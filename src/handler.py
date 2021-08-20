import json
from urllib.parse import urljoin

import boto3
import requests
from twilio.rest import Client


ssm = boto3.client("ssm")


def get_parameter(parameter_name: str):
    """
    Return value of the named parameter from SSM parameter store.
    """
    try:
        response = ssm.get_parameter(Name=parameter_name)
        return response["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        raise RuntimeError(
            f"Parameter {parameter_name} not found when calling the GetParameter operation",
        )


ROUTES = {
    "E4",
    "64",
}
BUS_STOPS = {
    "11TH_ST_IRVING_ST_NORTHBOUND": 1002008,
    "MISSOURI_AVE_2ND_ST_EASTBOUND": 1003900,
    "FORT_TOTTEN_STATION_BUS_BAY_K": 1003435,
    "NEW_HAMPSHIRE_AVE_1ST_ST_SOUTHBOND": 1002570,
}


class Wmata:
    BASE_URL = "https://api.wmata.com/"

    @property
    def headers(self):
        return {
            "api_key": self.api_key,
            "Accept": "application/json",
            "Connection": "keep-alive",
        }

    def __init__(self):
        self.api_key = get_parameter("/wmata/API_KEY")

    def get(self, resource, params):
        url = urljoin(self.BASE_URL, resource)
        response = requests.get(url, params, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_next_bus_prediction(self, stop_id):
        resource = "NextBusService.svc/json/jPredictions"
        return self.get(resource, {"StopID": stop_id})

    def get_bus_positions(self, route_id):
        """
        Returns bus positions for the given route, with an optional search radius. If no parameters are specified, all bus positions are returned.
        Note that the RouteID parameter accepts only base route names and no variations, i.e.: use 10A instead of 10Av1 or 10Av2.
        Bus positions are refreshed approximately every 20 to 30 7 to 10 seconds.
        """
        resource = "Bus.svc/json/jBusPositions"
        return self.get(resource, {"RouteID": route_id})

    def get_bus_stops(self):
        """
        Returns a list of nearby bus stops based on latitude, longitude, and radius. 
        Omit all parameters to retrieve a list of all stops.
        """
        resource = "Bus.svc/json/jStops"
        return self.get(resource)

    def get_schedule_at_stop(self):
        """
        Returns a set of buses scheduled at a stop for a given date.
        """
        raise NotImplementedError()

    def get_routes(self):
        """
        Returns a list of all bus route variants (patterns).
        For example, the 10A and 10Av1 are the same route, but may stop at slightly different locations.
        """
        raise NotImplementedError()

    def get_schedule(self):
        """
        Returns schedules for a given route variant for a given date.
        """
        raise NotImplementedError()

    def bus_stop_predictions(self):
        results = {}
        for stop_id in BUS_STOPS.values():
            response = self.get_next_bus_prediction(stop_id=stop_id)
            results[response["StopName"]] = [
                f"{prediction['Minutes']} minutes: {prediction['RouteID']} {prediction['DirectionText']}"
                for prediction in response["Predictions"]
                if prediction["RouteID"] in ROUTES
            ]
        return results


def main(event, context):
    print(event)
    message_from = event["queryStringParameters"]["From"]
    reply_to = event["queryStringParameters"]["To"]
    # body = event["queryStringParameters"]["Body"]
    twilio_account_sid = get_parameter("/twilio/ACCOUNT_SID")
    twilio_auth_token = get_parameter("/twilio/ACCOUNT_AUTH_TOKEN")
    twilio = Client(twilio_account_sid, twilio_auth_token)

    predictions = Wmata().bus_stop_predictions()
    body = ""
    for stop, items in predictions.items():
        body += f"{stop}\n"
        for item in items:
            body += f"{item}\n"
    message = twilio.messages.create(to=message_from, from_=reply_to, body=body)

    print(message.sid)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"success": True}),
        "isBase64Encoded": False,
    }


if __name__ == "__main__":
    # TODO: make a test event to use here.
    pass
