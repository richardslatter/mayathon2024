# read refresh_token from .env

# POST /api/v3/oauth/internal/token/refresh?client_id=2&client_secret=3bf7cfbe375675dd9329e9de56d046b4f02a186f&grant_type=refresh_token&refresh_token={refresh_token}
# response = 
# {
#   "access_token": "xxxxxx",
#   "expires_at": 1714322040,
#   "expires_in": 4893,
#   "refresh_token": "zzzzz"
# }

# keep access token, save refresh token as latest_refresh_token in .env
# try catch every http call after this, refresh access token, then try again 3 times


## MEMBERS THREAD, RUN ONCE EVERY 5 MINS

# GET /api/v3/clubs/Mayathon24/members HTTP/1.1
# Authorization: Bearer {access_token}
# response = 
# [
#   {
#     "id": 27915608,
#     "firstname": "Richard",
#     "lastname": "Slatter",
#     "city": "Brisbane",
#     "profile_medium": "https://graph.facebook.com/534637463586558/picture?height=256&width=256",
#     *other stuff*
#   },
#   {
#     "id": 18902757,
#     "firstname": "Alexandra",
#     "lastname": "Malec",
#     ....
#   }
#   ...
# ]

# save to members.json


## ACTIVITIES THREAD, RUN ONCE EVERY 2 MINS OR ON REFRESH

# read members.json

# for each member, pull activities

# GET /api/v3/feed/athlete/31923513 HTTP/1.1
# Authorization: Bearer {access_token}
# response =
# [
#   {
#     "item": {
#       "id": 10894455532,
#       "name": "Evening Run",
#       "type": "Run",
#       "distance": 2536.5,
#       "start_date": "2024-03-05T10:40:10Z",
#       *other stuff*
#     }
#     ...}
#     ...
# ]

# add missing activities for that member to activities.json

import threading
import requests
import json
from dotenv import load_dotenv
import os
import time
from flask import Flask, render_template
import pytz
from datetime import datetime

app = Flask(__name__)

members = []
all_activities = {}
total_distances = {}
pulling = True

def refresh_access_token():
    try:
        refresh_token = os.getenv("refresh_token")
        client_id = 2
        client_secret = "3bf7cfbe375675dd9329e9de56d046b4f02a186f"
        url = f"http://www.strava.com/api/v3/oauth/internal/token/refresh?client_id={client_id}&client_secret={client_secret}&grant_type=refresh_token&refresh_token={refresh_token}"
        response = requests.post(url)
        data = response.json()
        os.environ["access_token"] = data["access_token"]
        os.environ["refresh_token"] = data["refresh_token"]
        print("Access token refreshed:", datetime.now(pytz.timezone('Australia/Brisbane')))
    except Exception as e:
        print("Error while refreshing access token:", e, datetime.now(pytz.timezone('Australia/Brisbane')))

def get_members():
    global members
    retries = 3
    while retries > 0:
        access_token = os.getenv("access_token")
        url = f"http://www.strava.com/api/v3/clubs/Mayathon24/members"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            break

        refresh_access_token()
        retries -= 1
    
    members_data = response.json()

    filtered_members = {}
    for member in members_data:
        if isinstance(member, dict) and "id" in member and "firstname" in member and "lastname" in member and "profile_medium" in member:
            member_id = str(member["id"])
            filtered_member = {
                "firstname": member["firstname"],
                "lastname": member["lastname"],
                "profile_medium": member["profile_medium"]
            }
            filtered_members[member_id] = filtered_member
        else:
            print("Error: Unexpected member format:", member)
            print("Response content:", response.text)
            return
    
    members = filtered_members
    
    with open("data/members.json", "w") as f:
        json.dump(members, f, indent=4)

