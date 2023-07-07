from __future__ import print_function

import datetime
import time
import logging
import config

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleMeet:
    """
    Creates a calendar event and returns the Google Meet link, phone number and pin
    """

    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/calendar.events']
        self.service_account_file = config.google_service_account_secret
        self.meeting = {}


    def create_meeting(self):

        try:
            credentials = service_account.Credentials.from_service_account_file(self.service_account_file, scopes=self.scopes)
            
            delegated_credentials = credentials.with_subject(config.google_account_email)
            service = build('calendar', 'v3', credentials=delegated_credentials)

            # Call the Calendar API
            now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            today = datetime.date.today()

            event = {
            # placeholder for now
            'summary': str(today)+'-new-incident-title',
            'location': 'Virtual',
            'description': 'Incident troubleshooting',
            'start': {
                'dateTime': now,
                'timeZone': 'America/Chicago',
            },
            'end': {
                'dateTime': now,
                'timeZone': 'America/Chicago',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
                ],

            },
            'conferenceData': {
                'createRequest': {
                    'requestId': '12355',
                   'conferenceSolutionKey': {
                   'type': 'hangoutsMeet'
                },
               }
            },
            'visibility': 'public',
            'guestsCanModify': False
            }

            print("Creating event")
            event = service.events().insert(calendarId='primary', body=event, conferenceDataVersion = 1).execute()

            print(f'Event created: {event.get("hangoutLink")}')
            self.meeting.update({"hangout_link": event.get("hangoutLink")})
            self.meeting.update({"meeting_id": event.get("id")})

            for details in event.get("conferenceData")["entryPoints"]:
                if details["entryPointType"] == "phone":
                    print(f'{details["uri"]}' +'\npin: '+ details["pin"])
                    self.meeting.update({"phone_number":details["uri"]})
                    self.meeting.update({"pin":details["pin"]})

            print(self.meeting_info)

        except HttpError as error:
            print('An error occurred: %s' % error)


    @property
    def meeting_info(self):
        return self.meeting


    def delete_meeting(self):
        credentials = service_account.Credentials.from_service_account_file(self.service_account_file, scopes=self.scopes)
            
        delegated_credentials = credentials.with_subject(config.google_account_email)
        service = build('calendar', 'v3', credentials=delegated_credentials)
        service.events().delete(calendarId='primary', eventId=self.meeting_info["meeting_id"]).execute()


