from app.main import _desk_company_id_for_project, _project_ids_from_desk_ticket


def test_desk_ticket_thread_task_id_is_not_treated_as_project_id():
    ticket = {"threads": [{"taskId": 33202226}]}

    assert _project_ids_from_desk_ticket(ticket) == []


def test_stratas_project_maps_to_stratas_desk_company():
    project = {"id": 928509, "name": "STRATAS | Application Managed Services", "company": {"id": 1368579}}

    assert _desk_company_id_for_project(project) == 29837