def get_activities_for_member(member_id):
    global all_activities
    global total_distances

    retries = 3
    while retries > 0:
        access_token = os.getenv("access_token")
        url = f"http://www.strava.com/api/v3/feed/athlete/{member_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            break
            
        refresh_access_token()
        retries -= 1

    activities = response.json()
    filtered_activities = []
    run_walk_distance = 0
    ride_distance = 0
    swim_distance = 0

    # Define the cutoff datetime in Brisbane timezone
    brisbane_tz = pytz.timezone('Australia/Brisbane')
    cutoff_datetime = brisbane_tz.localize(datetime(2024, 5, 1))

    for activity in activities:
        try:
            activity_start_date = datetime.strptime(activity["item"]["start_date"], "%Y-%m-%dT%H:%M:%SZ")
            # Convert activity start date to Brisbane timezone
            activity_start_date = activity_start_date.replace(tzinfo=pytz.utc).astimezone(brisbane_tz)

            # Check if the activity start date is after the cutoff datetime
            if activity_start_date > cutoff_datetime:
                filtered_activity = {
                    "id": activity["item"]["id"],
                    "name": activity["item"]["name"],
                    "type": activity["item"]["type"],
                    "distance": activity["item"]["distance"],
                    "start_date": activity["item"]["start_date"]
                }
                
                filtered_activities.append(filtered_activity)
        except Exception as e:
            print("Error during activities:", e, datetime.now(pytz.timezone('Australia/Brisbane')))
        
    if member_id in all_activities:
        existing_activity_ids = {activity["id"] for activity in all_activities[member_id]}
        for activity in filtered_activities:
            if activity["id"] not in existing_activity_ids:
                all_activities[member_id].append(activity)
    else:
        all_activities[member_id] = filtered_activities

    for activity in all_activities[member_id]:
        try:
            # Categorize activities and calculate total distances for each category
                if activity["type"] in ["Run", "Walk"]:
                    run_walk_distance += activity["distance"]
                elif activity["type"] == "Ride":
                    ride_distance += activity["distance"]
                elif activity["type"] == "Swim":
                    swim_distance += activity["distance"]
        except Exception as e:
            print("Error during filtering activities:", e, datetime.now(pytz.timezone('Australia/Brisbane')))

    # Update total distance for the member
    total_distance = sum(activity["distance"] for activity in all_activities[member_id])
    total_distances[member_id] = {
        "run_walk_distance": run_walk_distance,
        "ride_distance": ride_distance,
        "swim_distance": swim_distance,
        "total_points": (run_walk_distance / 1000) + (ride_distance / 2500) + (swim_distance / 250)
    }

def get_activities():
    global all_activities
    global members
    global total_distances
    global pulling
    
    for member_id, _ in members.items():
        get_activities_for_member(member_id)
    
    # Save updated activities and total distances with pretty formatting
    with open("data/all_activities.json", "w") as f:
        json.dump(all_activities, f, indent=4)
    with open("data/total_distances.json", "w") as f:
        json.dump(total_distances, f, indent=4)

def run_flask():
    # Specify paths to SSL certificate and key files
    ssl_cert = 'certs/certificate.crt'
    ssl_key = 'certs/private.key'

    while True:
        try:
            app.run(host='0.0.0.0', port=443, ssl_context=(ssl_cert, ssl_key))
        except Exception as e:
            print("Error:", e, datetime.now(pytz.timezone('Australia/Brisbane')))
            time.sleep(10)

def main():
    load_dotenv()
    global members
    global all_activities
    global total_distances

    # Load members and all_activities from files at the start of the program
    if os.path.exists("data/members.json"):
        with open("data/members.json", "r") as f:
            members = json.load(f)
    
    if os.path.exists("data/all_activities.json"):
        with open("data/all_activities.json", "r") as f:
            all_activities = json.load(f)

    if os.path.exists("data/total_distances.json"):
        with open("data/total_distances.json", "r") as f:
            total_distances = json.load(f)

    thread = threading.Thread(target=run_flask)
    thread.daemon = True
    thread.start()

    backup_thread = threading.Thread(target=backup)
    backup_thread.daemon = True
    backup_thread.start()

    while True:
        if pulling:
            try:
                get_members()
                get_activities()
            except Exception as e:
                print("Error during pulling:", e, datetime.now(pytz.timezone('Australia/Brisbane')))
        print("Server running, Pulling:", pulling, datetime.now(pytz.timezone('Australia/Brisbane')))
        time.sleep(120)

def backup():
    while True:
        try:
            time.sleep(600)  # sleep 10 minutes
            combined_data = {
                "members": members,
                "all_activities": all_activities,
                "total_distances": total_distances
            }
            backup_time = datetime.now(pytz.timezone('Australia/Brisbane')).strftime("%Y-%m-%d_%H-%M-%S")
            with open(f"backups/backup_{backup_time}.json", "w") as f:
                json.dump(combined_data, f, indent=4)
            print("Backup complete:", backup_time, datetime.now(pytz.timezone('Australia/Brisbane')))
        except Exception as e:
            print("Error during backup:", e, datetime.now(pytz.timezone('Australia/Brisbane')))

@app.route('/')
def index():
    sorted_total_points = dict(sorted(total_distances.items(), key=lambda item: item[1]["total_points"], reverse=True))

    # Pass the sorted total distances and other global variables to the template
    return render_template('index.html', all_activities=all_activities, members=members, total_points=sorted_total_points)

@app.route('/start')
def start():
    global pulling
    pulling = True
    return "Pulling started", 200

@app.route('/stop')
def stop():
    global pulling
    pulling = False
    return "Pulling stopped", 200

@app.route('/status')
def status():
    global pulling
    return f"Pulling is {'running' if pulling else 'stopped'}", 200

if __name__ == "__main__":
    main()
