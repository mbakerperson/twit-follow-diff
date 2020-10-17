from flask import (
    Blueprint, render_template, request
)
import os
import requests

from .errors import NotAuthorizedForUserError

bp = Blueprint('follow_diff', __name__)

HATERS_TYPE = 'haters'
VICTIMS_TYPE = 'victims'
FOLLOWERS_KEY = "followers"
FRIENDS_KEY = "friends"
BASE_TEMPLATE = 'base.html'
RESULT_TEMPLATE = 'result.html'
MAX_ACCOUNT_NUM = 5000


@bp.route("/")
def index():
    return render_template(BASE_TEMPLATE)


@bp.route("/diff")
def diff():
    username = request.args.get('username')
    type = request.args.get('type')
    errors = []

    # validate parameters
    if not username:
        errors.append("Username is required")
    if not type:
        errors.append("Type is required.")
    elif type != HATERS_TYPE and type != VICTIMS_TYPE:
        errors.append("Invalid account type.")
    if len(errors) > 0:
        return render_template(BASE_TEMPLATE, errors=errors)

    # Retrieve friends and followers from twitter api
    try:
        friends_and_followers = get_friends_and_followers(username)
    except NotAuthorizedForUserError as notAuthExec:
        return render_template(BASE_TEMPLATE, errors=[notAuthExec.message])

    # Render error if we reach our account number limit
    if len(friends_and_followers[FRIENDS_KEY]) >= MAX_ACCOUNT_NUM:
        errors.append("Unable to retrieve all the accounts this one follows. Results likely inaccurate.")
    if len(friends_and_followers[FOLLOWERS_KEY]) >= MAX_ACCOUNT_NUM:
        errors.append("Unable to retrieve all the followers of this account. Results likely inaccurate.")

    # Render appropriate list according to input type
    if type == HATERS_TYPE:
        they_hate_you = list(set(friends_and_followers[FRIENDS_KEY]) - set(friends_and_followers[FOLLOWERS_KEY]))
        return render_template(RESULT_TEMPLATE, username=username, result=get_user_list(they_hate_you), errors=errors)
    elif type == VICTIMS_TYPE:
        you_hate_them = list(set(friends_and_followers[FOLLOWERS_KEY]) - set(friends_and_followers[FRIENDS_KEY]))
        return render_template(RESULT_TEMPLATE, username=username, result=get_user_list(you_hate_them), errors=errors)


# TODO: use dot env to load this instead
# To set your enviornment variables in your terminal run the following line:
# export 'BEARER_TOKEN'='<your_bearer_token>'
def get_bearer_token_header():
    headers = {"Authorization": "Bearer {}".format(os.environ.get("BEARER_TOKEN"))}
    return headers


# there's probably a client for this but mehhh
def get_account_list(account_type, display_name):
    # just grabbing ids cuz it's simpler to run the diff + fewer requets needed to get all the users
    url = "https://api.twitter.com/1.1/{}/ids.json?screen_name={}".format(account_type, display_name)
    print("Requesting {} for user: {}".format(account_type, display_name))

    response = requests.request("GET", url, headers=get_bearer_token_header())
    if response.status_code == 401:
        print(response.text)
        raise NotAuthorizedForUserError(
            display_name, "Not authorized to receive {} for user: {}".format(account_type, display_name)
        )
    elif response.status_code != 200:
        raise Exception(
            "Request returned an error: {} {}".format(
                response.status_code, response.text
            )
        )
    response_json = response.json()
    return response_json["ids"]


def get_friends_and_followers(username):
    return {
        FOLLOWERS_KEY: get_account_list(FOLLOWERS_KEY, username),
        FRIENDS_KEY: get_account_list(FRIENDS_KEY, username)
    }


def get_user_info(user_ids):
    user_fields = "description,profile_image_url"
    url = "https://api.twitter.com/2/users?ids={}&user.fields={}".format(user_ids, user_fields)
    response = requests.request("GET", url, headers=get_bearer_token_header())
    if response.status_code != 200:
        raise Exception(
            "Request returned an error: {} {}".format(
                response.status_code, response.text
            )
        )
    return response.json()["data"]


# user info api only allows 100 user ids at a time, divide into chunks and pass
def divide_into_chunks(user_ids, chunk_size=100):
    for i in range(0, len(user_ids), chunk_size):
        yield user_ids[i:i+chunk_size]


def get_user_list(user_list):
    chunks = list(divide_into_chunks(user_list))
    data = []
    for chunk in chunks:
        chunk_string = ",".join(str(id) for id in chunk)
        data += get_user_info(chunk_string)
    return {'accounts': data}