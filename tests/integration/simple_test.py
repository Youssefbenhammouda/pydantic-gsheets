from datetime import datetime
import os
from typing import Annotated, Type
import pytest
from google.auth import default
from googleapiclient.discovery import build
from faker import Faker
from pydantic_gsheets import GoogleWorkSheet, SheetRow,GSIndex,GSRequired,GSFormat
from random import randint
pytestmark = pytest.mark.sheets

sheet_id = os.environ["SHEET_ID"]


creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])



class SampleData1(SheetRow):
    username: Annotated[str, GSRequired,GSIndex(0)]
    id: Annotated[int, GSRequired,GSIndex(1)]
    email: Annotated[str, GSRequired,GSIndex(2)]
    age: Annotated[int, GSIndex(3)]
    location: Annotated[str, GSIndex(4)]
    created_at: Annotated[datetime, GSRequired,GSIndex(5),GSFormat('DATE_TIME', 'dd-MM-yyyy HH:mm')]



@pytest.fixture
def sheets_service():
    return build("sheets", "v4", credentials=creds)

@pytest.fixture(scope="function")
def test_worksheet1(sheets_service):
    sheet_name = "Test Sheet1"
    existing_sheets = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    for sheet in existing_sheets.get("sheets", []):
        if sheet.get("properties", {}).get("title") == sheet_name:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "requests": [
                        {"deleteSheet": {"sheetId": sheet.get("properties", {}).get("sheetId")}}
                    ]
                }
            ).execute()
            break
    yield GoogleWorkSheet.create_sheet(SampleData1, sheets_service, sheet_id,sheet_name,skip_if_exists=False)
    existing_sheets = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    for sheet in existing_sheets.get("sheets", []):
        if sheet.get("properties", {}).get("title") == sheet_name:
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "requests": [
                        {"deleteSheet": {"sheetId": sheet.get("properties", {}).get("sheetId")}}
                    ]
                }
            ).execute()
            break
    else:
        raise ValueError(f"Sheet {sheet_name} not found for cleanup.")
def test_can_read_sheet_title(sheets_service):


    meta = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()

    assert "properties" in meta
    assert "title" in meta["properties"]

def test_can_create_worksheet(test_worksheet1):



    
    data = []
    for _ in range(randint(1, 20)):
        Faker.seed()
        fake = Faker()
        data.append(
            SampleData1(
                username=fake.name(),
                id=fake.random_int(min=1, max=1000),
                email=fake.email(),
                age=fake.random_int(min=18, max=60),
                location=fake.city(),
                created_at=fake.date_time_this_decade()
            )
        )
    test_worksheet1.saveRows(data)
    data = data.copy()  # Copy the data to avoid mutation issues
    queried_data = list(test_worksheet1.rows(refresh=True,skip_rows_missing_required=False))
    assert queried_data == data, f"Expected {data} but got {queried_data}"



