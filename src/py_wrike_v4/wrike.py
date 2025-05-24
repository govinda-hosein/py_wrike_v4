import requests
import logging
from urllib.parse import unquote
from enum import Enum

from .helpers import convert_list_to_dict, convert_list_to_string


# Logging
logging.getLogger(__name__).addHandler(logging.NullHandler())
logger = logging.getLogger(__name__)


class Wrike:
    """
    A wrapper for Wrike API calls. Some API calls save data to a cache which this object manages. If at some point you'd like to clear those caches, simply call wrike.reinitialize()

    Args:
        :param base_url (string): Base Wrike URL, it should look like "https://<host>/api/v4/" (the trailing / is important)
        :param perm_access_token (string): A permanent access token obtained from Wrike's dashboard
        :param ssl_verify (bool): Set to false during testing

    """

    def __init__(self, base_url: str, perm_access_token: str, ssl_verify: bool = True):
        self.base_url = base_url
        self.ssl_verify = ssl_verify
        self.__headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + perm_access_token,
        }
        self.reinitialize()

    def reinitialize(self):
        """
        Clears the wrike's object data cache
        """
        self._contacts = None
        self._custom_fields = None
        self._custom_statuses = None
        self._folders = None
        self._workflows = None

    # region Properties (Does Caching)

    @property
    def contacts(self) -> dict:
        if not self._contacts:
            all_contacts = self.query_contacts_all()["data"]
            self._contacts = convert_list_to_dict(all_contacts)
        return self._contacts

    @property
    def custom_fields(self) -> dict:
        if not self._custom_fields:
            all_custom_fields = self.query_custom_fields_all()["data"]
            self._custom_fields = convert_list_to_dict(all_custom_fields)
        return self._custom_fields

    @property
    def custom_statuses(self) -> dict:
        if not self._custom_statuses:
            self._custom_statuses = {}
            for workflow in self.workflows.values():
                for custom_status in workflow["customStatuses"]:
                    self._custom_statuses[custom_status["id"]] = custom_status
        return self._custom_statuses

    @property
    def folders(self) -> dict:
        if not self._folders:
            all_folders = self.query_folders_all()["data"]
            self._folders = convert_list_to_dict(all_folders)
        return self._folders

    @property
    def workflows(self) -> dict:
        if not self._workflows:
            workflows = self.query_workflows()["data"]
            self._workflows = convert_list_to_dict(workflows)
        return self._workflows

    # endregion

    # region Base HTTP Methods

    def get(self, path: str, params: dict = None) -> dict:
        response = requests.get(
            self.base_url + path,
            headers=self.__headers,
            params=params,
            verify=self.ssl_verify
        )
        logger.debug(f"Actual requested URL: {unquote(response.url)}")
        return response.json()

    def post(self, path: str, body: dict) -> dict:
        response = requests.post(
            self.base_url + path,
            json=body,
            headers=self.__headers,
            verify=self.ssl_verify,
        )
        return response.json()

    # endregion

    # region ID conversion

    class IdTypes(Enum):
        """ Enumeration of API v2 endpoints """
        ACCOUNT = "ApiV2Account"
        USER = "ApiV2User"
        FOLDER = "ApiV2Folder"
        TASK = "ApiV2Task"
        COMMENT = "ApiV2Comment"
        ATTACHMENT = "ApiV2Attachment"
        TIMELOG = "ApiV2Timelog"

    def convert_to_id4s(self, id2s: list[str], idType: IdTypes) -> dict:
        """ Convert from v2 to v4 ID format.

        The Wrike API v4 requires queries with the v4 ID format. The Wrike
        website reports in the v2 format, so a conversion is necessary.

        The IdType must match the type of the v2 ID, or it won't find the
        associated v4 ID. It's not a conversion, it's a lookup.
        """
        params = {
            'type': idType.value,
            'ids':  str(id2s)
        }
        return self.get("ids/", params)

    # endregion

    # region Contacts

    def query_contacts(self, id4s: list) -> dict:
        id4s = convert_list_to_string(id4s)
        return self.get(f"contacts/{id4s}")

    def query_contacts_all(self) -> dict:
        return self.get("contacts")

    def query_contact_me(self) -> dict:
        return self.get("contacts?me=true")

    # endregion

    # region Custom Fields

    def query_custom_fields(self, id4s: list) -> dict:
        id4s = convert_list_to_string(id4s)
        return self.get(f"customfields/{id4s}")

    def query_custom_fields_all(self) -> dict:
        return self.get("customfields")

    # endregion

    # region Extract Methods

    def extract_project_status(self, folder: dict) -> str:
        """
        Extracts project status from a folder. Returns None if it isn't set
        """
        # return "test"
        status = Wrike.extract_project_value_from_folder("status", folder)
        custom_status_id = Wrike.extract_project_value_from_folder(
            "customStatusId", folder
        )
        if str(status) == "Custom" and custom_status_id:
            status = self.custom_statuses[custom_status_id]["name"]

        return status

    @staticmethod
    def extract_project_value_from_folder(key: str, folder: dict):
        """
        Returns the value at specified key in a folder's 'project' object.
        If the key doesn't exist, returns None
        """
        try:
            extract = folder["project"][key]
            return extract
        except Exception as e:
            return None

    # endregion

    # region Folders

    def query_folders(self, id4s: list) -> dict:
        id4s = convert_list_to_string(id4s)
        return self.get(f"folders/{id4s}")

    def query_folders_all(self) -> dict:
        return self.get("folders")

    def query_folder_by_title(self, title: str) -> dict:
        for key, folder in self.folders.items():
            if folder["title"] == title:
                return folder

    def query_folder_subtrees(self, folder_id: str) -> dict:
        return self.get(f"folders/{folder_id}/folders")

    def query_folder_subtrees_by_title(self, title: str) -> dict:
        folder = self.query_folder_by_title(title)
        return self.query_folder_subtrees(folder["id"])

    # endregion

    # region Groups

    def query_group(self, group_id: str) -> dict:
        return self.get(f"groups/{group_id}")

    def query_groups_all(self) -> dict:
        return self.get(f"groups")

    # endregion

    # region Tasks

    def query_tasks(self, id4s: list) -> dict:
        id4s = convert_list_to_string(id4s)
        return self.get(f"tasks/{id4s}")

    def query_tasks_all(self) -> dict:
        return self.get("tasks")

    def query_tasks_in_folder(self, folder_id: str) -> dict:
        return self.get(f"folders/{folder_id}/tasks")

    # endregion

    # region Users

    def query_user(self, user_id: str) -> dict:
        return self.get(f"users/{user_id}")

    # endregion

    # region Workflows

    def query_workflows(self) -> dict:
        return self.get("workflows")

    # endregion

    # region Timelogs

    def query_timelogs(self,
                       location: str = "",
                       tracked_date: list[str] = []
                      ) -> dict:
        """ Get the timelogs from an optional location and tracked date range.

        This method always uses descendants = True, so that it recursively
        retrieves timelogs from subtasks and subfolders.

        Args:
            location: API endpoint location, such as for a folder or a task (e.g. "tasks/{task_id}")
            tracked_date: Optional list of date strings for tracked date filter
                         Format: [start_date] or [start_date, end_date] or [equal_date]
                         Date format: yyyy-MM-dd'T'HH:mm:ss ('T'HH:mm:ss is optional)

        Returns:
            dict: API response containing timelog data
        """
        params = {
                'descendants': 'true'
                }

        if tracked_date:
            if len(tracked_date) == 1:
                # Single date - treat as exact match
                params['trackedDate'] = str({'equal': tracked_date[0]})
            elif len(tracked_date) == 2:
                # Date range
                params['trackedDate'] = str({
                    'start': tracked_date[0],
                    'end': tracked_date[1]
                })

        return self.get(f"{location}/timelogs", params)

    # endregion
